"""One-shot import of the monolith's saved VNC connections into this app.

Reads ``<monolith>/src/config/remote_desktop.json`` — the flat
``{"connections": [{id, name, host, port, password}]}`` list this app
replaces — decrypts each password with the monolith's OWN
``src.api.secrets_crypto`` key (the same key that file was written with), and
POSTs the result to this app's ``/hosts/upsert``, which writes the row to
``app__remote-screen__hosts`` and the password to the workspace secret store.

Upsert-by-name makes it re-runnable: importing twice updates the same hosts
instead of duplicating them.

    python scripts/import_from_monolith.py \\
        --monolith /opt/aw-workspace/repos/agentic-workspace \\
        --api http://127.0.0.1:9030 \\
        --api-key "$AW_WORKSPACE_API_KEY"

``--dry-run`` prints what would be imported (never the passwords) and exits.

If the monolith's crypto key isn't importable from here (different container,
key not mounted), the password simply comes through empty and the host is
still imported — re-enter it once in Settings › Remote Desktop. That is a
better outcome than refusing to migrate the inventory at all.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def load_connections(monolith: Path) -> list[dict]:
    config = monolith / "src" / "config" / "remote_desktop.json"
    if not config.exists():
        raise SystemExit(f"no monolith config at {config}")
    return json.loads(config.read_text()).get("connections", [])


def make_decryptor(monolith: Path):
    """Return a ``ciphertext -> plaintext`` callable, or one that yields ""
    when the monolith's crypto module can't be imported from this process."""
    sys.path.insert(0, str(monolith))
    try:
        from src.api.secrets_crypto import decrypt  # type: ignore
    except Exception as e:  # noqa: BLE001 — any import/key failure is the same outcome
        print(f"WARN: monolith secrets_crypto unavailable ({e}); "
              "hosts will import WITHOUT passwords.", file=sys.stderr)
        return lambda _blob: ""

    def _decrypt(blob: str) -> str:
        if not blob:
            return ""
        try:
            return decrypt(blob)
        except Exception:
            # Key rotated or ciphertext corrupted — same handling the monolith
            # itself used: behave as "no password saved".
            return ""
    return _decrypt


def post(api: str, api_key: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"{api.rstrip('/')}/api/apps/remote-screen/hosts/upsert",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-Api-Key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.loads(res.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{body['name']}: HTTP {e.code} {e.read().decode()[:300]}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--monolith", default="/opt/aw-workspace/repos/agentic-workspace",
                    type=Path)
    ap.add_argument("--api", default=os.environ.get("AW_WORKSPACE_API",
                                                    "http://127.0.0.1:9030"))
    ap.add_argument("--api-key", default=os.environ.get("AW_WORKSPACE_API_KEY", ""))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    connections = load_connections(args.monolith)
    if not connections:
        print("nothing to import — monolith config has no connections")
        return
    decrypt = make_decryptor(args.monolith)

    for i, conn in enumerate(connections):
        body = {
            "name": conn["name"],
            "protocol": "vnc",       # the monolith only ever did VNC
            "host": conn["host"],
            "port": int(conn["port"]),
            "sort_order": i,
        }
        password = decrypt(conn.get("password") or "")
        if password:
            body["password"] = password
        if args.dry_run:
            print(f"would import {body['name']} → {body['host']}:{body['port']} "
                  f"(password: {'yes' if password else 'no'})")
            continue
        if not args.api_key:
            raise SystemExit("--api-key (or AW_WORKSPACE_API_KEY) is required "
                             "unless --dry-run")
        row = post(args.api, args.api_key, body)
        print(f"imported {row['name']} → {row['host']}:{row['port']} "
              f"(password: {'yes' if row['has_password'] else 'no'})")


if __name__ == "__main__":
    main()
