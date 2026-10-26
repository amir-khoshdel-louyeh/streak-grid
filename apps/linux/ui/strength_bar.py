"""Strength bar — tiny horizontal meter for per-habit strength (0..1).

Sits in each Stats row next to the numbers; length encodes the value so
rows are comparable at a glance. Theme-aware.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget


class StrengthBar(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._value = 0.0
        self._track = QColor("#24283b")
        self._fill = QColor("#40c463")
        self.setFixedSize(96, 10)
        self.setToolTip("Strength: 0%")
        self.refresh_theme()

    def refresh_theme(self) -> None:
        from ui.theme import chart_colors

        colors = chart_colors()
        self._track = QColor(colors["chart_empty"])
        self._fill = QColor(colors["chart_fill"])
        self.update()

    def set_value(self, value: float) -> None:
        self._value = max(0.0, min(1.0, float(value)))
        self.setToolTip(f"Strength: {self._value:.0%}")
        self.update()

    def value(self) -> float:
        return self._value

    def sizeHint(self) -> QSize:
        return QSize(96, 10)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._track)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 5, 5)
        fill_w = int(self.width() * self._value)
        if fill_w >= 2:
            painter.setBrush(self._fill)
            painter.drawRoundedRect(0, 0, fill_w, self.height(), 5, 5)
        painter.end()
