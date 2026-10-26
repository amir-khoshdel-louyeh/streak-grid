"""Week chart — 7 bars for per-weekday completion (like site stats).

Polished: value labels, best-day accent, 50/100% gridlines, bars rounded
only on top (flat base sits on the track), theme-aware.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class WeekChart(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rates: list[float] = [0.0] * 7
        self._empty = QColor("#24283b")
        self._fill = QColor("#40c463")
        self._accent = QColor("#7aa2f7")
        self._text = QColor("#7f88b3")
        self._grid = QColor("#2c3145")
        self.setMinimumHeight(140)
        self.refresh_theme()

    def refresh_theme(self) -> None:
        from ui.theme import chart_colors

        colors = chart_colors()
        self._empty = QColor(colors["chart_empty"])
        self._fill = QColor(colors["chart_fill"])
        self._accent = QColor(colors["grid_accent"])
        self._text = QColor(colors["chart_text"])
        self._grid = QColor(colors["grid_line"])
        self.update()

    def set_rates(self, rates: list[float]) -> None:
        self._rates = [max(0.0, min(1.0, float(r))) for r in list(rates)[:7]]
        while len(self._rates) < 7:
            self._rates.append(0.0)
        self.update()

    def rates(self) -> list[float]:
        return list(self._rates)

    def best_day(self) -> int | None:
        """Index of the best weekday, or None when everything is 0."""
        top = max(self._rates)
        return self._rates.index(top) if top > 0 else None

    def sizeHint(self) -> QSize:
        return QSize(420, 150)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        top_pad, label_h = 24, 18
        plot_h = max(10.0, h - top_pad - label_h - 4)
        plot_top = top_pad
        slot = w / 7
        bar_w = min(46.0, slot - 16)
        best = self.best_day()

        # gridlines at 100% / 50%
        painter.setPen(self._grid)
        for frac in (1.0, 0.5):
            y = plot_top + plot_h * (1.0 - frac)
            painter.drawLine(0, int(y), w, int(y))

        painter.setFont(QFont("Sans", 9))
        for i, rate in enumerate(self._rates):
            cx = slot * i + slot / 2
            x = cx - bar_w / 2
            base = plot_top + plot_h
            bh = max(0.0, rate * plot_h)
            color = self._accent if i == best else self._fill

            painter.setPen(Qt.NoPen)
            painter.setBrush(self._empty)
            painter.drawRoundedRect(int(x), int(plot_top), int(bar_w), int(plot_h), 5, 5)

            if bh >= 1:
                painter.setBrush(color)
                painter.drawPath(self._top_rounded_rect(x, base - bh, bar_w, bh, 5))

            # value label (accent for the best day)
            painter.setPen(self._accent if i == best else self._text)
            painter.drawText(int(slot * i), 0, int(slot), top_pad - 2,
                             Qt.AlignHCenter | Qt.AlignBottom, f"{rate:.0%}")
            # weekday label
            painter.setPen(self._text)
            painter.drawText(int(slot * i), h - label_h, int(slot), label_h,
                             Qt.AlignCenter, DAYS[i])
        painter.end()

    @staticmethod
    def _top_rounded_rect(x: float, y: float, w: float, h: float,
                          radius: float) -> QPainterPath:
        """Rect with rounded top corners and a flat base (sits on the track)."""
        r = max(0.0, min(radius, w / 2, h))
        path = QPainterPath()
        path.moveTo(x, y + h)
        path.lineTo(x, y + r)
        path.quadTo(x, y, x + r, y)
        path.lineTo(x + w - r, y)
        path.quadTo(x + w, y, x + w, y + r)
        path.lineTo(x + w, y + h)
        path.closeSubpath()
        return path
