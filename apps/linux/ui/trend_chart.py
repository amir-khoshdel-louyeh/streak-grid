"""Trend chart — 30-day daily completion share, oldest→newest.

Line + subtle fill, end dot on today, min/max labels, 50/100% gridlines.
Theme-aware, width-flexible (small screens just get a narrower chart).

Also hosts HabitLinesChart: one smoothed line per habit (7-day rolling
average) with a toggleable legend, so lines stay readable instead of
collapsing onto 0%/100% like raw daily 0/1 values would.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QGridLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


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


PALETTE = [
    "#7aa2f7", "#40c463", "#e5a50a", "#e06c75",
    "#c678dd", "#56b6c2", "#ff8c42", "#89ddff",
]


class _HabitLinesCanvas(QWidget):
    """Paints the visible series (no legend, no layout)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._data: list[tuple[str, QColor, list[float]]] = []
        self._text = QColor("#7f88b3")
        self._grid = QColor("#2c3145")
        self.setMinimumHeight(150)

    def set_data(self, data: list[tuple[str, QColor, list[float]]]) -> None:
        self._data = [(n, c, [max(0.0, min(1.0, float(r))) for r in rates])
                      for n, c, rates in data]
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(420, 160)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        top_pad, bottom_pad = 8, 6
        plot_h = max(10.0, h - top_pad - bottom_pad)
        plot_top = top_pad
        n = max((len(rates) for _, _, rates in self._data), default=0)
        if not self._data or n < 2 or w < 10:
            painter.setPen(self._text)
            painter.setFont(QFont("Sans", 9))
            painter.drawText(0, 0, w, h, Qt.AlignCenter, "Not enough data yet")
            painter.end()
            return

        def point(rates: list[float], i: int) -> QPointF:
            x = 4 + (w - 8) * (i / (n - 1))
            v = rates[i] if i < len(rates) else rates[-1]
            return QPointF(x, plot_top + plot_h * (1.0 - v))

        painter.setPen(self._grid)
        for frac in (1.0, 0.5, 0.0):
            y = plot_top + plot_h * (1.0 - frac)
            painter.drawLine(0, int(y), w, int(y))

        for _, color, rates in self._data:
            line = QPainterPath()
            line.moveTo(point(rates, 0))
            for i in range(1, n):
                line.lineTo(point(rates, i))
            painter.setPen(QPen(color, 2.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(line)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(point(rates, n - 1), 3.5, 3.5)
        painter.end()


class HabitLinesChart(QWidget):
    """One smoothed line per habit + clickable legend to show/hide lines."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._series: list[tuple[str, list[float]]] = []
        self._hidden: set[int] = set()
        self._colors: list[QColor] = [QColor(c) for c in PALETTE]
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)
        self._legend_host = QWidget()
        self._legend = QGridLayout(self._legend_host)
        self._legend.setContentsMargins(0, 0, 0, 0)
        self._legend.setSpacing(4)
        outer.addWidget(self._legend_host)
        self._canvas = _HabitLinesCanvas()
        self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        outer.addWidget(self._canvas)

    def refresh_theme(self) -> None:
        from ui.theme import chart_colors

        colors = chart_colors()
        self._canvas._text = QColor(colors["chart_text"])
        self._canvas._grid = QColor(colors["grid_line"])
        self._canvas.update()

    def set_series(self, series: list[tuple[str, list[float]]]) -> None:
        """Replace data. `series` = [(habit name, 30 rolling rates)]."""
        self._series = [(name, [max(0.0, min(1.0, float(r))) for r in rates])
                        for name, rates in series]
        self._hidden = set()
        self._rebuild_legend()
        self._push_visible()

    def series(self) -> list[tuple[str, list[float]]]:
        return [(n, list(r)) for n, r in self._series]

    def visible_count(self) -> int:
        return sum(1 for i in range(len(self._series)) if i not in self._hidden)

    def _rebuild_legend(self) -> None:
        while self._legend.count():
            item = self._legend.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        if not self._series:
            self._legend_host.setVisible(False)
            return
        self._legend_host.setVisible(True)
        for i, (name, _rates) in enumerate(self._series):
            short = name if len(name) <= 16 else name[:15] + "…"
            btn = QPushButton(f"●  {short}")
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(f"Toggle {name}")
            btn.setStyleSheet(f"color: {PALETTE[i % len(PALETTE)]}; text-align: left;")
            btn.toggled.connect(lambda _c, idx=i: self._on_toggle(idx, _c))
            self._legend.addWidget(btn, i // 3, i % 3)

    def _on_toggle(self, index: int, checked: bool) -> None:
        if checked:
            self._hidden.discard(index)
        else:
            self._hidden.add(index)
        self._push_visible()

    def _push_visible(self) -> None:
        self._canvas.set_data([
            (name, QColor(PALETTE[i % len(PALETTE)]), rates)
            for i, (name, rates) in enumerate(self._series)
            if i not in self._hidden
        ])
