-- 0001 — uniqueness + lookup indexes for the hosts table.
--
-- Deliberately NOT folded into store.py's TABLE_COLUMNS_SQL: ctx.db.create()
-- takes a single column list and runs CREATE TABLE IF NOT EXISTS, so on an
-- install that already has the table (every update) a changed column list is
-- silently ignored. Index/constraint changes therefore belong here, where the
-- runtime guarantees exactly-once application per (app_id, filename).
--
-- Unqualified on purpose — src/apps/migrations.py sets search_path to this
-- workspace's schema for the transaction, so the same file is correct in every
-- tenant. Do not hard-code a schema name here.

-- upsert_by_name() treats the name as the human's natural key; enforce that in
-- the DB too, so two rows can never disagree about which machine "office-mac"
-- means (the monolith's JSON list happily allowed duplicates).
CREATE UNIQUE INDEX IF NOT EXISTS "app__remote-screen__hosts_name_lower_key"
    ON "app__remote-screen__hosts" (lower(name));

-- list() orders by (sort_order, lower(name)) on every settings-panel render.
CREATE INDEX IF NOT EXISTS "app__remote-screen__hosts_order_idx"
    ON "app__remote-screen__hosts" (sort_order, lower(name));
