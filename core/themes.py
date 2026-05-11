# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
#
# This program is free software: you can redistribute it
# and/or modify it under the terms of the GNU General
# Public License as published by the Free Software
# Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General
# Public License along with this program. If not, see
# <https://www.gnu.org/licenses/>.

"""
Squelch -- core/themes.py
Application theme definitions.
Dark (default), Light, High Contrast, Night (red-safe for dark ops).
"""

from dataclasses import dataclass


@dataclass
class Theme:
    name:            str
    bg_primary:      str   # main background
    bg_secondary:    str   # panel/group background
    bg_tertiary:     str   # input field background
    bg_alt:          str   # alternating table row
    fg_primary:      str   # main text
    fg_secondary:    str   # secondary text
    fg_muted:        str   # disabled/hint text
    accent:          str   # primary accent (green in dark)
    accent_alt:      str   # secondary accent
    border:          str   # widget borders
    border_focus:    str   # focused input border
    tx_color:        str   # PTT/TX indicator
    warn_color:      str   # warning
    error_color:     str   # error
    tab_bg:          str   # tab background
    tab_selected_bg: str   # selected tab background
    header_bg:       str   # table header background
    meter_bg:        str   # meter/progress background
    tooltip_bg:      str   # tooltip background


DARK = Theme(
    name            = "Dark",
    bg_primary      = "#0f0f0f",
    bg_secondary    = "#1a1a1a",
    bg_tertiary     = "#141414",
    bg_alt          = "#111111",
    fg_primary      = "#cccccc",
    fg_secondary    = "#888888",
    fg_muted        = "#555555",
    accent          = "#3fbe6f",
    accent_alt      = "#44aaff",
    border          = "#2a2a2a",
    border_focus    = "#3fbe6f",
    tx_color        = "#ff4444",
    warn_color      = "#eeaa22",
    error_color     = "#cc4444",
    tab_bg          = "#1a1a1a",
    tab_selected_bg = "#111111",
    header_bg       = "#141414",
    meter_bg        = "#0a0a0a",
    tooltip_bg      = "#1a2a1a",
)

LIGHT = Theme(
    name            = "Light",
    bg_primary      = "#f5f5f5",
    bg_secondary    = "#ffffff",
    bg_tertiary     = "#eeeeee",
    bg_alt          = "#f9f9f9",
    fg_primary      = "#1a1a1a",
    fg_secondary    = "#555555",
    fg_muted        = "#aaaaaa",
    accent          = "#1a7a3f",
    accent_alt      = "#1a5aaa",
    border          = "#cccccc",
    border_focus    = "#1a7a3f",
    tx_color        = "#cc2222",
    warn_color      = "#cc8800",
    error_color     = "#cc2222",
    tab_bg          = "#e0e0e0",
    tab_selected_bg = "#ffffff",
    header_bg       = "#e8e8e8",
    meter_bg        = "#dddddd",
    tooltip_bg      = "#ffffcc",
)

HIGH_CONTRAST = Theme(
    name            = "High Contrast",
    bg_primary      = "#000000",
    bg_secondary    = "#0a0a0a",
    bg_tertiary     = "#111111",
    bg_alt          = "#050505",
    fg_primary      = "#ffffff",
    fg_secondary    = "#dddddd",
    fg_muted        = "#888888",
    accent          = "#00ff88",
    accent_alt      = "#00aaff",
    border          = "#444444",
    border_focus    = "#00ff88",
    tx_color        = "#ff0000",
    warn_color      = "#ffaa00",
    error_color     = "#ff0000",
    tab_bg          = "#111111",
    tab_selected_bg = "#000000",
    header_bg       = "#111111",
    meter_bg        = "#000000",
    tooltip_bg      = "#002200",
)

NIGHT = Theme(
    name            = "Night (Red-safe)",
    bg_primary      = "#0a0000",
    bg_secondary    = "#150000",
    bg_tertiary     = "#1a0000",
    bg_alt          = "#120000",
    fg_primary      = "#ff9999",
    fg_secondary    = "#cc6666",
    fg_muted        = "#883333",
    accent          = "#ff4444",
    accent_alt      = "#ff8844",
    border          = "#331111",
    border_focus    = "#ff4444",
    tx_color        = "#ff0000",
    warn_color      = "#ff8800",
    error_color     = "#ff2222",
    tab_bg          = "#150000",
    tab_selected_bg = "#0a0000",
    header_bg       = "#1a0000",
    meter_bg        = "#080000",
    tooltip_bg      = "#200000",
)

THEMES: dict[str, Theme] = {
    "Dark":          DARK,
    "Light":         LIGHT,
    "High Contrast": HIGH_CONTRAST,
    "Night":         NIGHT,
}


