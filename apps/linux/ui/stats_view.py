"""Stats view — S15-2: rates + perfect days + weekday chart."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.week_chart import WeekChart

from core.schedule import is_due
from core.streak import (
    best_streak,
    completion_rate,
    current_streak,
    is_done,
    is_paused,
    strength_score,
)
from db.store import export_completions_csv, get_completions, list_habits, list_pauses


class StatsView(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self.conn = conn
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(12)
        self.summary = QLabel("")
        self.summary.setObjectName("CardTitle")
        self.summary.setWordWrap(True)
        self.layout.addWidget(self.summary)
        self.extra = QLabel("")
        self.extra.setObjectName("MutedText")
        # These lines are long: wrapping keeps them from forcing the window
        # wider than a small screen can show.
        self.extra.setWordWrap(True)
        self.layout.addWidget(self.extra)
        self.rows_host = QVBoxLayout()
        self.rows_host.setSpacing(8)
        self.layout.addLayout(self.rows_host)
        self.week_chart = WeekChart()
        self.layout.addWidget(self.week_chart)
        self.export_button = QPushButton("Export CSV")
        self.export_button.clicked.connect(self._on_export)
        self.import_button = QPushButton("Import CSV")
        self.import_button.clicked.connect(self._on_import)
        io_row = QHBoxLayout()
        io_row.addStretch(1)
        io_row.addWidget(self.export_button)
        io_row.addWidget(self.import_button)
        self.layout.addLayout(io_row)
        self.rows: list[QFrame] = []

    def refresh(self, today: str | None = None) -> None:
        today_iso = today or date.today().isoformat()
        for r in self.rows:
            self.rows_host.removeWidget(r)
            r.deleteLater()
        self.rows = []
        habits = list_habits(self.conn)
        if not habits:
            self.summary.setText("No data yet.")
            return
        lines = []
        strengths: list[float] = []
        for h in habits:
            hd = dict(h)
            completions = get_completions(self.conn, int(h["id"]))
            pauses = [(p["start_date"], p["end_date"]) for p in list_pauses(self.conn, int(h["id"]))]
            r30 = completion_rate(hd, completions, pauses, today_iso, days=30)
            r90 = completion_rate(hd, completions, pauses, today_iso, days=90)
            rall = completion_rate(hd, completions, pauses, today_iso, days=365 * 3)
            best = best_streak(hd, completions, pauses, today_iso)
            cur = current_streak(hd, completions, pauses, today_iso)
            strength = strength_score(hd, completions, pauses, today_iso)
            strengths.append(strength)
            card = QFrame()
            card.setProperty("card", True)
            card_box = QHBoxLayout(card)
            card_box.setContentsMargins(14, 10, 14, 10)
            card_box.setSpacing(10)
            title = QLabel(str(h["name"]))
            title.setObjectName("CardTitle")
            title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            title.setToolTip(str(h["name"]))
            detail = QLabel(
                f"30d {r30:.0%}   ·   90d {r90:.0%}   ·   all {rall:.0%}   ·   "
                f"streak {cur}   ·   best {best}   ·   strength {strength:.0%}"
            )
            detail.setObjectName("CardMeta")
            detail.setWordWrap(True)
            card_box.addWidget(title, 1)
            card_box.addWidget(detail)
            self.rows_host.addWidget(card)
            self.rows.append(card)
            lines.append(f"{h['name']} {r30:.2f} {best}")
        overall = sum(strengths) / len(strengths) if strengths else 0.0
        self.summary.setText(
            f"{len(habits)} habits tracked   ·   overall strength {overall:.0%}"
        )
        self.extra.setText(self._extra_text(today_iso))
        self.week_chart.set_rates(self.weekday_rates(today_iso))

    def weekday_rates(self, today_iso: str) -> list[float]:
        """Per-weekday completion over last 12 weeks (for the bar chart)."""
        end = date.fromisoformat(today_iso)
        habits = [dict(h) for h in list_habits(self.conn)]
        comp = {int(h["id"]): get_completions(self.conn, int(h["id"])) for h in habits}
        pauses = {
            int(h["id"]): [(p["start_date"], p["end_date"]) for p in list_pauses(self.conn, int(h["id"]))]
            for h in habits
        }
        done = [0] * 7
        total = [0] * 7
        for i in range(84):
            d = end - timedelta(days=i)
            wd = d.weekday()
            for h in habits:
                if is_due(h, d) and not is_paused(pauses[int(h["id"])], d):
                    total[wd] += 1
                    iso = d.isoformat()
                    if is_done(h, comp[int(h["id"])].get(iso), iso in comp[int(h["id"])]):
                        done[wd] += 1
        return [(done[i] / total[i] if total[i] else 0.0) for i in range(7)]

    def _extra_text(self, today_iso: str) -> str:
        """Perfect days (30d) + best/worst weekday over last 12 weeks."""
        end = date.fromisoformat(today_iso)
        habits = [dict(h) for h in list_habits(self.conn)]
        comp = {int(h["id"]): get_completions(self.conn, int(h["id"])) for h in habits}
        pauses = {
            int(h["id"]): [(p["start_date"], p["end_date"]) for p in list_pauses(self.conn, int(h["id"]))]
            for h in habits
        }
        perfect = 0
        for i in range(30):
            d = end - timedelta(days=i)
            iso = d.isoformat()
            due = [h for h in habits if is_due(h, d) and not is_paused(pauses[int(h["id"])], d)]
            if due and all(is_done(h, comp[int(h["id"])].get(iso), iso in comp[int(h["id"])]) for h in due):
                perfect += 1
        wd_done = [0] * 7
        wd_total = [0] * 7
        for i in range(84):
            d = end - timedelta(days=i)
            wd = d.weekday()
            for h in habits:
                if is_due(h, d) and not is_paused(pauses[int(h["id"])], d):
                    wd_total[wd] += 1
                    iso = d.isoformat()
                    if is_done(h, comp[int(h["id"])].get(iso), iso in comp[int(h["id"])]):
                        wd_done[wd] += 1
        rates = [(wd_done[i] / wd_total[i] if wd_total[i] else 0.0) for i in range(7)]
        names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        best_i = max(range(7), key=lambda i: rates[i])
        worst_i = min(range(7), key=lambda i: rates[i])
        chart = " ".join(f"{names[i]} {rates[i]:.0%}" for i in range(7))
        return f"Perfect days (30d): {perfect} | best {names[best_i]} | worst {names[worst_i]} | {chart}"

    def export_csv(self, out_dir: str | None = None) -> str:
        from pathlib import Path

        base = Path(out_dir) if out_dir else Path.home() / "Documents"
        base.mkdir(parents=True, exist_ok=True)
        path = str(base / f"streakgrid-{date.today().isoformat()}.csv")
        return export_completions_csv(self.conn, path)

    def _on_export(self) -> None:
        from core.entitlements import can

        if not can(self.conn, "export"):
            QMessageBox.information(
                self, "Pro feature",
                "CSV export requires Pro (coming soon). "
                "Your data stays readable on-device.")
            return
        path = self.export_csv()
        QMessageBox.information(self, "Exported", f"Saved {path}")

    def import_csv(self, in_path: str) -> dict:
        from db.store import import_completions_csv

        result = import_completions_csv(self.conn, in_path)
        self.refresh()
        return result

    def _on_import(self) -> None:
        from pathlib import Path

        path, _ = QFileDialog.getOpenFileName(
            self, "Import CSV", str(Path.home()), "CSV (*.csv)")
        if not path:
            return
        try:
            result = self.import_csv(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Import failed", str(exc))
            return
        parent = self.parent()
        while parent is not None and not hasattr(parent, "refresh_all"):
            parent = parent.parent()
        if parent is not None:
            parent.refresh_all()
        skipped = len(result["skipped"])
        QMessageBox.information(
            self, "Imported",
            f"{result['imported']} rows imported, {skipped} skipped.")
