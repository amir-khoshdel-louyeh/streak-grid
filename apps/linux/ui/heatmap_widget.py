"""Mini heatmap — S10-1: green grid via paintEvent (fixed, responsive, axis)."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

COLORS = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]
DEFAULT_COLS = 53
PAD_LEFT = 26  # gutter for weekday labels (axis mode)
PAD_TOP = 16   # gutter for month labels (axis mode)


class HeatmapWidget(QWidget):
    """Paints a columns x 7 grid of intensity cells.

    `responsive=True` scales the cell size down to fit the available width
    (never above `cell`), so the grid never forces a horizontal scrollbar.
    `axis=True` reserves gutters and draws month / weekday labels.
    """

    def __init__(self, parent=None, cell: int = 12, gap: int = 3,
                 responsive: bool = False, axis: bool = False) -> None:
        super().__init__(parent)
        self._grid: list[list[int]] = [[0] * 7 for _ in range(DEFAULT_COLS)]
        self._cell = cell
        self._gap = gap
        self._responsive = responsive
        self._axis = axis
        self._month_marks: list[tuple[int, str]] = []
        self._colors = list(COLORS)
        self._label = QColor("#8c959f")
        if responsive:
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.setMinimumWidth(160)
            self.setFixedHeight(self._height_for_width(760))
        else:
            self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self.setMinimumSize(self.sizeHint())
        self.refresh_theme()

    # -- theme ----------------------------------------------------------
    def refresh_theme(self) -> None:
        from ui.theme import chart_colors

        colors = chart_colors()
        self._colors = list(colors["heatmap"])
        self._label = QColor(colors["chart_text"])
        self.update()

    # -- data / config ---------------------------------------------------
    def set_matrix(self, grid: list[list[int]]) -> None:
        self._grid = grid
        self._resize_for_width()
        self.updateGeometry()
        self.update()

    def matrix(self) -> list[list[int]]:
        return self._grid

    def set_axis(self, axis: bool) -> None:
        if axis == self._axis:
            return
        self._axis = axis
        self._resize_for_width()
        self.updateGeometry()
        self.update()

    def set_month_marks(self, marks: list[tuple[int, str]]) -> None:
        self._month_marks = list(marks)
        self.update()

    # -- sizing ----------------------------------------------------------
    def _cols(self) -> int:
        return max(1, len(self._grid))

    def _pad_left(self) -> int:
        return PAD_LEFT if self._axis else 0

    def _pad_top(self) -> int:
        return PAD_TOP if self._axis else 0

    def _fill_mode(self) -> bool:
        """Year grid with many columns stretches to fill the full width."""
        return bool(self._responsive and self._cols() >= 20)

    def _cell_for_width(self, width: int) -> int:
        cols = self._cols()
        usable = int(width) - self._pad_left() - (cols + 1) * self._gap
        fill = usable // max(1, cols)
        if self._fill_mode():
            # Year view: grow to fill the full width (no upper cap),
            # so the chart touches the box with only a small margin.
            return max(3, fill)
        return max(3, min(self._cell, fill))

    def _cell_float_for_width(self, width: int) -> float:
        """Exact (fractional) cell size so the grid ends flush on the right."""
        cols = self._cols()
        usable = float(width) - self._pad_left() - (cols + 1) * self._gap
        return max(3.0, usable / max(1, cols))

    def _height_for_width(self, width: int) -> int:
        import math

        if self._fill_mode():
            cell = self._cell_float_for_width(max(1, int(width)))
            return int(math.ceil(self._pad_top() + 7 * (cell + self._gap) + self._gap))
        return self._pad_top() + 7 * (self._cell_for_width(width) + self._gap) + self._gap

    def _resize_for_width(self) -> None:
        if self._responsive:
            self.setFixedHeight(self._height_for_width(self.width()))

    def sizeHint(self) -> QSize:
        cols = self._cols()
        cell = self._cell_for_width(760) if self._responsive else self._cell
        return QSize(self._pad_left() + cols * (cell + self._gap) + self._gap,
                     self._pad_top() + 7 * (cell + self._gap) + self._gap)

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._resize_for_width()
        super().resizeEvent(event)

    # -- paint ----------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        cols = self._cols()
        gap = self._gap
        pad_left, pad_top = self._pad_left(), self._pad_top()
        if self._fill_mode():
            cell_f = self._cell_float_for_width(self.width())
            offset_x = float(pad_left)
            step = cell_f + gap
            radius = max(1.0, cell_f / 4.0)

            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen("transparent")
            for col in range(cols):
                for row in range(7):
                    level = 0
                    if col < len(self._grid) and row < len(self._grid[col]):
                        level = max(0, min(4, int(self._grid[col][row])))
                    painter.setBrush(QColor(self._colors[level]))
                    x = offset_x + col * step
                    y = pad_top + gap + row * step
                    painter.drawRoundedRect(x, y, cell_f, cell_f, radius, radius)

            if self._axis:
                painter.setPen(self._label)
                painter.setFont(QFont("Sans", max(7, min(9, int(cell_f)))))
                for row, text in ((0, "Mon"), (2, "Wed"), (4, "Fri")):
                    y = pad_top + gap + row * step
                    painter.drawText(0, int(y), pad_left - 5, int(cell_f),
                                     Qt.AlignRight | Qt.AlignVCenter, text)
                for col, text in self._month_marks:
                    if 0 <= col < cols:
                        x = offset_x + col * step
                        painter.drawText(int(x), 0, 64, pad_top,
                                         Qt.AlignLeft | Qt.AlignVCenter, text)
            painter.end()
            return

        cell = self._cell_for_width(self.width()) if self._responsive else self._cell
        total_w = cols * (cell + gap) + gap
        offset_x = pad_left if self._axis else max(gap, (self.width() - total_w) // 2)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen("transparent")
        radius = max(1, cell // 4)
        for col in range(cols):
            for row in range(7):
                level = 0
                if col < len(self._grid) and row < len(self._grid[col]):
                    level = max(0, min(4, int(self._grid[col][row])))
                painter.setBrush(QColor(self._colors[level]))
                x = offset_x + col * (cell + gap)
                y = pad_top + gap + row * (cell + gap)
                painter.drawRoundedRect(x, y, cell, cell, radius, radius)

        if self._axis:
            painter.setPen(self._label)
            painter.setFont(QFont("Sans", max(7, min(9, cell))))
            for row, text in ((0, "Mon"), (2, "Wed"), (4, "Fri")):
                y = pad_top + gap + row * (cell + gap)
                painter.drawText(0, y, pad_left - 5, cell,
                                 Qt.AlignRight | Qt.AlignVCenter, text)
            for col, text in self._month_marks:
                if 0 <= col < cols:
                    x = offset_x + col * (cell + gap)
                    painter.drawText(x, 0, 64, pad_top,
                                     Qt.AlignLeft | Qt.AlignVCenter, text)
        painter.end()
