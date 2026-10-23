# Linux app (Python + PySide6)

Status: v1 — single scrollable page (Today + All habits + Heatmap + Stats)
with achievements, tray/nag/widget.

## Features

- **Today** — progress ring, due habits as tappable cards (counter habits step up/down).
- **This week** — a contribution-style table: one row per task, one column per day
  (Mon–Sun). Only today's column is tickable; past days show what was done and
  future days are dimmed.
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
