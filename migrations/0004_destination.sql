-- 0004 — Destination = custom address vs. a linked remote host.
--
-- Until now a host's `host`/`port` always meant "dial this address FROM the
-- workspace container" — fine for a LAN box, useless for a mesh IP the
-- container has no route to (the problem that motivated this card). A linked
-- aw-remote-host already holds an outbound /link WebSocket open, and
-- aw-backend's existing tcp_bridge relay can dial on its behalf — the same
-- mechanism aw-app-tunnel already ships for its own tunnels.
--
--   dest_kind       'custom'       dial host/port directly, from here (unchanged default)
--                   'remote_host'  ask the linked host at remote_host_id to dial
--                                  host/port FROM ITS OWN network
--   remote_host_id  which linked host, when dest_kind='remote_host'; '' otherwise
--
-- Default is 'custom': every existing row keeps working exactly as before.

ALTER TABLE "app__remote-screen__hosts"
    ADD COLUMN IF NOT EXISTS dest_kind TEXT NOT NULL DEFAULT 'custom';

ALTER TABLE "app__remote-screen__hosts"
    ADD COLUMN IF NOT EXISTS remote_host_id TEXT NOT NULL DEFAULT '';
