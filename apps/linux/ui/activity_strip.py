"""Activity strip — 90-day pulse line per habit row (All habits).

A heartbeat-style sparkline: done days spike, missed days dip, off-schedule
days break the line. Unlike the old year mini-grid it stretches with the row,
so it stays readable at any window width instead of shrinking to dots.
Values: 1.0 done, 0.0 missed, None = not due/paused (gap).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


class ActivityStrip(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._series: list[float | None] = []
        self._line = QColor("#40c463")
        self._today = QColor("#7aa2f7")
        self._grid = QColor("#2c3145")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumSize(120, 40)
        self.setFixedHeight(40)
        self.setToolTip("Last 90 days — spikes are done days")
        self.refresh_theme()

    def refresh_theme(self) -> None:
        from ui.theme import chart_colors

        colors = chart_colors()
        self._line = QColor(colors["chart_fill"])
        self._today = QColor(colors["grid_accent"])
        self._grid = QColor(colors["grid_line"])
        self.update()

    def set_series(self, series: list[float | None]) -> None:
        self._series = list(series)
        self.update()

    def series(self) -> list[float | None]:
        return list(self._series)

    def sizeHint(self) -> QSize:
        return QSize(280, 40)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        n = len(self._series)
        # baseline
        painter.setPen(self._grid)
        painter.drawLine(0, h - 3, w, h - 3)
        if n < 2 or w < 20:
            painter.end()
            return

        top_pad, bottom_pad = 5, 5
        plot_h = max(4.0, h - top_pad - bottom_pad)

        def point(i: int) -> QPointF:
            v = self._series[i]
            x = 2 + (w - 4) * (i / (n - 1))
            y = top_pad + plot_h * (1.0 - (v or 0.0))
            return QPointF(x, y)

        # one path per run of due days (None breaks the line)
        run: list[QPointF] = []

        def flush() -> None:
            if len(run) < 2:
                return
            path = QPainterPath()
            path.moveTo(run[0])
            for pt in run[1:]:
                path.lineTo(pt)
            painter.setPen(QPen(self._line, 1.6))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)

        for i, v in enumerate(self._series):
            if v is None:
                flush()
                run = []
            else:
                run.append(point(i))
        flush()

        # today dot
        if self._series and self._series[-1] is not None:
            painter.setPen(Qt.NoPen)
            painter.setBrush(self._today)
            painter.drawEllipse(point(n - 1), 3.0, 3.0)
        painter.end()
