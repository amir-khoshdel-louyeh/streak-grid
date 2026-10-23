# LICENSING — StreakGrid Phase 6 contract (frozen for C01)

> Cross-platform account + offline-first license. Single DB spec lives in
> `SPEC.md`; migrations in `MIGRATIONS.md`. This file is the API + behavior
> contract for Linux, Windows, Android and future Web. Backend-agnostic
> (default: Supabase Auth + Postgres; alt: self-hosted FastAPI).
> Rule: no platform changes this contract — change only via a new C-scope.

## 1. Model

One-time free activation, then offline with grace. Pro features via entitlement.

- `user_id`: server UUID, stable forever (future sync/web reuse, no re-activation).
- `device_id`: client UUID, generated once per install, never rotated.
- `platform`: `linux | windows | android | web` (open enum — new values are
  additive, old clients ignore unknown values, never crash).
- Server is a **registry only** (users/devices/entitlements/heartbeats).
  Habit content stays on-device in v1; it is never uploaded.

## 2. Server tables (Postgres)

```sql
users(id UUID PK, email TEXT UNIQUE NOT NULL,
      created_at TIMESTAMPTZ NOT NULL,
      status TEXT NOT NULL DEFAULT 'active'
        CHECK(status IN ('active','suspended','banned')),
      plan TEXT NOT NULL DEFAULT 'free'
        CHECK(plan IN ('free','pro')));
devices(user_id UUID REFERENCES users(id) ON DELETE CASCADE,
        device_id UUID NOT NULL,
        platform TEXT NOT NULL,
        app_version TEXT NOT NULL DEFAULT '',
        last_seen TIMESTAMPTZ,
        PRIMARY KEY(user_id, device_id));
entitlements(user_id UUID REFERENCES users(id) ON DELETE CASCADE,
             plan TEXT NOT NULL CHECK(plan IN ('free','pro')),
             expires_at TIMESTAMPTZ,          -- NULL = no expiry (free, lifetime pro)
             source TEXT NOT NULL DEFAULT 'signup',  -- signup | stripe | lemonsqueezy | admin
             updated_at TIMESTAMPTZ NOT NULL,
             PRIMARY KEY(user_id));
heartbeats(user_id UUID, device_id UUID, app_version TEXT,
           platform TEXT, seen_at TIMESTAMPTZ NOT NULL);
-- heartbeats is append-mostly; roll up into devices.last_seen.
```

## 3. API v1 (prefix `/v1` — breaking change = new version)

Auth: `Authorization: Bearer <access_jwt>` (standard JWT). Signup/login use
PKCE-ready flow so browsers can reuse them unchanged. CORS enabled from day 1.

| Method | Path | Body | Success |
|---|---|---|---|
| POST | `/v1/signup` | `{email, password, device_id, platform, app_version}` | `201 {user_id, access_jwt, refresh_jwt, plan}` |
| POST | `/v1/login` | `{email, password, device_id, platform, app_version}` | `200 {user_id, access_jwt, refresh_jwt, plan}` |
| POST | `/v1/refresh` | `{refresh_jwt, device_id}` | `200 {access_jwt, refresh_jwt}` |
| POST | `/v1/logout` | `{refresh_jwt}` | `204` (revoke refresh) |
| GET | `/v1/me` | — | `200 {user_id, email, status, plan, entitlements:{plan, expires_at}}` |
| POST | `/v1/heartbeat` | `{device_id, platform, app_version}` | `204` (updates `devices.last_seen`) |
| POST | `/v1/account/delete` | — (auth) | `202` (async wipe; runbook in C05) |

Errors: `401 {code:"revoked"}` (refresh/access revoked → client clears tokens),
`403 {code:"suspended"|"banned", reason}` (client locks, keeps local data),
`429` rate-limit, `5xx` → client treats as offline (fail-open).

Payment webhooks (stub in L10, contract now):
`POST /v1/webhooks/stripe|lemonsqueezy` → upsert `entitlements`.

## 4. Client states (computed offline from cache — see C03 vectors)

```
unactivated --(signup/login ok)--> active --(offline, last_check fresh)--> active
active --(offline > grace)--> grace_expired (banner, still usable)
any --(/me says suspended|banned | 401 revoked)--> locked (read-only + reason + support button)
locked --(logout / fresh login)--> active | unactivated
```

- `grace_days = 30` default. `last_check` = last successful `/v1/me`.
  Clock skew tolerance ±24h (vectors in C03).
- **Fail-open:** any network error/timeout (>5s) = stay in current state,
  never block UI, silent retry later (platform scheduler).
- Unactivated device: limited mode (decision: max 1 habit, read-only past
  data kept) + prominent Activate button. No blocking modal while offline.
- Lock applies **only after an online** `/me` says so (by design — offline
  lock is impossible offline). Local data is never deleted on lock.

## 5. Local cache (same tables on every platform — DDL in SPEC §8)

`meta(user_id, device_id, platform, app_version, cached_status, plan, last_check)`
`entitlements_cache(plan, expires_at, source, updated_at)`
Tokens live in the platform SecureStore (keyring / DPAPI / Keystore /
httpOnly cookie+IndexedDB on web) — **never plain-text in SQLite**.

## 6. free/pro matrix (v1 proposal — changeable only via SPEC amendment)

| Feature | free | pro |
|---|---|---|
| Active habits | ≤ 5 | unlimited |
| History, streaks, heatmap, stats | ✓ | ✓ |
| CSV/PNG export | — | ✓ |
| Desktop widget / tray quick actions | — | ✓ |
| Devices per user | 2 | unlimited |

Gating reads **cached** `plan` only — never network at point of use.

## 7. Heartbeat payload (privacy-minimal — full text in C05)

`{user_id, device_id, platform, app_version, seen_at}`. No habit names,
no completions, no notes — ever.

## 8. Web readiness (B00 checklist source)

- PKCE + CORS + standard JWT: reusable from browsers unchanged.
- Web SecureStore = httpOnly cookie (refresh) + IndexedDB cache (status/plan).
  Tokens in `localStorage` are forbidden.
- Web local DB (wasm-sqlite/IndexedDB) uses the same SPEC schema.

## 9. Versioning

- `/v1` frozen once C02 ships. Breaking change → `/v2` + 6-month overlap.
- `vectors.json` (C03) frozen with this file; new behavior = new vector case.
