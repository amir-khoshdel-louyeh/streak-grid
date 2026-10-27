"""Main window — R1: single scrollable page (Today / Progress / All / Heatmap / Stats)."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.achievements import ACHIEVEMENTS, check_unlocks, unlock
from core.heatmap import build_matrix, build_month_matrix
from core.schedule import is_due
from core.streak import best_streak, current_streak, is_done, is_paused
from services.nag import NagService
from services.tray import (
    add_interval_menu,
    add_quick_actions,
    create_tray,
    minimize_to_tray,
    set_alert,
)
from db.store import (
    clear_completion,
    create_folder,
    create_habit,
    get_completions,
    get_meta,
    init_db,
    list_folders,
    list_habits,
    list_pauses,
    log_completion,
)
from ui.achievements_dialog import AchievementsDialog
from ui.add_dialog import AddHabitDialog
from ui.cards import HabitCard
from ui.detail_dialog import DetailDialog
from ui.folders_dialog import FoldersDialog
from ui.heatmap_widget import HeatmapWidget
from ui.list_view import ListView
from ui.progress_ring import ProgressRing
from ui.stats_view import StatsView
from ui.theme import apply_theme, is_dark, set_dark
from ui.timeline import TimelineTable
from widgets.desktop_widget import DesktopWidget


class MainWindow(QMainWindow):
    def __init__(self, conn: sqlite3.Connection | None = None,
                 db_path: str | None = None) -> None:
        from PySide6.QtCore import QSize

        from ui.screen import fit_to_screen

        super().__init__()
        self.setWindowTitle("StreakGrid")
        # Small screens (and large font scaling) get a window that fits them
        # instead of one that opens wider than the display.
        self.window_minimum = QSize(520, 380)
        self.compact_chrome = False
        self._cards_columns: int | None = None
        fit_to_screen(self, QSize(1040, 720), self.window_minimum, margin=24)
        from db.store import DEFAULT_DB_PATH

        self.conn = conn or init_db()
        self.db_path = db_path or (DEFAULT_DB_PATH if conn is None else None)

        file_menu = self.menuBar().addMenu("File")
        self.backup_action = file_menu.addAction("Backup now…")
        self.backup_action.setShortcut("Ctrl+B")
        self.backup_action.triggered.connect(self._on_backup)
        self.restore_action = file_menu.addAction("Restore backup…")
        self.restore_action.triggered.connect(self._on_restore)
        habits_menu = self.menuBar().addMenu("Habits")
        self.new_action = habits_menu.addAction("New habit…  (Ctrl+N)")
        self.new_action.triggered.connect(self._on_add)
        self.folders_action = habits_menu.addAction("Folders…")
        self.folders_action.triggered.connect(self._on_manage_folders)
        view_menu = self.menuBar().addMenu("View")
        self.theme_action = view_menu.addAction("Toggle theme")
        self.theme_action.setShortcut("Ctrl+T")
        self.theme_action.triggered.connect(self._on_toggle_theme)
        self.widget_action = view_menu.addAction("Desktop widget")
        self.widget_action.setCheckable(True)
        self.widget_action.setChecked(False)  # real state applied in _setup_widget
        self.widget_action.triggered.connect(self._toggle_widget)
        account_menu = self.menuBar().addMenu("Account")
        self.account_action = account_menu.addAction("Account…")
        self.account_action.triggered.connect(self._on_account)
        self.upgrade_action = account_menu.addAction("Go Pro…")
        self.upgrade_action.triggered.connect(self._on_upgrade)

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self._build_header())
        central_layout.addWidget(self._build_account_bar())

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        page = QWidget()
        page.setObjectName("Page")
        page_layout = QVBoxLayout(page)
        page_layout.setSpacing(10)
        page_layout.setContentsMargins(22, 18, 22, 26)
        self.sections: list[QGroupBox] = []

        page_layout.addWidget(self._build_today_section())
        page_layout.addWidget(self._build_progress_section())
        page_layout.addWidget(self._build_list_section())
        page_layout.addWidget(self._build_grid_section())
        page_layout.addWidget(self._build_stats_section())
        page_layout.addStretch(1)

        self.scroll.setWidget(page)
        central_layout.addWidget(self.scroll, 1)
        self.setCentralWidget(central)
        self._setup_shortcuts()
        self._folder_ids: list[int | None] = [None]
        self.refresh_folders()
        self.tray = create_tray(self, on_show=self._show_from_tray, on_quit=self._quit_from_tray)
        self._force_quit = False
        self.snoozed_until = None
        add_quick_actions(self.tray, on_done=self._on_tray_done, on_snooze=self._on_tray_snooze)
        from datetime import datetime as _dt

        from PySide6.QtCore import QSettings as _QS

        from services.notify import send as _send

        nag_min = int(_QS("StreakGrid", "StreakGrid").value("streakgrid/nag_min", 15) or 15)
        add_interval_menu(self.tray, nag_min, on_pick=self._on_pick_nag_interval)
        self.nag = NagService(
            self.conn,
            interval_min=nag_min,
            notify=lambda t, b: _send(t, b, urgency="critical"),
            is_snoozed=lambda: self.snoozed_until is not None
            and _dt.now() < self.snoozed_until,
            on_tick=lambda pending: set_alert(self.tray, bool(pending)),
        )
        self.nag.start()

        self.desktop_widget = DesktopWidget(
            self.conn, on_check=self._on_widget_check, parent=self
        )
        self.desktop_widget.start_auto_refresh(60)
        if self.desktop_widget._settings().value("pos") is None:
            screen = QApplication.primaryScreen()
            if screen is not None:
                area = screen.availableGeometry()
                self.desktop_widget.move(area.right() - 320, area.bottom() - 220)
        self._setup_widget()
        self.refresh_all()
        self._setup_account()

    # -- layout builders (presentation only, no behaviour) ---------------
    def _build_header(self) -> QFrame:
        from PySide6.QtCore import Qt

        from services.tray import make_icon

        header = QFrame()
        header.setObjectName("AppHeader")
        header.setFixedHeight(64)
        row = QHBoxLayout(header)
        row.setContentsMargins(22, 10, 22, 10)
        row.setSpacing(12)

        logo = QLabel()
        logo.setPixmap(make_icon().pixmap(34, 34))
        logo.setFixedSize(34, 34)
        row.addWidget(logo)

        titles = QVBoxLayout()
        titles.setSpacing(0)
        title = QLabel("StreakGrid")
        title.setObjectName("AppTitle")
        self.app_subtitle = QLabel("Build habits that stick")
        self.app_subtitle.setObjectName("AppSubtitle")
        titles.addWidget(title)
        titles.addWidget(self.app_subtitle)
        row.addLayout(titles)
        row.addStretch(1)

        self.theme_button = QPushButton("🌙" if is_dark() else "☀️")
        self.theme_button.setProperty("role", "ghost")
        self.theme_button.setFixedWidth(46)
        self.theme_button.setCursor(Qt.PointingHandCursor)
        self.theme_button.setToolTip("Toggle light / dark theme  (Ctrl+T)")
        self.theme_button.clicked.connect(self._on_toggle_theme)
        self.achv_button = QPushButton("🏆  Achievements")
        self.achv_button.setProperty("role", "ghost")
        self.achv_button.setCursor(Qt.PointingHandCursor)
        self.achv_button.setToolTip("Achievements")
        self.achv_button.clicked.connect(self._on_show_achievements)
        self.add_button = QPushButton("＋  New habit")
        self.add_button.setProperty("role", "primary")
        self.add_button.setCursor(Qt.PointingHandCursor)
        self.add_button.setToolTip("Create a habit  (Ctrl+N)")
        self.add_button.clicked.connect(self._on_add)

        row.addWidget(self.theme_button)
        row.addWidget(self.achv_button)
        row.addWidget(self.add_button)
        return header

    def _build_today_section(self) -> QGroupBox:
        from PySide6.QtCore import Qt

        section = QGroupBox("Today")
        self.sections.append(section)
        layout = QVBoxLayout(section)
        layout.setSpacing(16)

        hero = QHBoxLayout()
        hero.setSpacing(18)
        self.progress_ring = ProgressRing()
        hero.addWidget(self.progress_ring, 0, Qt.AlignVCenter)
        info = QVBoxLayout()
        info.setSpacing(4)
        self.progress_label = QLabel("Today")
        self.progress_label.setObjectName("HeroTitle")
        self.today_summary = QLabel("")
        self.today_summary.setObjectName("MutedText")
        info.addStretch(1)
        info.addWidget(self.progress_label)
        info.addWidget(self.today_summary)
        info.addStretch(1)
        hero.addLayout(info)
        hero.addStretch(1)
        self.date_label = QLabel(date.today().strftime("%A, %d %b"))
        self.date_label.setObjectName("DateLabel")
        hero.addWidget(self.date_label, 0, Qt.AlignTop | Qt.AlignRight)
        layout.addLayout(hero)

        filters = QHBoxLayout()
        filters.setSpacing(10)
        caption = QLabel("Folder")
        caption.setObjectName("MutedText")
        self.folder_filter = QComboBox()
        self.folder_filter.setMinimumWidth(150)
        self.folder_filter.currentIndexChanged.connect(lambda _i: self.refresh_today())
        filters.addWidget(caption)
        filters.addWidget(self.folder_filter)
        filters.addStretch(1)
        layout.addLayout(filters)

        self.cards_box = QGridLayout()
        self.cards_box.setSpacing(12)
        for col in range(3):
            self.cards_box.setColumnStretch(col, 1)
        cards_host = QWidget()
        cards_host.setLayout(self.cards_box)
        layout.addWidget(cards_host)
        self.empty_label = QLabel("No habits yet — add your first habit to get started.")
        self.empty_label.setObjectName("EmptyState")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)
        self.today_cards: list[HabitCard] = []
        return section

    def _build_progress_section(self) -> QGroupBox:
        section = QGroupBox("Progress")
        self.sections.append(section)
        layout = QVBoxLayout(section)
        layout.setSpacing(12)
        self.progress_table = TimelineTable(self.conn, on_toggle=self._on_progress_toggle)
        layout.addWidget(self.progress_table)
        return section

    def _build_list_section(self) -> QGroupBox:
        section = QGroupBox("All habits")
        self.sections.append(section)
        self.list_section = section
        layout = QVBoxLayout(section)
        layout.setSpacing(10)
        self.list_view = ListView(self.conn, on_open=self._on_open_detail)
        layout.addWidget(self.list_view)
        return section

    def _build_grid_section(self) -> QGroupBox:
        from PySide6.QtCore import Qt

        section = QGroupBox("Heatmap")
        self.sections.append(section)
        layout = QVBoxLayout(section)
        layout.setSpacing(14)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.grid_title = QLabel("All habits combined")
        self.grid_title.setObjectName("CardTitle")
        view = QLabel("View")
        view.setObjectName("MutedText")
        self.grid_mode = QComboBox()
        self.grid_mode.addItems(["Year", "Month"])
        self.grid_mode.setFixedWidth(110)
        self.grid_mode.currentIndexChanged.connect(lambda _i: self.refresh_grid())
        top.addWidget(self.grid_title)
        top.addStretch(1)
        top.addWidget(view)
        top.addWidget(self.grid_mode)
        layout.addLayout(top)

        summary_row = QHBoxLayout()
        summary_row.setSpacing(8)
        self.heatmap_summary = QLabel("")
        self.heatmap_summary.setObjectName("MutedText")
        self.heatmap_summary.setWordWrap(True)
        self.month_prev = QPushButton("◀")
        self.month_prev.setObjectName("IconButton")
        self.month_prev.setFixedSize(32, 32)
        self.month_prev.setCursor(Qt.PointingHandCursor)
        self.month_prev.setToolTip("Previous month")
        self.month_prev.clicked.connect(lambda: self._shift_month(-1))
        self.month_label = QLabel("")
        self.month_label.setObjectName("DateLabel")
        self.month_label.setMinimumWidth(140)
        self.month_next = QPushButton("▶")
        self.month_next.setObjectName("IconButton")
        self.month_next.setFixedSize(32, 32)
        self.month_next.setCursor(Qt.PointingHandCursor)
        self.month_next.setToolTip("Next month")
        self.month_next.clicked.connect(lambda: self._shift_month(1))
        summary_row.addWidget(self.heatmap_summary)
        summary_row.addStretch(1)
        summary_row.addWidget(self.month_prev)
        summary_row.addWidget(self.month_label)
        summary_row.addWidget(self.month_next)
        layout.addLayout(summary_row)

        self.grid_heatmap = HeatmapWidget(cell=15, gap=3, responsive=True, axis=True)
        layout.addWidget(self.grid_heatmap)

        footer = QHBoxLayout()
        footer.setSpacing(5)
        less = QLabel("Less")
        less.setObjectName("MutedText")
        footer.addWidget(less)
        self._legend_swatches: list[QLabel] = []
        for _ in range(5):
            swatch = QLabel()
            swatch.setFixedSize(12, 12)
            self._legend_swatches.append(swatch)
            footer.addWidget(swatch)
        more = QLabel("More")
        more.setObjectName("MutedText")
        footer.addWidget(more)
        footer.addStretch(1)
        self.export_button = QPushButton("Export PNG")
        self.export_button.setCursor(Qt.PointingHandCursor)
        self.export_button.clicked.connect(self._on_export_grid)
        footer.addWidget(self.export_button)
        layout.addLayout(footer)
        return section

    def _build_stats_section(self) -> QGroupBox:
        section = QGroupBox("Stats")
        self.sections.append(section)
        layout = QVBoxLayout(section)
        layout.setSpacing(12)
        self.stats_view = StatsView(self.conn)
        layout.addWidget(self.stats_view)
        return section

    def _on_backup(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        from services.backup import backup_db, default_backup_path

        path, _ = QFileDialog.getSaveFileName(
            self, "Backup database", default_backup_path(), "SQLite (*.db)")
        if path:
            self.do_backup(path)

    def do_backup(self, path: str) -> str:
        from services.backup import backup_db

        backup_db(self.conn, path)
        QMessageBox.information(self, "Backup", f"Saved {path}")
        return path

    def _on_restore(self) -> None:
        from pathlib import Path

        from PySide6.QtWidgets import QFileDialog

        if self.db_path is None:
            QMessageBox.warning(self, "Restore",
                                "Restore needs a file database (restart the app normally).")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Restore backup", str(Path.home()), "SQLite (*.db)")
        if not path:
            return
        if QMessageBox.question(
                self, "Restore",
                "Replace current data with this backup?") != QMessageBox.Yes:
            return
        self.do_restore(path)

    def do_restore(self, backup_path: str) -> None:
        """Swap live DB file for backup and reconnect every view (B1)."""
        from services.backup import restore_db_file

        if self.db_path is None:
            raise ValueError("no file database to restore into")
        try:
            self.conn.close()
        except sqlite3.Error:
            pass
        restore_db_file(backup_path, self.db_path)
        new_conn = init_db(self.db_path)
        self.conn = new_conn
        self.list_view.conn = new_conn
        self.stats_view.conn = new_conn
        self.nag.conn = new_conn
        self.progress_table.conn = new_conn
        if getattr(self, "desktop_widget", None) is not None:
            self.desktop_widget.conn = new_conn
        self.refresh_folders()
        self.refresh_all()
        QMessageBox.information(self, "Restore", "Backup restored.")

    def _on_pick_nag_interval(self, minutes: int) -> None:
        from PySide6.QtCore import QSettings as _QS

        _QS("StreakGrid", "StreakGrid").setValue("streakgrid/nag_min", int(minutes))
        self.nag.set_interval(int(minutes))

    def _setup_shortcuts(self) -> None:
        """Ctrl+N new habit, Ctrl+1..N scroll to sections, / focuses search."""
        from PySide6.QtGui import QShortcut

        QShortcut("Ctrl+N", self, activated=self._on_add_focus)
        for i in range(min(9, len(self.sections))):
            QShortcut(f"Ctrl+{i + 1}", self,
                      activated=lambda idx=i: self.scroll.ensureWidgetVisible(
                          self.sections[idx], 50, 50))
        QShortcut("/", self, activated=self._on_focus_search)

    def _on_focus_search(self) -> None:
        self.scroll.ensureWidgetVisible(self.list_section, 50, 50)
        self.list_view.search.setFocus()

    def _on_add_focus(self) -> None:
        self.scroll.verticalScrollBar().setValue(0)
        self._on_add()

    def _show_from_tray(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _quit_from_tray(self) -> None:
        self._force_quit = True
        self.close()

    def _on_toggle_theme(self) -> None:
        from PySide6.QtWidgets import QApplication

        set_dark(not is_dark())
        apply_theme(QApplication.instance())
        if hasattr(self, "theme_button"):
            self.theme_button.setText("🌙" if is_dark() else "☀️")
        self._refresh_painted_theme()
        self.refresh_all()

    def _refresh_painted_theme(self) -> None:
        """Re-colour manually painted widgets for the active theme."""
        for widget in (getattr(self, "progress_ring", None),
                       getattr(self, "grid_heatmap", None)):
            if widget is not None and hasattr(widget, "refresh_theme"):
                widget.refresh_theme()
        chart = getattr(getattr(self, "stats_view", None), "week_chart", None)
        if chart is not None:
            chart.refresh_theme()
        trend = getattr(getattr(self, "stats_view", None), "trend_chart", None)
        if trend is not None:
            trend.refresh_theme()
        progress = getattr(self, "progress_table", None)
        if progress is not None:
            progress.refresh_theme()
        listing = getattr(self, "list_view", None)
        if listing is not None and hasattr(listing, "refresh_theme"):
            listing.refresh_theme()
        self._update_heatmap_legend()

    def _on_tray_done(self) -> None:
        """Complete first due-undone habit today (tray quick action)."""
        if not self._require_writable():
            return
        from datetime import date as _d

        today_iso = _d.today().isoformat()
        for h in list_habits(self.conn):
            hd = dict(h)
            if not is_due(hd, today_iso):
                continue
            comp = get_completions(self.conn, int(h["id"]))
            if not is_done(hd, comp.get(today_iso), today_iso in comp):
                self._on_tap(int(h["id"]))
                return

    def _on_tray_snooze(self) -> None:
        from datetime import datetime, timedelta

        self.snoozed_until = datetime.now() + timedelta(minutes=15)

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._force_quit and minimize_to_tray(self, self.tray, event):
            return
        super().closeEvent(event)

    def refresh_all(self) -> None:
        self.refresh_today()
        self.refresh_grid()
        if hasattr(self, "progress_table"):
            self.progress_table.refresh()
        if hasattr(self, "list_view"):
            self.list_view.refresh()
            self.list_section.setTitle(f"All habits ({self.list_view.count})")
        if hasattr(self, "stats_view"):
            self.stats_view.refresh()
        widget = getattr(self, "desktop_widget", None)
        if widget is not None:
            widget.refresh()

    def refresh_folders(self) -> None:
        current = self.folder_filter.currentData() if hasattr(self, "folder_filter") else None
        self.folder_filter.blockSignals(True)
        self.folder_filter.clear()
        self.folder_filter.addItem("All folders", None)
        self._folder_ids = [None]
        for f in list_folders(self.conn):
            self.folder_filter.addItem(f"● {f['name']}", int(f["id"]))
            self._folder_ids.append(int(f["id"]))
        if current in self._folder_ids:
            self.folder_filter.setCurrentIndex(self._folder_ids.index(current))
        self.folder_filter.blockSignals(False)

    def _clear_cards(self) -> None:
        for card in self.today_cards:
            self.cards_box.removeWidget(card)
            card.deleteLater()
        self.today_cards = []

    def refresh_today(self, today: str | None = None) -> None:
        today_iso = today or date.today().isoformat()
        if hasattr(self, "date_label"):
            self.date_label.setText(date.fromisoformat(today_iso).strftime("%A, %d %b"))
        self._clear_cards()
        wanted = self.folder_filter.currentData() if hasattr(self, "folder_filter") else None
        folders = {int(f["id"]): dict(f) for f in list_folders(self.conn)}
        habits = [h for h in list_habits(self.conn) if is_due(dict(h), today_iso)]
        if wanted is not None:
            habits = [h for h in habits if h["folder_id"] == wanted]
        self.empty_label.setVisible(not habits)
        done_count = 0
        active_count = 0
        best_all = 0
        for h in habits:
            hd = dict(h)
            completions = get_completions(self.conn, int(h["id"]))
            pauses = [(p["start_date"], p["end_date"]) for p in list_pauses(self.conn, int(h["id"]))]
            has_row = today_iso in completions
            done = is_done(hd, completions.get(today_iso), has_row)
            done_count += 1 if done else 0
            counter_text = ""
            if hd.get("type") == "counter":
                counter_text = f"{int(completions.get(today_iso, 0))}/{int(hd.get('target_count', 1))}"
            streak = current_streak(hd, completions, pauses, today_iso)
            best_all = max(best_all, best_streak(hd, completions, pauses, today_iso))
            active_count += 1 if streak > 0 else 0
            folder_tag = ""
            folder_color = ""
            if hd.get("folder_id") in folders:
                folder_tag = str(folders[int(hd["folder_id"])]["name"])
                folder_color = str(folders[int(hd["folder_id"])].get("color", ""))
            card = HabitCard(
                int(h["id"]),
                str(h["name"]),
                on_tap=self._on_tap,
                on_open=self._on_open_detail,
                on_decrement=self._on_decrement,
                counter_text=counter_text,
                streak_active=streak > 0,
                done=done,
                folder_tag=folder_tag,
                folder_color=folder_color,
                stepper=hd.get("type") == "counter",
            )
            columns = self.cards_per_row()
            self._set_card_columns(columns)
            self.cards_box.addWidget(card, len(self.today_cards) // columns,
                                      len(self.today_cards) % columns)
            self.today_cards.append(card)
        self.progress_ring.set_progress(done_count, len(habits))
        self.progress_label.setText(f"Today — {done_count}/{len(habits)} done")
        self.today_summary.setText(f"🔥 {active_count} active · best {best_all}")

    def _on_tap(self, habit_id: int) -> None:
        if not self._require_writable():
            return
        today_iso = date.today().isoformat()
        row = self.conn.execute("SELECT * FROM habits WHERE id=?", (habit_id,)).fetchone()
        if row is None:
            return
        hd = dict(row)
        completions = get_completions(self.conn, habit_id)
        current = int(completions.get(today_iso, 0))
        if hd.get("type") == "counter":
            new_value = current + 1
        else:
            new_value = 1  # yes_no check-off; dont_do slip (MVP)
        log_completion(self.conn, habit_id, today_iso, new_value)
        self.refresh_all()
        self.check_achievements(show_banner=True)

    def _on_decrement(self, habit_id: int) -> None:
        """Step a counter back down (min 0), fixing overshoots without dialog."""
        if not self._require_writable():
            return
        today_iso = date.today().isoformat()
        completions = get_completions(self.conn, habit_id)
        new_value = max(0, int(completions.get(today_iso, 0)) - 1)
        log_completion(self.conn, habit_id, today_iso, new_value)
        self.refresh_all()

    def _on_open_detail(self, habit_id: int) -> None:
        if not self._require_writable():
            return
        dlg = DetailDialog(self.conn, habit_id, self)
        dlg.exec()
        self.refresh_all()
        self.check_achievements(show_banner=True)

    def _combined_heatmap(
        self, start: date, end: date
    ) -> tuple[dict[str, int], int, int]:
        """Per-day intensity across every habit: share of due habits done.

        Values are 0-100 so `build_matrix(..., target=100)` maps each day onto
        the standard 0-4 scale. Days where nothing was due, or nothing was
        done, are omitted (they render as empty cells). Also returns the
        window totals `(done, due)` for the summary line.
        """
        tracked = []
        for h in list_habits(self.conn):
            hd = dict(h)
            tracked.append((
                hd,
                get_completions(self.conn, int(h["id"])),
                [(p["start_date"], p["end_date"])
                 for p in list_pauses(self.conn, int(h["id"]))],
            ))
        values: dict[str, int] = {}
        done_total = due_total = 0
        day = start
        while day <= end:
            iso = day.isoformat()
            due = done = 0
            for hd, completions, pauses in tracked:
                if not is_due(hd, day) or is_paused(pauses, day):
                    continue
                due += 1
                if is_done(hd, completions.get(iso), iso in completions):
                    done += 1
            if due and done:
                values[iso] = max(1, int(round(done / due * 100)))
            done_total += done
            due_total += due
            day += timedelta(days=1)
        return values, done_total, due_total

    def _year_month_marks(self, end: date) -> list[tuple[int, str]]:
        """(column, month abbrev) where each month starts, for the year axis."""
        import calendar as _cal

        end_monday = end - timedelta(days=end.weekday())
        marks: list[tuple[int, str]] = []
        seen_month = None
        last_col = -10
        for col in range(53):
            monday = end_monday - timedelta(days=(52 - col) * 7)
            if monday.month != seen_month and col - last_col >= 3:
                marks.append((col, _cal.month_abbr[monday.month]))
                seen_month = monday.month
                last_col = col
        return marks

    def _update_heatmap_legend(self) -> None:
        from ui.theme import chart_colors

        swatches = getattr(self, "_legend_swatches", [])
        for swatch, color in zip(swatches, chart_colors()["heatmap"]):
            swatch.setStyleSheet(f"background: {color}; border-radius: 3px;")

    def _set_heatmap_summary(self, active: int, done: int, due: int) -> None:
        consistency = (done / due) if due else 0.0
        self.heatmap_summary.setText(
            f"{active} active days   ·   {done}/{due} due completed   ·   "
            f"{consistency:.0%} consistency"
        )

    def refresh_grid(self, today: str | None = None) -> None:
        """Heatmap aggregated across all habits (year or month view)."""
        today_iso = today or date.today().isoformat()
        count = len(list_habits(self.conn))
        self.grid_title.setText(
            "No habits yet" if not count else f"All habits combined · {count}"
        )
        self._update_heatmap_legend()
        month_mode = self.grid_mode.currentText() == "Month"
        self.month_prev.setVisible(month_mode)
        self.month_next.setVisible(month_mode)
        self.month_label.setVisible(month_mode)
        import calendar as _cal

        if not month_mode:
            end = date.fromisoformat(today_iso)
            values, done, due = self._combined_heatmap(end - timedelta(days=364), end)
            self.grid_heatmap.set_axis(True)
            self.grid_heatmap.set_month_marks(self._year_month_marks(end))
            self.grid_heatmap.set_matrix(
                build_matrix(values, end_date=today_iso, days=365, target=100)
            )
            self._set_heatmap_summary(len(values), done, due)
            return
        if not hasattr(self, "_view_year"):
            t = date.fromisoformat(today_iso)
            self._view_year, self._view_month = t.year, t.month
        last_day = _cal.monthrange(self._view_year, self._view_month)[1]
        values, done, due = self._combined_heatmap(
            date(self._view_year, self._view_month, 1),
            date(self._view_year, self._view_month, last_day),
        )
        self.grid_heatmap.set_axis(False)
        self.grid_heatmap.set_month_marks([])
        self.month_label.setText(f"{_cal.month_name[self._view_month]} {self._view_year}")
        self.grid_heatmap.set_matrix(
            build_month_matrix(values, self._view_year, self._view_month, target=100)
        )
        self._set_heatmap_summary(len(values), done, due)

    def _shift_month(self, delta: int) -> None:
        m = getattr(self, "_view_month", date.today().month)
        y = getattr(self, "_view_year", date.today().year)
        m += delta
        while m < 1:
            m += 12
            y -= 1
        while m > 12:
            m -= 12
            y += 1
        self._view_year, self._view_month = y, m
        self.refresh_grid()

    def export_grid_png(self, out_dir: str | None = None) -> str:
        """Export current grid widget to ~/Pictures/streakgrid-YYYY-MM-DD.png (S14 DoD)."""
        from pathlib import Path

        today_iso = date.today().isoformat()
        base = Path(out_dir) if out_dir else Path.home() / "Pictures"
        base.mkdir(parents=True, exist_ok=True)
        path = str(base / f"streakgrid-{today_iso}.png")
        self.grid_heatmap.grab().save(path)
        return path

    def _pro_message(self, feature: str) -> None:
        QMessageBox.information(
            self, "Pro feature",
            f"{feature} requires Pro (coming soon). "
            "Your data stays readable on-device.")

    def _on_export_grid(self) -> None:
        from core.entitlements import can

        if not can(self.conn, "export"):
            self._pro_message("PNG export")
            return
        path = self.export_grid_png()
        QMessageBox.information(self, "Exported", f"Saved {path}")

    # -- responsive chrome / layout --------------------------------------
    def cards_per_row(self, width: int | None = None) -> int:
        """1–3 habit cards per row depending on the window width."""
        width = self.width() if width is None else width
        if width >= 1180:
            return 3
        if width >= 660:
            return 2
        return 1

    def _set_card_columns(self, columns: int) -> None:
        """Re-flow Today's cards without rebuilding them from the database."""
        if columns == self._cards_columns or not hasattr(self, "cards_box"):
            return
        self._cards_columns = columns
        for col in range(3):
            self.cards_box.setColumnStretch(col, 1 if col < columns else 0)
        for index, card in enumerate(self.today_cards):
            self.cards_box.removeWidget(card)
            self.cards_box.addWidget(card, index // columns, index % columns)

    def _apply_compact_chrome(self) -> None:
        """Trim the header (not the content) when the window is narrow."""
        compact = self.width() < 620
        if compact == self.compact_chrome:
            return
        self.compact_chrome = compact
        if hasattr(self, "app_subtitle"):
            self.app_subtitle.setVisible(not compact)
        if hasattr(self, "achv_button"):
            self.achv_button.setText("🏆" if compact else "🏆  Achievements")
        if hasattr(self, "add_button"):
            self.add_button.setText("＋" if compact else "＋  New habit")

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_compact_chrome()
        self._set_card_columns(self.cards_per_row())
        if hasattr(self, "date_label"):
            self.date_label.setVisible(self.width() >= 560)

    def _on_progress_toggle(self, habit_id: int) -> None:
        """Tick / untick a habit for *today* from the progress grid."""
        if not self._require_writable():
            return
        today_iso = date.today().isoformat()
        row = self.conn.execute("SELECT * FROM habits WHERE id=?", (habit_id,)).fetchone()
        if row is None:
            return
        hd = dict(row)
        completions = get_completions(self.conn, habit_id)
        done = is_done(hd, completions.get(today_iso), today_iso in completions)
        if hd.get("type") == "dont_do":
            # "done" = a clean day (no row); unticking records a slip.
            if done:
                log_completion(self.conn, habit_id, today_iso, 1)
            else:
                clear_completion(self.conn, habit_id, today_iso)
        elif done:
            clear_completion(self.conn, habit_id, today_iso)
        else:
            value = int(hd.get("target_count", 1) or 1) \
                if hd.get("type") == "counter" else 1
            log_completion(self.conn, habit_id, today_iso, value)
        self.refresh_all()
        self.check_achievements(show_banner=False)

    def _on_manage_folders(self) -> None:
        if not self._require_writable():
            return
        dlg = FoldersDialog(self.conn, self)
        dlg.exec()
        self.refresh_folders()
        self.refresh_all()

    def _setup_widget(self) -> None:
        """Desktop widget stays hidden until the user enables it in View menu."""
        visible = self.desktop_widget._settings().value("visible", False)
        show = visible is True or str(visible).lower() == "true"
        self.widget_action.setChecked(show)
        if show:
            self.desktop_widget.refresh()
            self.desktop_widget.show()

    def _toggle_widget(self, checked: bool) -> None:
        from core.entitlements import can

        if checked and not can(self.conn, "widget"):
            self.widget_action.setChecked(False)
            self._pro_message("Desktop widget")
            return
        widget = getattr(self, "desktop_widget", None)
        if widget is None:
            return
        widget._settings().setValue("visible", bool(checked))
        if checked:
            widget.start_auto_refresh(60)
            widget.refresh()
            widget.show()
        else:
            widget.stop_auto_refresh()
            widget.hide()

    def _on_widget_check(self, habit_id: int) -> None:
        """One-tap check-off from the desktop widget (no modal banner)."""
        if self._locked():
            return
        today_iso = date.today().isoformat()
        row = self.conn.execute("SELECT * FROM habits WHERE id=?", (habit_id,)).fetchone()
        if row is None:
            return
        hd = dict(row)
        current = int(get_completions(self.conn, habit_id).get(today_iso, 0))
        new_value = current + 1 if hd.get("type") == "counter" else 1
        log_completion(self.conn, habit_id, today_iso, new_value)
        self.refresh_all()
        self.check_achievements(show_banner=False)

    def _on_add(self) -> None:
        if not self._require_writable():
            return
        if self._activation_cap_reached():
            QMessageBox.information(
                self, "Limited mode",
                "Limited mode allows 1 habit — activate free to add more.")
            self._on_account()
            return
        from core.entitlements import habit_limit_for

        limit = habit_limit_for(self.conn)
        if limit is not None and len(list_habits(self.conn)) >= limit:
            self._pro_message(f"Free allows up to {limit} habits")
            return
        dlg = AddHabitDialog(self, self.conn)
        if dlg.exec():
            try:
                create_habit(self.conn, **dlg.values())
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid habit", str(exc))
                return
            self.refresh_folders()
            self.refresh_all()
            self.check_achievements(show_banner=False)

    def _achievement_inputs(self, today_iso: str) -> dict:
        from datetime import timedelta

        end = date.fromisoformat(today_iso)
        habits = [dict(h) for h in list_habits(self.conn)]
        total = int(self.conn.execute("SELECT COUNT(*) FROM completions").fetchone()[0])
        best_cur = 0
        done7_ids: set[int] = set()
        for h in habits:
            comp = get_completions(self.conn, int(h["id"]))
            pauses = [(p["start_date"], p["end_date"]) for p in list_pauses(self.conn, int(h["id"]))]
            best_cur = max(best_cur, current_streak(dict(h), comp, pauses, today_iso))
            for i in range(7):
                d = (end - timedelta(days=i)).isoformat()
                due = is_due(dict(h), d) and not is_paused(pauses, d)
                if due and is_done(dict(h), comp.get(d), d in comp):
                    done7_ids.add(int(h["id"]))
                    break
        perfect = False
        for i in range(30):
            d = (end - timedelta(days=i)).isoformat()
            due = [
                h for h in habits
                if is_due(h, d) and not is_paused(
                    [(p["start_date"], p["end_date"]) for p in list_pauses(self.conn, int(h["id"]))], d
                )
            ]
            if due:
                ok = True
                for h in due:
                    comp = get_completions(self.conn, int(h["id"]))
                    if not is_done(h, comp.get(d), d in comp):
                        ok = False
                        break
                if ok:
                    perfect = True
                    break
        return {
            "total_completions": total,
            "best_current_streak": best_cur,
            "habits_done_last_7d": len(done7_ids),
            "has_perfect_day": perfect,
        }

    def check_achievements(self, show_banner: bool = True) -> list[str]:
        """Unlock newly earned achievements, persist + banner (S16 DoD)."""
        inputs = self._achievement_inputs(date.today().isoformat())
        fresh = []
        for code in check_unlocks(**inputs):
            if unlock(self.conn, code):
                fresh.append(code)
        if fresh and show_banner:
            names = ", ".join(ACHIEVEMENTS[c] for c in fresh)
            QMessageBox.information(self, "Achievement unlocked!", f"🏅 {names}")
        return fresh

    def _on_show_achievements(self) -> None:
        AchievementsDialog(self.conn, self).exec()

    # -- Phase 6 account (activation gate + background check, fail-open) --
    def _build_account_bar(self) -> QFrame:
        from PySide6.QtWidgets import QHBoxLayout

        bar = QFrame()
        bar.setObjectName("AccountBar")
        self.account_bar = bar
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(22, 6, 22, 6)
        layout.setSpacing(12)
        self.account_label = QLabel("")
        self.account_label.setWordWrap(True)
        layout.addWidget(self.account_label, 1)
        self.account_button = QPushButton("Activate…")
        self.account_button.clicked.connect(self._on_account)
        layout.addWidget(self.account_button)
        bar.setVisible(False)
        return bar

    def _setup_account(self) -> None:
        from PySide6.QtCore import QTimer

        from services.identity import APP_VERSION, ensure_identity

        ensure_identity(self.conn, platform="linux", app_version=APP_VERSION)
        self._license_thread = None
        self._refresh_account_bar()
        # Delayed so startup (and its offline path) stays instant.
        QTimer.singleShot(2000, self._start_license_check)

    def _start_license_check(self) -> None:
        from services import identity
        from services.identity import APP_VERSION
        from services.license_check import LicenseCheckThread
        from services.registry import base_url

        thread = getattr(self, "_license_thread", None)
        if thread is not None and thread.isRunning():
            return
        access, refresh_jwt, _email = identity.load_tokens()
        if not access:
            return  # unactivated: nothing to verify
        meta = get_meta(self.conn)
        self._license_thread = LicenseCheckThread(
            base_url(), access=access, refresh_jwt=refresh_jwt,
            device_id=meta.get("device_id") or "", platform="linux",
            app_version=APP_VERSION, parent=self)
        self._license_thread.done.connect(self._on_license_done)
        self._license_thread.finished.connect(self._license_thread.deleteLater)
        self._license_thread.start()

    def _on_license_done(self, result: dict) -> None:
        from services import identity
        from services.license_check import apply_result

        _access, _refresh, email = identity.load_tokens()
        apply_result(self.conn, result, email=email)
        self._refresh_account_bar()

    def _account_state(self) -> tuple[str, dict]:
        from datetime import datetime, timezone

        from services.license_check import load_reference

        meta = get_meta(self.conn)
        ref = load_reference()
        state = ref.effective_state(
            meta.get("cached_status") or "unactivated",
            meta.get("last_check") or "",
            datetime.now(timezone.utc).isoformat())
        return state, meta

    def _refresh_account_bar(self) -> None:
        state, meta = self._account_state()
        bar = getattr(self, "account_bar", None)
        if bar is None:
            return
        if state == "active":
            bar.setVisible(False)
            return
        if state == "unactivated":
            self.account_label.setText(
                "Limited mode (1 habit). Activate once — free — then use "
                "StreakGrid fully offline.")
            self.account_button.setText("Activate…")
        elif state == "grace_expired":
            self.account_label.setText(
                f"Last verified {self._days_since_check(meta)} — connect once "
                "to refresh. Everything still works.")
            self.account_button.setText("Account…")
        else:  # locked
            self.account_label.setText(
                "Account locked — the app is read-only. Log in with another "
                "account or contact support.")
            self.account_button.setText("Account…")
        bar.setVisible(True)

    @staticmethod
    def _days_since_check(meta: dict) -> str:
        from datetime import datetime, timezone

        try:
            text = (meta.get("last_check") or "").replace("Z", "+00:00")
            last = datetime.fromisoformat(text)
            days = (datetime.now(timezone.utc) - last).days
            return f"{max(days, 0)} days ago"
        except ValueError:
            return "a while ago"

    def _on_account(self) -> None:
        from ui.auth_dialog import open_account_dialog

        if open_account_dialog(self, self.conn):
            self._refresh_account_bar()
            self.refresh_all()

    def _on_upgrade(self) -> None:
        from ui.upgrade_dialog import open_upgrade_dialog

        open_upgrade_dialog(self, self.conn)
        self._refresh_account_bar()

    def _activation_cap_reached(self) -> bool:
        """Unactivated devices are limited to 1 habit (L08 gate)."""
        state, _meta = self._account_state()
        if state != "unactivated":
            return False
        return len(list_habits(self.conn)) >= 1

    # -- Phase 6 enforcement (L09: locked = read-only, offline) ------------
    def _locked(self) -> bool:
        from core.entitlements import is_locked

        return is_locked(self.conn)

    def _require_writable(self) -> bool:
        if not self._locked():
            return True
        QMessageBox.information(
            self, "Locked",
            "Account locked — the app is read-only. Log in with another "
            "account or contact support.")
        return False
