"""Android protocol — live screen mirror over the remote-agent EXEC channel.

Ported from the monolith's ``src/api/routes/android_viewer.py``. Unlike the
vnc/rdp bridge in ``routes.py`` there is **no VNC server and no TCP endpoint**
here: the device is attached to a machine that this workspace can only reach
through the remote-agent's HTTP exec endpoint, so frames are produced by
shelling out ``adb exec-out screencap -p | base64`` on that machine, decoding
locally, and pushing each PNG as a binary WebSocket message. Input travels the
other way on the same socket and becomes ``adb shell input ...``.

~2 fps. screencap + base64 + the HTTP round-trip dominate the loop, so there is
nothing to tune below that.

What changed vs. the monolith: it hard-coded PROFILE_ID/DEVICE_SERIAL/ADB_BIN/
BACKEND_URL as module constants, so it could mirror exactly one device on one
machine forever. Here all four come off the host row (``host`` carries the
remote-agent profile id for an android host), which is what makes "Android" a
protocol you can add N hosts of rather than a hard-wired singleton.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import shlex

import os
from pathlib import Path

import httpx
from fastapi import WebSocket, WebSocketDisconnect

log = logging.getLogger("aw_apps.remote-screen.android")

FRAME_INTERVAL_S = 0.5  # ~2 fps

# The exec channel truncates stdout at 1 MiB. A full-resolution PNG of a busy
# Android screen base64s to ~1.7 MB, so the frame arrived CUT — a partial PNG,
# which `createImageBitmap` rejects outright and the viewer paints as nothing.
# It looked intermittent because a plain app screen compresses under the cap
# while a wallpapered launcher does not. Measured 2026-08-13: 1 252 402 B PNG
# -> 1 669 873 B base64, delivered as exactly 1 048 576.
EXEC_STDOUT_CAP = 1024 * 1024

# Downscale + JPEG on the capture host instead. 900px on the long edge at
# quality 60 is ~30 KB (3% of the cap) — 41x smaller than the raw PNG, which
# also takes 41x off the /link tunnel, the slowest hop in the chain.
FRAME_MAX_PX = 900
FRAME_JPEG_QUALITY = 60
DEFAULT_AGENT_URL = "http://127.0.0.1:10005"
DEFAULT_ADB_BIN = "~/Android/platform-tools/adb"


def agent_url(row: dict) -> str:
    return (row.get("agent_base_url") or "").strip() or DEFAULT_AGENT_URL


def adb_bin(row: dict) -> str:
    return (row.get("adb_bin") or "").strip() or DEFAULT_ADB_BIN


def adb(row: dict) -> str:
    """``adb`` invocation for this host, device-scoped when a serial is set.

    A blank ``device_serial`` deliberately means "the only attached device"
    rather than an error — ``adb`` already picks it, and demanding a serial for
    a single-device machine is friction with no safety win.
    """
    serial = (row.get("device_serial") or "").strip()
    return f"{adb_bin(row)} -s {serial}" if serial else adb_bin(row)


WORKSPACE_DIR = os.environ.get("AW_WORKSPACE_CONTAINER_DIR", "/opt/aw-workspace")
DEFAULT_BACKEND_URL = "http://127.0.0.1:9025"


def _env(name: str) -> str:
    """os.environ first, then <AW_WORKSPACE_HOME>/.env — the app process and a
    cross-container caller see different environments but the same file. The
    remote-host-cli plugin republishes these on every activate."""
    value = os.environ.get(name)
    if value:
        return value
    env_file = Path(os.environ.get(
        "AW_WORKSPACE_ENV_FILE", f"{WORKSPACE_DIR}/.aw-workspace/.env"))
    if not env_file.is_file():
        return ""
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        if key.strip() == name:
            return val.strip().strip('"').strip("'")
    return ""


async def _exec_remote_agent(client: httpx.AsyncClient, row: dict, command: str,
                             timeout: float) -> list[dict]:
    """Legacy monolith path: a remote-agent backend in the caller's own netns,
    streaming ndjson straight back."""
    resp = await client.post(
        f"{agent_url(row)}/api/clients/{row['host']}/exec",
        json={"command": command, "timeout": timeout},
        timeout=timeout + 15,
    )
    resp.raise_for_status()
    return [json.loads(line) for line in resp.text.splitlines() if line.strip()]


async def _exec_aw_remote_host(client: httpx.AsyncClient, row: dict, command: str,
                               timeout: float) -> list[dict]:
    """This workspace's own path: aw-backend relays the command over the /link
    WebSocket the host already holds open. It is start+wait rather than a
    stream, so the result is adapted into the same ndjson shape ``collect()``
    already understands — that keeps one parser for both channels."""
    backend = (_env("AW_BACKEND_URL") or DEFAULT_BACKEND_URL).rstrip("/")
    workspace, token = _env("AW_WORKSPACE"), _env("AW_WORKSPACE_HOST_TOKEN")
    if not (workspace and token):
        raise RuntimeError(
            "AW_WORKSPACE / AW_WORKSPACE_HOST_TOKEN are not published — this "
            "only works inside a workspace that completed the /link handshake")
    base = f"{backend}/api/workspaces/{workspace}/remote-hosts/{row['host']}"
    headers = {"Authorization": f"Bearer {token}"}

    started = await client.post(f"{base}/exec", json={"command": command,
                                                      "timeout_s": timeout},
                                headers=headers, timeout=timeout + 15)
    started.raise_for_status()
    job_id = started.json().get("job_id")
    if not job_id:
        raise RuntimeError(f"exec did not return a job_id: {started.text[:200]}")

    done = await client.post(f"{base}/exec/{job_id}/wait", json={"timeout_s": timeout},
                             headers=headers, timeout=timeout + 30)
    done.raise_for_status()
    result = done.json()
    return [
        {"stream": "stdout", "data": result.get("stdout") or ""},
        {"stream": "stderr", "data": result.get("stderr") or ""},
        {"done": True, "returncode": result.get("exit_code",
                                                result.get("returncode", 0)) or 0},
    ]


async def exec_ndjson(client: httpx.AsyncClient, row: dict, command: str,
                      timeout: float = 30) -> list[dict]:
    """Run one command on the machine this host row points at, over whichever
    exec channel it is configured for."""
    if (row.get("agent_kind") or "aw_remote_host") == "remote_agent":
        return await _exec_remote_agent(client, row, command, timeout)
    return await _exec_aw_remote_host(client, row, command, timeout)


def collect(lines: list[dict]) -> tuple[str, str, int]:
    out_chunks, err_chunks, code = [], [], 0
    for line in lines:
        if line.get("done"):
            code = line.get("returncode", 0)
        elif line.get("stream") == "stderr":
            err_chunks.append(line.get("data", ""))
        else:
            out_chunks.append(line.get("data", ""))
    return "".join(out_chunks), "".join(err_chunks), code


def build_input_command(row: dict, data: dict) -> str | None:
    """Translate one control message into an ``adb shell input`` command, or
    None if it is malformed. Returning None (rather than raising) keeps a
    garbage frame from tearing down a live mirror session."""
    msg_type = data.get("type")
    prefix = f"{adb(row)} shell input"
    if msg_type == "tap":
        try:
            x, y = int(data["x"]), int(data["y"])
        except (KeyError, TypeError, ValueError):
            return None
        return f"{prefix} tap {x} {y}"
    if msg_type == "swipe":
        try:
            x1, y1 = int(data["x1"]), int(data["y1"])
            x2, y2 = int(data["x2"]), int(data["y2"])
        except (KeyError, TypeError, ValueError):
            return None
        duration = data.get("duration_ms")
        dur_part = f" {int(duration)}" if isinstance(duration, (int, float)) else ""
        return f"{prefix} swipe {x1} {y1} {x2} {y2}{dur_part}"
    if msg_type == "text":
        text = data.get("text")
        if not text or not isinstance(text, str):
            return None
        return f"{prefix} text {shlex.quote(text)}"
    if msg_type == "key":
        code = data.get("code")
        if not code or not isinstance(code, str):
            return None
        # Symbolic keycodes are alphanumeric/underscore (KEYCODE_HOME) or plain
        # numbers. Anything else is rejected rather than shell-quoted — this
        # value is interpolated into a command that runs on the remote machine.
        if not all(c.isalnum() or c == "_" for c in code):
            return None
        return f"{prefix} keyevent {code}"
    return None


def capture_command(row: dict) -> str:
    """Grab a frame and downscale it ON THE CAPTURE HOST before base64.

    Sending the raw PNG blew the exec channel's 1 MiB stdout cap (see
    EXEC_STDOUT_CAP) and cost ~1.7 MB per frame on the /link tunnel. Resizing
    first is both the correctness fix and the optimisation.

    The resizer is whatever that machine has, tried in order and falling back
    to the raw PNG so a host with neither still mirrors (just at full size,
    and subject to the cap). `sips` ships with macOS; ImageMagick covers most
    Linux hosts. Both PNG and JPEG decode client-side with no change there.
    """
    src, jpg = "/tmp/aw-remote-screen.png", "/tmp/aw-remote-screen.jpg"
    q, px = FRAME_JPEG_QUALITY, FRAME_MAX_PX
    return (
        f"{adb(row)} exec-out screencap -p > {src} 2>/dev/null; "
        f"(sips -Z {px} -s format jpeg -s formatOptions {q} --out {jpg} {src} "
        f">/dev/null 2>&1 && base64 < {jpg}) "
        f"|| (magick {src} -resize {px}x{px}\\> -quality {q} {jpg} "
        f">/dev/null 2>&1 && base64 < {jpg}) "
        f"|| (convert {src} -resize {px}x{px}\\> -quality {q} {jpg} "
        f">/dev/null 2>&1 && base64 < {jpg}) "
        f"|| base64 < {src}"
    )


async def status(row: dict) -> dict:
    """Is the remote agent reachable, and is the device attached?"""
    async with httpx.AsyncClient() as client:
        try:
            lines = await exec_ndjson(client, row, f"{adb_bin(row)} devices -l", timeout=15)
        except Exception as e:  # noqa: BLE001 — any failure means "can't tell"
            return {"online": False, "device_present": False, "error": str(e)}
        out, err, code = collect(lines)
        serial = (row.get("device_serial") or "").strip()
        # With no serial configured, "any attached device" is the bar — the
        # header line is always present, so count the lines below it.
        present = (serial in out) if serial else any(
            "\tdevice" in ln or " device " in ln
            for ln in out.splitlines()[1:]
        )
        return {
            "online": True,
            "device_present": present,
            "devices_output": out.strip(),
            "returncode": code,
            "stderr": err.strip() or None,
        }


class _Capture:
    """ONE screencap loop per host, fanned out to every viewer watching it.

    Before this, each viewer ran its own loop. That is not just wasteful, it
    does not scale at all: every frame costs a start+wait pair through
    aw-backend and the /link tunnel, so N viewers meant N times the traffic on
    a channel that is already the slowest link in the chain. Eight stacked
    loops were enough to congest it to the point where a plain `echo` on the
    host timed out (observed 2026-08-13).

    Now the cost is fixed at one capture stream per DEVICE no matter how many
    tabs are open, and the loop stops the moment the last viewer leaves.
    """

    def __init__(self, row: dict) -> None:
        self.row = row
        self.subscribers: set[WebSocket] = set()
        self.task: asyncio.Task | None = None
        self.warned_truncated = False

    async def _run(self) -> None:
        async with httpx.AsyncClient() as client:
            while self.subscribers:
                try:
                    lines = await exec_ndjson(
                        client, self.row, capture_command(self.row), timeout=30)
                    out, err, code = collect(lines)
                    if code:
                        log.warning("android %s: capture failed (exit %s): %s",
                                    self.row["name"], code, err or out)
                    else:
                        b64_text = "".join(out.split())
                        if len(b64_text) >= EXEC_STDOUT_CAP:
                            # Truncated: decoding this yields a partial image
                            # the browser silently refuses. Skip the frame and
                            # say so once, rather than push something broken.
                            if not self.warned_truncated:
                                self.warned_truncated = True
                                log.warning(
                                    "android %s: frame hit the %d B exec cap and was "
                                    "dropped — the capture host has no downscaler, so "
                                    "frames are full-resolution PNG",
                                    self.row["name"], EXEC_STDOUT_CAP)
                        elif b64_text:
                            await self._fan_out(base64.b64decode(b64_text))
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001 — one bad poll is not fatal
                    log.warning("android %s: capture error: %s", self.row["name"], exc)
                await asyncio.sleep(FRAME_INTERVAL_S)
        log.info("android %s: no viewers left, capture stopped", self.row["name"])

    async def _fan_out(self, png: bytes) -> None:
        """Send one frame to every viewer, dropping the ones that have gone.

        A failed send means that viewer's socket is closed. The previous code
        logged it as "bad frame" and carried on — which is exactly how a closed
        viewer left an immortal capture loop behind, and how eight of them
        piled up. A send failure is now what UNSUBSCRIBES a viewer.
        """
        for ws in list(self.subscribers):
            try:
                await ws.send_bytes(png)
            except Exception:  # noqa: BLE001 — this viewer is gone, others are not
                self.subscribers.discard(ws)


_captures: dict[str, _Capture] = {}


def _subscribe(row: dict, ws: WebSocket) -> _Capture:
    cap = _captures.get(row["id"])
    if cap is None:
        cap = _Capture(row)
        _captures[row["id"]] = cap
    cap.subscribers.add(ws)
    if cap.task is None or cap.task.done():
        cap.task = asyncio.create_task(cap._run())
    return cap


def _unsubscribe(cap: _Capture, ws: WebSocket) -> None:
    cap.subscribers.discard(ws)
    if cap.subscribers:
        return
    # Last viewer out cancels the loop rather than letting it notice on its
    # next poll — that would be up to FRAME_INTERVAL_S + a full exec round
    # trip of pointless traffic on the tunnel.
    if cap.task is not None:
        cap.task.cancel()
        cap.task = None
    _captures.pop(cap.row["id"], None)


def capture_count() -> int:
    """Live capture loops — one per device with at least one viewer."""
    return len(_captures)


async def stream(ws: WebSocket, row: dict) -> None:
    """One viewer: subscribe to the host's shared capture, handle its input."""
    await ws.accept()
    cap = _subscribe(row, ws)
    try:
        async with httpx.AsyncClient() as client:
            while True:
                try:
                    msg = await ws.receive_text()
                except WebSocketDisconnect:
                    return
                except Exception as exc:  # noqa: BLE001 — a stray binary frame
                    log.warning("android %s: bad control frame: %s", row["name"], exc)
                    return
                try:
                    data = json.loads(msg)
                except json.JSONDecodeError:
                    continue
                command = build_input_command(row, data)
                if command:
                    try:
                        await exec_ndjson(client, row, command, timeout=15)
                    except Exception as exc:  # noqa: BLE001
                        log.warning("android %s: control failed: %s", row["name"], exc)
    finally:
        # Runs on every exit path, including a cancelled task — without it the
        # subscriber set keeps a dead socket and the capture never stops.
        _unsubscribe(cap, ws)
