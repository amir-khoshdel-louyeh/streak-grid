"""Progress ranges — P: window maths for the Progress view. Pure logic, no Qt.

The Progress view shows one row per habit over a day range. A range is
described by a `RangeSpec`; `window()` turns a spec plus a *basis* into the
inclusive `(start, end)` day window that should be drawn:

* ``calendar`` — anchored to the calendar: "This week" is Mon–Sun (future
  days included, they render dimmed) and month ranges are whole calendar
  months, e.g. "3 months" on 15 Oct is 1 Aug – 31 Oct. "10 days" has no
  calendar equivalent, so it always uses the rolling window.
* ``rolling`` — a window that always ends today, e.g. "1 month" = the last
  30 days.

Every range also carries the smallest day-cell width and the row height the
widget should use. Policy (enforced in timeline.py, mirrored here): day cells
never shrink below 22px and rows never below 26px — a year stays scrollable
while a week stays roomy, and tick targets stay tappable at every range.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

CALENDAR = "calendar"
ROLLING = "rolling"

#: Hard floor for tickable day cells (policy: cells never get smaller).
MIN_CELL = 22
#: Hard floor for habit rows (policy: names stay readable at every range).
MIN_ROW_H = 26


@dataclass(frozen=True)
class RangeSpec:
    """One entry of the range picker."""

    key: str
    label: str
    rolling_days: int          # length of the rolling window ending today
    months: int | None         # calendar span in whole months; None = rolling only
    calendar_week: bool = False
    min_cell: int = 26         # smallest readable day-cell width
    row_h: int = 32            # habit row height


RANGES: tuple[RangeSpec, ...] = (
    RangeSpec("week", "This week", rolling_days=7, months=1, calendar_week=True,
              min_cell=34, row_h=36),
    RangeSpec("10d", "10 days", rolling_days=10, months=None, min_cell=26, row_h=32),
    RangeSpec("1m", "1 month", rolling_days=30, months=1, min_cell=22, row_h=26),
    RangeSpec("3m", "3 months", rolling_days=90, months=3, min_cell=22, row_h=26),
    RangeSpec("6m", "6 months", rolling_days=182, months=6, min_cell=22, row_h=26),
    RangeSpec("1y", "1 year", rolling_days=365, months=12, min_cell=22, row_h=26),
)

# Short labels keep the picker narrow enough for small screens; the widget
# carries the longer explanation as a tooltip.
BASES: tuple[tuple[str, str], ...] = (
    (CALENDAR, "Calendar"),
    (ROLLING, "Rolling"),
)

DEFAULT_RANGE = "week"
DEFAULT_BASE = CALENDAR


def spec_for(key: str) -> RangeSpec:
    """Range spec by key, falling back to the first range for unknown keys."""
    for spec in RANGES:
        if spec.key == key:
            return spec
    return RANGES[0]


def base_for(key: str) -> str:
    return key if key in (CALENDAR, ROLLING) else DEFAULT_BASE


def window(
    spec: RangeSpec,
    base: str = CALENDAR,
    today: date | None = None,
) -> tuple[date, date]:
    """Inclusive ``(start, end)`` window for `spec` under `base`."""
    day = today or date.today()
    base = base_for(base)
    if spec.calendar_week and base == CALENDAR:
        monday = day - timedelta(days=day.weekday())
        return monday, monday + timedelta(days=6)
    if base == ROLLING or spec.months is None:
        return day - timedelta(days=spec.rolling_days - 1), day
    first = day.replace(day=1)
    start = shift_months(first, -(spec.months - 1))
    end = day.replace(day=calendar.monthrange(day.year, day.month)[1])
    return start, end


def days_between(start: date, end: date) -> list[date]:
    """Every day of the inclusive window, oldest first."""
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def shift_months(day: date, months: int) -> date:
    """First day of the month `months` away from `day` (month arithmetic)."""
    total = day.year * 12 + (day.month - 1) + months
    return date(total // 12, total % 12 + 1, 1)
