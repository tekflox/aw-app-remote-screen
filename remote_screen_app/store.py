"""Saved remote-desktop hosts — this app's own Postgres table + secret store.

Replaces the monolith's ``src/config/remote_desktop.json`` (a flat JSON list
whose passwords were encrypted with ``src.api.secrets_crypto``, i.e. the same
key as the NordVPN credentials) with the two mechanisms the app framework
actually provides:

* ``ctx.db`` (``db:own-tables``) — rows in ``app__remote-screen__hosts``, created in
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

# The three protocols this app speaks. They are NOT one mechanism with three
# labels — each is a distinct transport:
#
#   vnc     raw WebSocket<->TCP byte bridge to host:port; noVNC speaks RFB over it.
#   rdp     same byte bridge, but no browser-side client exists that can drive a
#           raw TCP tunnel — needs a server-side protocol translator
#           (FreeRDP/Guacamole-shaped). Storable, not yet connectable.
#   android no TCP endpoint at all: frames are polled with `adb exec-out
#           screencap` over the remote-agent EXEC channel and pushed as PNGs,
#           input goes back as `adb shell input`. See android.py.
PROTOCOLS = ("vnc", "rdp", "android")

# Protocols whose transport can actually reach a host and render today.
SUPPORTED_PROTOCOLS = ("vnc", "android")

# Protocols addressed by host:port rather than by a remote-agent profile id.
TCP_PROTOCOLS = ("vnc", "rdp")

# Columns added AFTER the initial shape, by migrations/0002_android_columns.sql.
# Declared here too because standalone mode has no migration runner (see
# __main__.py) — it applies these directly. test_schema_matches_migration
# asserts the two never drift apart; edit both or neither.
POST_INIT_COLUMNS = {
    "device_serial": "TEXT NOT NULL DEFAULT ''",
    "agent_base_url": "TEXT NOT NULL DEFAULT ''",
    "adb_bin": "TEXT NOT NULL DEFAULT ''",
}


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
            "SELECT id, name, protocol, host, port, username, has_password, sort_order, "
            "device_serial, agent_base_url, adb_bin "
            "FROM {table} ORDER BY sort_order, lower(name)",
        )
        return [self._public(r) for r in rows]

    def get(self, host_id: str) -> dict:
        rows = self._ctx.db.execute(
            self._table,
            "SELECT id, name, protocol, host, port, username, has_password, sort_order, "
            "device_serial, agent_base_url, adb_bin "
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
            "device_serial": row[8],
            "agent_base_url": row[9],
            "adb_bin": row[10],
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
        if protocol not in PROTOCOLS:
            raise HostError(f"protocol must be one of {', '.join(PROTOCOLS)}")
        if not name or not host:
            raise HostError("name and host are required")
        if protocol in TCP_PROTOCOLS:
            if not port:
                raise HostError("port is required for vnc/rdp")
            if not 1 <= port <= 65535:
                raise HostError("port must be between 1 and 65535")
        else:
            # android is addressed by remote-agent profile id, not host:port.
            port = 0

        password = body.get("password") or ""
        host_id = str(body.get("id") or _uuid.uuid4())
        self._ctx.db.execute(
            self._table,
            "INSERT INTO {table} "
            "(id, name, protocol, host, port, username, has_password, sort_order, "
            " device_serial, agent_base_url, adb_bin) "
            "VALUES (:id, :name, :protocol, :host, :port, :username, :has_password, "
            "        :sort_order, :device_serial, :agent_base_url, :adb_bin)",
            {
                "id": host_id,
                "name": name,
                "protocol": protocol,
                "host": host,
                "port": port,
                "username": (body.get("username") or "").strip(),
                "has_password": bool(password),
                "sort_order": int(body.get("sort_order") or 0),
                "device_serial": (body.get("device_serial") or "").strip(),
                "agent_base_url": (body.get("agent_base_url") or "").strip(),
                "adb_bin": (body.get("adb_bin") or "").strip(),
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
            merged["port"] = int(merged["port"] or 0)
        except (TypeError, ValueError):
            raise HostError("port must be a number")
        if merged["protocol"] not in PROTOCOLS:
            raise HostError(f"protocol must be one of {', '.join(PROTOCOLS)}")
        if not merged["name"] or not merged["host"]:
            raise HostError("name and host cannot be blank")
        if merged["protocol"] in TCP_PROTOCOLS:
            if not 1 <= merged["port"] <= 65535:
                raise HostError("port must be between 1 and 65535")
        else:
            merged["port"] = 0
        for field in POST_INIT_COLUMNS:
            merged[field] = (current[field] if body.get(field) is None
                             else str(body[field]).strip())

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
            "sort_order = :sort_order, device_serial = :device_serial, "
            "agent_base_url = :agent_base_url, adb_bin = :adb_bin, "
            "updated_at = now() WHERE id = :id",
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
