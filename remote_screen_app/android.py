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


async def stream(ws: WebSocket, row: dict) -> None:
    """Frame loop + input control for one viewer session."""
    await ws.accept()
    async with httpx.AsyncClient() as client:

        async def send_frames() -> None:
            while True:
                try:
                    lines = await exec_ndjson(
                        client, row,
                        f"{adb(row)} exec-out screencap -p | base64",
                        timeout=30,
                    )
                    out, err, code = collect(lines)
                    if code:
                        log.warning("android %s: screencap failed (exit %s): %s",
                                    row["name"], code, err or out)
                    else:
                        b64_text = "".join(out.split())
                        if b64_text:
                            try:
                                await ws.send_bytes(base64.b64decode(b64_text))
                            except Exception as exc:  # noqa: BLE001
                                log.warning("android %s: bad frame: %s", row["name"], exc)
                except (WebSocketDisconnect, RuntimeError):
                    raise
                except Exception as exc:  # noqa: BLE001 — one bad poll is not fatal
                    log.warning("android %s: capture error: %s", row["name"], exc)
                await asyncio.sleep(FRAME_INTERVAL_S)

        async def recv_controls() -> None:
            while True:
                # receive_text() raises on a binary frame or a closing socket;
                # letting that escape would end the session (see the gather
                # below), so a bad control frame must never be fatal.
                try:
                    msg = await ws.receive_text()
                except WebSocketDisconnect:
                    raise
                except Exception as exc:  # noqa: BLE001
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

        # return_exceptions=True is load-bearing: without it, ONE raise on the
        # control side (a stray binary frame, a socket hiccup while an exec is
        # in flight) propagates out of gather and takes the FRAME LOOP down
        # with it. The viewer keeps showing the last painted frame and looks
        # live while the device has moved on — the worst possible failure for a
        # mirror. Found live 2026-08-13: pressing Home froze the picture while
        # `dumpsys` confirmed the device had actually gone to the launcher.
        results = await asyncio.gather(send_frames(), recv_controls(),
                                       return_exceptions=True)
        for result in results:
            if isinstance(result, Exception) and not isinstance(result, WebSocketDisconnect):
                log.warning("android %s: %s", row["name"], result)
