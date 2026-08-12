"""remote_screen_app's mode-agnostic FastAPI sub-app.

Mounted at ``/api/apps/remote-screen`` in both modes (integrated: behind the
runtime's IdentityGuard; standalone: by ``__main__.py``), so every path here
is RELATIVE — see ``aw-app-template/template_app/routes.py`` for the contract.

    GET    /hosts                     list saved hosts (never passwords)
    POST   /hosts                     create
    POST   /hosts/upsert              create-or-update by name (Settings form)
    PUT    /hosts/{id}                update
    DELETE /hosts/{id}                delete (+ purge its secret)
    GET    /hosts/{id}/credentials    plaintext password, for noVNC's client-
                                      side DES challenge-response
    WS     /ws/bridge/{id}            raw byte bridge to the host's host:port

The bridge carries no VNC-protocol awareness at all — it is byte-for-byte
websockify, exactly as the monolith's ``/ws/remote-desktop/{id}`` was. That is
also precisely why only VNC works: noVNC speaks RFB over this socket. RDP has
no browser-side client that can drive a raw TCP tunnel, so a host stored with
``protocol: "rdp"`` is rejected here with a distinct close code instead of
being handed a stream nothing on the other end can parse.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from . import android as android_mod
from .hosts_ui import HOSTS_UI_HTML
from .store import HostError, HostNotFound, HostStore, TCP_PROTOCOLS

log = logging.getLogger("aw_apps.remote-screen")

# WebSocket close codes — distinct per failure so the frontend can say what
# actually went wrong instead of a generic "connection lost".
WS_NOT_FOUND = 4404
WS_UNSUPPORTED_PROTOCOL = 4415
WS_CONNECT_FAILED = 4502


def build_routes(ctx, store: HostStore) -> FastAPI:
    app = FastAPI(title="remote-screen")

    def _connect_timeout() -> float:
        return float((getattr(ctx, "config", {}) or {}).get("connect_timeout_s") or 10)

    # ── REST: host CRUD ─────────────────────────────────────────────────────

    @app.get("/hosts")
    async def list_hosts() -> dict:
        return {"hosts": store.list()}

    @app.post("/hosts")
    async def create_host(body: dict = Body(...)) -> dict:
        try:
            return store.create(body)
        except HostError as e:
            raise HTTPException(400, str(e))

    @app.post("/hosts/upsert")
    async def upsert_host(body: dict = Body(...)) -> dict:
        try:
            return store.upsert_by_name(body)
        except HostError as e:
            raise HTTPException(400, str(e))

    @app.put("/hosts/{host_id}")
    async def update_host(host_id: str, body: dict = Body(...)) -> dict:
        try:
            return store.update(host_id, body)
        except HostNotFound:
            raise HTTPException(404, "Host not found")
        except HostError as e:
            raise HTTPException(400, str(e))

    @app.delete("/hosts/{host_id}")
    async def delete_host(host_id: str) -> dict:
        try:
            store.delete(host_id)
        except HostNotFound:
            raise HTTPException(404, "Host not found")
        return {"ok": True}

    @app.get("/hosts/{host_id}/credentials")
    async def credentials(host_id: str) -> dict:
        try:
            return store.credentials(host_id)
        except HostNotFound:
            raise HTTPException(404, "Host not found")

    @app.get("/settings")
    async def settings() -> dict:
        """Viewer defaults the frontend reads before building the noVNC URL,
        so the config_schema knobs actually take effect without the bundle
        having to reach into the framework's own /api/apps/<id> payload."""
        cfg = getattr(ctx, "config", {}) or {}
        return {
            "default_scaling": cfg.get("default_scaling") or "scale",
            "view_only": bool(cfg.get("view_only")),
        }

    @app.get("/ui/hosts", response_class=HTMLResponse)
    async def hosts_ui() -> HTMLResponse:
        """The hosts editor, rendered into the Settings panel's iframe widget
        (windows/hosts.json). See hosts_ui.py for why this isn't declarative
        widgets. Behind IdentityGuard like every other route here."""
        return HTMLResponse(HOSTS_UI_HTML)

    @app.get("/hosts/{host_id}/android/status")
    async def android_status(host_id: str) -> dict:
        try:
            row = store.get(host_id)
        except HostNotFound:
            raise HTTPException(404, "Host not found")
        if row["protocol"] != "android":
            raise HTTPException(400, "not an android host")
        return await android_mod.status(row)

    @app.websocket("/ws/android/{host_id}")
    async def android_stream(ws: WebSocket, host_id: str) -> None:
        try:
            row = store.get(host_id)
        except HostNotFound:
            await ws.close(code=WS_NOT_FOUND)
            return
        if row["protocol"] != "android":
            await ws.close(code=WS_UNSUPPORTED_PROTOCOL)
            return
        await android_mod.stream(ws, row)

    # ── WebSocket: raw byte bridge to host:port (websockify-equivalent) ─────

    @app.websocket("/ws/bridge/{host_id}")
    async def bridge(ws: WebSocket, host_id: str) -> None:
        try:
            row = store.get(host_id)
        except HostNotFound:
            await ws.close(code=WS_NOT_FOUND)
            return
        if row["protocol"] not in TCP_PROTOCOLS or not row["supported"]:
            log.warning("remote-screen %s: protocol %s has no browser client yet",
                        host_id, row["protocol"])
            await ws.close(code=WS_UNSUPPORTED_PROTOCOL)
            return

        await ws.accept()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(row["host"], row["port"]),
                timeout=_connect_timeout(),
            )
        except Exception as e:
            log.warning("remote-screen %s: connect to %s:%s failed: %s",
                        host_id, row["host"], row["port"], e)
            await ws.close(code=WS_CONNECT_FAILED)
            return

        async def tcp_to_ws() -> None:
            try:
                while True:
                    chunk = await reader.read(65536)
                    if not chunk:
                        break
                    await ws.send_bytes(chunk)
            except Exception:
                pass  # tcp connection or websocket closed — bridge tearing down

        async def ws_to_tcp() -> None:
            try:
                while True:
                    chunk = await ws.receive_bytes()
                    writer.write(chunk)
                    await writer.drain()
            except (WebSocketDisconnect, Exception):
                pass  # client disconnected or tcp write failed — tearing down

        try:
            await asyncio.gather(tcp_to_ws(), ws_to_tcp(), return_exceptions=True)
        finally:
            writer.close()

    return app
