"""Week table — W1: contribution-style grid (rows = tasks, cols = Mon–Sun).

Each row is a habit and each column a day of the current week. Only today's
column is interactive: clicking a cell toggles that habit's completion for
today. Past / future / unscheduled days render as read-only indicators.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.schedule import is_due
from core.streak import is_done, is_paused
from db.store import get_completions, list_habits, list_pauses

CELL = 36
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _repolish(widget: QWidget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


def _set_prop(widget: QWidget, name: str, value) -> None:
    widget.setProperty(name, value)
    _repolish(widget)


class WeekTable(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None, on_toggle=None) -> None:
        super().__init__(parent)
        self.conn = conn
        self._on_toggle = on_toggle
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)
        self.caption = QLabel("")
        self.caption.setObjectName("MutedText")
        outer.addWidget(self.caption)
        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(6)
        self._grid.setVerticalSpacing(6)
        self._grid.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(self._grid)
        self._cells: list[QWidget] = []

    # -- build -----------------------------------------------------------
    def _clear(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._cells = []

    def _make_cell(self, state: str, *, interactive: bool, habit_id: int,
                   done: bool, weekday: str) -> QWidget:
        if interactive:
            cell = QPushButton("✓" if done else "")
            cell.setObjectName("WeekTick")
            cell.setFixedSize(CELL, CELL)
            cell.setCursor(Qt.PointingHandCursor)
            cell.setToolTip(
                f"{'Untick' if done else 'Tick'} {weekday} (today)"
            )
            _set_prop(cell, "wbstate", "done" if done else "todo")
            cell.clicked.connect(lambda _c=False, hid=habit_id: self._toggle(hid))
        else:
            cell = QLabel("✓" if done else "")
            cell.setAlignment(Qt.AlignCenter)
            cell.setFixedSize(CELL, CELL)
            _set_prop(cell, "weekcell", state)
        return cell

    def _toggle(self, habit_id: int) -> None:
        if self._on_toggle is not None:
            self._on_toggle(habit_id)

    def refresh(self, today: date | None = None) -> None:
        self._clear()
        today = today or date.today()
        monday = today - timedelta(days=today.weekday())
        days = [monday + timedelta(days=i) for i in range(7)]

        span = f"{monday.strftime('%d %b')} – {(monday + timedelta(days=6)).strftime('%d %b')}"
        self.caption.setText(
            f"Week of {span}   ·   tick today's column ({DAY_NAMES[today.weekday()]})"
        )

        # header
        corner = QLabel("Task")
        corner.setObjectName("MutedText")
        self._grid.addWidget(corner, 0, 0)
        for col, day in enumerate(days):
            is_today = day == today
            header = QLabel(
                f"{DAY_NAMES[col]}<br><b>{day.day}</b>"
            )
            header.setTextFormat(Qt.RichText)
            header.setAlignment(Qt.AlignCenter)
            header.setMinimumWidth(CELL)
            header.setObjectName("WeekHeaderToday" if is_today else "WeekHeader")
            self._grid.addWidget(header, 0, col + 1)

        habits = list_habits(self.conn)
        self._grid.setColumnStretch(0, 1)
        if not habits:
            empty = QLabel("No habits yet — add one to start filling the week.")
            empty.setObjectName("EmptyState")
            self._grid.addWidget(empty, 1, 0, 1, 8)
            return

        for row, h in enumerate(habits, start=1):
            hd = dict(h)
            habit_id = int(h["id"])
            completions = get_completions(self.conn, habit_id)
            pauses = [(p["start_date"], p["end_date"])
                      for p in list_pauses(self.conn, habit_id)]

            name = QLabel(str(h["name"]))
            name.setObjectName("CardTitle")
            name.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            name.setToolTip(str(h["name"]))
            self._grid.addWidget(name, row, 0)

            for col, day in enumerate(days):
                iso = day.isoformat()
                due = is_due(hd, day)
                paused = is_paused(pauses, day)
                done = is_done(hd, completions.get(iso), iso in completions)
                is_today = day == today
                if day > today:
                    state = "future"
                elif not due or paused:
                    state = "off"
                elif done:
                    state = "done"
                else:
                    state = "empty"
                interactive = is_today and due and not paused
                cell = self._make_cell(
                    state, interactive=interactive, habit_id=habit_id,
                    done=done, weekday=DAY_NAMES[col],
                )
                self._grid.addWidget(cell, row, col + 1)
                self._cells.append(cell)
