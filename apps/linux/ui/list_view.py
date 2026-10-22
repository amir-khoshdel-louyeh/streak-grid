"""List view — D2: drag-to-reorder rows (order persisted in SQLite)."""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)

from core.heatmap import build_matrix
from core.streak import best_streak, current_streak
from db.store import get_completions, list_habits, list_pauses, set_habit_order
from ui.heatmap_widget import HeatmapWidget


class ListView(QWidget):
    COLS = 2
    ROW_H = 56

    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self.conn = conn
        self.layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search habits… (drag rows to reorder)")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self.refresh())
        self.layout.addWidget(self.search)
        self.list = QListWidget()
        self.list.setDragEnabled(True)
        self.list.setAcceptDrops(True)
        self.list.setDropIndicatorShown(True)
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setDefaultDropAction(Qt.MoveAction)
        self.list.setFlow(QListView.LeftToRight)
        self.list.setWrapping(True)
        self.list.setResizeMode(QListView.Adjust)
        self.list.setMovement(QListView.Static)
        self.list.setUniformItemSizes(True)
        self.list.model().rowsMoved.connect(lambda *a: self._persist_order())
        self.layout.addWidget(self.list)
        self.empty = QLabel("No habits yet.")
        self.layout.addWidget(self.empty)
        self.rows: list[QWidget] = []

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_grid()

    def _build_row(self, h: sqlite3.Row, today_iso: str) -> QWidget:
        hd = dict(h)
        completions = get_completions(self.conn, int(h["id"]))
        pauses = [(p["start_date"], p["end_date"]) for p in list_pauses(self.conn, int(h["id"]))]
        cur = current_streak(hd, completions, pauses, today_iso)
        best = best_streak(hd, completions, pauses, today_iso)
        row = QWidget()
        box = QHBoxLayout(row)
        box.setContentsMargins(4, 4, 4, 4)
        grip = QLabel("⋮⋮")
        grip.setToolTip("Drag to reorder")
        archived_tag = "  [archived]" if h["archived"] else ""
        name = QLabel(f"{h['name']}  🔥{cur}  best {best}{archived_tag}")
        mini = HeatmapWidget(cell=3, gap=2)
        mini.setFixedHeight(7 * (3 + 2) + 2)
        mini.setFixedWidth(53 * (3 + 2) + 2)
        mini.set_matrix(
            build_matrix(completions, end_date=today_iso, days=120,
                         target=int(hd.get("target_count", 1) or 1))
        )
        box.addWidget(grip)
        box.addWidget(name, stretch=1)
        box.addWidget(mini)
        return row

    def refresh(self, today: str | None = None) -> None:
        from datetime import date

        today_iso = today or date.today().isoformat()
        self.list.clear()
        self.rows = []
        habits = list_habits(self.conn, include_archived=True)
        query = self.search.text().strip().lower()
        if query:
            habits = [h for h in habits if query in str(h["name"]).lower()]
        self.empty.setVisible(not habits)
        self.empty.setText("No habits found." if query and not habits else "No habits yet.")
        for h in habits:
            row = self._build_row(h, today_iso)
            item = QListWidgetItem()
            item.setData(Qt.UserRole, int(h["id"]))
            item.setSizeHint(QSize(200, self.ROW_H))
            self.list.addItem(item)
            self.list.setItemWidget(item, row)
            self.rows.append(row)
        self._update_grid()

    def _update_grid(self) -> None:
        """Two equal columns across the available width."""
        col_w = max(200, self.list.viewport().width() // self.COLS)
        self.list.setGridSize(QSize(col_w, self.ROW_H))

    def _persist_order(self) -> None:
        """Save visual row order to SQLite (skipped while searching)."""
        if self.search.text().strip():
            return
        ids = [int(self.list.item(i).data(Qt.UserRole)) for i in range(self.list.count())]
        set_habit_order(self.conn, ids)
        self.refresh()
