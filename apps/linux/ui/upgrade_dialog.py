"""Upgrade dialog — Pro plans mock (L10, Phase 6).

Real checkout (Stripe/Lemon Squeezy → entitlements webhook) lands after
release; until then this screen documents the matrix from LICENSING.md §6
and restores an existing Pro from the cached/server plan. Never needs the
network to *display*; restore is best-effort online.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from db.store import get_meta
from services import identity
from services.license_check import apply_result, check_once
from services.identity import APP_VERSION
from services.registry import base_url
from ui.screen import fit_to_screen


class UpgradeDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None,
                 base: str | None = None) -> None:
        super().__init__(parent)
        self.conn = conn
        self.base = base or base_url()
        self.setWindowTitle("StreakGrid Pro")

        layout = QVBoxLayout(self)
        title = QLabel("Free vs Pro")
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(title)

        meta = get_meta(self.conn)
        plan = (meta.get("plan") or "free").strip()
        self.plan_label = QLabel(f"Current plan: {plan}")
        layout.addWidget(self.plan_label)

        matrix = QLabel(
            "Free: up to 5 habits, 2 devices, full tracking.\n"
            "Pro (coming soon): unlimited habits/devices, CSV/PNG export, "
            "desktop widget.\n\n"
            "Checkout is not wired yet — your data stays readable on-device "
            "either way.")
        matrix.setWordWrap(True)
        layout.addWidget(matrix)

        self.message = QLabel("")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)

        choose = QPushButton("Choose Pro (coming soon)")
        choose.clicked.connect(lambda: self.message.setText(
            "Payments launch after release — this button will open checkout."))
        layout.addWidget(choose)

        restore = QPushButton("Restore purchase")
        restore.clicked.connect(self._on_restore)
        layout.addWidget(restore)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        fit_to_screen(self, QSize(440, 360), QSize(300, 240))

    def _on_restore(self) -> None:
        access, refresh_jwt, email = identity.load_tokens()
        if not access:
            self.message.setText("No account on this device — log in first.")
            return
        meta = get_meta(self.conn)
        result = check_once(  # never raises: failures come back as offline/locked
            self.base, access=access, refresh_jwt=refresh_jwt,
            device_id=meta.get("device_id") or "", platform="linux",
            app_version=APP_VERSION)
        if result.get("outcome") == "offline":
            self.message.setText("No connection — restore needs one online check.")
            return
        apply_result(self.conn, result, email=email)
        plan = (get_meta(self.conn).get("plan") or "free").strip()
        self.plan_label.setText(f"Current plan: {plan}")
        self.message.setText("Restored." if plan == "pro" else
                             "No Pro found on this account (still free).")


def open_upgrade_dialog(parent: QWidget | None, conn: sqlite3.Connection) -> None:
    UpgradeDialog(conn, parent).exec()
