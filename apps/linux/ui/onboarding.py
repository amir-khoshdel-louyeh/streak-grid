"""Onboarding — P6: first-run welcome with the 66-day story (like the site)."""

from __future__ import annotations

from PySide6.QtCore import QSettings, QSize
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.screen import fit_to_screen

SETTINGS_KEY = "streakgrid/onboarded"


def is_onboarded() -> bool:
    return bool(QSettings("StreakGrid", "StreakGrid").value(SETTINGS_KEY, False))


def mark_onboarded() -> None:
    QSettings("StreakGrid", "StreakGrid").setValue(SETTINGS_KEY, True)


class WelcomeDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Welcome to StreakGrid")
        layout = QVBoxLayout(self)
        title = QLabel("You Are What You Do. Forge the Identity.")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        title.setWordWrap(True)
        layout.addWidget(title)
        story = QLabel(
            "66 days. That's all it takes.\n\n"
            "UCL researchers found a new behavior becomes automatic after "
            "about 66 days on average — not 21, not overnight. Every day you "
            "check the box, the pattern encodes a little deeper until it stops "
            "requiring willpower. The heatmap is there so you can watch it happen."
        )
        story.setWordWrap(True)
        layout.addWidget(story)
        privacy = QLabel(
            "One free account, activated once — then fully offline. "
            "We store only your email, a random device ID, app version "
            "and last-seen time. Your habits never leave this computer. "
            "See PRIVACY.md."
        )
        privacy.setWordWrap(True)
        layout.addWidget(privacy)
        go = QPushButton("Start forging")
        go.clicked.connect(self.accept)
        layout.addWidget(go)
        fit_to_screen(self, QSize(520, 380), QSize(300, 240))


def maybe_welcome(parent: QWidget | None = None) -> bool:
    """Show welcome once. Returns True if it was shown."""
    if is_onboarded():
        return False
    WelcomeDialog(parent).exec()
    mark_onboarded()
    return True
