"""Background license check (L08, Phase 6).

Rule: network runs in a worker thread; SQLite/SecureStore writes stay on
the UI thread. `check_once` never raises — any failure is `offline`
(fail-open). The caller applies the result via `apply_result`.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from services.registry import (
    RegistryError,
    heartbeat,
    logout,
    me,
    refresh,
)

# outcome: ok | locked | offline
# ok:     {outcome, me, access?, refresh?} (tokens only when rotated)
# locked: {outcome, code}                  (suspended|banned|revoked)
# offline:{outcome}

_reference = None


def load_reference():
    """Load core/licensing/reference.py (single source, rule R5).

    Imported by path (not `import core...`) because `apps/linux/core`
    owns the bare `core` package name on sys.path.
    """
    global _reference
    if _reference is None:
        import importlib.util
        from pathlib import Path

        # services -> linux -> apps -> repo root.
        path = Path(__file__).resolve().parents[3] / "core" / "licensing" / "reference.py"
        if not path.is_file():
            raise RuntimeError(f"shared license reference missing: {path}")
        spec = importlib.util.spec_from_file_location(
            "streakgrid_license_reference", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _reference = module
    return _reference


def check_once(base: str, *, access: str, refresh_jwt: str | None,
               device_id: str, platform: str, app_version: str) -> dict:
    """One /me (+heartbeat) round-trip. Never raises."""
    try:
        profile = me(base, access_jwt=access)
    except RegistryError as exc:
        if exc.code == "revoked" and refresh_jwt:
            return _try_refresh(base, refresh_jwt, device_id, platform, app_version)
        if exc.code in ("suspended", "banned", "revoked"):
            return {"outcome": "locked", "code": exc.code}
        return {"outcome": "offline"}
    try:
        heartbeat(base, access_jwt=access, device_id=device_id,
                  platform=platform, app_version=app_version)
    except RegistryError:
        pass  # /me already succeeded: heartbeat is best-effort only
    return {"outcome": "ok", "me": profile}


def _try_refresh(base: str, refresh_jwt: str, device_id: str,
                 platform: str, app_version: str) -> dict:
    try:
        pair = refresh(base, refresh_jwt=refresh_jwt, device_id=device_id)
    except RegistryError as exc:
        if exc.code in ("suspended", "banned", "revoked"):
            return {"outcome": "locked", "code": exc.code}
        return {"outcome": "offline"}
    try:
        profile = me(base, access_jwt=pair["access_jwt"])
    except RegistryError as exc:
        if exc.code in ("suspended", "banned", "revoked"):
            return {"outcome": "locked", "code": exc.code}
        return {"outcome": "offline"}
    try:
        heartbeat(base, access_jwt=pair["access_jwt"], device_id=device_id,
                  platform=platform, app_version=app_version)
    except RegistryError:
        pass
    return {"outcome": "ok", "me": profile,
            "access": pair["access_jwt"], "refresh": pair["refresh_jwt"]}


def apply_result(conn, result: dict, *, email: str = "") -> None:
    """UI-thread side: persist check outcome to meta/SecureStore/entitlements."""
    from datetime import datetime, timezone

    from db.store import get_meta, set_meta
    from services import identity

    if result["outcome"] == "offline":
        return
    if result["outcome"] == "locked":
        identity.clear_tokens()
        set_meta(conn, user_id="", cached_status="locked",
                 plan=get_meta(conn).get("plan") or "free", last_check="")
        return
    profile = result["me"]
    if result.get("access"):
        identity.save_tokens(result["access"], result.get("refresh") or "", email)
    ent = profile.get("entitlements") or {}
    conn.execute(
        """INSERT INTO entitlements_cache(user_id, plan, expires_at, source, updated_at)
           VALUES(?,?,?,?,?)
           ON CONFLICT(user_id) DO UPDATE SET plan=excluded.plan,
             expires_at=excluded.expires_at, source=excluded.source,
             updated_at=excluded.updated_at""",
        (profile.get("user_id") or "", ent.get("plan") or profile.get("plan") or "free",
         ent.get("expires_at"), "registry",
         datetime.now(timezone.utc).isoformat()),
    )
    set_meta(conn, user_id=profile.get("user_id") or "", cached_status="active",
             plan=ent.get("plan") or profile.get("plan") or "free",
             last_check=datetime.now(timezone.utc).isoformat())
    conn.commit()


class LicenseCheckThread(QThread):
    """Worker: runs check_once off the UI thread. Emits `done` with result."""

    done = Signal(dict)

    def __init__(self, base: str, *, access: str, refresh_jwt: str | None,
                 device_id: str, platform: str, app_version: str,
                 parent=None) -> None:
        super().__init__(parent)
        self._args = (base, {"access": access, "refresh_jwt": refresh_jwt,
                             "device_id": device_id, "platform": platform,
                             "app_version": app_version})

    def run(self) -> None:  # noqa: N802 (Qt naming)
        base, kwargs = self._args
        self.done.emit(check_once(base, **kwargs))


def logout_everywhere(base: str, access: str | None) -> None:
    """Best-effort server logout; local state is cleared by the caller."""
    if not access:
        return
    try:
        logout(base, access_jwt=access)
    except RegistryError:
        pass
