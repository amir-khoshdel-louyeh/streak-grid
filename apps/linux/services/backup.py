"""Backup & restore — B1-1: full SQLite backup via online backup API."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

REQUIRED_TABLES = {"folders", "habits", "completions", "pauses", "achievements"}


def default_backup_path(out_dir: str | None = None) -> str:
    base = Path(out_dir) if out_dir else Path.home() / "Documents"
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return str(base / f"streakgrid-backup-{stamp}.db")


def backup_db(conn: sqlite3.Connection, dest_path: str) -> str:
    """Online backup of open DB (works for :memory: too). Returns dest path."""
    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
    target = sqlite3.connect(dest_path)
    try:
        conn.backup(target)
    finally:
        target.close()
    return dest_path


def is_valid_backup(path: str) -> bool:
    """A file is restorable if it's SQLite with our 5 tables."""
    try:
        probe = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        tables = {r[0] for r in probe.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        return REQUIRED_TABLES <= tables
    except sqlite3.DatabaseError:
        return False
    finally:
        probe.close()


def restore_db_file(backup_path: str, db_path: str) -> str:
    """Replace live DB file with a validated backup. Returns db path."""
    if not is_valid_backup(backup_path):
        raise ValueError("not a StreakGrid backup file")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_path, db_path)
    return db_path
