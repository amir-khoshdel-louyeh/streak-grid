"""Stats view — trend chart only (last 30 days)."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui.trend_chart import HabitLinesChart, TrendChart

from core.schedule import is_due
from core.streak import (
    is_done,
    is_paused,
)
from db.store import get_completions, list_habits, list_pauses


class StatsView(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self.conn = conn
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(12)
        trend_title = QLabel("Last 30 days")
        trend_title.setObjectName("MutedText")
        self.layout.addWidget(trend_title)
        self.trend_chart = TrendChart()
        self.layout.addWidget(self.trend_chart)
        per_habit_title = QLabel("Per habit · 7-day average")
        per_habit_title.setObjectName("MutedText")
        self.layout.addWidget(per_habit_title)
        self.habit_chart = HabitLinesChart()
        self.layout.addWidget(self.habit_chart)

    def refresh_theme(self) -> None:
        """Re-colour painted charts (called on theme toggle)."""
        self.trend_chart.refresh_theme()
        self.habit_chart.refresh_theme()

    def refresh(self, today: str | None = None) -> None:
        today_iso = today or date.today().isoformat()
        habits = list_habits(self.conn)
        if not habits:
            self.trend_chart.set_rates([])
            self.habit_chart.set_series([])
            return
        window30 = self._window_rates(today_iso, 30)
        self.trend_chart.set_rates(self.trend_rates(window30))
        self.habit_chart.set_series(self.per_habit_rolling(today_iso, 30))

    def _window_rates(self, today_iso: str, days: int) -> list[tuple[int, int]]:
        """Per-day (done, due) oldest→newest ending today, for the trend."""
        end = date.fromisoformat(today_iso)
        habits = [dict(h) for h in list_habits(self.conn)]
        comp = {int(h["id"]): get_completions(self.conn, int(h["id"])) for h in habits}
        pauses = {
            int(h["id"]): [(p["start_date"], p["end_date"]) for p in list_pauses(self.conn, int(h["id"]))]
            for h in habits
        }
        out: list[tuple[int, int]] = []
        for back in range(days - 1, -1, -1):
            day = end - timedelta(days=back)
            iso = day.isoformat()
            done = total = 0
            for h in habits:
                if is_due(h, day) and not is_paused(pauses[int(h["id"])], day):
                    total += 1
                    if is_done(h, comp[int(h["id"])].get(iso), iso in comp[int(h["id"])]):
                        done += 1
            out.append((done, total))
        return out

    def trend_rates(self, window30: list[tuple[int, int]]) -> list[float]:
        """Per-day completion share over 30d, oldest→newest (for the trend)."""
        return [(done / total if total else 0.0) for done, total in window30]

    def per_habit_rolling(self, today_iso: str, days: int = 30,
                          window: int = 7) -> list[tuple[str, list[float]]]:
        """One smoothed line per habit: 7-day rolling average, oldest→newest.

        Daily credit is 1.0 done / 0.0 missed, with partial credit for
        counters (e.g. 3/8 glasses = 0.375). Days the habit isn't due or is
        paused carry no credit and are skipped in the average, so lines for
        habits with different schedules stay comparable instead of all
        collapsing onto 0%/100%.
        """
        end = date.fromisoformat(today_iso)
        habits = [dict(h) for h in list_habits(self.conn)]
        comp = {int(h["id"]): get_completions(self.conn, int(h["id"])) for h in habits}
        pauses = {
            int(h["id"]): [(p["start_date"], p["end_date"]) for p in list_pauses(self.conn, int(h["id"]))]
            for h in habits
        }
        out: list[tuple[str, list[float]]] = []
        for h in habits:
            hid = int(h["id"])
            daily: list[float | None] = []
            for back in range(days - 1, -1, -1):
                day = end - timedelta(days=back)
                iso = day.isoformat()
                if not is_due(h, day) or is_paused(pauses[hid], day):
                    daily.append(None)
                    continue
                values = comp[hid]
                has_row = iso in values
                if h.get("type") == "counter":
                    target = int(h.get("target_count", 1) or 1)
                    daily.append(min(int(values.get(iso, 0)) / target, 1.0))
                elif h.get("type") == "dont_do":
                    daily.append(1.0 if not has_row else 0.0)
                else:
                    daily.append(1.0 if is_done(h, values.get(iso), has_row) else 0.0)
            if not any(v is not None for v in daily):
                continue
            smoothed: list[float] = []
            last = 0.0
            for i in range(len(daily)):
                part = [v for v in daily[max(0, i - window + 1):i + 1] if v is not None]
                last = sum(part) / len(part) if part else last
                smoothed.append(last)
            out.append((str(h["name"]), smoothed))
        return out
