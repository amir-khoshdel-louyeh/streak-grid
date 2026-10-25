# Shared spec — StreakGrid v0.1 (frozen for Linux S02)

> Parity target: HabitForge Tactical (https://www.tryhabitforge.com).
> Stack Linux: Python 3.11+ + PySide6 (Qt6) + SQLite.
> DB path Linux: `~/.local/share/streakgrid/streakgrid.db` (tests: `:memory:`).
> Dates: TEXT `YYYY-MM-DD` (local day, no timezone shift). `updated_at`: UTC ISO-8601.

## 1. SQLite schema (v0.1 frozen)

```sql
CREATE TABLE folders(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  color TEXT NOT NULL DEFAULT '#888888',
  sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE habits(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  type TEXT NOT NULL CHECK(type IN ('yes_no','counter','dont_do')),
  target_count INTEGER NOT NULL DEFAULT 1,
  schedule_type TEXT NOT NULL CHECK(schedule_type IN
    ('daily','weekly_days','interval','times_per_week','times_per_month')),
  schedule_json TEXT NOT NULL DEFAULT '{}',
  start_date TEXT NOT NULL,
  created_at TEXT NOT NULL,
  archived INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE completions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
  date TEXT NOT NULL,
  value INTEGER NOT NULL DEFAULT 1,
  note TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  UNIQUE(habit_id, date)
);

CREATE TABLE pauses(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT ''
);

CREATE TABLE achievements(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  unlocked_at TEXT
);
```

`schedule_json` examples:
- `daily`: `{}`
- `weekly_days`: `{"days":[1,3,5]}` (Mon=1..Sun=7, ISO)
- `interval`: `{"every_n_days":3}` (anchored at `start_date`)
- `times_per_week`: `{"times":3}` (Mon-Sun window)
- `times_per_month`: `{"times":10}` (calendar month window)

## 2. Scheduling — `is_due(habit, date) -> bool`

- `daily`: due every day `>= start_date`.
- `weekly_days`: due iff `date.isoweekday() in days` and `date >= start_date`.
- `interval`: due iff `(date - start_date).days % every_n_days == 0`.
- `times_per_week`: flexible goal — every day is due (user must hit `times` completions Mon-Sun).
  `next_due` = today if weekly count < times else next Monday.
- `times_per_month`: same idea on calendar-month window.
- `archived=1` habits are never due. Dates before `start_date` are never due.

## 3. Completion semantics + streaks (schedule-aware, pause-safe)

Done predicate `is_done(habit, date, value)`:
- `yes_no`: `value >= 1`
- `counter`: `value >= target_count`
- `dont_do`: done iff NO row for that date (clean day). Any row with `value >= 1` = slip = fail.

Pause: date `d` is paused for habit iff exists `pauses` row with `start_date <= d <= end_date`.

Streak walk (backwards from end date, default today):
1. Skip dates `< start_date`, `archived` ignored at query level.
2. Skip unscheduled dates (per §2, except flexible types where every day counts).
3. Skip paused dates — neither break nor build streak.
4. If done -> `streak += 1`, continue back.
5. If not done and date is due + not paused:
   - if date == today and today not yet done -> skip today (streak still alive), keep walking.
   - else -> break.
6. `dont_do`: slip breaks; clean counts.

`current_streak`, `best_streak` (max run over full history), `completion_rate(days)` =
`done_due_days / total_due_days` over window, paused days excluded from denominator.

Retroactive edit: any insert/update/delete in `completions` or `pauses` requires full
recompute for that habit (no cached streaks in v0.1).

## 4. Heatmap (rolling 1-year, GitHub-style)

- `build_matrix(completions_by_date, end_date, days=365) -> 53 cols x 7 rows`.
- Cols = weeks (oldest left), rows = Mon..Sun (row 0 = Monday).
- Intensity 0-4 from `value/target`:
  - `0`: no completion
  - `1`: `0 < ratio < 0.33`
  - `2`: `0.33 <= ratio < 0.66`
  - `3`: `0.66 <= ratio < 1.0`
  - `4`: `ratio >= 1.0`
- `yes_no`/`dont_do`: ratio is 0 or 1. `dont_do` clean day = 4, slip = 0 with red tint in UI.
- Future dates and pre-`start_date` cells are dimmed/empty, excluded from export stats.

## 5. Achievements (8, frozen codes)

| code | name | unlock rule |
|---|---|---|
| `first_step` | First Step | >=1 completion |
| `week_warrior` | Week Warrior | any `current_streak >= 7` |
| `triplet` | Triplet | >=3 active (non-archived) habits each done at least once in last 7d |
| `perfect_day` | Perfect Day | all due habits done on same day |
| `month_master` | Month Master | any `current_streak >= 30` |
| `day66` | 66 Days | any `current_streak >= 66` (UCL habit-formation ref) |
| `half_century` | Half Century | any `current_streak >= 50` |
| `century_club` | Century Club | any `current_streak >= 100` |

`achievements(code)` row created on unlock with `unlocked_at` UTC; never auto-relocked.

## 6. Stats (v0.1 definitions)

- `completion_rate(30/90/all)`: per §3 over rolling windows.
- `best_streak(habit)`, `perfect_days` (count all-due-done days in window),
  `strength_score` = weighted mean of last-30d completion (weight 1.0 today -> 0.3 day-30).
- Weekly chart: per-weekday completion % over last 12 weeks (best/worst weekday).

## 7. Linux non-goals v1

No AI, no HealthKit equiv. X11 + Wayland supported;
widget falls back to tray menu if compositor denies always-on-top.
(Account/registry moved to Phase 6, §8 — habit content itself is still
on-device only.)

## 8. Phase 6 — shared account tables (single DB, all platforms)

`SPEC.md` is the sole schema source (rule R1). These tables are identical on
Linux, Windows, Android and future Web. Changes are additive + versioned
(rule R2, see `MIGRATIONS.md`). Tokens never live here — only cached status.

```sql
CREATE TABLE schema_version(
  version INTEGER NOT NULL PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE meta(
  id INTEGER PRIMARY KEY CHECK(id = 1),  -- single row
  user_id TEXT NOT NULL DEFAULT '',      -- server UUID, '' = unactivated
  device_id TEXT NOT NULL DEFAULT '',    -- client UUID, generated once
  platform TEXT NOT NULL DEFAULT '',     -- linux | windows | android | web
  app_version TEXT NOT NULL DEFAULT '',
  cached_status TEXT NOT NULL DEFAULT 'unactivated'
    CHECK(cached_status IN
      ('unactivated','active','grace_expired','locked','suspended')),
  plan TEXT NOT NULL DEFAULT 'free' CHECK(plan IN ('free','pro')),
  last_check TEXT NOT NULL DEFAULT ''    -- UTC ISO-8601 of last /v1/me, '' = never
);

CREATE TABLE entitlements_cache(
  user_id TEXT NOT NULL DEFAULT '' UNIQUE,
  plan TEXT NOT NULL DEFAULT 'free' CHECK(plan IN ('free','pro')),
  expires_at TEXT,                       -- UTC ISO-8601, NULL = no expiry
  source TEXT NOT NULL DEFAULT 'signup',
  updated_at TEXT NOT NULL DEFAULT ''
);
```

Notes:
- Fresh/v1 DBs: `meta` holds one default row (`unactivated`); `last_check=''`.
- Pre-Phase-6 DBs migrate without data loss (C04 test-case); habits,
  completions, folders, pauses, achievements are untouched by this delta.
- `device_id` is generated once (UUID4) and never rotated — future sync/web
  reuse it without re-activation (rule R3).
