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

from rdp_vnc_app.__main__ import _SqliteCtx  # noqa: E402
from rdp_vnc_app.routes import build_routes  # noqa: E402
from rdp_vnc_app.store import HostError, HostNotFound, HostStore  # noqa: E402


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr("rdp_vnc_app.__main__.DATA_DIR", tmp_path)
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
    res = client.get("/ui/hosts")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    body = res.text
    assert "/api/apps/rdp-vnc" in body       # talks to this app's own routes
    assert "<script" in body and "src=" not in body.split("<script")[1][:200]
    # No unrendered \u escapes leaking into markup (they're only valid in JS).
    head = body.split("<script")[0]
    assert "\\u" not in head
