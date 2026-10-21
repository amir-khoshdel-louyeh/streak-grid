"""Tray icon — N1: painted icon + minimize-to-tray (X11/Wayland safe)."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget


def make_icon(alert: bool = False) -> QIcon:
    """Painted 3x3 heatmap icon (green; orange when nagging). No asset files."""
    size = 64
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#24283b"))
    painter.drawRoundedRect(0, 0, size, size, 14, 14)
    cells = ["#216e39", "#40c463", "#9be9a8",
             "#30a14e", "#216e39", "#40c463",
             "#9be9a8", "#30a14e", "#216e39"]
    if alert:
        cells = ["#e0af68"] * 9
    pad, gap = 12, 4
    cell = (size - 2 * pad - 2 * gap) // 3
    for i, color in enumerate(cells):
        painter.setBrush(QColor(color))
        x = pad + (i % 3) * (cell + gap)
        y = pad + (i // 3) * (cell + gap)
        painter.drawRoundedRect(x, y, cell, cell, 4, 4)
    painter.end()
    return QIcon(pix)


def create_tray(
    host: QWidget,
    on_show: Callable[[], None] | None = None,
    on_quit: Callable[[], None] | None = None,
) -> QSystemTrayIcon | None:
    """Create tray icon; None when no system tray (headless/Wayland w/o tray)."""
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None
    tray = QSystemTrayIcon(make_icon(), host)
    tray.setToolTip("StreakGrid")
    menu = QMenu()
    show_action = menu.addAction("Show")
    show_action.triggered.connect(on_show or host.show)
    quit_action = menu.addAction("Quit")
    quit_action.triggered.connect(on_quit or host.close)
    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: (on_show or host.show)()
        if reason == QSystemTrayIcon.Trigger
        else None
    )
    tray.show()
    return tray


def add_quick_actions(tray: QSystemTrayIcon | None, on_done=None, on_snooze=None) -> None:
    """Append Done / Snooze 15m actions to existing tray menu (S17-3)."""
    if tray is None:
        return
    menu = tray.contextMenu() or QMenu()
    menu.addSeparator()
    if on_done is not None:
        done_action = menu.addAction("Done (first due)")
        done_action.triggered.connect(on_done)
    if on_snooze is not None:
        snooze_action = menu.addAction("Snooze 15m")
        snooze_action.triggered.connect(on_snooze)
    tray.setContextMenu(menu)


def minimize_to_tray(window: QWidget, tray: QSystemTrayIcon | None, event) -> bool:
    """Hide to tray on close when tray exists. Returns True if handled."""
    if tray is not None and tray.isVisible():
        event.ignore()
        window.hide()
        return True
    return False
