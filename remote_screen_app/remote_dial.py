"""Dial a TCP address FROM a linked aw-remote-host, over its /link tunnel.

Port of ``aw-app-tunnel/tunnel_app/remote_dial.py`` for remote-screen's own
bridge. A ``custom`` host is dialled directly by ``routes.py`` with
``asyncio.open_connection`` — plain TCP, this workspace's own route. A
``remote_host`` host cannot be: the address is on that machine's own network
(its loopback, its LAN), which this workspace has no route to. The host,
though, already holds an outbound WebSocket to aw-backend — so it dials on
our behalf and relays the bytes.

The chain, once, so the failure modes are legible:

    browser  ->  routes.py's bridge  ->  this module  ->  wss aw-backend .../tcp
                                       ->  /link (tcp_open/tcp_data/tcp_close)
                                       ->  aw-remote-host  ->  net.Dial(host:port)

Everything here speaks raw bytes. The base64 lives on the /link hop only,
because that hop is a JSON protocol; neither socket this module touches ever
sees it.

Auth is this workspace's own ``awlk_`` host credential — the same one the
remote-host exec calls (see ``android.py``) use, read from the environment or
``<AW_WORKSPACE_HOME>/.env``.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from urllib.parse import quote

import websockets
from fastapi import WebSocket

log = logging.getLogger("aw_apps.remote-screen")

WORKSPACE_DIR = os.environ.get("AW_WORKSPACE_CONTAINER_DIR", "/opt/aw-workspace")
DEFAULT_BACKEND_URL = "http://127.0.0.1:9025"


class RemoteDialError(RuntimeError):
    """Could not establish the relayed connection — reported to the browser
    as a closed WebSocket (WS_CONNECT_FAILED), never as a hang."""


def _env(name: str) -> str:
    """os.environ first, then <AW_WORKSPACE_HOME>/.env — an app process and a
    cross-container caller see different environments but the same file."""
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


def bridge_url(remote_host_id: str, host: str, port: int) -> str:
    backend = (_env("AW_BACKEND_URL") or DEFAULT_BACKEND_URL).rstrip("/")
    workspace = _env("AW_WORKSPACE")
    if not workspace:
        raise RemoteDialError("AW_WORKSPACE is not published in this workspace")
    ws_base = backend.replace("https://", "wss://").replace("http://", "ws://")
    return (f"{ws_base}/api/workspaces/{quote(workspace)}"
            f"/remote-hosts/{quote(remote_host_id)}/tcp"
            f"?host={quote(host)}&port={port}")


async def open_bridge(remote_host_id: str, host: str, port: int):
    """Open the relay WebSocket. Raises RemoteDialError if it cannot."""
    token = _env("AW_WORKSPACE_HOST_TOKEN")
    if not token:
        raise RemoteDialError(
            "AW_WORKSPACE_HOST_TOKEN is not published — a remote-host "
            "destination needs the credential the /link handshake minted "
            "for this workspace")
    url = bridge_url(remote_host_id, host, port)
    try:
        return await websockets.connect(
            url, additional_headers={"Authorization": f"Bearer {token}"},
            max_size=None, open_timeout=15,
        )
    except Exception as e:  # noqa: BLE001 — every failure is "cannot dial"
        raise RemoteDialError(f"relay connect failed: {e}") from e


async def pump(ws: WebSocket, bridge) -> None:
    """Pipe the browser's WebSocket and the relay WebSocket together until
    either end goes. The WS<->WS counterpart of routes.py's TCP<->WS bridge
    (``tcp_to_ws``/``ws_to_tcp``) — needed because a ``remote_host``
    destination has no local TCP socket at all, only the relay — and it
    swallows its own teardown exceptions the same way those do, so the
    caller only has to close the bridge afterwards.
    """

    async def up() -> None:
        try:
            while True:
                chunk = await ws.receive_bytes()
                await bridge.send(chunk)
        except Exception:
            pass  # browser disconnected or relay send failed — tearing down

    async def down() -> None:
        try:
            async for message in bridge:
                if isinstance(message, str):
                    # The relay only ever sends binary; a text frame means the
                    # far side is speaking a different protocol than we think.
                    log.warning("remote-screen: unexpected text frame on the relay")
                    continue
                await ws.send_bytes(message)
        except Exception:
            pass  # relay closed or browser write failed — tearing down

    tasks = [asyncio.create_task(up()), asyncio.create_task(down())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
