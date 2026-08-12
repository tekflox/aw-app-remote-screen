-- 0002 — per-host fields the Android protocol needs.
--
-- The monolith hard-coded all four of these as module constants in
-- src/api/routes/android_viewer.py (PROFILE_ID = "macbook-fred",
-- DEVICE_SERIAL = "emulator-5554", ADB_BIN, BACKEND_URL), which is why it could
-- only ever mirror one device on one machine. Here they are columns, so
-- "Android" is a protocol you can add N hosts of, exactly like VNC.
--
-- For an android row: `host` carries the remote-agent PROFILE ID (the machine
-- the device is attached to, e.g. "macbook-fred"), not a hostname — there is no
-- TCP endpoint to name. `port` is unused and stored as 0.
--
-- Unqualified on purpose: src/apps/migrations.py sets search_path to this
-- workspace's schema for the transaction.

ALTER TABLE "app__remote-screen__hosts"
    ADD COLUMN IF NOT EXISTS device_serial TEXT NOT NULL DEFAULT '';

ALTER TABLE "app__remote-screen__hosts"
    ADD COLUMN IF NOT EXISTS agent_base_url TEXT NOT NULL DEFAULT '';

ALTER TABLE "app__remote-screen__hosts"
    ADD COLUMN IF NOT EXISTS adb_bin TEXT NOT NULL DEFAULT '';

-- The 0001 unique index assumed every host has a real port; nothing to change
-- there, but android rows all share port 0, so make sure nothing downstream
-- assumes (host, port) is unique. Name stays the natural key.
