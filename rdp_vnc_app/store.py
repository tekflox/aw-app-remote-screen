"""Saved remote-desktop hosts — this app's own Postgres table + secret store.

Replaces the monolith's ``src/config/remote_desktop.json`` (a flat JSON list
whose passwords were encrypted with ``src.api.secrets_crypto``, i.e. the same
key as the NordVPN credentials) with the two mechanisms the app framework
actually provides:

* ``ctx.db`` (``db:own-tables``) — rows in ``app__rdp-vnc__hosts``, created in
  this workspace's own schema under the enforced ``app__<slug>__`` prefix.
  The INITIAL shape is created here via ``ctx.db.create`` (idempotent
  ``CREATE TABLE IF NOT EXISTS``, journaled as ``db:table``); every later
  change to that shape is a numbered file in ``migrations/`` (see
  ``migrations/0001_hosts_indexes.sql``), applied at most once per
  (app_id, filename) by the runtime on both install and update.
* ``ctx.secrets`` (``secrets:own``) — the host password, one secret per host
  under ``host:<id>:password``. It never lives in the table, so a DB dump,
  a ``SELECT *`` or an accidentally-wide API response can't leak it; the
  table only carries the boolean ``has_password`` so the UI can say
  "saved password" without the value round-tripping.

Why the password still has to reach the browser at all: VNC auth is a DES
challenge-response the server issues over the RFB channel itself, so noVNC
performs it client-side. ``credentials()`` below is the single, deliberate
place that hands the plaintext back, and only to an identity-authenticated
caller. Same constraint the monolith documented — not a regression.
"""
from __future__ import annotations

import uuid as _uuid

TABLE_SUFFIX = "hosts"

# Initial shape only — evolve it with a numbered file in migrations/, never by
# editing this string (an existing install already has the old shape; the
# CREATE is IF NOT EXISTS and will not alter it).
TABLE_COLUMNS_SQL = """
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    protocol     TEXT NOT NULL DEFAULT 'vnc',
    host         TEXT NOT NULL,
    port         INTEGER NOT NULL,
    username     TEXT NOT NULL DEFAULT '',
    has_password BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order   INTEGER NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
"""

# Only VNC is actually bridgeable today (see routes.bridge). RDP is accepted as
# a stored value so a host inventory can be migrated/entered ahead of the
# protocol landing, and is rejected at connect time with a clear message
# rather than silently opening a byte bridge noVNC can't speak.
PROTOCOLS = ("vnc", "rdp")

SUPPORTED_PROTOCOLS = ("vnc",)


class HostError(ValueError):
    """Bad input from a caller — routes.py turns this into a 400."""


class HostNotFound(LookupError):
    """No row with that id — routes.py turns this into a 404."""


def _password_key(host_id: str) -> str:
    return f"host:{host_id}:password"


