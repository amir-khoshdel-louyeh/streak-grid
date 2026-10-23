"""Add/edit-habit dialog — S08-2: friendly name/type/target/schedule form."""

from __future__ import annotations

import json
import sqlite3
from datetime import date

from PySide6.QtCore import QSize, QTime, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QStackedWidget,
    QTimeEdit,
    QToolButton,
    QWidget,
)

from db.store import list_folders
from ui.screen import fit_to_screen

# (label, store value) pairs — the dialog never shows raw enum strings.
_TYPES = [
    ("Yes / No — check it off", "yes_no"),
    ("Counter — hit a target", "counter"),
    ("Avoid — stay clean", "dont_do"),
]
_SCHEDULES = [
    ("Every day", "daily"),
    ("Specific weekdays", "weekly_days"),
    ("Every N days", "interval"),
    ("A few times a week", "times_per_week"),
    ("A few times a month", "times_per_month"),
]
_WEEKDAYS = [("Mon", 1), ("Tue", 2), ("Wed", 3), ("Thu", 4),
             ("Fri", 5), ("Sat", 6), ("Sun", 7)]


def _set_combo_data(combo: QComboBox, value) -> None:
    idx = combo.findData(value)
    if idx >= 0:
        combo.setCurrentIndex(idx)


class AddHabitDialog(QDialog):
    def __init__(self, parent=None, conn: sqlite3.Connection | None = None) -> None:
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("New habit")
        self.setMinimumWidth(340)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Read 20 min")

        self.type_box = QComboBox()
        for label, value in _TYPES:
            self.type_box.addItem(label, value)

        self.target_spin = QSpinBox()
        self.target_spin.setRange(1, 1000)
        self.target_spin.setValue(1)
        self.target_spin.setSuffix(" times")
        self.type_box.currentIndexChanged.connect(self._sync_target)

        self.schedule_box = QComboBox()
        for label, value in _SCHEDULES:
            self.schedule_box.addItem(label, value)
        self.schedule_box.currentIndexChanged.connect(self._sync_schedule)

        self.detail_stack = QStackedWidget()
        self.detail_stack.addWidget(QWidget())          # 0: daily (nothing)
        self.detail_stack.addWidget(self._weekday_page())  # 1: weekly_days
        self.detail_stack.addWidget(self._interval_page())  # 2: interval
        self.detail_stack.addWidget(self._times_page())     # 3: times_per_*

        self.folder_box = QComboBox()
        self._load_folders()

        self.remind_check = QCheckBox("Remind me at")
        self.remind_time = QTimeEdit()
        self.remind_time.setDisplayFormat("HH:mm")
        self.remind_time.setEnabled(False)
        self.remind_check.toggled.connect(self.remind_time.setEnabled)
        remind_row = QHBoxLayout()
        remind_row.addWidget(self.remind_check)
        remind_row.addWidget(self.remind_time)
        remind_row.addStretch(1)

        form = QFormLayout(self)
        form.setSpacing(10)
        form.addRow("Name", self.name_edit)
        form.addRow("Type", self.type_box)
        form.addRow("Target", self.target_spin)
        form.addRow("Schedule", self.schedule_box)
        form.addRow("When", self.detail_stack)
        form.addRow("Folder", self.folder_box)
        form.addRow("Reminder", remind_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Save")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        self._sync_target()
        self._sync_schedule()
        fit_to_screen(self, self.sizeHint(), QSize(340, 300))

    # -- sub-pages -------------------------------------------------------
    def _weekday_page(self) -> QWidget:
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self._day_buttons: list[QToolButton] = []
        self._day_group = QButtonGroup(page)
        self._day_group.setExclusive(False)
        for label, iso in _WEEKDAYS:
            button = QToolButton()
            button.setText(label)
            button.setCheckable(True)
            button.setMinimumWidth(38)
            button.setProperty("habit_id", iso)
            self._day_group.addButton(button)
            self._day_buttons.append(button)
            row.addWidget(button)
        row.addStretch(1)
        return page

    def _interval_page(self) -> QWidget:
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("Repeat every"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 365)
        self.interval_spin.setValue(3)
        self.interval_spin.setSuffix(" days")
        row.addWidget(self.interval_spin)
        row.addStretch(1)
        return page

    def _times_page(self) -> QWidget:
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        self.times_label = QLabel("Times per week")
        row.addWidget(self.times_label)
        self.times_spin = QSpinBox()
        self.times_spin.setRange(1, 31)
        self.times_spin.setValue(3)
        row.addWidget(self.times_spin)
        row.addStretch(1)
        return page

    # -- sync ------------------------------------------------------------
    def _sync_target(self) -> None:
        is_counter = self.type_box.currentData() == "counter"
        self.target_spin.setEnabled(is_counter)
        self.target_spin.setToolTip("" if is_counter else "Only used by counter habits")

    def _sync_schedule(self) -> None:
        stype = self.schedule_box.currentData()
        page = {"daily": 0, "weekly_days": 1, "interval": 2,
                "times_per_week": 3, "times_per_month": 3}.get(stype, 0)
        if stype == "times_per_week":
            self.times_label.setText("Times per week")
        elif stype == "times_per_month":
            self.times_label.setText("Times per month")
        self.detail_stack.setCurrentIndex(page)

    def _load_folders(self) -> None:
        self.folder_box.clear()
        self.folder_box.addItem("No folder", None)
        if self.conn is not None:
            for folder in list_folders(self.conn):
                self.folder_box.addItem(str(folder["name"]), int(folder["id"]))

    # -- prefill / collect -----------------------------------------------
    def set_values(self, habit: dict) -> None:
        """Prefill form from a habit row (for editing, U1)."""
        self.setWindowTitle(f"Edit habit — {habit.get('name', '')}")
        self.name_edit.setText(str(habit.get("name", "")))
        _set_combo_data(self.type_box, str(habit.get("type", "yes_no")))
        self.target_spin.setValue(int(habit.get("target_count", 1) or 1))
        stype = str(habit.get("schedule_type", "daily"))
        _set_combo_data(self.schedule_box, stype)
        try:
            params = json.loads(habit.get("schedule_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            params = {}
        if stype == "weekly_days":
            wanted = {int(d) for d in params.get("days", [])}
            for button, (_, iso) in zip(self._day_buttons, _WEEKDAYS):
                button.setChecked(iso in wanted)
        elif stype == "interval":
            self.interval_spin.setValue(int(params.get("every_n_days", 1) or 1))
        elif stype in ("times_per_week", "times_per_month"):
            self.times_spin.setValue(int(params.get("times", 3) or 3))
        _set_combo_data(self.folder_box, habit.get("folder_id"))
        remind_at = str(habit.get("remind_at") or "")
        self.remind_check.setChecked(bool(remind_at))
        if remind_at:
            self.remind_time.setTime(QTime.fromString(remind_at, "HH:mm"))
        self._sync_target()
        self._sync_schedule()

    def values(self) -> dict:
        """Validated dialog values -> store.create_habit kwargs."""
        name = self.name_edit.text().strip()
        if not name:
            raise ValueError("habit name is required")
        habit_type = str(self.type_box.currentData())
        schedule_type = str(self.schedule_box.currentData())
        schedule_json = "{}"
        if schedule_type == "weekly_days":
            days = [iso for button, (_, iso) in zip(self._day_buttons, _WEEKDAYS)
                    if button.isChecked()]
            if not days:
                raise ValueError("pick at least one weekday")
            schedule_json = json.dumps({"days": days})
        elif schedule_type == "interval":
            schedule_json = json.dumps({"every_n_days": int(self.interval_spin.value())})
        elif schedule_type in ("times_per_week", "times_per_month"):
            schedule_json = json.dumps({"times": int(self.times_spin.value())})
        return {
            "name": name,
            "habit_type": habit_type,
            "target_count": int(self.target_spin.value()),
            "schedule_type": schedule_type,
            "schedule_json": schedule_json,
            "start_date": date.today().isoformat(),
            "remind_at": self.remind_time.time().toString("HH:mm")
            if self.remind_check.isChecked() else "",
            "folder_id": self.folder_box.currentData(),
        }
