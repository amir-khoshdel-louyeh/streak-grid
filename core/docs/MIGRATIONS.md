# MIGRATIONS — shared SQLite contract (C04)

Single DB (rule R1): every platform runs the **same ordered migrations**
against the same schema. Rule R2: additive only, versioned, never rewrite.

## Versions

| v | Content | File |
|---|---|---|
| 1 | Baseline: `folders/habits/completions/pauses/achievements` (+ `remind_at`, `sort_order` columns) | pre-Phase-6 `migrate()` |
| 2 | Phase 6: `schema_version` + `meta` + `entitlements_cache` | `core/licensing/migrate_v2.sql` |

## Runner contract (each platform implements this, same order)

1. Open DB. Auto-backup the file first (desktop) / journal mode (mobile).
2. `CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)`.
3. If `schema_version` is empty: the DB predates versioning → `INSERT (1, now)`.
   (v1 shape is detected by the pre-existing tables; never re-create them.)
4. `current = MAX(version)`. Apply every `migrate_vN.sql` with N > current,
   in order, each inside one transaction; after each, `INSERT (N, now)`.
5. `PRAGMA foreign_keys = ON` (or platform equivalent) for the session.

## Rules

- Migrations are append-only: fix a bad migration with vN+1, never edit vN
  after it ships. Changing shipped SQL requires a C-scope.
- SQL must be portable SQLite (no Postgres-isms): it runs under Python
  `sqlite3`, C# `Microsoft.Data.Sqlite`, Room, and wasm-sqlite unchanged.
- `meta` always holds exactly one row (`id = 1`); runners `INSERT OR IGNORE`
  the default `unactivated` row, never duplicate it.
- Test-case (DoD): a v1 DB with 1 habit + 1 completion migrates to v2 with
  habits/completions byte-identical and `meta` = `unactivated`, `last_check=''`.
