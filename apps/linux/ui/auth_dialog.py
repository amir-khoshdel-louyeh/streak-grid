"""Account dialog — one-time activation UI (L07, Phase 6).

Offline-aware: every message says the internet is needed only for this
single step; the app itself keeps working offline (fail-open).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from db.store import get_meta, set_meta
from services import identity
from services.identity import APP_VERSION, ensure_identity, get_device_id
from services.registry import RegistryError, base_url, login, logout, signup
from ui.screen import fit_to_screen

PLATFORM = "linux"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class AccountDialog(QDialog):
    """Signup/login/logout. Sets `changed=True` when meta/tokens changed."""

    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None,
                 base: str | None = None) -> None:
        super().__init__(parent)
        self.conn = conn
        self.base = base or base_url()
        self.changed = False
        self.setWindowTitle("StreakGrid account")

        layout = QVBoxLayout(self)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        form = QFormLayout()
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("you@example.com")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Email", self.email_edit)
        form.addRow("Password", self.password_edit)
        layout.addLayout(form)

        self.message = QLabel("")
        self.message.setWordWrap(True)
        self.message.setObjectName("MutedText")
        layout.addWidget(self.message)

        row = QPushButton("Sign up")
        row.clicked.connect(self._on_signup)
        self.signup_button = row
        login_btn = QPushButton("Log in")
        login_btn.clicked.connect(self._on_login)
        self.login_button = login_btn
        self.logout_button = QPushButton("Log out")
        self.logout_button.clicked.connect(self._on_logout)
        for btn in (self.signup_button, self.login_button, self.logout_button):
            layout.addWidget(btn)

        note = QLabel("One free account, activated once — then fully offline. "
                      "We store only email + device ID, never your habits. "
                      "See PRIVACY.md.")
        note.setWordWrap(True)
        note.setObjectName("MutedText")
        layout.addWidget(note)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        _access, _refresh, email = identity.load_tokens()
        if email:
            self.email_edit.setText(email)
        self._refresh_status()
        fit_to_screen(self, QSize(420, 380), QSize(300, 260))

    # -- state ----------------------------------------------------------
    def _refresh_status(self) -> None:
        meta = get_meta(self.conn)
        _access, _refresh, email = identity.load_tokens()
        if meta.get("user_id"):
            self.status_label.setText(
                f"Activated as {email or meta['user_id'][:8]} — plan: {meta.get('plan')}")
            self.logout_button.setVisible(True)
        else:
            state = meta.get("cached_status") or "unactivated"
            self.status_label.setText(
                "Not activated — limited mode (1 habit). Activate once, then offline."
                if state == "unactivated" else f"Status: {state}")
            self.logout_button.setVisible(False)

    def _set_busy(self, busy: bool) -> None:
        for btn in (self.signup_button, self.login_button, self.logout_button):
            btn.setDisabled(busy)
        self.setCursor(Qt.WaitCursor if busy else Qt.ArrowCursor)

    # -- actions ---------------------------------------------------------
    def _on_signup(self) -> None:
        self._run_auth(signup, "Signed up — activated.")

    def _on_login(self) -> None:
        self._run_auth(login, "Logged in — activated.")

    def _run_auth(self, call, ok_text: str) -> None:
        email = self.email_edit.text().strip().lower()
        password = self.password_edit.text()
        if not email or not password:
            self.message.setText("Enter both email and password.")
            return
        device_id = ensure_identity(self.conn, platform=PLATFORM, app_version=APP_VERSION)
        self._set_busy(True)
        try:
            payload = call(self.base, email=email, password=password,
                           device_id=device_id, platform=PLATFORM, app_version=APP_VERSION)
        except RegistryError as exc:
            self.message.setText(self._friendly(exc))
            return
        finally:
            self._set_busy(False)
        identity.save_tokens(payload["access_jwt"], payload["refresh_jwt"], email)
        set_meta(self.conn, user_id=payload["user_id"], cached_status="active",
                 plan=payload.get("plan") or "free", last_check=_utcnow())
        self.changed = True
        self.message.setText(ok_text)
        self._refresh_status()

    def _on_logout(self) -> None:
        access, _refresh, _email = identity.load_tokens()
        if access:
            try:
                logout(self.base, access_jwt=access)
            except RegistryError:
                pass  # server unreachable: still clear local state (fail-open)
        identity.clear_tokens()
        set_meta(self.conn, user_id="", cached_status="unactivated",
                 plan="free", last_check="")
        self.changed = True
        self.message.setText("Logged out — limited mode.")
        self._refresh_status()

    @staticmethod
    def _friendly(exc: RegistryError) -> str:
        if exc.code == "offline":
            return ("No connection — the internet is needed only for this "
                    "one-time step. The app itself works offline.")
        if exc.code == "email_taken":
            return "This email is already registered — try Log in instead."
        if exc.code == "bad_credentials":
            return "Wrong email or password."
        if exc.code in ("suspended", "banned"):
            return (f"Account {exc.code}. The app is read-only. "
                    "Contact support to appeal.")
        return f"Registry error ({exc.code}) — try again later."


def open_account_dialog(parent: QWidget | None, conn: sqlite3.Connection) -> bool:
    """Show the dialog. Returns True if account state changed."""
    _ = get_device_id(conn)  # ensure a device_id exists even if dialog closes
    dlg = AccountDialog(conn, parent)
    dlg.exec()
    return dlg.changed
