"""Entitlement gates — thin wrapper over the shared vectors (L09).

Everything reads the *cached* plan/status from SQLite: gating never touches
the network, so all checks work fully offline (rule R7).
"""

from __future__ import annotations

import sqlite3

from db.store import get_meta
from services.license_check import load_reference


def plan_of(conn: sqlite3.Connection) -> str:
    """Cached plan ('free' | 'pro'). Unknown values behave as free."""
    plan = (get_meta(conn).get("plan") or "free").strip()
    return plan if plan in ("free", "pro") else "free"


def is_locked(conn: sqlite3.Connection) -> bool:
    """True when the cached status means read-only (locked/suspended)."""
    return (get_meta(conn).get("cached_status") or "") in ("locked", "suspended")


def can(conn: sqlite3.Connection, feature: str) -> bool:
    """Gate `export` | `widget` | `core` from the cached plan."""
    return bool(load_reference().can_use_feature(plan_of(conn), feature))


def habit_limit_for(conn: sqlite3.Connection) -> int | None:
    """Max active habits for the cached plan. None = unlimited."""
    return load_reference().habit_limit(plan_of(conn))
