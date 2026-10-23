"""List view — G1: two-column grid with real drag-reorder (no QListView)."""

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
    QVBoxLayout,
    QWidget,
)

from core.heatmap import build_matrix
from core.streak import best_streak, current_streak
from db.store import get_completions, list_habits, list_pauses, set_habit_order
from ui.heatmap_widget import HeatmapWidget


class ListView(QWidget):
    COLS = 2
    ROW_H = 64
    GAP = 8
    SCROLL_AFTER = 10  # inner scroll only when habits exceed this
    MAX_ROWS = 5  # = ceil(10 / 2): fits ten habits exactly

    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self.conn = conn
        self.layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search habits… (drag ⋮⋮ to reorder)")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self.refresh())
        self.layout.addWidget(self.search)
        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setFrameShape(QFrame.NoFrame)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.area.viewport().setAcceptDrops(True)
        self.area.viewport().installEventFilter(self)
        self.host = QWidget()
        self.grid = QGridLayout(self.host)
        self.grid.setSpacing(self.GAP)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)
        self.area.setWidget(self.host)
        self.layout.addWidget(self.area)
        self.empty = QLabel("No habits yet.")
        self.layout.addWidget(self.empty)
        self._order: list[int] = []
        self._rows: dict[int, QFrame] = {}
        self._press: tuple[int, QPoint] | None = None

    # -- rows ------------------------------------------------------------
    def _build_row(self, h: sqlite3.Row, today_iso: str) -> QFrame:
        hd = dict(h)
        completions = get_completions(self.conn, int(h["id"]))
        pauses = [(p["start_date"], p["end_date"]) for p in list_pauses(self.conn, int(h["id"]))]
        cur = current_streak(hd, completions, pauses, today_iso)
        best = best_streak(hd, completions, pauses, today_iso)
        row = QFrame()
        row.setFrameShape(QFrame.StyledPanel)
        row.setFixedHeight(self.ROW_H)
        box = QHBoxLayout(row)
        box.setContentsMargins(8, 4, 8, 4)
        grip = QLabel("⋮⋮")
        grip.setCursor(Qt.OpenHandCursor)
        grip.setToolTip("Drag to reorder")
        grip.setProperty("habit_id", int(h["id"]))
        grip.installEventFilter(self)
        archived_tag = "  [archived]" if h["archived"] else ""
        name = QLabel(f"{h['name']}  🔥{cur}  best {best}{archived_tag}")
        mini = HeatmapWidget(cell=4, gap=2)
        mini.setFixedHeight(7 * (4 + 2) + 2)
        mini.setFixedWidth(53 * (4 + 2) + 2)
        box.addWidget(grip)
        box.addWidget(name, stretch=1)
        box.addWidget(mini)
        return row

    def refresh(self, today: str | None = None) -> None:
        from datetime import date

        today_iso = today or date.today().isoformat()
        for w in self._rows.values():
            w.deleteLater()
        self._rows = {}
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

    def _habit_name(self, hid: int) -> str:
        row = self.conn.execute("SELECT name FROM habits WHERE id=?", (hid,)).fetchone()
        return str(row["name"]) if row else ""

    def _relayout(self) -> None:
        while self.grid.count():
            self.grid.takeAt(0)
        for i, hid in enumerate(self._visible):
            self.grid.addWidget(self._rows[hid], i // self.COLS, i % self.COLS)

    def _fit_height(self) -> None:
        rows = (len(self._visible) + self.COLS - 1) // self.COLS
        total = len(self._order)
        self.area.setVisible(bool(self._visible))
        if not self._visible:
            return
        if total > self.SCROLL_AFTER:
            capped = self.MAX_ROWS * self.ROW_H + (self.MAX_ROWS - 1) * self.GAP
            self.area.setMinimumHeight(capped)
            self.area.setMaximumHeight(capped)
        else:
            content = rows * self.ROW_H + max(0, rows - 1) * self.GAP
            self.area.setMinimumHeight(content)
            self.area.setMaximumHeight(content)
        self.area.updateGeometry()  # force scrollbar range refresh on re-layout

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
