-- 0003 — how an android host's exec channel is reached.
--
-- The monolith's android_viewer.py talked to a "remote-agent" backend at
-- http://127.0.0.1:10005 inside ITS OWN netns. aw-workspace has no such thing:
-- its path to a linked machine is aw-backend's
-- POST /api/workspaces/{slug}/remote-hosts/{host_id}/exec over the /link
-- WebSocket the host already holds open.
--
-- So the exec channel is a per-host choice, not a constant:
--   remote_agent    legacy monolith path (agent_base_url + host as profile id)
--   aw_remote_host  this workspace's own path (host = the linked host id)
--
-- Default is aw_remote_host: a host added in THIS workspace almost never wants
-- the monolith's endpoint, and defaulting to the unreachable one would make
-- every new android host fail with a confusing connection error.

ALTER TABLE "app__remote-screen__hosts"
    ADD COLUMN IF NOT EXISTS agent_kind TEXT NOT NULL DEFAULT 'aw_remote_host';
