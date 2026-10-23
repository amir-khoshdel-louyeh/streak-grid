"""Achievements dialog — S16-1: 8 medals with icon + unlock date."""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

from core.achievements import ACHIEVEMENTS
from ui.screen import fit_to_screen


class AchievementsDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Achievements")
        layout = QVBoxLayout(self)
        unlocked = {
            r["code"]: r["unlocked_at"]
            for r in conn.execute("SELECT code, unlocked_at FROM achievements")
        }
        self.rows: list[QLabel] = []
        for code, name in ACHIEVEMENTS.items():
            at = unlocked.get(code)
            icon = "🏅" if at else "🔒"
            lab = QLabel(f"{icon} {name} ({code})" + (f" — {at}" if at else ""))
            lab.setWordWrap(True)
            layout.addWidget(lab)
            self.rows.append(lab)
        fit_to_screen(self, QSize(460, 340), QSize(300, 240))
