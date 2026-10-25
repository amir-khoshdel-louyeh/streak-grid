"""Identity — device_id + token storage (L06, Phase 6).

No Qt, no network: safe to use from the main thread at startup.
Token backend order: `keyring` (libsecret on GNOME) when importable,
otherwise a 0600 JSON file. Load tries keyring first, then the file;
clear wipes both. Worst case of a backend hiccup is a re-login —
tokens are a cache of server truth, never the data itself.
"""

from __future__ import annotations

import json
import os
import sqlite3
import stat
import tempfile
import uuid
from pathlib import Path

SERVICE_NAME = "StreakGrid"
APP_VERSION = "0.2.0-dev"
_ACCESS_KEY = "access_jwt"
_REFRESH_KEY = "refresh_jwt"
_EMAIL_KEY = "account_email"


def _have_keyring() -> bool:
    try:
        import keyring  # noqa: F401

        return True
    except ImportError:
        return False


def _secret_file() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / "streakgrid" / "secrets.json"


def _read_secret_file() -> dict:
    path = _secret_file()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_secret_file(data: dict) -> None:
    path = _secret_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".secrets-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def save_tokens(access_jwt: str, refresh_jwt: str, email: str = "") -> None:
    """Persist tokens (+login email for display) to the preferred backend."""
    saved = False
    if _have_keyring():
        try:
            import keyring

            keyring.set_password(SERVICE_NAME, _ACCESS_KEY, access_jwt)
            keyring.set_password(SERVICE_NAME, _REFRESH_KEY, refresh_jwt)
            keyring.set_password(SERVICE_NAME, _EMAIL_KEY, email)
            saved = True
        except Exception:
            saved = False
    if not saved:
        data = _read_secret_file()
        data[_ACCESS_KEY] = access_jwt
        data[_REFRESH_KEY] = refresh_jwt
        data[_EMAIL_KEY] = email
        _write_secret_file(data)


def load_tokens() -> tuple[str | None, str | None, str]:
    """Return (access, refresh, email); missing sides are None/''."""
    access: str | None = None
    refresh: str | None = None
    email = ""
    if _have_keyring():
        try:
            import keyring

            access = keyring.get_password(SERVICE_NAME, _ACCESS_KEY)
            refresh = keyring.get_password(SERVICE_NAME, _REFRESH_KEY)
            email = keyring.get_password(SERVICE_NAME, _EMAIL_KEY) or ""
        except Exception:
            access, refresh, email = None, None, ""
    if not access and not refresh and not email:
        data = _read_secret_file()
        access = data.get(_ACCESS_KEY)
        refresh = data.get(_REFRESH_KEY)
        email = data.get(_EMAIL_KEY) or ""
    return access, refresh, email


def clear_tokens() -> None:
    if _have_keyring():
        try:
            import keyring

            for key in (_ACCESS_KEY, _REFRESH_KEY, _EMAIL_KEY):
                try:
                    keyring.delete_password(SERVICE_NAME, key)
                except Exception:
                    pass
        except Exception:
            pass
    data = _read_secret_file()
    for key in (_ACCESS_KEY, _REFRESH_KEY, _EMAIL_KEY):
        data.pop(key, None)
    _write_secret_file(data)


def get_device_id(conn: sqlite3.Connection) -> str:
    """Stable per-install UUID (rule R3). Generated once, stored in meta."""
    from db.store import get_meta, set_meta

    device_id = (get_meta(conn).get("device_id") or "").strip()
    if not device_id:
        device_id = str(uuid.uuid4())
        set_meta(conn, device_id=device_id)
    return device_id


def ensure_identity(conn: sqlite3.Connection, *, platform: str, app_version: str) -> str:
    """Fill device_id/platform/app_version blanks. Returns device_id."""
    from db.store import get_meta, set_meta

    meta = get_meta(conn)
    patch: dict[str, str] = {}
    device_id = (meta.get("device_id") or "").strip()
    if not device_id:
        device_id = str(uuid.uuid4())
        patch["device_id"] = device_id
    if not (meta.get("platform") or "").strip() and platform:
        patch["platform"] = platform
    if not (meta.get("app_version") or "").strip() and app_version:
        patch["app_version"] = app_version
    if patch:
        set_meta(conn, **patch)
    return device_id
