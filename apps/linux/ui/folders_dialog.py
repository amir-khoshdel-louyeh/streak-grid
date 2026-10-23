"""Folders dialog — F1: colour-coded categories for grouping habits."""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from db.store import create_folder, delete_folder, list_folders, update_folder
from ui.screen import fit_to_screen

DEFAULT_COLOR = "#7aa2f7"


def _swatch(color: str, size: int = 16) -> QIcon:
    """Small rounded colour chip used as the list item icon."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    from PySide6.QtGui import QPainter

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(0, 0, size, size, 5, 5)
    painter.end()
    return QIcon(pix)


class FolderEditDialog(QDialog):
    """Name + colour picker for creating or editing a folder."""

    def __init__(self, parent=None, name: str = "", color: str = DEFAULT_COLOR) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit folder" if name else "New folder")
        self._color = color or DEFAULT_COLOR

        self.name_edit = QLineEdit(name)
        self.name_edit.setPlaceholderText("e.g. Health")
        self.color_button = QPushButton()
        self.color_button.setFixedSize(72, 28)
        self.color_button.setToolTip("Pick a colour")
        self.color_button.clicked.connect(self._pick_color)
        self._apply_swatch()

        form = QFormLayout(self)
        form.addRow("Name", self.name_edit)
        form.addRow("Colour", self.color_button)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _pick_color(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._color), self, "Folder colour")
        if chosen.isValid():
            self._color = chosen.name()
            self._apply_swatch()

    def _apply_swatch(self) -> None:
        self.color_button.setText("")
        self.color_button.setStyleSheet(
            f"background: {self._color}; border: 1px solid #666; border-radius: 6px;"
        )

    def values(self) -> dict:
        name = self.name_edit.text().strip()
        if not name:
            raise ValueError("folder name is required")
        return {"name": name, "color": self._color}


class FoldersDialog(QDialog):
    """Manage folders: create, rename/recolour, delete."""

    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self.conn = conn
        self.changed = False
        self.setWindowTitle("Folders")
        fit_to_screen(self, QSize(440, 420), QSize(300, 260))

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        hint = QLabel("Group habits into colour-coded folders.")
        hint.setObjectName("MutedText")
        layout.addWidget(hint)

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _item: self.edit_selected())
        layout.addWidget(self.list, 1)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.new_button = QPushButton("New folder…")
        self.new_button.setProperty("role", "primary")
        self.new_button.clicked.connect(self.new_folder)
        self.edit_button = QPushButton("Edit…")
        self.edit_button.clicked.connect(self.edit_selected)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_selected)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        row.addWidget(self.new_button)
        row.addWidget(self.edit_button)
        row.addWidget(self.delete_button)
        row.addStretch(1)
        row.addWidget(close_button)
        layout.addLayout(row)

        self.refresh()

    # -- data -----------------------------------------------------------
    def refresh(self) -> None:
        self.list.clear()
        for folder in list_folders(self.conn):
            item = QListWidgetItem(_swatch(str(folder["color"])), str(folder["name"]))
            item.setData(Qt.UserRole, int(folder["id"]))
            item.setData(Qt.UserRole + 1, str(folder["color"]))
            self.list.addItem(item)
        has_any = self.list.count() > 0
        self.edit_button.setEnabled(has_any)
        self.delete_button.setEnabled(has_any)

    def _selected(self) -> QListWidgetItem | None:
        return self.list.currentItem()

    # -- actions --------------------------------------------------------
    def new_folder(self) -> None:
        dlg = FolderEditDialog(self)
        if not dlg.exec():
            return
        try:
            create_folder(self.conn, **dlg.values())
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid folder", str(exc))
            return
        self.changed = True
        self.refresh()

    def edit_selected(self) -> None:
        item = self._selected()
        if item is None:
            return
        folder_id = int(item.data(Qt.UserRole))
        dlg = FolderEditDialog(self, name=item.text(),
                               color=str(item.data(Qt.UserRole + 1)))
        if not dlg.exec():
            return
        try:
            update_folder(self.conn, folder_id, **dlg.values())
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid folder", str(exc))
            return
        self.changed = True
        self.refresh()

    def delete_selected(self) -> None:
        item = self._selected()
        if item is None:
            return
        if QMessageBox.question(
            self, "Delete folder",
            f"Delete the folder '{item.text()}'?\n"
            "Habits inside it are kept and become ungrouped.",
        ) != QMessageBox.Yes:
            return
        delete_folder(self.conn, int(item.data(Qt.UserRole)))
        self.changed = True
        self.refresh()
