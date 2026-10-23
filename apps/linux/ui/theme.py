"""Themes — U4: dark + light palettes with persisted toggle.

Both stylesheets are generated from one template plus a palette, so the two
themes stay visually consistent. Chart colours (heatmap / ring / week bars)
are painted widgets, so they read their colours from `chart_colors()` instead
of the stylesheet.
"""

from __future__ import annotations

from string import Template

from PySide6.QtCore import QSettings

THEME_KEY = "streakgrid/dark"

# --- palettes -----------------------------------------------------------------

_DARK = {
    "bg": "#1a1b26",
    "surface": "#1f2335",
    "surface2": "#24283b",
    "hover": "#2a2f45",
    "pressed": "#3b4261",
    "border": "#2c3145",
    "border_strong": "#3d4463",
    "text": "#c0caf5",
    "muted": "#7f88b3",
    "faint": "#565f89",
    "accent": "#7aa2f7",
    "accent_hover": "#8fb3ff",
    "on_accent": "#15161f",
    "green": "#9ece6a",
    "green_strong": "#7bc95a",
    "on_green": "#15161f",
    "done_bg": "#1e2b23",
}

_LIGHT = {
    "bg": "#f5f7fa",
    "surface": "#ffffff",
    "surface2": "#f6f8fa",
    "hover": "#eef1f4",
    "pressed": "#e4e9ef",
    "border": "#e4e8ec",
    "border_strong": "#d0d7de",
    "text": "#1f2328",
    "muted": "#59606a",
    "faint": "#8c959f",
    "accent": "#0969da",
    "accent_hover": "#218bff",
    "on_accent": "#ffffff",
    "green": "#1a7f37",
    "green_strong": "#1f883d",
    "on_green": "#ffffff",
    "done_bg": "#eef8f1",
}

# --- stylesheet ---------------------------------------------------------------

_CSS = Template(
    """
/* ---- base ---------------------------------------------------------- */
QMainWindow, QDialog { background: $bg; color: $text; }
QWidget { color: $text; font-size: 13px; }
QToolTip {
    background: $surface; color: $text;
    border: 1px solid $border_strong; border-radius: 6px; padding: 4px 8px;
}

/* ---- scroll containers --------------------------------------------- */
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
#Page { background: $bg; }

/* ---- labels -------------------------------------------------------- */
QLabel { background: transparent; }
#AppTitle { font-size: 18px; font-weight: 700; }
#AppSubtitle { color: $muted; font-size: 12px; }
#HeroTitle { font-size: 21px; font-weight: 700; }
#CardTitle { font-size: 14px; font-weight: 600; }
#CardMeta { color: $muted; font-size: 12px; }
#MutedText { color: $muted; font-size: 12px; }
#DateLabel { color: $muted; font-size: 13px; font-weight: 600; }
#EmptyState { color: $muted; font-size: 13px; padding: 26px; }

/* ---- header -------------------------------------------------------- */
#AppHeader { background: $surface; border: none; border-bottom: 1px solid $border; }

/* ---- section cards ------------------------------------------------- */
QGroupBox {
    background: $surface;
    border: 1px solid $border;
    border-radius: 14px;
    margin-top: 28px;
    padding: 18px 20px 18px 20px;
    font-size: 15px;
    font-weight: 700;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: 3px;
    padding: 0 8px;
    color: $text;
}

/* ---- habit cards / list rows --------------------------------------- */
QFrame[card="true"] {
    background: $surface2;
    border: 1px solid $border_strong;
    border-radius: 12px;
}
QFrame[card="true"]:hover { border: 1px solid $accent; }
QFrame[card="true"][done="true"] { background: $done_bg; border: 1px solid $green; }

/* ---- week contribution table --------------------------------------- */
#WeekHeader { color: $muted; font-size: 12px; }
#WeekHeaderToday { color: $accent; font-size: 12px; font-weight: 700; }
QLabel[weekcell="done"] {
    background: $green; border: 1px solid $green; border-radius: 9px;
    color: $on_green; font-size: 15px; font-weight: 700;
}
QLabel[weekcell="empty"] {
    background: $surface2; border: 1px solid $border_strong; border-radius: 9px;
}
QLabel[weekcell="off"], QLabel[weekcell="future"] {
    background: transparent; border: 1px dashed $border; border-radius: 9px;
}
/* grid rules that tie a task to its seven days */
QFrame[role="weekline"] { background: $border; border: none; }
QFrame[role="weekheadline"] { background: $border_strong; border: none; }
QPushButton#WeekTick { padding: 0; border-radius: 9px; font-size: 15px; font-weight: 700; }
QPushButton#WeekTick[wbstate="done"] {
    background: $green; border: 1px solid $green; color: $on_green;
}
QPushButton#WeekTick[wbstate="done"]:hover {
    background: $green_strong; border-color: $green_strong;
}
QPushButton#WeekTick[wbstate="todo"] {
    background: $surface2; border: 2px solid $accent; color: $muted;
}
QPushButton#WeekTick[wbstate="todo"]:hover { background: $hover; color: $accent; }

/* ---- buttons ------------------------------------------------------- */
QPushButton {
    background: $surface2;
    color: $text;
    border: 1px solid $border_strong;
    border-radius: 9px;
    padding: 7px 14px;
}
QPushButton:hover { background: $hover; }
QPushButton:pressed { background: $pressed; }
QPushButton:disabled { color: $faint; border-color: $border; }
QPushButton[role="primary"] {
    background: $accent;
    color: $on_accent;
    border: 1px solid $accent;
    font-weight: 700;
    padding: 8px 16px;
}
QPushButton[role="primary"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[role="ghost"] {
    background: transparent;
    border: 1px solid transparent;
    color: $muted;
    padding: 6px 10px;
}
QPushButton[role="ghost"]:hover { background: $hover; color: $text; }
QPushButton#CheckButton {
    background: transparent;
    border: 2px solid $border_strong;
    border-radius: 20px;
    color: $muted;
    font-size: 17px;
    font-weight: 700;
    padding: 0;
}
QPushButton#CheckButton:hover { border-color: $accent; color: $accent; }
QPushButton#CheckButton[state="done"] {
    background: $green;
    border-color: $green;
    color: $on_green;
}
QPushButton#CheckButton[state="done"]:hover {
    background: $green_strong;
    border-color: $green_strong;
}
QPushButton#IconButton {
    background: transparent;
    border: 1px solid transparent;
    color: $muted;
    padding: 0;
    font-size: 15px;
}
QPushButton#IconButton:hover { background: $hover; color: $text; }

/* ---- inputs -------------------------------------------------------- */
QLineEdit, QComboBox, QSpinBox, QDateEdit, QTimeEdit {
    background: $surface2;
    color: $text;
    border: 1px solid $border_strong;
    border-radius: 9px;
    padding: 6px 10px;
    min-height: 18px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
QDateEdit:focus, QTimeEdit:focus { border: 1px solid $accent; }
QLineEdit { selection-background-color: $accent; selection-color: $on_accent; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: $surface;
    color: $text;
    border: 1px solid $border_strong;
    border-radius: 8px;
    selection-background-color: $accent;
    selection-color: $on_accent;
    padding: 4px;
}
QSpinBox::up-button, QSpinBox::down-button,
QDateEdit::up-button, QDateEdit::down-button,
QTimeEdit::up-button, QTimeEdit::down-button {
    width: 16px; border: none; background: transparent;
}

/* ---- calendar (dialogs) -------------------------------------------- */
QCalendarWidget QWidget { alternate-background-color: $surface; }
QCalendarWidget QAbstractItemView:enabled {
    background: $surface2;
    color: $text;
    selection-background-color: $accent;
    selection-color: $on_accent;
}
QCalendarWidget QToolButton { background: transparent; color: $text; }

/* ---- lists --------------------------------------------------------- */
QListWidget {
    background: $surface2;
    border: 1px solid $border_strong;
    border-radius: 9px;
}
QListWidget::item { padding: 5px 8px; border-radius: 7px; }
QListWidget::item:selected { background: $accent; color: $on_accent; }

/* ---- menus --------------------------------------------------------- */
QMenuBar { background: transparent; color: $text; }
QMenuBar::item { background: transparent; padding: 5px 10px; border-radius: 7px; }
QMenuBar::item:selected { background: $hover; }
QMenu { background: $surface; color: $text; border: 1px solid $border_strong; border-radius: 10px; padding: 5px; }
QMenu::item { padding: 6px 22px; border-radius: 7px; }
QMenu::item:selected { background: $accent; color: $on_accent; }
QMenu::separator { height: 1px; background: $border; margin: 5px 8px; }

/* ---- scrollbars ---------------------------------------------------- */
QScrollBar:vertical { background: transparent; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: $border_strong; min-height: 32px; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: $accent; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 2px; }
QScrollBar::handle:horizontal { background: $border_strong; min-width: 32px; border-radius: 5px; }
QScrollBar::handle:horizontal:hover { background: $accent; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

/* ---- dialog buttons ------------------------------------------------ */
QDialogButtonBox QPushButton { min-width: 84px; }
"""
)

