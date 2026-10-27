"""Progress timeline — P: per-habit day grid from one week up to one year.

Rows are habits, columns are days of the selected window. The *Range* picker
chooses the span ("This week" … "1 year") and the *Window* picker chooses how
that span is anchored (calendar spans vs a rolling window ending today); both
choices persist in QSettings. See `core.ranges` for the window maths.

The day grid is painted rather than built from widgets, so a one-year span
with many habits stays cheap, and the habit-name column sits outside the
scroll area so names stay visible while a long range is scrolled sideways.
Day cells stretch to fill the section width but never shrink below 22px and
rows never below 26px (policy floor — tick targets stay tappable and names
readable); beyond that the grid keeps its size and scrolls sideways.
Today's column is highlighted, and its cell is the only clickable one.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

from PySide6.QtCore import QRect, QSettings, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from core.ranges import (
    BASES,
    DEFAULT_BASE,
    DEFAULT_RANGE,
    MIN_CELL,
    MIN_ROW_H,
    RANGES,
    RangeSpec,
    base_for,
    days_between,
    spec_for,
)
from core.ranges import window as range_window
from core.schedule import is_due
from core.streak import is_done, is_paused
from db.store import get_completions, list_habits, list_pauses

SETTINGS_ORG = "StreakGrid"
SETTINGS_APP = "StreakGrid"
RANGE_KEY = "streakgrid/progress_range"
BASE_KEY = "streakgrid/progress_base"

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTH_NAMES = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

GUTTER = 168        # widest habit-name column
GUTTER_MIN = 84     # narrowest, so small windows keep room for the day cells
GUTTER_RATIO = 0.22
AXIS_WIDE = 34      # weekday + day number labels
AXIS_DAY = 22       # day numbers only
AXIS_MONTH = 20     # month labels only

TODAY_ALPHA = 26    # highlight band behind today's column
HOVER_ALPHA = 46    # hovered (clickable) cell tint
FUTURE_ALPHA = 110  # upcoming days are faded further than scheduled-off days

STATE_LABELS = {
    "done": "done",
    "empty": "not done",
    "off": "not scheduled",
    "future": "upcoming",
}


def _settings() -> QSettings:
    return QSettings(SETTINGS_ORG, SETTINGS_APP)


def read_setting(key: str, default: str) -> str:
    value = _settings().value(key, default)
    return str(value) if value not in (None, "") else default


def write_setting(key: str, value: str) -> None:
    store = _settings()
    store.setValue(key, str(value))
    store.sync()


def gap_for(cell: int) -> int:
    """Gap between day cells, kept small once the cells themselves get small."""
    if cell >= 14:
        return 6
    if cell >= 8:
        return 2
    return 1


def floor_cell(spec: RangeSpec) -> int:
    """Smallest day-cell width for `spec` — never below the policy floor."""
    return max(spec.min_cell, MIN_CELL)


def floor_row(spec: RangeSpec) -> int:
    """Habit row height for `spec` — never below the policy floor."""
    return max(spec.row_h, MIN_ROW_H)


def min_width(spec: RangeSpec, cols: int) -> int:
    """Width the day cells need at the range's smallest cell size."""
    cell = floor_cell(spec)
    gap = gap_for(cell)
    return max(1, cols) * (cell + gap) + gap


@dataclass
class Row:
    """One habit's states across the window, oldest day first."""

    habit_id: int
    name: str
    states: list[str]        # "done" | "empty" | "off" | "future"


@dataclass(frozen=True)
class Metrics:
    """Day-cell geometry for one width. Shared with the name column."""

    gap: int
    cell: int
    row_h: int
    row_gap: int
    axis_h: int
    mode: str                # "wide" | "day" | "month"
    cols: int
    left: int                # x of the first day column

    def x(self, col: int) -> int:
        return self.left + col * (self.cell + self.gap)

    def y(self, row: int) -> int:
        return self.axis_h + self.row_gap + row * (self.row_h + self.row_gap)

    def height(self, rows: int) -> int:
        return self.y(max(1, rows))


