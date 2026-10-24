# Licensing ports — REFERENCE (C03)

`reference.py` is the normative implementation; `vectors.json` is the
conformance suite. A port is done when it passes **every** vector case
with the same function names and edge semantics below.

## Functions to port (1:1)

```
parse_iso(s) -> moment | null        # UTC ISO-8601, '' / invalid -> null
is_in_grace(last_check, now, grace_days=30, skew_hours=24) -> bool
  - either unparsable -> false
  - last_check > now + skew -> false   # invalid cache, re-check when online
  - last_check > now -> true           # small skew / backwards clock
  - else (now - last_check) <= grace_days
effective_state(cached, last_check, now, server=null) -> state
  - server != null: 'active' iff server == 'active' else 'locked'
  - offline: 'locked'/'suspended' -> 'locked' (sticks)
  - offline: 'unactivated' -> 'unactivated'
  - offline: 'active'/'grace_expired' -> grace check
  - offline: anything else -> 'unactivated'
can_use_feature(plan, feature) -> bool
  - unknown feature -> false; unknown plan -> free row
habit_limit(plan) -> int | null
  - 'pro' -> null (unlimited); anything else -> 5
```

## Rules for ports

1. Pure logic only — no clock reads, no I/O inside these functions. The caller
   passes `now`; tests freeze it.
2. Never edit an existing vector expectation to make a port pass. Add a new
   case + bump `vectors.json:version` instead (via a C-scope).
3. Datetimes must be timezone-aware (UTC). Naive-local parsing is the classic
   cross-platform bug — the skew vectors catch it.
4. Suggested homes: C# `Core/Licensing/LicenseState.cs`, Kotlin
   `core/licensing/LicenseState.kt`, TS `core/licensing/license.ts`.
