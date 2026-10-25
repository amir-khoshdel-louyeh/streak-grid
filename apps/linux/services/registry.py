"""Registry client — /v1 per core/docs/LICENSING.md §3 (L07).

Stdlib only (`urllib`), no Qt: usable from dialogs and background workers.
Every call has a short timeout and raises RegistryError; network failures
surface as code "offline" so callers can fail open (never block the app).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

TIMEOUT = 5  # seconds — a slow network must never freeze the UI for long
DEFAULT_BASE_URL = "https://registry.streakgrid.app"


def base_url() -> str:
    """Deployment override: STREAKGRID_REGISTRY_URL (dev: mock on localhost)."""
    return os.environ.get("STREAKGRID_REGISTRY_URL", DEFAULT_BASE_URL).rstrip("/")


class RegistryError(Exception):
    """code: offline | bad_credentials | email_taken | revoked |
    suspended | banned | bad_request | server_error | ..."""

    def __init__(self, code: str, message: str = "", http: int | None = None) -> None:
        super().__init__(message or code)
        self.code = code
        self.http = http


def _call(method: str, url: str, body: dict | None = None,
          token: str | None = None) -> tuple[int, dict]:
    data = json.dumps(body or {}).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, data=data,
                                 headers={"Content-Type": "application/json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode() or "{}"
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode() or "{}")
        except ValueError:
            payload = {}
        code = str(payload.get("code") or f"http_{exc.code}")
        raise RegistryError(code, http=exc.code)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise RegistryError("offline", str(exc))


def signup(base: str, *, email: str, password: str, device_id: str,
           platform: str, app_version: str) -> dict:
    _, payload = _call("POST", f"{base}/v1/signup", {
        "email": email, "password": password, "device_id": device_id,
        "platform": platform, "app_version": app_version})
    return payload


def login(base: str, *, email: str, password: str, device_id: str,
          platform: str, app_version: str) -> dict:
    _, payload = _call("POST", f"{base}/v1/login", {
        "email": email, "password": password, "device_id": device_id,
        "platform": platform, "app_version": app_version})
    return payload


def refresh(base: str, *, refresh_jwt: str, device_id: str) -> dict:
    _, payload = _call("POST", f"{base}/v1/refresh",
                       {"refresh_jwt": refresh_jwt, "device_id": device_id})
    return payload


def logout(base: str, *, access_jwt: str) -> None:
    _call("POST", f"{base}/v1/logout", {}, token=access_jwt)


def me(base: str, *, access_jwt: str) -> dict:
    """Raises RegistryError(suspended|banned) with http=403, (revoked) 401."""
    _, payload = _call("GET", f"{base}/v1/me", None, token=access_jwt)
    return payload


def heartbeat(base: str, *, access_jwt: str, device_id: str,
              platform: str, app_version: str) -> None:
    _call("POST", f"{base}/v1/heartbeat", {
        "device_id": device_id, "platform": platform, "app_version": app_version},
        token=access_jwt)
