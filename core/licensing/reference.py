"""Phase 6 license logic — pure reference (C03).

No Qt, no network, no storage. Every platform port (C#/Kotlin/TS) must
reproduce these exact semantics; `vectors.json` is the conformance suite.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

GRACE_DAYS = 30
SKEW_HOURS = 24

FREE_HABIT_LIMIT = 5

_MATRIX: dict[str, dict[str, bool]] = {
    # feature: {plan: allowed} — mirrors LICENSING.md §6.
    "core": {"free": True, "pro": True},      # habits, streaks, heatmap, stats
    "export": {"free": False, "pro": True},   # CSV/PNG export
    "widget": {"free": False, "pro": True},   # desktop widget + tray actions
}


def _parse_iso(value: str) -> datetime | None:
    """Parse UTC ISO-8601 (`...Z` or offset). None on empty/invalid."""
    text = (value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def is_in_grace(last_check: str, now: str,
                grace_days: int = GRACE_DAYS,
                skew_hours: int = SKEW_HOURS) -> bool:
    """True when the cached check is fresh enough to count as active."""
    checked = _parse_iso(last_check)
    moment = _parse_iso(now)
    if checked is None or moment is None:
        return False
    if checked > moment + timedelta(hours=skew_hours):
        return False  # wildly future timestamp: cache is invalid, re-check
    if checked > moment:
        return True  # small skew / backwards clock: fail-open
    return moment - checked <= timedelta(days=grace_days)


def effective_state(cached: str, last_check: str, now: str,
                    server: str | None = None,
                    grace_days: int = GRACE_DAYS) -> str:
    """Offline-capable client state.

    `server`: result of a just-completed online `/v1/me` —
      None (offline), 'active', 'suspended', 'banned', 'revoked'.
    Returns: 'unactivated' | 'active' | 'grace_expired' | 'locked'.
    `grace_expired` and `unactivated`-limited are still usable offline.
    """
    if server is not None:
        return "active" if server == "active" else "locked"
    if cached in ("locked", "suspended"):
        return "locked"  # known-bad sticks while offline
    if cached == "unactivated":
        return "unactivated"
    if cached in ("active", "grace_expired"):
        return "active" if is_in_grace(last_check, now, grace_days) else "grace_expired"
    return "unactivated"  # unknown cached value: safe default


def can_use_feature(plan: str, feature: str) -> bool:
    """Gate a feature from the *cached* plan only. Unknown fails closed."""
    allowed = _MATRIX.get(feature)
    if allowed is None:
        return False
    return allowed.get(plan, allowed["free"])


def habit_limit(plan: str) -> int | None:
    """Max active habits for `plan`. None = unlimited. Unknown = free cap."""
    if plan == "pro":
        return None
    return FREE_HABIT_LIMIT
