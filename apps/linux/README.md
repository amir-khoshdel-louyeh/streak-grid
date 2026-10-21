# Linux app (Python + PySide6)

Status: v1 — single scrollable page (Today + All habits + Heatmap + Stats)
with achievements, tray/nag/widget.

## Shortcuts

`Ctrl+N` new habit · `Ctrl+1..4` jump to sections · `/` search · `Ctrl+T` theme

## Run

```bash
pip install -r requirements.txt
python main.py
```

Smoke (headless): `QT_QPA_PLATFORM=offscreen timeout 10 python main.py` stays alive.

## Exports

- Grid PNG: Grid tab → Export PNG → `~/Pictures/streakgrid-YYYY-MM-DD.png`
- CSV: Stats tab → Export CSV → `~/Documents/streakgrid-YYYY-MM-DD.csv`

## Packaging (S20)

- Desktop entry: `packaging/streakgrid.desktop` (`Exec` points at installed `main.py`)
- Flatpak: `packaging/flatpak.json` (`org.kde.Platform//6.7`)
- Autostart: created at runtime via `services/autostart.py` → `~/.config/autostart/*.desktop`
