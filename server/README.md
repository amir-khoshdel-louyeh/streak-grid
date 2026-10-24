# Server — Phase 6 registry

Contract: `core/docs/LICENSING.md`. Migration: `migrations/001_phase6.sql`.

## Layout

- `migrations/001_phase6.sql` — Postgres DDL (deploy target: Supabase).
- `mock.py` — stdlib-only local mock of the `/v1` contract for client dev.
  Not for production.

## Mock: run + verify

```bash
python3 mock.py --port 8765 --db ./registry.db
```

Full flow (DoD of C02):

```bash
# signup → 201
curl -s -X POST localhost:8765/v1/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"u1@x.io","password":"pw123456","device_id":"11111111-1111-1111-1111-111111111111","platform":"linux","app_version":"0.0-test"}'
# → {"user_id":..., "access_jwt":..., "refresh_jwt":..., "plan":"free"}

# me → 200 active (use access_jwt from above)
curl -s localhost:8765/v1/me -H "Authorization: Bearer <access_jwt>"

# heartbeat → 204, records devices.last_seen
curl -s -o /dev/null -w '%{http_code}\n' -X POST localhost:8765/v1/heartbeat \
  -H 'Content-Type: application/json' -H "Authorization: Bearer <access_jwt>" \
  -d '{"device_id":"11111111-1111-1111-1111-111111111111","platform":"linux","app_version":"0.0-test"}'

# ban (admin = direct DB, same on Supabase SQL editor):
#   UPDATE users SET status='suspended' WHERE email='u1@x.io';
# me → 403 {"status":"suspended",...}  (client must lock, keep local data)
```

## Supabase deploy (production)

1. New project → SQL editor → paste `migrations/001_phase6.sql` → run.
2. Auth stays Supabase Auth; this registry mirrors `users` rows on
   signup webhook (or the FastAPI alt below). JWTs are Supabase-issued;
   clients verify with the project JWKS (C03 reference shows the checks).
3. Admin = Table editor / SQL editor (no custom panel in MVP).

## Admin SQL (works on Supabase too)

```sql
-- find user + devices
SELECT u.id, u.email, u.status, u.plan, d.device_id, d.platform, d.app_version, d.last_seen
FROM users u LEFT JOIN devices d ON d.user_id = u.id
WHERE u.email = 'u1@x.io';

-- lock / unlock (client enforces on next online /v1/me)
UPDATE users SET status = 'suspended' WHERE email = 'u1@x.io';
UPDATE users SET status = 'active'    WHERE email = 'u1@x.io';

-- grant pro (until payment webhooks land in L10)
UPDATE entitlements SET plan='pro', source='admin', updated_at=now()
WHERE user_id = (SELECT id FROM users WHERE email='u1@x.io');
UPDATE users SET plan='pro' WHERE email='u1@x.io';

-- delete account (C05 runbook points here)
DELETE FROM users WHERE email = 'u1@x.io';  -- cascades devices/entitlements/heartbeats
```

## Self-host alt (FastAPI)

Any framework is fine as long as it serves the frozen `/v1` paths with the
exact status codes + error shapes from `LICENSING.md §3` and passes the
same curl flow above. The mock is the reference behavior until then.
