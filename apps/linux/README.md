# Linux app (Python + PySide6)

Status: v1 — single scrollable page (Today + All habits + Heatmap + Stats)
with achievements, tray/nag/widget.

## Features

- **Today** — progress ring, due habits as tappable cards (counter habits step up/down).
- **Progress** — a contribution-style timeline: one row per task, one column per
  day. Pick a **Range** (This week, 10 days, 1 month, 3 months, 6 months, 1 year)
  and a **Window**: *Calendar* (calendar week, whole months; future days dimmed)
  or *Rolling* (ends today). Both choices are remembered. Only today's column is
  tickable; long ranges shrink their day cells and then scroll sideways, with the
  task names pinned on the left.
- **All habits** — searchable full-width rows, drag ⋮⋮ to reorder, double-click to
  open details; each row shows its folder, streak, best, next due date and a
  full-year mini heatmap.
- **Heatmap** — one rolling GitHub-style graph aggregated across *all* habits
  (share of due habits completed each day) with month/weekday axes, a Less–More
  legend and an active-days / consistency summary; Year or Month view.
- **Stats** — 30/90/all completion rates, streaks, weighted **strength** score,
  perfect days and a per-weekday chart.
- **Folders** (`Habits ▸ Folders…`) — colour-coded categories; pick a habit's folder
  in the add/edit dialog and filter Today by folder.
- **Desktop widget** (`View ▸ Desktop widget`) — pin-anywhere, one-tap check-off
  without opening the main window.
- **Achievements** — 8 badges; tray quick actions and Nag Mode reminders.

## Shortcuts

`Ctrl+N` new habit · `Ctrl+1..5` jump to sections · `/` search · `Ctrl+T` theme

## Screens

Every window is clamped to the display it opens on, so the app also fits a
1366x768 panel at 150% scaling or a small netbook screen:

- the header trims to compact icons; Today reflows between 1 and 3 habit cards
  per row; long lists drop their year mini heatmap and Stats text wraps;
- Progress scales its task column with the window, short ranges fill the width
  and long ranges keep a readable day size and scroll sideways;
- under ~430px of width the page scrolls sideways instead of clipping;
- dialogs (habit detail, new habit, folders, achievements, welcome) are sized to
  the screen, with the habit detail body scrolling inside the dialog.

## Order

Drag rows in All habits to reorder — Today follows the same order.

## Run

```bash
pip install -r requirements.txt
python main.py
```

Smoke (headless): `QT_QPA_PLATFORM=offscreen timeout 10 python main.py` stays alive.

## Exports

- Grid PNG: Heatmap section → Export PNG → `~/Pictures/streakgrid-YYYY-MM-DD.png`
- CSV: Stats section → Export CSV → `~/Documents/streakgrid-YYYY-MM-DD.csv`
- CSV import: Stats section → Import CSV (matches habits by name, skips unknown)

## Backup (File menu)

- Backup now (`Ctrl+B`) → `~/Documents/streakgrid-backup-*.db`
- Restore backup → validates the file, then reconnects every view

## Packaging (S20)

- Desktop entry: `packaging/streakgrid.desktop` (`Exec` points at installed `main.py`)
- Flatpak: `packaging/flatpak.json` (`org.kde.Platform//6.7`)
- Autostart: created at runtime via `services/autostart.py` → `~/.config/autostart/*.desktop`
