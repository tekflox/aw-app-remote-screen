"""Entrypoint referenced by aw-app.json's runtime.entrypoint
("remote_screen_app.plugin:RemoteDesktopAppPlugin").

Ports the monolith's ``/api/remote-desktop/*`` + ``/ws/remote-desktop/{id}``
(``src/api/routes/remote_desktop.py``) onto the F4 ``ctx`` facades:

* ``ctx.routes`` (``routes:register``) — HTTP + WS sub-app mounted at
  ``/api/apps/remote-screen``.
* ``ctx.db`` (``db:own-tables``) — saved hosts live in this app's own
  ``app__remote-screen__hosts`` table instead of ``src/config/remote_desktop.json``.
* ``ctx.secrets`` (``secrets:own``) — one secret per host password, instead of
  the monolith's ``secrets_crypto`` field inside that same JSON file.

Nothing here touches the table beyond the idempotent create in ``HostStore``:
the runtime applies ``migrations/*.sql`` AFTER ``activate()`` returns, so a
migration can safely ALTER what this just ensured exists — but by the same
token ``activate()`` must not depend on a migration having run yet.
"""
from __future__ import annotations

import logging

from . import routes as routes_mod
from .store import HostStore

log = logging.getLogger("aw_apps.remote-screen")


class RemoteDesktopAppPlugin:
    async def activate(self, ctx) -> None:
        self.ctx = ctx
        self.store = HostStore(ctx)
        ctx.routes.register(routes_mod.build_routes(ctx, self.store))
        log.info("aw-app-remote-screen activated (%d saved host(s))", len(self.store.list()))

    async def on_config_saved(self, ctx) -> None:
        # Viewer defaults are read per-request off ctx.config (GET /settings),
        # so a save needs no rebuild — just re-point at the fresh ctx.
        self.ctx = ctx
        log.info("aw-app-remote-screen config saved")

    async def deactivate(self) -> None:
        # The table and its secrets deliberately SURVIVE unload: reconcile()'s
        # upgrade path is uninstall+install for a plain version bump, so
        # dropping here would wipe the user's saved hosts on every update.
        log.info("aw-app-remote-screen deactivated")
