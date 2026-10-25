# Runbook — account operations (C05)

Covers the `docs/delete-account.md` item from plan.tmp (kept here because
`docs/` is git-ignored local-draft space; this file is the versioned record).

## Delete account (user request)

1. Verify the requester owns the address (login or email challenge).
2. Run, on Postgres/Supabase SQL editor (mock: `sqlite3 registry.db`):
   ```sql
   DELETE FROM users WHERE email = '<address>';  -- cascades devices/entitlements/heartbeats
   ```
3. Confirm zero rows remain:
   ```sql
   SELECT COUNT(*) FROM users WHERE email = '<address>';
   SELECT COUNT(*) FROM heartbeats WHERE user_id NOT IN (SELECT id FROM users);
   ```
4. Reply within 30 days (Privacy §5). Tell the user: local on-device data is
   theirs to delete (uninstall / clear app data); we never had it.

## Lock / unlock

```sql
UPDATE users SET status = 'suspended' WHERE email = '<address>';  -- read-only on next online check
UPDATE users SET status = 'active'    WHERE email = '<address>';
```

## Grant / revoke pro (until L10 webhooks)

```sql
UPDATE entitlements SET plan='pro', source='admin', updated_at=now()
WHERE user_id = (SELECT id FROM users WHERE email='<address>');
UPDATE users SET plan='pro' WHERE email='<address>';
```
