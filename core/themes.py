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
    # Calmer light theme inspired by GitHub Light & Atom One Light. The
    # previous palette used pure white #ffffff backgrounds which made the
    # interface feel harsh; the user described it as needing to "calm down."
    # This version uses warm off-whites and a muted dark blue-gray for text,
    # softer borders, and a gentler accent green that doesn't fight the
    # background.
    name            = "Light",
    bg_primary      = "#fafbfc",   # main bg — very light gray, not pure white
    bg_secondary    = "#f1f3f5",   # panel bg — subtle depression
    bg_tertiary     = "#e7ebef",   # input bg — slightly deeper
    bg_alt          = "#eef1f4",   # alt rows
    fg_primary      = "#1f2328",   # text — dark blue-gray, not pure black
    fg_secondary    = "#57606a",   # muted text
    fg_muted        = "#8c959f",   # very muted
    accent          = "#1f7a3f",   # green — muted from the dark theme's #3fbe6f
    accent_alt      = "#0969da",   # GitHub-style blue for links/secondary
    border          = "#d0d7de",   # soft borders
    border_focus    = "#1f7a3f",
    tx_color        = "#cf222e",   # error/TX red
    warn_color      = "#9a6700",   # warm amber
    error_color     = "#cf222e",
    tab_bg          = "#e7ebef",
    tab_selected_bg = "#fafbfc",
    header_bg       = "#e7ebef",
    meter_bg        = "#d8dce0",
    tooltip_bg      = "#fff8c5",   # soft yellow
)

HIGH_CONTRAST = Theme(
    # Accessibility-focused palette. WCAG AAA contrast ratios throughout.
    # Must be visually unmistakable vs Dark theme at a glance:
    #   Dark   → dark grey backgrounds (#1a1a1a), soft green accent
    #   High C → pure black background,  pure white text, vivid cyan/yellow
    name            = "High Contrast",
    bg_primary      = "#000000",   # pure black — maximum contrast
    bg_secondary    = "#0d0d0d",   # barely-off-black for panels
    bg_tertiary     = "#1a1a1a",   # input fields
    bg_alt          = "#060606",
    fg_primary      = "#ffffff",   # pure white text
    fg_secondary    = "#ffff00",   # YELLOW secondary — visually distinct from Dark
    fg_muted        = "#aaaaaa",
    accent          = "#00ffcc",   # vivid cyan — nothing like Dark's green
    accent_alt      = "#ff6600",   # vivid orange for secondary actions
    border          = "#ffffff",   # WHITE borders — fat, visible, unmistakable
    border_focus    = "#00ffcc",
    tx_color        = "#ff2222",
    warn_color      = "#ffcc00",
    error_color     = "#ff2222",
    tab_bg          = "#111111",
    tab_selected_bg = "#000000",
    header_bg       = "#000000",
    meter_bg        = "#000000",
    tooltip_bg      = "#001a11",
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
    "System":        DARK,  # resolved at runtime by _detect_system_theme()
    "Dark":          DARK,
    "Light":         LIGHT,
    "High Contrast": HIGH_CONTRAST,
    "Night":         NIGHT,
    "Custom":        DARK,  # resolved at runtime by custom_theme_from_config()
}


def custom_theme_from_config(cfg) -> Theme:
    """Build a Theme from user-picked colors stored in config."""
    def _c(key: str, default: str) -> str:
        return cfg.get(f"theme.custom.{key}", default) or default

    bg1 = _c("bg_primary",   "#0f0f0f")
    bg2 = _c("bg_secondary", "#1a1a1a")
    fg1 = _c("fg_primary",   "#cccccc")
    acc = _c("accent",       "#3fbe6f")
    tx  = _c("tx_color",     "#ff4444")
    brd = _c("border",       "#2a2a2a")
    return Theme(
        name            = "Custom",
        bg_primary      = bg1,
        bg_secondary    = bg2,
        bg_tertiary     = bg2,
        bg_alt          = bg1,
        fg_primary      = fg1,
        fg_secondary    = "#888888",
        fg_muted        = "#555555",
        accent          = acc,
        accent_alt      = "#44aaff",
        border          = brd,
        border_focus    = acc,
        tx_color        = tx,
        warn_color      = "#eeaa22",
        error_color     = "#cc4444",
        tab_bg          = bg2,
        tab_selected_bg = bg1,
        header_bg       = bg2,
        meter_bg        = "#0a0a0a",
        tooltip_bg      = "#1a2a1a",
    )


