# aw-app-remote-screen — Remote Desktop

Browser-side remote desktop for aw-workspace. Ported from the aw monolith
(`src/api/routes/remote_desktop.py` + `src/app/src/components/RemoteDesktopWindow.jsx`).

- **Viewer** — the vendored noVNC client in an iframe, fed by a raw
  WebSocket→TCP byte bridge (`/api/apps/remote-screen/ws/bridge/{id}`). No
  VNC-protocol awareness on the server side; byte-for-byte websockify, same as
  the monolith's `/ws/remote-desktop/{id}`.
- **Hosts** — add / edit / remove saved machines from **Settings › Remote
  Desktop**, or from *Manage hosts* in the viewer's picker.

## What changed vs. the monolith

| | monolith | this app |
|---|---|---|
| Host list | `src/config/remote_desktop.json` (flat file) | `app__remote-screen__hosts` Postgres table (`db:own-tables`) |
| Passwords | same JSON file, encrypted with `secrets_crypto` (the NordVPN key) | workspace secret store, one secret per host (`secrets:own`) |
| Schema changes | edit the file | numbered SQL in `migrations/` |
| Android emulator | wedged into the same connection picker | removed — unrelated transport, belongs to whichever app owns the emulator |

## Migrations

The app declares `"migrations": {"dir": "migrations"}`. The runtime applies
each `.sql` file at most once per `(app_id, filename)`, tracked in core's
`_app_migrations` table, on **both** install and update — after
`plugin.activate()`, so a migration can ALTER a table the plugin's
`ctx.db.create()` just ensured exists.

Split of responsibilities:

- **`store.py`'s `TABLE_COLUMNS_SQL`** — the table's INITIAL shape only.
  `ctx.db.create()` runs `CREATE TABLE IF NOT EXISTS`, so on an install that
  already has the table (i.e. every update) a changed column list is silently
  ignored. Never evolve the schema by editing that string.
- **`migrations/NNNN_*.sql`** — everything after that: added columns,
  indexes, constraints, backfills.

Write migration SQL **unqualified** (`CREATE INDEX ... ON "app__remote-screen__hosts"`).
The schema name is per-tenant and unknown at authoring time; core sets
`search_path` for the migration's transaction.

> Portable migrations required a core fix (aw-workspace `src/apps/migrations.py`):
> the engine's `schema_translate_map` only rewrites SQLAlchemy `Table` metadata,
> never text SQL, so before that change an unqualified `CREATE TABLE` in a
> migration file landed in `public` instead of the workspace schema — and an app
> had no way to qualify it correctly either. Core now issues
> `SET LOCAL search_path` per migration transaction. Files that *do* qualify
> explicitly (like the existing core test's) still work unchanged.

## Importing the monolith's saved connections

```bash
python scripts/import_from_monolith.py --dry-run
python scripts/import_from_monolith.py --api-key "$AW_WORKSPACE_API_KEY"
```

Reads the monolith's `remote_desktop.json`, decrypts each password with the
monolith's own `secrets_crypto` key, and POSTs to `/hosts/upsert` — keyed by
name, so re-running updates instead of duplicating. If the monolith's crypto
module isn't importable from where you run this, hosts still import, just
without passwords (re-enter them once in Settings).

## RDP

**Not implemented.** `protocol: "rdp"` is a storable value so a host inventory
can be entered ahead of the protocol landing, and rows carry `supported:
false`; the viewer refuses them with a real message and the bridge closes with
`4415`. RDP needs a server-side protocol translator (FreeRDP/Guacamole-style)
plus its own browser client — it is not something the raw byte bridge can
carry, because there is no browser-side RDP client to put on the other end.

## Layout

```
remote_screen_app/
  plugin.py     activate(ctx) — routes + store
  store.py      hosts table (ctx.db) + passwords (ctx.secrets)
  routes.py     REST CRUD, /ui/hosts, WS bridge
  hosts_ui.py   the Settings-panel hosts editor (see below)
  __main__.py   standalone mode, SQLite-backed fake ctx
migrations/     numbered SQL, applied once each by the runtime
windows/        hosts.json — declarative settings panel
ui/src/         component-mode bundle: nav row + viewer window body
```

### Why the settings panel is an iframe

aw-workspace-ui's declarative renderer (`src/components/AppWindow.jsx`)
supports `markdown`, `list`, `button`, `iframe`, `app_iframe`, `collapsible`,
`form`, `auth_status`. Its `list` renders **static** items from the spec, and
there is **no `table` widget** — so a widget spec cannot render a live,
editable list of rows. `iframe { src: "/api/*" }` is the vocabulary's own
escape hatch, so `windows/hosts.json` points at `/api/apps/remote-screen/ui/hosts`
(`hosts_ui.py`): one dependency-free HTML page with the full CRUD, behind the
same IdentityGuard as every other route.

> Note for other apps: `aw-app-proxy`'s and any other manifest's `table`
> widgets are inert for the same reason — the renderer has no `table` case.

## Tests

```bash
pip install jsonschema pytest fastapi httpx uvicorn
python tests/validate_manifest.py
python -m pytest tests/ -q
```

The suite runs the store against the same SQLite-backed `ctx` standalone mode
uses, so it exercises the real SQL. The Postgres half (prefix enforcement,
schema isolation, migrations applying exactly once) is core's and is covered
by aw-workspace's `src/tests/integration/apps/test_db_tables.py`.

## Building the frontend

```bash
cd ui && npm install && npm run build   # -> ui/dist/remote-screen.js
```