class HostStore:
    def __init__(self, ctx) -> None:
        self._ctx = ctx
        self._table = ctx.db.table(f"app__{ctx.app_id}__{TABLE_SUFFIX}")
        ctx.db.create(self._table, TABLE_COLUMNS_SQL)

    # ── reads ───────────────────────────────────────────────────────────────

    def list(self) -> list[dict]:
        rows = self._ctx.db.execute(
            self._table,
            "SELECT id, name, protocol, host, port, username, has_password, sort_order "
            "FROM {table} ORDER BY sort_order, lower(name)",
        )
        return [self._public(r) for r in rows]

    def get(self, host_id: str) -> dict:
        rows = self._ctx.db.execute(
            self._table,
            "SELECT id, name, protocol, host, port, username, has_password, sort_order "
            "FROM {table} WHERE id = :id",
            {"id": host_id},
        )
        if not rows:
            raise HostNotFound(host_id)
        return self._public(rows[0])

    def credentials(self, host_id: str) -> dict:
        """Plaintext password for a host — the one deliberate read (see module
        docstring). A host row with no stored secret returns ``""`` rather than
        raising, so a password-less VNC server behaves the same as one whose
        secret was purged."""
        row = self.get(host_id)
        password = self._ctx.secrets.read(_password_key(host_id)) or ""
        return {"username": row["username"], "password": password}

    @staticmethod
    def _public(row) -> dict:
        """Shape returned to the frontend — deliberately never the password,
        just whether one is set, so the host list/editor can't round-trip the
        plaintext through the browser by accident."""
        return {
            "id": row[0],
            "name": row[1],
            "protocol": row[2],
            "host": row[3],
            "port": row[4],
            "username": row[5],
            "has_password": bool(row[6]),
            "sort_order": row[7],
            "supported": row[2] in SUPPORTED_PROTOCOLS,
        }

    # ── writes ──────────────────────────────────────────────────────────────

    def create(self, body: dict) -> dict:
        name = (body.get("name") or "").strip()
        host = (body.get("host") or "").strip()
        protocol = (body.get("protocol") or "vnc").strip().lower()
        try:
            port = int(body.get("port") or 0)
        except (TypeError, ValueError):
            raise HostError("port must be a number")
        if not name or not host or not port:
            raise HostError("name, host and port are required")
        if not 1 <= port <= 65535:
            raise HostError("port must be between 1 and 65535")
        if protocol not in PROTOCOLS:
            raise HostError(f"protocol must be one of {', '.join(PROTOCOLS)}")

        password = body.get("password") or ""
        host_id = str(body.get("id") or _uuid.uuid4())
        self._ctx.db.execute(
            self._table,
            "INSERT INTO {table} "
            "(id, name, protocol, host, port, username, has_password, sort_order) "
            "VALUES (:id, :name, :protocol, :host, :port, :username, :has_password, :sort_order)",
            {
                "id": host_id,
                "name": name,
                "protocol": protocol,
                "host": host,
                "port": port,
                "username": (body.get("username") or "").strip(),
                "has_password": bool(password),
                "sort_order": int(body.get("sort_order") or 0),
            },
        )
        if password:
            self._ctx.secrets.write(_password_key(host_id), password)
        return self.get(host_id)

    def update(self, host_id: str, body: dict) -> dict:
        current = self.get(host_id)
        merged = {
            "name": (body.get("name") or current["name"]).strip(),
            "protocol": (body.get("protocol") or current["protocol"]).strip().lower(),
            "host": (body.get("host") or current["host"]).strip(),
            "port": body.get("port") if body.get("port") not in (None, "") else current["port"],
            # username is genuinely clearable, so distinguish "absent" from "".
            "username": (current["username"] if body.get("username") is None
                         else str(body.get("username")).strip()),
            "sort_order": (current["sort_order"] if body.get("sort_order") is None
                           else int(body.get("sort_order"))),
        }
        try:
            merged["port"] = int(merged["port"])
        except (TypeError, ValueError):
            raise HostError("port must be a number")
        if not merged["name"] or not merged["host"]:
            raise HostError("name and host cannot be blank")
        if not 1 <= merged["port"] <= 65535:
            raise HostError("port must be between 1 and 65535")
        if merged["protocol"] not in PROTOCOLS:
            raise HostError(f"protocol must be one of {', '.join(PROTOCOLS)}")

        # Password is optional on update — omit/blank to KEEP the existing one,
        # so editing a name or port doesn't force re-typing it. An explicit
        # empty-string `clear_password` is the way to actually remove it.
        has_password = current["has_password"]
        if body.get("clear_password"):
            self._ctx.secrets.delete(_password_key(host_id))
            has_password = False
        elif body.get("password"):
            self._ctx.secrets.write(_password_key(host_id), body["password"])
            has_password = True

        self._ctx.db.execute(
            self._table,
            "UPDATE {table} SET name = :name, protocol = :protocol, host = :host, "
            "port = :port, username = :username, has_password = :has_password, "
            "sort_order = :sort_order, updated_at = now() WHERE id = :id",
            {**merged, "has_password": has_password, "id": host_id},
        )
        return self.get(host_id)

    def upsert_by_name(self, body: dict) -> dict:
        """Create, or update the existing host with the same (case-insensitive)
        name. This is what the declarative Settings panel's single "Add or
        update host" form submits to — the declarative widget vocabulary has no
        way to load a table row back into a form, so name is the natural key a
        human already uses to mean "that machine"."""
        name = (body.get("name") or "").strip()
        if not name:
            raise HostError("name is required")
        rows = self._ctx.db.execute(
            self._table, "SELECT id FROM {table} WHERE lower(name) = lower(:name)",
            {"name": name},
        )
        if rows:
            return self.update(rows[0][0], body)
        return self.create(body)

    def delete(self, host_id: str) -> None:
        self.get(host_id)  # 404 before we touch anything
        self._ctx.secrets.delete(_password_key(host_id))
        self._ctx.db.execute(
            self._table, "DELETE FROM {table} WHERE id = :id", {"id": host_id})