def build_stylesheet(t: Theme, font_size: int = 11) -> str:
    """Generate a complete PyQt6 stylesheet from a Theme.
    Font size is propagated to every widget rule explicitly."""
    fs   = max(8, min(20, font_size))
    fs_s = fs - 1
    fs_l = fs + 2
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
    padding: 7px 14px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: {fs}px;
}}
QTabBar::tab:selected {{
    color: {t.accent};
    border-bottom: 2px solid {t.accent};
    font-size: {fs}px;
}}
QTabBar::tab:hover {{
    color: {t.fg_primary};
    background: {t.bg_tertiary};
}}
QFrame {{
    background: {t.bg_primary};
    color: {t.fg_primary};
}}
QFrame[frameShape="4"],
QFrame[frameShape="5"] {{
    color: {t.border};
}}
QGroupBox {{
    border: 1px solid {t.border};
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 4px;
    font-size: {fs}px;
    color: {t.fg_secondary};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: {t.fg_secondary};
    font-size: {fs_s}px;
}}
QPushButton {{
    background: {t.bg_secondary};
    border: 1px solid {t.border};
    border-radius: 4px;
    padding: 4px 10px;
    color: {t.fg_primary};
    font-size: {fs}px;
    min-width: 40px;
}}
QPushButton:hover {{
    background: {t.bg_tertiary};
    border-color: {t.border_focus};
}}
QPushButton:pressed {{
    background: {t.bg_alt};
}}
QPushButton:disabled {{
    color: {t.fg_muted};
    border-color: {t.border};
}}
QLabel {{
    color: {t.fg_primary};
    background: transparent;
    font-size: {fs}px;
}}
QLineEdit {{
    background: {t.bg_secondary};
    border: 1px solid {t.border};
    border-radius: 4px;
    padding: 4px 8px;
    color: {t.fg_primary};
    font-size: {fs}px;
}}
QLineEdit:focus {{
    border-color: {t.border_focus};
}}
QComboBox {{
    background: {t.bg_secondary};
    border: 1px solid {t.border};
    border-radius: 4px;
    padding: 3px 8px;
    color: {t.fg_primary};
    font-size: {fs}px;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QAbstractItemView {{
    background: {t.bg_secondary};
    color: {t.fg_primary};
    selection-background-color: {t.accent};
    selection-color: {t.bg_primary};
    font-size: {fs}px;
}}
QComboBox QAbstractItemView {{
    background: {t.bg_secondary};
    color: {t.fg_primary};
    selection-background-color: {t.accent};
    selection-color: {t.bg_primary};
    border: 1px solid {t.border};
    outline: 0;
}}
QCheckBox {{
    color: {t.fg_primary};
    font-size: {fs}px;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {t.border};
    border-radius: 2px;
    background: {t.bg_secondary};
}}
QCheckBox::indicator:checked {{
    background: {t.accent};
    border-color: {t.accent};
}}
QRadioButton {{
    color: {t.fg_primary};
    font-size: {fs}px;
}}
QTextEdit, QPlainTextEdit {{
    background: {t.bg_secondary};
    border: 1px solid {t.border};
    border-radius: 4px;
    color: {t.fg_primary};
    font-size: {fs}px;
}}
QSpinBox, QDoubleSpinBox,
QDateEdit, QTimeEdit, QDateTimeEdit {{
    background: {t.bg_secondary};
    border: 1px solid {t.border};
    border-radius: 4px;
    padding: 3px 6px;
    color: {t.fg_primary};
    font-size: {fs}px;
}}
QDateEdit::drop-down, QTimeEdit::drop-down,
QDateTimeEdit::drop-down {{
    border: none;
    width: 20px;
}}
QDateEdit:focus, QTimeEdit:focus, QDateTimeEdit:focus {{
    border-color: {t.border_focus};
}}
QProgressBar {{
    background: {t.bg_alt};
    border: 1px solid {t.border};
    border-radius: 3px;
    text-align: center;
    color: {t.fg_primary};
    font-size: {fs_s}px;
}}
QProgressBar::chunk {{
    background: {t.accent};
    border-radius: 2px;
}}
QScrollBar:vertical {{
    background: {t.bg_alt};
    width: 10px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: {t.border};
    border-radius: 5px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {t.border_focus};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {t.bg_alt};
    height: 10px;
    border-radius: 5px;
}}
QScrollBar::handle:horizontal {{
    background: {t.border};
    border-radius: 5px;
    min-width: 20px;
}}
QHeaderView::section {{
    background: {t.bg_secondary};
    color: {t.fg_secondary};
    border: none;
    border-right: 1px solid {t.border};
    padding: 4px 6px;
    font-size: {fs_s}px;
}}
QTableWidget {{
    background: {t.bg_alt};
    gridline-color: {t.border};
    alternate-background-color: {t.bg_secondary};
    font-size: {fs}px;
}}
QTableWidget::item:selected {{
    background: {t.accent};
    color: {t.bg_primary};
}}
QListWidget {{
    background: {t.bg_secondary};
    border: 1px solid {t.border};
    border-radius: 4px;
    font-size: {fs}px;
}}
QTreeWidget {{
    background: {t.bg_secondary};
    border: 1px solid {t.border};
    font-size: {fs}px;
}}
QStatusBar {{
    background: {t.bg_alt};
    color: {t.fg_secondary};
    border-top: 1px solid {t.border};
    font-size: {fs_s}px;
}}
QMenuBar {{
    background: {t.bg_secondary};
    color: {t.fg_primary};
    font-size: {fs}px;
}}
QMenuBar::item:selected {{
    background: {t.accent};
    color: {t.bg_primary};
}}
QMenu {{
    background: {t.bg_secondary};
    border: 1px solid {t.border};
    color: {t.fg_primary};
    font-size: {fs}px;
}}
QMenu::item:selected {{
    background: {t.accent};
    color: {t.bg_primary};
}}
QToolTip {{
    background: {t.bg_secondary};
    border: 1px solid {t.border};
    color: {t.fg_primary};
    padding: 4px;
    font-size: {fs_s}px;
}}
QSplitter::handle {{
    background: {t.border};
}}
QDockWidget {{
    titlebar-close-icon: url(none);
    font-size: {fs}px;
    color: {t.fg_primary};
}}
QDockWidget::title {{
    background: {t.bg_secondary};
    padding: 6px;
    border-bottom: 1px solid {t.border};
    font-size: {fs}px;
    color: {t.fg_primary};
}}
"""
    # High Contrast — add strong overrides that inline stylesheets can't
    # easily hide. White borders everywhere, thick focus rings, vivid text.
    _hc_extra = ""
    if t.name == "High Contrast":
        _hc_extra = f"""
QWidget {{
    border-color: {t.border};
}}
QPushButton {{
    border: 2px solid {t.border};
    color: {t.fg_primary};
    font-weight: bold;
    padding: 4px 10px;
}}
QPushButton:hover {{
    border: 2px solid {t.accent};
    color: {t.accent};
}}
QPushButton:pressed {{
    background: {t.accent};
    color: #000000;
}}
QGroupBox {{
    border: 2px solid {t.border};
    margin-top: 8px;
    font-weight: bold;
    color: {t.fg_secondary};
}}
QGroupBox::title {{
    color: {t.fg_secondary};
    subcontrol-position: top left;
    padding: 0 4px;
}}
QTabBar::tab {{
    border: 2px solid {t.border};
    color: {t.fg_primary};
    font-weight: bold;
    padding: 4px 12px;
}}
QTabBar::tab:selected {{
    border-bottom: 3px solid {t.accent};
    color: {t.accent};
    background: {t.bg_primary};
}}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
QDateEdit, QTimeEdit, QDateTimeEdit {{
    border: 2px solid {t.border};
    color: {t.fg_primary};
}}
QLineEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus,
QDateEdit:focus, QTimeEdit:focus, QDateTimeEdit:focus {{
    border: 2px solid {t.accent};
}}
QLabel {{
    color: {t.fg_primary};
}}
QCheckBox {{
    color: {t.fg_primary};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 2px solid {t.border};
}}
QCheckBox::indicator:checked {{
    background: {t.accent};
    border-color: {t.accent};
}}
QHeaderView::section {{
    background: {t.bg_secondary};
    color: {t.fg_secondary};
    border: 1px solid {t.border};
    font-weight: bold;
    padding: 4px;
}}
QTableWidget {{
    gridline-color: {t.border};
}}
"""

def _detect_system_theme() -> Theme:
    """Detect the OS light/dark preference (Qt 6.5+), fall back to Dark."""
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        app = QApplication.instance()
        if app is not None:
            hints = app.styleHints()
            scheme = getattr(hints, "colorScheme", None)
            if scheme is not None:
                if scheme() == Qt.ColorScheme.Light:
                    return LIGHT
                return DARK
        # Fallback: inspect the window background palette
        from PyQt6.QtGui import QPalette
        if app is not None:
            win = app.palette().color(QPalette.ColorRole.Window)
            # Luminance > 128 means a light background
            lum = 0.299 * win.red() + 0.587 * win.green() + 0.114 * win.blue()
            return LIGHT if lum > 128 else DARK
    except Exception:
        pass
    return DARK


def get_theme(name: str) -> Theme:
    if name in ("System", "System Default", "Auto"):
        return _detect_system_theme()
    return THEMES.get(name, DARK)


def get_stylesheet(name: str, font_size: int = 11) -> str:
    return build_stylesheet(get_theme(name), font_size)