def metrics_for(spec: RangeSpec, cols: int, width: int) -> Metrics:
    """Cell size for `width`: fill the space, down to the policy minimum."""
    cols = max(1, cols)
    floor = floor_cell(spec)
    row_h = floor_row(spec)
    gap = gap_for(floor)
    inner = width - gap * (cols + 1)
    cell = max(floor, inner // cols)
    gap = gap_for(cell)
    inner = width - gap * (cols + 1)
    cell = max(floor, inner // cols)
    # Keep the right edge flush: hand any rounding remainder to the left inset.
    left = gap + max(0, inner - cell * cols)
    mode = "wide" if cell >= 40 else "day" if cell >= 16 else "month"
    axis_h = AXIS_WIDE if mode == "wide" else AXIS_DAY if mode == "day" else AXIS_MONTH
    return Metrics(gap=gap, cell=cell, row_h=row_h,
                    row_gap=max(2, min(6, row_h // 4)), axis_h=axis_h,
                    mode=mode, cols=cols, left=left)


class TimelineCells(QWidget):
    """Painted day grid: one row per habit, one column per day."""

    def __init__(self, on_toggle=None, parent=None) -> None:
        super().__init__(parent)
        self._on_toggle = on_toggle
        self.on_metrics = None                      # callback(axis_h, row_h, row_gap, height)
        self._spec = spec_for(DEFAULT_RANGE)
        self._days: list[date] = []
        self._rows: list[Row] = []
        self._today_col = -1
        self._hover: tuple[int, int] | None = None
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        self.setMouseTracking(True)
        self.refresh_theme()

    # -- theme -----------------------------------------------------------
    def refresh_theme(self) -> None:
        from ui.theme import chart_colors

        colors = chart_colors()
        self._fill = QColor(colors["chart_fill"])
        self._empty = QColor(colors["chart_empty"])
        self._text = QColor(colors["chart_text"])
        self._line = QColor(colors["grid_line"])
        self._line_strong = QColor(colors["grid_line_strong"])
        self._accent = QColor(colors["grid_accent"])
        self._on_fill = QColor(colors["grid_on_fill"])
        self._off = QColor(colors["grid_off"])
        self._future = QColor(self._off)
        self._future.setAlpha(FUTURE_ALPHA)
        self._band = QColor(self._accent)
        self._band.setAlpha(TODAY_ALPHA)
        self._hover_fill = QColor(self._accent)
        self._hover_fill.setAlpha(HOVER_ALPHA)
        self.update()

    # -- data ------------------------------------------------------------
    def set_data(self, *, spec: RangeSpec, days: list[date], rows: list[Row],
                 today: date) -> None:
        self._spec = spec
        self._days = list(days)
        self._rows = list(rows)
        self._today_col = self._days.index(today) if today in self._days else -1
        self._hover = None
        self.setMinimumWidth(min_width(spec, len(self._days)))
        self._resize()
        self.update()

    def rows(self) -> list[Row]:
        return list(self._rows)

    def days(self) -> list[date]:
        return list(self._days)

    def metrics(self) -> Metrics:
        return metrics_for(self._spec, len(self._days), max(1, self.width()))

    # -- sizing ----------------------------------------------------------
    def sizeHint(self) -> QSize:
        return QSize(self.minimumWidth(), self.height())

    def _resize(self) -> None:
        m = self.metrics()
        height = m.height(len(self._rows)) if self._rows else m.axis_h + 8
        if height != self.height():
            self.setFixedHeight(height)
        if self.on_metrics is not None:
            self.on_metrics(m.axis_h, m.row_h, m.row_gap, height)

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._resize()
        super().resizeEvent(event)

    # -- interaction -----------------------------------------------------
    def cell_at(self, pos) -> tuple[int, int] | None:
        """(row, col) under a widget-local point, or None outside the cells."""
        m = self.metrics()
        if not self._rows or pos.y() < m.y(0):
            return None
        row = (pos.y() - m.y(0)) // (m.row_h + m.row_gap)
        if row >= len(self._rows) or pos.x() < m.left:
            return None
        col = (pos.x() - m.left) // (m.cell + m.gap)
        if col >= m.cols or pos.x() - m.x(col) >= m.cell:
            return None
        return int(row), int(col)

    def interactive(self, row: int, col: int) -> bool:
        """Only today's column can be ticked, and only when it is due."""
        if col != self._today_col or row >= len(self._rows):
            return False
        return self._state(row, col) not in ("future", "off")

    def _state(self, row: int, col: int) -> str:
        states = self._rows[row].states
        return states[col] if col < len(states) else "future"

    def _touch_hover(self, pos) -> None:
        cell = self.cell_at(pos)
        if cell is not None and not self.interactive(*cell):
            cell = None
        if cell == self._hover:
            return
        self._hover = cell
        if cell is None:
            self.setCursor(Qt.ArrowCursor)
            self.setToolTip("")
        else:
            self.setCursor(Qt.PointingHandCursor)
            self.setToolTip(self._tooltip(*cell))
        self.update()

    def _tooltip(self, row: int, col: int) -> str:
        day = self._days[col]
        when = f"{DAY_NAMES[day.weekday()]} {day.day} {MONTH_NAMES[day.month]}"
        return f"{self._rows[row].name}\n{when} — {STATE_LABELS[self._state(row, col)]}"

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        self._touch_hover(event.position().toPoint())

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = None
        self.setCursor(Qt.ArrowCursor)
        self.setToolTip("")
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton:
            return
        cell = self.cell_at(event.position().toPoint())
        if cell is not None and self.interactive(*cell) and self._on_toggle is not None:
            self._on_toggle(self._rows[cell[0]].habit_id)

    # -- paint -----------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        m = self.metrics()
        visible = event.rect()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, m.cell >= 10)
        height = m.height(len(self._rows))
        if self._rows and self._today_col >= 0:
            band = QRect(m.x(self._today_col) - m.gap // 2, m.axis_h,
                         m.cell + m.gap, max(1, height - m.axis_h))
            painter.fillRect(band, self._band)
        self._paint_axis(painter, m, visible)
        self._paint_cells(painter, m, visible)
        self._paint_rules(painter, m, visible, height)
        painter.end()

    def _visible_cols(self, m: Metrics, visible: QRect) -> tuple[int, int]:
        first = max(0, (visible.left() - m.x(0)) // (m.cell + m.gap))
        last = min(m.cols - 1, max(0, (visible.right() - m.x(0)) // (m.cell + m.gap)))
        if visible.left() < m.left:
            first = 0
        return int(first), int(last)

    def _paint_axis(self, painter: QPainter, m: Metrics, visible: QRect) -> None:
        if visible.top() > m.axis_h:
            return
        first, last = self._visible_cols(m, visible)
        small = QFont("Sans", 8)
        strong = QFont("Sans", 10)
        strong.setWeight(QFont.Weight.DemiBold)
        for col in range(first, last + 1):
            day = self._days[col]
            today = col == self._today_col
            painter.setPen(self._accent if today else self._text)
            x = m.x(col)
            if m.mode == "wide":
                painter.setFont(small)
                painter.drawText(QRect(x, 0, m.cell, m.axis_h // 2),
                                 Qt.AlignHCenter | Qt.AlignBottom,
                                 DAY_NAMES[day.weekday()])
                painter.setFont(strong)
                painter.drawText(QRect(x, m.axis_h // 2 - 2, m.cell, m.axis_h // 2 + 2),
                                 Qt.AlignHCenter | Qt.AlignTop, str(day.day))
            elif m.mode == "day":
                painter.setFont(small)
                painter.drawText(QRect(x, 0, m.cell, m.axis_h),
                                 Qt.AlignHCenter | Qt.AlignVCenter, str(day.day))
            elif day.day == 1 or col == 0:
                painter.setFont(small)
                label = MONTH_NAMES[day.month]
                if day.month == 1 or col == 0:
                    label = f"{label} '{day.year % 100:02d}"
                painter.drawText(QRect(x, 0, 72, m.axis_h),
                                 Qt.AlignLeft | Qt.AlignVCenter, label)
        painter.fillRect(QRect(0, m.axis_h, self.width(), 1), self._line_strong)

    def _paint_cells(self, painter: QPainter, m: Metrics, visible: QRect) -> None:
        if not self._rows:
            return
        first_col, last_col = self._visible_cols(m, visible)
        first_row = max(0, (visible.top() - m.y(0)) // (m.row_h + m.row_gap))
        last_row = min(len(self._rows) - 1,
                       max(0, (visible.bottom() - m.y(0)) // (m.row_h + m.row_gap)))
        radius = max(1, min(9, min(m.cell, m.row_h) // 4))
        glyph = QFont("Sans", max(7, min(15, m.row_h - 18)))
        glyph.setWeight(QFont.Weight.Bold)
        check = m.cell >= 18
        # Dense ranges would lose their state colour under a 2px today ring;
        # there the tinted column band and the accent axis label mark today.
        ring = m.cell >= 14 and m.row_h >= 14
        for row in range(first_row, last_row + 1):
            y = m.y(row)
            for col in range(first_col, last_col + 1):
                state = self._state(row, col)
                rect = QRect(m.x(col), y, m.cell, m.row_h)
                if state == "done":
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(self._fill)
                    painter.drawRoundedRect(rect, radius, radius)
                elif state == "empty":
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(self._empty)
                    painter.drawRoundedRect(rect, radius, radius)
                else:
                    painter.setBrush(Qt.NoBrush)
                    colour = self._future if state == "future" else self._off
                    pen = QPen(colour, 1)
                    pen.setStyle(Qt.DotLine if state == "future" else Qt.DashLine)
                    painter.setPen(pen)
                    if radius > 1:
                        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1),
                                                radius, radius)
                    else:
                        painter.drawRect(rect.adjusted(0, 0, -1, -1))
                if self._hover == (row, col) and self.interactive(row, col):
                    painter.fillRect(rect, self._hover_fill)
                if col == self._today_col and state != "future" and ring:
                    painter.setBrush(Qt.NoBrush)
                    painter.setPen(QPen(self._accent, 2))
                    painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)
                if state == "done" and check:
                    painter.setPen(self._on_fill)
                    painter.setFont(glyph)
                    painter.drawText(rect, Qt.AlignCenter, "✓")

    def _paint_rules(self, painter: QPainter, m: Metrics, visible: QRect,
                     height: int) -> None:
        if not self._rows:
            return
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._line)
        for row in range(len(self._rows) - 1):
            y = m.y(row) + m.row_h + m.row_gap // 2
            if visible.top() - 1 <= y <= min(visible.bottom() + 1, height):
                painter.fillRect(QRect(0, y, self.width(), 1), self._line)


class TimelineNames(QWidget):
    """Frozen habit-name column, row-aligned with `TimelineCells`."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._names: list[str] = []
        self._axis_h = AXIS_WIDE
        self._row_h = 36
        self._row_gap = 4
        self.setFixedWidth(GUTTER)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.refresh_theme()

    def set_gutter(self, width: int) -> None:
        """Width of the name column, driven by the section width."""
        width = max(GUTTER_MIN, min(GUTTER, int(width)))
        if width != self.width():
            self.setFixedWidth(width)
            self.update()

    def refresh_theme(self) -> None:
        from ui.theme import chart_colors

        colors = chart_colors()
        self._text = QColor(colors["grid_text"])
        self._muted = QColor(colors["chart_text"])
        self._line = QColor(colors["grid_line"])
        self._line_strong = QColor(colors["grid_line_strong"])
        self.update()

    def set_names(self, names: list[str]) -> None:
        self._names = list(names)
        self.update()

    def sync(self, axis_h: int, row_h: int, row_gap: int, height: int) -> None:
        """Adopt the day grid's row geometry so rows line up exactly."""
        resized = axis_h != self._axis_h or row_h != self._row_h or row_gap != self._row_gap
        self._axis_h, self._row_h, self._row_gap = axis_h, row_h, row_gap
        if self.height() != height:
            self.setFixedHeight(height)
        if resized:
            self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        width = max(1, self.width())
        text_width = max(10, width - 10)
        painter.setPen(self._muted)
        painter.setFont(QFont("Sans", 8))
        painter.drawText(QRect(0, 0, text_width, self._axis_h),
                         Qt.AlignLeft | Qt.AlignVCenter, "Task")
        painter.fillRect(QRect(0, self._axis_h, width, 1), self._line_strong)

        font = QFont("Sans", max(7, min(11, self._row_h - 6)))
        font.setWeight(QFont.Weight.DemiBold)
        elide = QFontMetrics(font)
        painter.setPen(self._text)
        painter.setFont(font)
        for index, name in enumerate(self._names):
            y = self._axis_h + self._row_gap + index * (self._row_h + self._row_gap)
            text = elide.elidedText(name, Qt.ElideRight, text_width)
            painter.drawText(QRect(0, y, text_width, self._row_h),
                             Qt.AlignLeft | Qt.AlignVCenter, text)
            if index < len(self._names) - 1:
                line_y = y + self._row_h + self._row_gap // 2
                painter.fillRect(QRect(0, line_y, width, 1), self._line)
        painter.end()


class TimelineTable(QWidget):
    """Progress section body: range pickers, caption and the day grid."""

    def __init__(self, conn: sqlite3.Connection, parent=None, on_toggle=None) -> None:
        super().__init__(parent)
        self.conn = conn
        self._on_toggle = on_toggle
        self._range_key = read_setting(RANGE_KEY, DEFAULT_RANGE)
        self._base = base_for(read_setting(BASE_KEY, DEFAULT_BASE))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        range_caption = QLabel("Range")
        range_caption.setObjectName("MutedText")
        self.range_picker = QComboBox()
        for spec in RANGES:
            self.range_picker.addItem(spec.label, spec.key)
        window_caption = QLabel("Window")
        window_caption.setObjectName("MutedText")
        self.base_picker = QComboBox()
        for key, label in BASES:
            self.base_picker.addItem(label, key)
        controls.addWidget(range_caption)
        controls.addWidget(self.range_picker)
        controls.addSpacing(6)
        controls.addWidget(window_caption)
        controls.addWidget(self.base_picker)
        controls.addStretch(1)
        outer.addLayout(controls)

        self.caption = QLabel("")
        self.caption.setObjectName("MutedText")
        # Wrapping keeps this long line from setting the section's minimum width.
        self.caption.setWordWrap(True)
        outer.addWidget(self.caption)

        self.names = TimelineNames()
        self.cells = TimelineCells(on_toggle=self._toggle)
        self.cells.on_metrics = self._on_cell_metrics
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setWidget(self.cells)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self.names, 0, Qt.AlignTop)
        body.addWidget(self.scroll, 1, Qt.AlignTop)
        outer.addLayout(body)

        self.empty = QLabel("No habits yet — add one to start filling the progress view.")
        self.empty.setObjectName("EmptyState")
        self.empty.setWordWrap(True)
        outer.addWidget(self.empty)

        self.range_picker.setCurrentIndex(self._picker_index(self.range_picker, self._range_key))
        self.base_picker.setCurrentIndex(self._picker_index(self.base_picker, self._base))
        self.range_picker.currentIndexChanged.connect(self._on_range_changed)
        self.base_picker.currentIndexChanged.connect(self._on_base_changed)
        self._sync_gutter()
        self.refresh()

    # -- geometry --------------------------------------------------------
    def _sync_gutter(self) -> None:
        """Name column shares the width with the day grid."""
        self.names.set_gutter(int(self.width() * GUTTER_RATIO))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._sync_gutter()

    def _on_cell_metrics(self, axis_h: int, row_h: int, row_gap: int,
                         height: int) -> None:
        """Keep the name column and the scroll viewport in step with the grid.

        A visible horizontal scrollbar eats into the viewport, which would clip
        the last habit row, so the scroll area is sized to the grid plus the
        space that scrollbar really takes (measured once it is on screen).
        """
        self.names.sync(axis_h, row_h, row_gap, height)
        viewport = self.scroll.viewport()
        reserve = 0
        if self.cells.width() > viewport.width():
            observed = max(0, self.scroll.height() - viewport.height())
            extent = self.scroll.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
            reserve = max(observed, extent)
        wanted = height + reserve
        if wanted != getattr(self, "_scroll_height", None):
            self._scroll_height = wanted
            self.scroll.setFixedHeight(wanted)

    # -- pickers ---------------------------------------------------------
    @staticmethod
    def _picker_index(picker: QComboBox, key: str) -> int:
        index = picker.findData(key)
        return index if index >= 0 else 0

    def _on_range_changed(self, index: int) -> None:
        self._range_key = str(self.range_picker.itemData(index))
        write_setting(RANGE_KEY, self._range_key)
        self.refresh()

    def _on_base_changed(self, index: int) -> None:
        self._base = str(self.base_picker.itemData(index))
        write_setting(BASE_KEY, self._base)
        self.refresh()

    def range_key(self) -> str:
        return self._range_key

    def base_key(self) -> str:
        return self._base

    def set_range(self, key: str) -> None:
        """Select a range programmatically (used by tests and shortcuts)."""
        self.range_picker.setCurrentIndex(self._picker_index(self.range_picker, key))

    def set_base(self, key: str) -> None:
        self.base_picker.setCurrentIndex(
            self._picker_index(self.base_picker, base_for(key)))

    # -- data ------------------------------------------------------------
    def refresh(self, today: date | None = None) -> None:
        today = today or date.today()
        spec = spec_for(self._range_key)
        start, end = range_window(spec, self._base, today)
        days = days_between(start, end)
        habits = list_habits(self.conn)
        rows = [self._row_for(h, days, today) for h in habits]
        self.names.set_names([row.name for row in rows])
        self.cells.set_data(spec=spec, days=days, rows=rows, today=today)
        self.caption.setText(self._caption(spec, days, today))
        supports_calendar = spec.months is not None
        self.base_picker.setEnabled(supports_calendar)
        self.base_picker.setToolTip(
            "Rolling — the window always ends today" if supports_calendar
            else "10 days has no calendar equivalent")
        tracked = bool(rows)
        self.names.setVisible(tracked)
        self.scroll.setVisible(tracked)
        self.empty.setVisible(not tracked)

    def _row_for(self, habit, days: list[date], today: date) -> Row:
        hd = dict(habit)
        habit_id = int(habit["id"])
        completions = get_completions(self.conn, habit_id)
        pauses = [(p["start_date"], p["end_date"])
                  for p in list_pauses(self.conn, habit_id)]
        states: list[str] = []
        for day in days:
            iso = day.isoformat()
            due = is_due(hd, day)
            paused = is_paused(pauses, day)
            done = is_done(hd, completions.get(iso), iso in completions)
            if day > today:
                states.append("future")
            elif not due or paused:
                states.append("off")
            elif done:
                states.append("done")
            else:
                states.append("empty")
        return Row(habit_id=habit_id, name=str(habit["name"]), states=states)

    def _caption(self, spec: RangeSpec, days: list[date], today: date) -> str:
        span = (f"{days[0].strftime('%d %b %Y')} – "
                f"{days[-1].strftime('%d %b %Y')}")
        return (f"{spec.label}   ·   {span}   ·   {len(days)} days"
                f"   ·   tick today's column ({DAY_NAMES[today.weekday()]})")

    # -- misc ------------------------------------------------------------
    def _toggle(self, habit_id: int) -> None:
        if self._on_toggle is not None:
            self._on_toggle(habit_id)

    def refresh_theme(self) -> None:
        self.names.refresh_theme()
        self.cells.refresh_theme()
