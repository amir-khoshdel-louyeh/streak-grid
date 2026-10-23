"""Progress ring — P1-1: daily done/due ring (like HabitForge today header)."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


class ProgressRing(QWidget):
    def __init__(self, parent=None, size: int = 96) -> None:
        super().__init__(parent)
        self._done = 0
        self._total = 0
        self._size = size
        self._track = QColor("#2c3145")
        self._fill = QColor("#7aa2f7")
        self._text = QColor("#c0caf5")
        self.setFixedSize(size, size)
        self.refresh_theme()

    def refresh_theme(self) -> None:
        from ui.theme import chart_colors

        colors = chart_colors()
        self._track = QColor(colors["ring_track"])
        self._fill = QColor(colors["ring_fill"])
        self._text = QColor(colors["ring_text"])
        self.update()

    def set_progress(self, done: int, total: int) -> None:
        self._done = max(0, int(done))
        self._total = max(0, int(total))
        self.update()

    def fraction(self) -> float:
        if self._total <= 0:
            return 0.0
        return min(1.0, self._done / self._total)

    def sizeHint(self) -> QSize:
        return QSize(self._size, self._size)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        margin = 8
        rect = self.rect().adjusted(margin, margin, -margin, -margin)
        track = QPen(self._track, 9)
        track.setCapStyle(Qt.RoundCap)
        painter.setPen(track)
        painter.drawEllipse(rect)
        if self._total > 0:
            done_pen = QPen(self._fill, 9)
            done_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(done_pen)
            painter.drawArc(rect, 90 * 16, -int(self.fraction() * 360 * 16))
        painter.setPen(self._text)
        painter.setFont(QFont("Sans", 11, QFont.Bold))
        painter.drawText(self.rect(), Qt.AlignCenter, f"{self._done}/{self._total}")
        painter.end()
