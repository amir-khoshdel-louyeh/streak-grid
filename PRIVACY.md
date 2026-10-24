# Privacy Policy — StreakGrid (Phase 6, shared across Linux/Windows/Android/Web)

Effective: 2026-10-15 (v1). Contact: [SUPPORT-EMAIL — fill before public release].

## 1. What lives on your device only

Your habits, completions, notes, folders, pauses and stats never leave your
device in v1. There is no habit-content sync, and we cannot see it.

## 2. What the account needs (registry only)

To keep one free account per person and to enforce bans, the app sends:

- `email` (login identifier), `user_id`, `device_id` (random UUID per install),
  `platform` (linux/windows/android/web), `app_version`, `last_seen`.
- Plan status (`free`/`pro`) and entitlement source (signup/store/admin).

This is the full list. Contract: `core/docs/LICENSING.md §7`.

## 3. What we never collect

Habit names, completion values, notes, streaks, heatmaps, file paths,
contacts, or any other app content. Heartbeat payloads are fixed-shape;
unknown fields are rejected server-side.

## 4. Crash & usage telemetry (separate from auth, opt-out)

- Crash reports (Sentry or equivalent): stack traces + app version only.
- Usage counts (PostHog self-hosted or equivalent): e.g. "habit created",
  never with names/values.
- Both are OFF until you accept the consent screen, queued offline, and
  deletable via Settings → Privacy. Declining changes nothing about the app.

## 5. Your rights

Export your local data anytime (CSV/PNG, pro-gated export notwithstanding —
your data is always readable on-device). Request full registry deletion per
`server/RUNBOOK.md` (delete-account): we wipe `users/devices/entitlements/
heartbeats` rows and confirm within 30 days.

## 6. Shared consent wording (translate per UI, same meaning)

> "StreakGrid needs a free account (one-time online activation), then works
> fully offline. We store only your email, a random device ID, app version
> and last-seen time — never your habits. Details: Privacy Policy. [Accept]
> [Use limited offline mode]"
