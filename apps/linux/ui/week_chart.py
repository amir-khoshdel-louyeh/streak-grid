"""Week chart — P7-1: 7 bars for per-weekday completion (like site stats)."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QWidget

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class WeekChart(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rates: list[float] = [0.0] * 7
        self._empty = QColor("#24283b")
        self._fill = QColor("#40c463")
        self._text = QColor("#7f88b3")
        self.setMinimumHeight(120)
        self.refresh_theme()

    def refresh_theme(self) -> None:
        from ui.theme import chart_colors

        colors = chart_colors()
        self._empty = QColor(colors["chart_empty"])
        self._fill = QColor(colors["chart_fill"])
        self._text = QColor(colors["chart_text"])
        self.update()

    def set_rates(self, rates: list[float]) -> None:
        self._rates = [max(0.0, min(1.0, float(r))) for r in list(rates)[:7]]
        while len(self._rates) < 7:
            self._rates.append(0.0)
        self.update()

    def rates(self) -> list[float]:
        return list(self._rates)

    def sizeHint(self) -> QSize:
        return QSize(420, 130)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        label_h, top = 18, 8
        max_bar = h - label_h - top - 4
        slot = w / 7
        bar_w = min(44.0, slot - 14)
        painter.setFont(QFont("Sans", 9))
        for i, rate in enumerate(self._rates):
            cx = slot * i + slot / 2
            bh = rate * max_bar
            x = cx - bar_w / 2
            y = top + (max_bar - bh)
            painter.setPen(Qt.NoPen)
            painter.setBrush(self._empty)
            painter.drawRoundedRect(int(x), top, int(bar_w), int(max_bar), 4, 4)
            if bh > 0:
                painter.setBrush(self._fill)
                painter.drawRoundedRect(int(x), int(y), int(bar_w), int(bh), 4, 4)
            painter.setPen(self._text)
            painter.drawText(int(slot * i), h - label_h, int(slot), label_h,
                             Qt.AlignCenter, DAYS[i])
        painter.end()
