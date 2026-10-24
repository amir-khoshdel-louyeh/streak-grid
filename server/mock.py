"""Phase 6 registry mock — stdlib only, implements core/docs/LICENSING.md §3.

Run:  python mock.py --port 8765 --db ./registry.db
NOT for production (Supabase is the deploy target). Exists so clients can
verify the /v1 contract + ban flow locally with curl before C02 ships.
Extra table `revoked_jtis` is mock-internal (logout support), not in contract.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

ACCESS_TTL = 3600          # 1h
REFRESH_TTL = 90 * 86400  # 90d


def b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def issue_jwt(secret: str, sub: str, email: str, typ: str, ttl: int) -> str:
    now = int(time.time())
    header = b64e(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = b64e(json.dumps({
        "sub": sub, "email": email, "typ": typ,
        "jti": uuid.uuid4().hex, "iat": now, "exp": now + ttl,
    }).encode())
    sig = b64e(hmac.new(secret.encode(), f"{header}.{payload}".encode(),
                        hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def verify_jwt(secret: str, token: str, typ: str) -> dict | None:
    try:
        header, payload, sig = token.split(".")
        want = b64e(hmac.new(secret.encode(), f"{header}.{payload}".encode(),
                             hashlib.sha256).digest())
        if not hmac.compare_digest(want, sig):
            return None
        data = json.loads(b64d(payload))
        if data.get("typ") != typ or int(data.get("exp", 0)) < int(time.time()):
            return None
        return data
    except (ValueError, KeyError):
        return None


def hash_pw(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"pbkdf2$100000${salt}${dk.hex()}"


def check_pw(password: str, stored: str) -> bool:
    try:
        _, it, salt, hexd = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(it))
        return hmac.compare_digest(dk.hex(), hexd)
    except (ValueError, AttributeError):
        return False


DDL = """
CREATE TABLE IF NOT EXISTS users(
  id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', plan TEXT NOT NULL DEFAULT 'free');
CREATE TABLE IF NOT EXISTS devices(
  user_id TEXT NOT NULL, device_id TEXT NOT NULL, platform TEXT NOT NULL DEFAULT '',
  app_version TEXT NOT NULL DEFAULT '', last_seen TEXT,
  PRIMARY KEY(user_id, device_id));
CREATE TABLE IF NOT EXISTS entitlements(
  user_id TEXT NOT NULL PRIMARY KEY, plan TEXT NOT NULL DEFAULT 'free',
  expires_at TEXT, source TEXT NOT NULL DEFAULT 'signup', updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS heartbeats(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, device_id TEXT NOT NULL,
  app_version TEXT NOT NULL DEFAULT '', platform TEXT NOT NULL DEFAULT '', seen_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS revoked_jtis(jti TEXT PRIMARY KEY, revoked_at TEXT NOT NULL);
"""


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Handler(BaseHTTPRequestHandler):
    server_version = "StreakGridMock/1"

    def _db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.server.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _send(self, code: int, obj: dict | None = None) -> None:
        body = json.dumps(obj or {}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, UnicodeDecodeError):
            return {}

    def _bearer(self) -> str:
        auth = self.headers.get("Authorization", "")
        return auth[7:] if auth.startswith("Bearer ") else ""

    def _auth_user(self, conn: sqlite3.Connection) -> sqlite3.Row | None:
        data = verify_jwt(self.server.secret, self._bearer(), "access")
        if not data:
            return None
        if conn.execute("SELECT 1 FROM revoked_jtis WHERE jti=?",
                        (data["jti"],)).fetchone():
            return None
        return conn.execute("SELECT * FROM users WHERE id=?", (data["sub"],)).fetchone()

    def log_message(self, *a) -> None:  # quieter logs
        pass

    # -- routes ---------------------------------------------------------
    def do_POST(self) -> None:
        path = urlparse(self.path).path
        body = self._body()
        conn = self._db()
        try:
            if path == "/v1/signup":
                self._signup(conn, body)
            elif path == "/v1/login":
                self._login(conn, body)
            elif path == "/v1/refresh":
                self._refresh(conn, body)
            elif path == "/v1/logout":
                self._logout(conn)
            elif path == "/v1/heartbeat":
                self._heartbeat(conn, body)
            elif path == "/v1/account/delete":
                self._delete(conn)
            else:
                self._send(404, {"code": "not_found"})
        finally:
            conn.close()

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/v1/me":
            conn = self._db()
            try:
                user = self._auth_user(conn)
                if not user:
                    self._send(401, {"code": "revoked"})
                    return
                ent = conn.execute(
                    "SELECT * FROM entitlements WHERE user_id=?", (user["id"],)).fetchone()
                self._send(200 if user["status"] == "active" else 403, {
                    "user_id": user["id"], "email": user["email"],
                    "status": user["status"], "plan": user["plan"],
                    "code": user["status"] if user["status"] != "active" else "ok",
                    "entitlements": {
                        "plan": ent["plan"] if ent else user["plan"],
                        "expires_at": ent["expires_at"] if ent else None,
                    },
                })
            finally:
                conn.close()
        else:
            self._send(404, {"code": "not_found"})

    # -- handlers --------------------------------------------------------
    def _need_device(self, body: dict) -> str | None:
        dev = (body.get("device_id") or "").strip()
        return dev or None

    def _tokens(self, user: sqlite3.Row) -> dict:
        s = self.server.secret
        return {
            "user_id": user["id"],
            "access_jwt": issue_jwt(s, user["id"], user["email"], "access", ACCESS_TTL),
            "refresh_jwt": issue_jwt(s, user["id"], user["email"], "refresh", REFRESH_TTL),
            "plan": user["plan"],
        }

    def _signup(self, conn: sqlite3.Connection, body: dict) -> None:
        email = (body.get("email") or "").strip().lower()
        password = body.get("password") or ""
        device = self._need_device(body)
        if not email or not password or not device:
            self._send(400, {"code": "bad_request"})
            return
        if conn.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            self._send(409, {"code": "email_taken"})
            return
        uid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO users(id,email,password_hash,created_at) VALUES(?,?,?,?)",
            (uid, email, hash_pw(password), now_iso()))
        conn.execute(
            "INSERT INTO entitlements(user_id,plan,source,updated_at) VALUES(?, 'free','signup',?)",
            (uid, now_iso()))
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        self._send(201, self._tokens(user))

    def _login(self, conn: sqlite3.Connection, body: dict) -> None:
        email = (body.get("email") or "").strip().lower()
        password = body.get("password") or ""
        device = self._need_device(body)
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not user or not check_pw(password, user["password_hash"]) or not device:
            self._send(401, {"code": "bad_credentials"})
            return
        self._send(200, self._tokens(user))

    def _refresh(self, conn: sqlite3.Connection, body: dict) -> None:
        data = verify_jwt(self.server.secret, body.get("refresh_jwt") or "", "refresh")
        if not data or conn.execute(
                "SELECT 1 FROM revoked_jtis WHERE jti=?", (data["jti"],)).fetchone():
            self._send(401, {"code": "revoked"})
            return
        user = conn.execute("SELECT * FROM users WHERE id=?", (data["sub"],)).fetchone()
        if not user:
            self._send(401, {"code": "revoked"})
            return
        conn.execute("INSERT OR IGNORE INTO revoked_jtis VALUES(?,?)",
                     (data["jti"], now_iso()))
        conn.commit()
        s = self.server.secret
        self._send(200, {
            "access_jwt": issue_jwt(s, user["id"], user["email"], "access", ACCESS_TTL),
            "refresh_jwt": issue_jwt(s, user["id"], user["email"], "refresh", REFRESH_TTL),
        })

    def _logout(self, conn: sqlite3.Connection) -> None:
        data = verify_jwt(self.server.secret, self._bearer(), "access")
        if data:
            conn.execute("INSERT OR IGNORE INTO revoked_jtis VALUES(?,?)",
                         (data["jti"], now_iso()))
            conn.commit()
        self._send(204)

    def _heartbeat(self, conn: sqlite3.Connection, body: dict) -> None:
        user = self._auth_user(conn)
        device = self._need_device(body)
        if not user or not device:
            self._send(401, {"code": "revoked"})
            return
        conn.execute(
            """INSERT INTO devices(user_id,device_id,platform,app_version,last_seen)
               VALUES(?,?,?,?,?)
               ON CONFLICT(user_id,device_id) DO UPDATE SET
                 platform=excluded.platform, app_version=excluded.app_version,
                 last_seen=excluded.last_seen""",
            (user["id"], device, body.get("platform") or "",
             body.get("app_version") or "", now_iso()))
        conn.execute(
            "INSERT INTO heartbeats(user_id,device_id,app_version,platform,seen_at)"
            " VALUES(?,?,?,?,?)",
            (user["id"], device, body.get("app_version") or "",
             body.get("platform") or "", now_iso()))
        conn.commit()
        self._send(204)

    def _delete(self, conn: sqlite3.Connection) -> None:
        user = self._auth_user(conn)
        if not user:
            self._send(401, {"code": "revoked"})
            return
        conn.execute("DELETE FROM users WHERE id=?", (user["id"],))
        conn.commit()
        self._send(202, {"code": "deleted"})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--db", default="registry.db")
    ap.add_argument("--secret", default="dev-only-secret-change-in-prod")
    args = ap.parse_args()
    conn = sqlite3.connect(args.db)
    conn.executescript(DDL)
    conn.commit()
    conn.close()
    srv = HTTPServer(("127.0.0.1", args.port), Handler)
    srv.db_path = args.db  # type: ignore[attr-defined]
    srv.secret = args.secret  # type: ignore[attr-defined]
    print(f"mock registry on 127.0.0.1:{args.port} db={args.db}")
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
