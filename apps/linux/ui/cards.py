"""Habit card — S11-3: tap + details buttons."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)


class HabitCard(QFrame):
    """Single habit row. `on_tap(id)` check-off, `on_open(id)` detail dialog."""

    def __init__(
        self,
        habit_id: int,
        name: str,
        on_tap=None,
        on_open=None,
        on_decrement=None,
        counter_text: str = "",
        streak_active: bool = False,
        done: bool = False,
        folder_tag: str = "",
        folder_color: str = "",
        stepper: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.habit_id = habit_id
        self._on_tap = on_tap
        self._on_open = on_open
        self._on_decrement = on_decrement
        self._base_name = name
        self._counter_text = counter_text
        self._streak_active = streak_active
        self._folder_tag = folder_tag
        self._folder_color = folder_color
        self._done = bool(done)
        self.dec_button: QPushButton | None = None

        self.setProperty("card", True)
        self.setMinimumHeight(70)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self.name_label = QLabel()
        self.name_label.setObjectName("CardTitle")
        self.name_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.name_label.setToolTip(str(name))
        self.meta_label = QLabel()
        self.meta_label.setObjectName("CardMeta")
        text_col.addWidget(self.name_label)
        text_col.addWidget(self.meta_label)
        layout.addLayout(text_col, 1)

        self.detail_button = QPushButton("📅")
        self.detail_button.setObjectName("IconButton")
        self.detail_button.setFixedSize(34, 34)
        self.detail_button.setCursor(Qt.PointingHandCursor)
        self.detail_button.setToolTip("Open habit details")
        self.detail_button.clicked.connect(self._handle_open)
        layout.addWidget(self.detail_button)

        if stepper:
            self.dec_button = QPushButton("−")
            self.dec_button.setObjectName("IconButton")
            self.dec_button.setFixedSize(34, 34)
            self.dec_button.setCursor(Qt.PointingHandCursor)
            self.dec_button.setToolTip("Decrease today's count")
            self.dec_button.clicked.connect(self._handle_decrement)
            layout.addWidget(self.dec_button)

        self.tap_button = QPushButton()
        self.tap_button.setObjectName("CheckButton")
        self.tap_button.setFixedSize(40, 40)
        self.tap_button.setCursor(Qt.PointingHandCursor)
        self.tap_button.clicked.connect(self._handle_tap)
        layout.addWidget(self.tap_button)

        self._render_name()
        self._apply_state()

    # -- rendering ------------------------------------------------------
    def _render_name(self) -> None:
        self.name_label.setText(self._base_name)
        parts: list[str] = []
        if self._streak_active:
            parts.append("🔥 active streak")
        if self._counter_text:
            parts.append(self._counter_text)
        if self._folder_tag:
            dot = (f'<font color="{self._folder_color}">●</font> '
                   if self._folder_color else "● ")
            parts.append(f"{dot}{self._folder_tag}")
        self.meta_label.setTextFormat(Qt.RichText)
        self.meta_label.setText("   ·   ".join(parts))
        self.meta_label.setVisible(bool(parts))

    def _apply_state(self) -> None:
        self.tap_button.setText("✓" if self._done else "○")
        self.tap_button.setToolTip("Done today — tap to undo" if self._done else "Mark done for today")
        self.tap_button.setProperty("state", "done" if self._done else "todo")
        self.setProperty("done", self._done)
        for widget in (self.tap_button, self):
            style = widget.style()
            style.unpolish(widget)
            style.polish(widget)

    # -- actions --------------------------------------------------------
    def _handle_tap(self) -> None:
        if self._on_tap is not None:
            self._on_tap(self.habit_id)

    def _handle_open(self) -> None:
        if self._on_open is not None:
            self._on_open(self.habit_id)

    def _handle_decrement(self) -> None:
        if self._on_decrement is not None:
            self._on_decrement(self.habit_id)

    # -- setters --------------------------------------------------------
    def set_done(self, done: bool) -> None:
        self._done = bool(done)
        self._apply_state()

    def set_counter(self, text: str) -> None:
        self._counter_text = text
        self._render_name()

    def set_streak(self, active: bool) -> None:
        self._streak_active = active
        self._render_name()
