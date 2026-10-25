-- migrate_v2.sql — Phase 6 shared migration (C04).
-- Runs UNCHANGED on Python sqlite3, C# Sqlite, Room, wasm-sqlite.
-- Idempotent: safe to re-run. Records version 2 in schema_version.

CREATE TABLE IF NOT EXISTS schema_version(
  version INTEGER NOT NULL PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta(
  id INTEGER PRIMARY KEY CHECK(id = 1),
  user_id TEXT NOT NULL DEFAULT '',
  device_id TEXT NOT NULL DEFAULT '',
  platform TEXT NOT NULL DEFAULT '',
  app_version TEXT NOT NULL DEFAULT '',
  cached_status TEXT NOT NULL DEFAULT 'unactivated'
    CHECK(cached_status IN
      ('unactivated','active','grace_expired','locked','suspended')),
  plan TEXT NOT NULL DEFAULT 'free' CHECK(plan IN ('free','pro')),
  last_check TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS entitlements_cache(
  user_id TEXT NOT NULL DEFAULT '' UNIQUE,
  plan TEXT NOT NULL DEFAULT 'free' CHECK(plan IN ('free','pro')),
  expires_at TEXT,
  source TEXT NOT NULL DEFAULT 'signup',
  updated_at TEXT NOT NULL DEFAULT ''
);

INSERT OR IGNORE INTO meta(id) VALUES(1);
INSERT OR IGNORE INTO schema_version(version, applied_at)
  VALUES(2, strftime('%Y-%m-%dT%H:%M:%SZ','now'));
