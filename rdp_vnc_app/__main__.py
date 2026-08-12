"""Standalone entrypoint (ADR Decision 4) — run this app WITHOUT the
aw-workspace runtime:

    python -m rdp_vnc_app                 # binds 127.0.0.1:9410
    PORT=9411 python -m rdp_vnc_app

Standalone has no ``ctx``, so there is no ``ctx.db`` / ``ctx.secrets`` and no
workspace Postgres schema to write into. Rather than pretend, this mode backs
the same ``HostStore`` API with a local SQLite file + a plaintext-adjacent
key file under ``.data/`` — good enough to develop the viewer against a real
VNC server, explicitly NOT a deployment posture (see the auth note below).

Auth: standalone has no ``IdentityGuard`` — that is runtime machinery, not app
code. This binds 127.0.0.1 only. Do not expose it; ``/hosts/{id}/credentials``
hands back a plaintext password to whoever asks.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from .routes import build_routes
from .store import TABLE_COLUMNS_SQL, HostStore

SLUG = "rdp-vnc"  # must match aw-app.json's "id"
DEFAULT_PORT = 9410  # must match aw-app.json's runtime.standalone.default_port

APP_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = APP_ROOT / ".data"


class _SqliteCtx:
    """Minimal ``ctx`` stand-in exposing only what ``HostStore`` uses:
    ``app_id``, ``config``, ``db.table/create/execute`` and
    ``secrets.read/write/delete``. SQLite accepts the same parameterised SQL
    the store writes, once ``:name`` binds and ``now()`` are translated."""

    def __init__(self, path: Path) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.app_id = SLUG
        self.config: dict = {}
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._secrets_path = DATA_DIR / "secrets.json"
        self.db = self._Db(self._conn)
        self.secrets = self._Secrets(self._secrets_path)

    class _Db:
        def __init__(self, conn: sqlite3.Connection) -> None:
            self._conn = conn

        def table(self, name: str) -> str:
            return name

        def create(self, name: str, columns_sql: str) -> str:
            cols = (columns_sql
                    .replace("TIMESTAMPTZ", "TEXT")
                    .replace("DEFAULT now()", "DEFAULT CURRENT_TIMESTAMP")
                    .replace("BOOLEAN", "INTEGER"))
            self._conn.execute(f'CREATE TABLE IF NOT EXISTS "{name}" ({cols})')
            self._conn.commit()
            return name

        def execute(self, name: str, sql: str, params: dict | None = None):
            stmt = sql.replace("{table}", f'"{name}"').replace("now()", "CURRENT_TIMESTAMP")
            cur = self._conn.execute(stmt, params or {})
            self._conn.commit()
            return cur.fetchall() if stmt.strip().lower().startswith("select") else cur

    class _Secrets:
        def __init__(self, path: Path) -> None:
            self._path = path

        def _load(self) -> dict:
            if not self._path.exists():
                return {}
            return json.loads(self._path.read_text())

        def _save(self, data: dict) -> None:
            self._path.write_text(json.dumps(data, indent=2))
            os.chmod(self._path, 0o600)

        def read(self, key: str):
            return self._load().get(key)

        def write(self, key: str, value: str) -> None:
            data = self._load()
            data[key] = value
            self._save(data)

        def delete(self, key: str) -> bool:
            data = self._load()
            existed = data.pop(key, None) is not None
            self._save(data)
            return existed


def build_standalone_app() -> FastAPI:
    app = FastAPI(title="rdp-vnc (standalone)")
    ctx = _SqliteCtx(DATA_DIR / "hosts.sqlite3")
    # Touch TABLE_COLUMNS_SQL through the store so both modes share one schema
    # definition rather than drifting apart.
    assert TABLE_COLUMNS_SQL
    store = HostStore(ctx)
    app.mount(f"/api/apps/{SLUG}", build_routes(ctx, store))
    return app


app = build_standalone_app()


def main() -> None:
    port = int(os.environ.get("PORT", str(DEFAULT_PORT)))
    uvicorn.run(app, host=os.environ.get("AW_APP_HOST", "127.0.0.1"), port=port)


if __name__ == "__main__":
    main()
