"""Screen sizing — keep windows and dialogs inside the display they open on.

Small laptops, 1366x768 panels at 150% scaling and multi-monitor setups all
report a much smaller *usable* area than the raw resolution, so every window
that has a preferred size is clamped through here instead of hard-coding one.
"""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QWidget

MARGIN = 48          # room for window decorations, panels and docks
FLOOR = QSize(320, 240)  # never clamp below this


def available_size(margin: int = MARGIN) -> QSize:
    """Usable size of the primary screen, minus `margin`."""
    screen = QApplication.primaryScreen()
    if screen is None:
        return QSize(1024, 720)
    area = screen.availableGeometry()
    return QSize(max(FLOOR.width(), area.width() - margin),
                 max(FLOOR.height(), area.height() - margin))


def clamp_size(preferred: QSize, minimum: QSize | None = None,
               margin: int = MARGIN) -> QSize:
    """`preferred` shrunk to the screen, but not below `minimum`.

    The screen always wins: on a display smaller than the preferred minimum
    the window is allowed to be smaller, otherwise it could not be used at all.
    """
    avail = available_size(margin)
    size = QSize(min(preferred.width(), avail.width()),
                 min(preferred.height(), avail.height()))
    if minimum is not None:
        floor = QSize(min(minimum.width(), avail.width()),
                      min(minimum.height(), avail.height()))
        size = QSize(max(size.width(), floor.width()),
                     max(size.height(), floor.height()))
    return size


def fit_to_screen(widget: QWidget, preferred: QSize, minimum: QSize | None = None,
                  margin: int = MARGIN) -> QSize:
    """Resize `widget` towards `preferred`, but inside the screen.

    A minimum larger than the screen is trimmed, otherwise the window could
    not be made small enough to use on that display.
    """
    size = clamp_size(preferred, minimum, margin)
    if minimum is not None:
        widget.setMinimumSize(QSize(min(minimum.width(), size.width()),
                                    min(minimum.height(), size.height())))
    widget.resize(size)
    return size


def compact_width(width: int, threshold: int) -> bool:
    """True when a layout should switch to its narrow form."""
    return width < threshold