TOKYONIGHT_DARK = _CSS.substitute(**_DARK)
TOKYONIGHT_LIGHT = _CSS.substitute(**_LIGHT)

# --- painted-widget colours (heatmap / progress ring / week chart) -------------

_CHART = {
    "dark": {
        "heatmap": ["#1b2033", "#0e4429", "#006d32", "#26a641", "#39d353"],
        "ring_track": "#2c3145",
        "ring_fill": "#7aa2f7",
        "ring_text": "#c0caf5",
        "chart_empty": "#24283b",
        "chart_fill": "#40c463",
        "chart_text": "#7f88b3",
        "grid_line": "#2c3145",
        "grid_line_strong": "#3d4463",
        "grid_off": "#2c3145",
        "grid_accent": "#7aa2f7",
        "grid_text": "#c0caf5",
        "grid_on_fill": "#15161f",
    },
    "light": {
        "heatmap": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "ring_track": "#d8dee4",
        "ring_fill": "#0969da",
        "ring_text": "#1f2328",
        "chart_empty": "#eaeef2",
        "chart_fill": "#2da44e",
        "chart_text": "#59606a",
        "grid_line": "#e4e8ec",
        "grid_line_strong": "#d0d7de",
        "grid_off": "#d0d7de",
        "grid_accent": "#0969da",
        "grid_text": "#1f2328",
        "grid_on_fill": "#ffffff",
    },
}


def apply_dark(app) -> None:
    app.setStyleSheet(TOKYONIGHT_DARK)


def is_dark() -> bool:
    return bool(QSettings("StreakGrid", "StreakGrid").value(THEME_KEY, True))


def set_dark(dark: bool) -> None:
    QSettings("StreakGrid", "StreakGrid").setValue(THEME_KEY, bool(dark))


def apply_theme(app) -> bool:
    """Apply persisted theme. Returns current dark flag."""
    dark = is_dark()
    app.setStyleSheet(TOKYONIGHT_DARK if dark else TOKYONIGHT_LIGHT)
    return dark


def chart_colors() -> dict:
    """Colours for manually painted widgets, matching the active theme."""
    return dict(_CHART["dark" if is_dark() else "light"])
