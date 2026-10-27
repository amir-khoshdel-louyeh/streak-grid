"""List view — full-width rows with drag-reorder and a 90-day pulse strip."""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import QEvent, QMimeData, QPoint, Qt
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.schedule import is_due, next_due
from core.streak import best_streak, current_streak, is_done, is_paused
from db.store import get_completions, list_folders, list_habits, list_pauses, set_habit_order
from ui.activity_strip import ActivityStrip


def _plain(text: str) -> str:
    """Drop the inline markup used for the folder colour dot (for tooltips)."""
    import re

    return re.sub(r"<[^>]+>", "", text)


class _HabitRow(QFrame):
    """Row frame that opens the habit on double-click."""

    def __init__(self, on_activate=None, parent=None) -> None:
        super().__init__(parent)
        self._on_activate = on_activate

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if self._on_activate is not None:
            self._on_activate()
        super().mouseDoubleClickEvent(event)


class ListView(QWidget):
    COLS = 1
    ROW_H = 72
    GAP = 8
    STRIP_DAYS = 90  # pulse strip window: done spikes, missed dips, off gaps

    def __init__(self, conn: sqlite3.Connection, parent=None, on_open=None) -> None:
        super().__init__(parent)
        self.conn = conn
        self._on_open = on_open
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Search habits…    drag ⋮⋮ to reorder  ·  double-click to open"
        )
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self.refresh())
        self.layout.addWidget(self.search)
        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setFrameShape(QFrame.NoFrame)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.area.viewport().setAcceptDrops(True)
        self.area.viewport().installEventFilter(self)
        self.host = QWidget()
        self.grid = QGridLayout(self.host)
        self.grid.setSpacing(self.GAP)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setColumnStretch(0, 1)
        self.area.setWidget(self.host)
        self.layout.addWidget(self.area)
        self.empty = QLabel("No habits yet.")
        self.empty.setObjectName("EmptyState")
        self.layout.addWidget(self.empty)
        self._order: list[int] = []
        self._visible: list[int] = []
        self._rows: dict[int, QFrame] = {}
        self._strips: dict[int, ActivityStrip] = {}
        self._folders: dict[int, dict] = {}
        self._press: tuple[int, QPoint] | None = None

    def refresh_theme(self) -> None:
        """Re-colour the pulse strips (called on theme toggle)."""
        for strip in self._strips.values():
            strip.refresh_theme()

    # -- rows ------------------------------------------------------------
    def _strip_series(self, hd: dict, completions: dict, pauses: list,
                      today_iso: str) -> list[float | None]:
        """90-day pulse data, oldest first: 1.0 done, 0.0 missed, None off."""
        from datetime import date, timedelta

        end = date.fromisoformat(today_iso)
        out: list[float | None] = []
        for back in range(self.STRIP_DAYS - 1, -1, -1):
            day = end - timedelta(days=back)
            iso = day.isoformat()
            if not is_due(hd, day) or is_paused(pauses, day):
                out.append(None)
            else:
                out.append(1.0 if is_done(hd, completions.get(iso),
                                         iso in completions) else 0.0)
        return out

    def _build_row(self, h: sqlite3.Row, today_iso: str) -> QFrame:
        hd = dict(h)
        completions = get_completions(self.conn, int(h["id"]))
        pauses = [(p["start_date"], p["end_date"]) for p in list_pauses(self.conn, int(h["id"]))]
        cur = current_streak(hd, completions, pauses, today_iso)
        best = best_streak(hd, completions, pauses, today_iso)

        row = _HabitRow(on_activate=self._activate_for(int(h["id"])))
        row.setProperty("card", True)
        row.setFixedHeight(self.ROW_H)
        box = QHBoxLayout(row)
        box.setContentsMargins(14, 11, 14, 11)
        box.setSpacing(12)

        grip = QLabel("⋮⋮")
        grip.setObjectName("MutedText")
        grip.setCursor(Qt.OpenHandCursor)
        grip.setToolTip("Drag to reorder")
        grip.setProperty("habit_id", int(h["id"]))
        grip.installEventFilter(self)

        text = QVBoxLayout()
        text.setSpacing(2)
        name = QLabel(str(h["name"]))
        name.setObjectName("CardTitle")
        name.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        name.setToolTip(str(h["name"]))
        meta = QLabel()
        meta.setObjectName("CardMeta")
        meta.setTextFormat(Qt.RichText)
        meta.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        parts: list[str] = []
        folder = self._folders.get(int(hd.get("folder_id") or -1))
        if folder:
            parts.append(f'<font color="{folder["color"]}">●</font> {folder["name"]}')
        if cur > 0:
            parts.append(f"🔥 {cur}")
        parts.append(f"best {best}")
        if not is_due(hd, today_iso):
            upcoming = next_due(hd, today_iso)
            if upcoming is not None:
                parts.append(f"next {upcoming.strftime('%a %d %b')}")
        if h["archived"]:
            parts.append("archived")
        meta.setText("   ·   ".join(parts))
        meta.setToolTip("   ·   ".join(_plain(p) for p in parts))
        text.addWidget(name)
        text.addWidget(meta)

        strip = ActivityStrip()
        strip.set_series(self._strip_series(hd, completions, pauses, today_iso))
        self._strips[int(h["id"])] = strip

        box.addWidget(grip)
        box.addLayout(text, 1)
        box.addWidget(strip)
        return row

    def _activate_for(self, habit_id: int):
        def activate() -> None:
            if self._on_open is not None:
                self._on_open(habit_id)
        return activate

    def refresh(self, today: str | None = None) -> None:
        from datetime import date

        today_iso = today or date.today().isoformat()
        for w in self._rows.values():
            w.deleteLater()
        self._rows = {}
        self._strips = {}
        self._folders = {int(f["id"]): dict(f) for f in list_folders(self.conn)}
        self._order = [int(h["id"]) for h in list_habits(self.conn, include_archived=True)]
        query = self.search.text().strip().lower()
        self._visible = [hid for hid in self._order
                         if not query or query in str(self._habit_name(hid)).lower()]
        for hid in self._visible:
            h = self.conn.execute("SELECT * FROM habits WHERE id=?", (hid,)).fetchone()
            self._rows[hid] = self._build_row(h, today_iso)
        self._relayout()
        self._fit_height()
        self.empty.setVisible(not self._visible)
        self.empty.setText("No habits found." if query and not self._visible else "No habits yet.")

    @property
    def rows(self) -> list[QWidget]:
        return [self._rows[hid] for hid in self._visible if hid in self._rows]

    @property
    def count(self) -> int:
        return len(self._visible)

    def _habit_name(self, hid: int) -> str:
        row = self.conn.execute("SELECT name FROM habits WHERE id=?", (hid,)).fetchone()
        return str(row["name"]) if row else ""

    def _relayout(self) -> None:
        while self.grid.count():
            self.grid.takeAt(0)
        for i, hid in enumerate(self._visible):
            self.grid.addWidget(self._rows[hid], i // self.COLS, i % self.COLS)

    def _fit_height(self) -> None:
        """Grow with the content and let the page's outer scroll handle it."""
        rows = (len(self._visible) + self.COLS - 1) // self.COLS
        self.area.setVisible(bool(self._visible))
        if not self._visible:
            return
        content = rows * self.ROW_H + max(0, rows - 1) * self.GAP
        self.area.setMinimumHeight(content)
        self.area.setMaximumHeight(content)
        self.area.updateGeometry()

    # -- drag & drop ------------------------------------------------------
    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() == QEvent.MouseButtonPress and isinstance(obj, QLabel):
            hid = obj.property("habit_id")
            if hid is not None:
                self._press = (int(hid), event.globalPosition().toPoint())
        elif event.type() == QEvent.MouseMove and self._press is not None:
            hid, start = self._press
            if (event.globalPosition().toPoint() - start).manhattanLength() >= QApplication.startDragDistance():
                self._press = None
                mime = QMimeData()
                mime.setText(str(hid))
                drag = QDrag(obj)
                drag.setMimeData(mime)
                drag.exec(Qt.MoveAction)
                return True
        elif event.type() == QEvent.MouseButtonRelease:
            self._press = None
        elif obj is self.area.viewport():
            if event.type() == QEvent.DragEnter and event.mimeData().hasText():
                event.acceptProposedAction()
                return True
            if event.type() == QEvent.DragMove and event.mimeData().hasText():
                event.acceptProposedAction()
                return True
            if event.type() == QEvent.Drop and event.mimeData().hasText():
                try:
                    moving = int(event.mimeData().text())
                except (ValueError, TypeError):
                    return True
                self._drop_at(event.position().toPoint(), moving)
                event.acceptProposedAction()
                return True
        return super().eventFilter(obj, event)

    def _drop_at(self, pos: QPoint, moving: int) -> None:
        if self.search.text().strip():
            return  # keep saved order intact while filtering
        if moving not in self._visible:
            return
        host_pos = self.host.mapFrom(self.area.viewport(), pos)
        target = len(self._visible)
        for i, hid in enumerate(self._visible):
            if self._rows[hid].geometry().contains(host_pos):
                target = i
                break
        order = [h for h in self._visible if h != moving]
        target = min(target, len(order))
        order.insert(target, moving)
        self._visible = order
        self._order = order + [h for h in self._order if h not in order]
        set_habit_order(self.conn, self._order)
        self._relayout()
