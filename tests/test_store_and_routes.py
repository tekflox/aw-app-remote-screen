"""HostStore + routes against a fake ctx — no Postgres, no runtime.

The fake ``ctx`` is SQLite-backed (``__main__._SqliteCtx``), which is exactly
what standalone mode uses, so these tests exercise the real store SQL rather
than a mock that agrees with whatever the code happens to do. The Postgres-
specific half (prefix enforcement, schema isolation, migrations applying once)
is core's job and is already covered by aw-workspace's
``src/tests/integration/apps/test_db_tables.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from remote_screen_app.__main__ import _SqliteCtx  # noqa: E402
from remote_screen_app.routes import build_routes  # noqa: E402
from remote_screen_app.store import HostError, HostNotFound, HostStore  # noqa: E402


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr("remote_screen_app.__main__.DATA_DIR", tmp_path)
    return _SqliteCtx(tmp_path / "hosts.sqlite3")


@pytest.fixture()
def store(ctx):
    return HostStore(ctx)


@pytest.fixture()
def client(ctx, store):
    app = build_routes(ctx, store)
    return TestClient(app)


def test_create_lists_without_password_but_credentials_returns_it(store):
    row = store.create({"name": "office", "host": "10.0.0.5", "port": 5900,
                        "password": "s3cret"})
    assert row["has_password"] is True
    assert "password" not in row  # never round-trips through the list shape
    listed = store.list()
    assert [h["name"] for h in listed] == ["office"]
    assert all("password" not in h for h in listed)
    assert store.credentials(row["id"])["password"] == "s3cret"


def test_update_without_password_keeps_the_saved_one(store):
    row = store.create({"name": "office", "host": "10.0.0.5", "port": 5900,
                        "password": "s3cret"})
    updated = store.update(row["id"], {"port": 5901})
    assert updated["port"] == 5901
    assert updated["has_password"] is True
    assert store.credentials(row["id"])["password"] == "s3cret"


def test_clear_password_removes_the_secret(store):
    row = store.create({"name": "office", "host": "10.0.0.5", "port": 5900,
                        "password": "s3cret"})
    updated = store.update(row["id"], {"clear_password": True})
    assert updated["has_password"] is False
    assert store.credentials(row["id"])["password"] == ""


def test_upsert_by_name_edits_instead_of_duplicating(store):
    store.create({"name": "office", "host": "10.0.0.5", "port": 5900})
    store.upsert_by_name({"name": "OFFICE", "host": "10.0.0.9", "port": 5902})
    rows = store.list()
    assert len(rows) == 1
    assert (rows[0]["host"], rows[0]["port"]) == ("10.0.0.9", 5902)


def test_delete_purges_the_secret_too(store, ctx):
    row = store.create({"name": "office", "host": "10.0.0.5", "port": 5900,
                        "password": "s3cret"})
    store.delete(row["id"])
    assert store.list() == []
    assert ctx.secrets.read(f"host:{row['id']}:password") is None
    with pytest.raises(HostNotFound):
        store.get(row["id"])


@pytest.mark.parametrize("body", [
    {"name": "", "host": "h", "port": 5900},
    {"name": "n", "host": "", "port": 5900},
    {"name": "n", "host": "h", "port": 0},
    {"name": "n", "host": "h", "port": 70000},
    {"name": "n", "host": "h", "port": 5900, "protocol": "telnet"},
])
def test_bad_input_rejected(store, body):
    with pytest.raises(HostError):
        store.create(body)


def test_rdp_is_storable_but_flagged_unsupported(store):
    row = store.create({"name": "win-box", "host": "10.0.0.7", "port": 3389,
                        "protocol": "rdp"})
    assert row["protocol"] == "rdp"
    # The viewer keys off this to refuse the connection with a real message
    # instead of opening a byte bridge noVNC can't parse.
    assert row["supported"] is False


# ── HTTP surface ────────────────────────────────────────────────────────────

def test_crud_over_http(client):
    created = client.post("/hosts", json={"name": "office", "host": "10.0.0.5",
                                          "port": 5900, "password": "pw"}).json()
    assert client.get("/hosts").json()["hosts"][0]["name"] == "office"
    assert client.get(f"/hosts/{created['id']}/credentials").json()["password"] == "pw"

    assert client.put(f"/hosts/{created['id']}", json={"name": "office-2"}).json()["name"] == "office-2"
    assert client.delete(f"/hosts/{created['id']}").status_code == 200
    assert client.get("/hosts").json()["hosts"] == []


def test_http_error_codes(client):
    assert client.post("/hosts", json={"name": "x"}).status_code == 400
    assert client.get("/hosts/nope/credentials").status_code == 404
    assert client.put("/hosts/nope", json={"name": "y"}).status_code == 404
    assert client.delete("/hosts/nope").status_code == 404


def test_settings_endpoint_reflects_config(ctx, store):
    ctx.config = {"default_scaling": "remote", "view_only": True}
    body = TestClient(build_routes(ctx, store)).get("/settings").json()
    assert body == {"default_scaling": "remote", "view_only": True}


def test_hosts_ui_page_is_served_and_self_contained(client):
    """The Settings panel is an iframe onto this page (see hosts_ui.py), so a
    regression here silently empties the settings pane rather than erroring."""
    res = client.get("/panel/hosts")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    body = res.text
    assert "/api/apps/remote-screen" in body       # talks to this app's own routes
    assert "<script" in body and "src=" not in body.split("<script")[1][:200]
    # No unrendered \u escapes leaking into markup (they're only valid in JS).
    head = body.split("<script")[0]
    assert "\\u" not in head


# ── Android protocol ────────────────────────────────────────────────────────

def test_post_init_columns_match_migration():
    """POST_INIT_COLUMNS is duplicated in store.py (for standalone, which has no
    migration runner) and in the migrations. Drift means standalone silently
    lacks a column the store SELECTs, so pin them together. Scans the whole
    migrations dir, not one file — columns arrive in different numbered files
    as the app grows."""
    from remote_screen_app.store import POST_INIT_COLUMNS
    mig_dir = Path(__file__).resolve().parent.parent / "migrations"
    sql = "\n".join(p.read_text() for p in sorted(mig_dir.glob("*.sql")))
    for col in POST_INIT_COLUMNS:
        assert f"ADD COLUMN IF NOT EXISTS {col}" in sql, col


def test_android_host_needs_no_port(store):
    row = store.create({"name": "pixel", "protocol": "android", "host": "macbook-fred",
                        "device_serial": "emulator-5554"})
    assert row["port"] == 0
    assert row["protocol"] == "android"
    assert row["supported"] is True          # android's transport really works
    assert row["device_serial"] == "emulator-5554"


def test_vnc_still_requires_a_port(store):
    with pytest.raises(HostError):
        store.create({"name": "mac", "protocol": "vnc", "host": "10.0.0.5"})


def test_android_fields_survive_a_partial_update(store):
    row = store.create({"name": "pixel", "protocol": "android", "host": "macbook-fred",
                        "device_serial": "emulator-5554", "adb_bin": "/opt/adb"})
    updated = store.update(row["id"], {"name": "pixel-2"})
    assert updated["device_serial"] == "emulator-5554"
    assert updated["adb_bin"] == "/opt/adb"


def test_adb_command_is_device_scoped_only_when_a_serial_is_set():
    from remote_screen_app.android import adb
    assert adb({"device_serial": "emulator-5554", "adb_bin": "adb"}) == "adb -s emulator-5554"
    # Blank serial means "the only attached device" — adb picks it itself.
    assert adb({"device_serial": "", "adb_bin": "adb"}) == "adb"


@pytest.mark.parametrize("msg,expected_tail", [
    ({"type": "tap", "x": 10, "y": 20}, "tap 10 20"),
    ({"type": "swipe", "x1": 1, "y1": 2, "x2": 3, "y2": 4}, "swipe 1 2 3 4"),
    ({"type": "swipe", "x1": 1, "y1": 2, "x2": 3, "y2": 4, "duration_ms": 300},
     "swipe 1 2 3 4 300"),
    ({"type": "key", "code": "KEYCODE_HOME"}, "keyevent KEYCODE_HOME"),
])
def test_input_commands_build(msg, expected_tail):
    from remote_screen_app.android import build_input_command
    cmd = build_input_command({"device_serial": "s", "adb_bin": "adb"}, msg)
    assert cmd.endswith(expected_tail)


@pytest.mark.parametrize("msg", [
    {"type": "tap", "x": "NaN", "y": 2},
    {"type": "key", "code": "HOME; rm -rf /"},      # injection attempt
    {"type": "key", "code": "$(whoami)"},
    {"type": "text", "text": ""},
    {"type": "nope"},
])
def test_malformed_or_injecting_input_is_dropped(msg):
    """Returning None (not raising) keeps one garbage frame from killing a live
    session; rejecting odd keycodes matters because the value is interpolated
    into a command that runs on the remote machine."""
    from remote_screen_app.android import build_input_command
    assert build_input_command({"device_serial": "s", "adb_bin": "adb"}, msg) is None


def test_text_input_is_shell_quoted():
    from remote_screen_app.android import build_input_command
    cmd = build_input_command({"device_serial": "s", "adb_bin": "adb"},
                              {"type": "text", "text": "hi; rm -rf /"})
    assert "'hi; rm -rf /'" in cmd


def test_android_endpoints_reject_a_vnc_host(client):
    vnc = client.post("/hosts", json={"name": "mac", "host": "10.0.0.5", "port": 5900}).json()
    assert client.get(f"/hosts/{vnc['id']}/android/status").status_code == 400


def test_android_defaults_to_this_workspaces_exec_channel(store):
    """The monolith's remote-agent endpoint lives in ITS netns and is not
    reachable from aw-workspace, so defaulting a new host to it would make
    every android host fail with a confusing connection error."""
    row = store.create({"name": "pixel", "protocol": "android", "host": "hostid"})
    assert row["agent_kind"] == "aw_remote_host"


def test_legacy_remote_agent_channel_is_still_selectable(store):
    row = store.create({"name": "legacy", "protocol": "android", "host": "macbook-fred",
                        "agent_kind": "remote_agent",
                        "agent_base_url": "http://127.0.0.1:10005"})
    assert row["agent_kind"] == "remote_agent"
    assert row["agent_base_url"] == "http://127.0.0.1:10005"


def test_activate_never_reads_the_table():
    """Migrations run AFTER activate(), so on a first install the table has only
    its initial shape. Any SELECT naming a migration-added column fails there
    and takes the whole install down — which is exactly what happened on the
    real-Postgres install of 0.2.0. Pin it: activate() must not touch the data.
    """
    src = (Path(__file__).resolve().parent.parent
           / "remote_screen_app" / "plugin.py").read_text()
    activate = src.split("async def activate", 1)[1].split("async def ", 1)[0]
    # Strip comments — the fix's own comment names store.list() to explain why
    # it is gone, and matching that would make the test assert on prose.
    activate = "\n".join(ln.split("#")[0] for ln in activate.splitlines())
    for forbidden in ("store.list(", "store.get(", "store.credentials("):
        assert forbidden not in activate, f"activate() must not call {forbidden}"
