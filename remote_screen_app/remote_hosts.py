"""Linked aw-remote-host lookup, for the destination picker.

Port of ``aw-app-tunnel/tunnel_app/remote_hosts.py``. Talks to aw-backend's
``GET /api/workspaces/{slug}/remote-hosts`` with this workspace's own
``awlk_`` credential — the same call ``aw-app-remote-host-cli``'s client
makes.

Failure is never fatal here: this only populates a dropdown, so a missing
credential or an unreachable backend degrades to an empty list plus a reason,
and the UI falls back to the ``custom`` destination.
"""
from __future__ import annotations

import logging

import httpx

from .remote_dial import DEFAULT_BACKEND_URL, _env

log = logging.getLogger("aw_apps.remote-screen")


async def list_linked_hosts() -> dict:
    backend = (_env("AW_BACKEND_URL") or DEFAULT_BACKEND_URL).rstrip("/")
    workspace = _env("AW_WORKSPACE")
    token = _env("AW_WORKSPACE_HOST_TOKEN")
    if not (workspace and token):
        return {"hosts": [], "error": "no workspace host credential published"}
    url = f"{backend}/api/workspaces/{workspace}/remote-hosts"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url, headers={"Authorization": f"Bearer {token}"}, timeout=15)
            resp.raise_for_status()
            return {"hosts": resp.json().get("hosts", []), "error": None}
    except Exception as e:  # noqa: BLE001 — a dropdown is not worth a 500
        log.warning("remote-screen: remote-host lookup failed: %s", e)
        return {"hosts": [], "error": str(e)}
