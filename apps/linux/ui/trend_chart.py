"""Trend chart — 30-day daily completion share, oldest→newest.

Line + subtle fill, end dot on today, min/max labels, 50/100% gridlines.
Theme-aware, width-flexible (small screens just get a narrower chart).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class TrendChart(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rates: list[float] = []
        self._fill = QColor("#40c463")
        self._accent = QColor("#7aa2f7")
        self._text = QColor("#7f88b3")
        self._grid = QColor("#2c3145")
        self.setMinimumHeight(130)
        self.refresh_theme()

    def refresh_theme(self) -> None:
        from ui.theme import chart_colors

        colors = chart_colors()
        self._fill = QColor(colors["chart_fill"])
        self._accent = QColor(colors["grid_accent"])
        self._text = QColor(colors["chart_text"])
        self._grid = QColor(colors["grid_line"])
        self.update()

    def set_rates(self, rates: list[float]) -> None:
        self._rates = [max(0.0, min(1.0, float(r))) for r in rates]
        self.update()

    def rates(self) -> list[float]:
        return list(self._rates)

    def sizeHint(self) -> QSize:
        return QSize(420, 140)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        top_pad, bottom_pad = 22, 6
        plot_h = max(10.0, h - top_pad - bottom_pad)
        plot_top = top_pad
        n = len(self._rates)
        if n < 2 or w < 10:
            painter.setPen(self._text)
            painter.setFont(QFont("Sans", 9))
            painter.drawText(0, 0, w, h, Qt.AlignCenter, "Not enough data yet")
            painter.end()
            return

        def point(i: int) -> QPointF:
            x = 4 + (w - 8) * (i / (n - 1))
            y = plot_top + plot_h * (1.0 - self._rates[i])
            return QPointF(x, y)

        painter.setPen(self._grid)
        for frac in (1.0, 0.5):
            y = plot_top + plot_h * (1.0 - frac)
            painter.drawLine(0, int(y), w, int(y))

        # fill under the curve
        fill = QPainterPath()
        fill.moveTo(point(0))
        for i in range(1, n):
            fill.lineTo(point(i))
        fill.lineTo(QPointF(point(n - 1).x(), plot_top + plot_h))
        fill.lineTo(QPointF(point(0).x(), plot_top + plot_h))
        fill.closeSubpath()
        soft = QColor(self._fill)
        soft.setAlpha(48)
        painter.setPen(Qt.NoPen)
        painter.setBrush(soft)
        painter.drawPath(fill)

        # line
        line = QPainterPath()
        line.moveTo(point(0))
        for i in range(1, n):
            line.lineTo(point(i))
        painter.setPen(QPen(self._fill, 2.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(line)

        # today dot + min/max labels
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._accent)
        last = point(n - 1)
        painter.drawEllipse(last, 4.0, 4.0)
        painter.setPen(self._text)
        painter.setFont(QFont("Sans", 9))
        lo, hi = min(self._rates), max(self._rates)
        painter.drawText(4, 0, w // 2, top_pad - 2,
                         Qt.AlignLeft | Qt.AlignBottom, f"low {lo:.0%}")
        painter.drawText(w // 2, 0, w // 2 - 4, top_pad - 2,
                         Qt.AlignRight | Qt.AlignBottom, f"high {hi:.0%}")
        painter.end()