def build_stylesheet(t: Theme, font_size: int = 11) -> str:
    """Generate a complete PyQt6 stylesheet from a Theme."""
    fs   = max(8, min(20, font_size))
    fs_s = fs - 1   # small
    fs_l = fs + 2   # large

    return f"""
QMainWindow, QWidget, QDialog {{
    background-color: {t.bg_primary};
    color: {t.fg_primary};
    font-family: 'Segoe UI', 'DejaVu Sans', sans-serif;
    font-size: {fs}px;
}}
QTabWidget::pane {{
    border: 1px solid {t.border};
    background: {t.bg_secondary};
}}
QTabBar::tab {{
    background: {t.tab_bg};
    color: {t.fg_secondary};
    padding: 7px 12px;
    border: 1px solid {t.border};
    border-bottom: none;
    margin-right: 2px;
    font-size: {fs_s}px;
}}
QTabBar::tab:selected {{
    background: {t.tab_selected_bg};
    color: {t.accent};
    border-bottom: 2px solid {t.accent};
}}
QTabBar::tab:hover {{
    background: {t.bg_secondary};
    color: {t.fg_primary};
}}
QGroupBox {{
    border: 1px solid {t.border};
    border-radius: 5px;
    margin-top: 8px;
    padding-top: 6px;
    font-size: {fs_s}px;
    color: {t.fg_secondary};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}}
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{
    background: {t.bg_tertiary};
    border: 1px solid {t.border};
    border-radius: 4px;
    padding: 3px 7px;
    color: {t.fg_primary};
    min-width: 60px;
}}
QComboBox {{
    padding-right: 20px;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background: {t.bg_secondary};
    color: {t.fg_primary};
    border: 1px solid {t.border};
    selection-background-color: {t.accent};
    selection-color: {t.bg_primary};
    min-width: 150px;
}}
QComboBox:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QLineEdit:focus {{
    border-color: {t.border_focus};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 16px;
    border: none;
    background: {t.bg_secondary};
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {t.border};
}}
QPushButton {{
    background: {t.bg_secondary};
    border: 1px solid {t.border};
    border-radius: 4px;
    padding: 4px 10px;
    color: {t.fg_primary};
    min-width: 40px;
}}
QPushButton:hover {{
    background: {t.bg_tertiary};
    border-color: {t.fg_muted};
}}
QPushButton:pressed {{
    background: {t.bg_primary};
}}
QPushButton:disabled {{
    color: {t.fg_muted};
    border-color: {t.border};
}}
QProgressBar {{
    background: {t.meter_bg};
    border: 1px solid {t.border};
    border-radius: 3px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {t.accent};
    border-radius: 2px;
}}
QScrollBar:vertical {{
    background: {t.bg_primary};
    width: 8px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {t.border};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {t.fg_muted};
}}
QScrollBar:horizontal {{
    background: {t.bg_primary};
    height: 8px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: {t.border};
    border-radius: 4px;
    min-width: 20px;
}}
QStatusBar {{
    background: {t.bg_primary};
    border-top: 1px solid {t.border};
    color: {t.fg_muted};
    font-size: {fs_s}px;
}}
QMenuBar {{
    background: {t.bg_primary};
    color: {t.fg_secondary};
    border-bottom: 1px solid {t.border};
}}
QMenuBar::item:selected {{
    background: {t.bg_secondary};
    color: {t.accent};
}}
QMenu {{
    background: {t.bg_secondary};
    border: 1px solid {t.border};
    color: {t.fg_primary};
    min-width: 160px;
}}
QMenu::item:selected {{
    background: {t.accent};
    color: {t.bg_primary};
}}
QMenu::separator {{
    height: 1px;
    background: {t.border};
    margin: 2px 8px;
}}
QTableWidget {{
    background: {t.bg_primary};
    alternate-background-color: {t.bg_alt};
    color: {t.fg_primary};
    gridline-color: {t.border};
    selection-background-color: {t.accent};
    selection-color: {t.bg_primary};
    font-size: {fs_s}px;
    font-family: 'Courier New', monospace;
    border: 1px solid {t.border};
}}
QHeaderView::section {{
    background: {t.header_bg};
    color: {t.fg_secondary};
    border: none;
    border-right: 1px solid {t.border};
    font-size: {fs_s}px;
    padding: 3px 6px;
}}
QTableWidget::item:hover {{
    background: {t.bg_secondary};
}}
QLabel {{
    color: {t.fg_primary};
}}
QCheckBox {{
    color: {t.fg_secondary};
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {t.border};
    border-radius: 3px;
    background: {t.bg_tertiary};
}}
QCheckBox::indicator:checked {{
    background: {t.accent};
    border-color: {t.accent};
}}
QSplitter::handle {{
    background: {t.border};
}}
QSplitter::handle:horizontal {{
    width: 3px;
}}
QSplitter::handle:vertical {{
    height: 3px;
}}
QToolTip {{
    background: {t.tooltip_bg};
    color: {t.fg_primary};
    border: 1px solid {t.border_focus};
    padding: 4px 8px;
    font-size: {fs_s}px;
}}
QTextEdit, QPlainTextEdit {{
    background: {t.bg_primary};
    color: {t.fg_primary};
    border: 1px solid {t.border};
    border-radius: 3px;
    font-family: 'Courier New', monospace;
    font-size: {fs_s}px;
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
"""


def get_theme(name: str) -> Theme:
    return THEMES.get(name, DARK)


def get_stylesheet(name: str, font_size: int = 11) -> str:
    return build_stylesheet(get_theme(name), font_size)
