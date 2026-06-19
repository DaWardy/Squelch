from __future__ import annotations
"""SettingsDialog appearance tab — extracted from settings_dialog.py."""
from PyQt6.QtWidgets import (QWidget, QFormLayout, QScrollArea, QFrame,
    QLabel, QLineEdit, QComboBox, QSpinBox, QCheckBox, QHBoxLayout,
    QVBoxLayout, QPushButton, QGroupBox, QDoubleSpinBox)
from PyQt6.QtCore import Qt

# (key, display label, Dark default)
_CUSTOM_COLORS = [
    ("bg_primary",   "Background",   "#0f0f0f"),
    ("bg_secondary", "Panels",       "#1a1a1a"),
    ("fg_primary",   "Text",         "#cccccc"),
    ("accent",       "Accent",       "#3fbe6f"),
    ("tx_color",     "TX / Alert",   "#ff4444"),
    ("border",       "Borders",      "#2a2a2a"),
]

def _scrolled() -> QWidget:
    """Return a plain widget (most tabs don't need scrolling)."""
    return QWidget()


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("margin:4px 0;")
    return f


def _section(form: QFormLayout, title: str):
    lbl = QLabel(title)
    lbl.setStyleSheet(
        "color:#3fbe6f;"
        "font-weight:bold;margin-top:8px;")
    form.addRow(lbl)


def _flatten(d: dict, prefix: str = "") -> dict:
    result = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result.update(_flatten(v, key))
        else:
            result[key] = v
    return result



class _SettingsAppearanceTab:
    """Mixed into SettingsDialog."""

    def _build_appearance_theme_section(self, f: "QFormLayout") -> None:
        _section(f, "Font")
        self._font_size = QComboBox()
        for size, label in [
            (10, "Small (10pt)"), (11, "Normal (11pt) — default"),
            (13, "Large (13pt)"), (15, "X-Large (15pt)"), (18, "XX-Large (18pt)"),
        ]:
            self._font_size.addItem(label, size)
        self._font_size.setToolTip(
            "Affects all labels, tooltips, and help text. "
            "Larger sizes for accessibility.")
        f.addRow("Font Size:", self._font_size)
        _section(f, "Theme")
        theme_note = QLabel("Use View → Theme to change the colour theme.")
        theme_note.setStyleSheet("color:#3fbe6f;")
        f.addRow("", theme_note)
        self._units = QComboBox()
        self._units.addItem("Metric (km, meters)", "metric")
        self._units.addItem("Imperial (miles, feet)", "imperial")
        self._units.setToolTip(
            "Units for distances and altitudes shown across the app "
            "(Local RF, log, satellites, map).")
        f.addRow("Units:", self._units)
        self._freq_units = QComboBox()
        self._freq_units.addItem("MHz (megahertz) — default", "MHz")
        self._freq_units.addItem("kHz (kilohertz)", "kHz")
        self._freq_units.addItem("Hz (hertz)", "Hz")
        self._freq_units.setToolTip(
            "Display unit for frequencies across the app.\n"
            "Affects the RF Lab watchlist, log entry form, and other panels.\n"
            "The VFO display always uses MHz.")
        f.addRow("Frequency Units:", self._freq_units)
        self._build_custom_colors_section(f)

    def _build_custom_colors_section(self, f: "QFormLayout") -> None:
        _section(f, "Custom Theme Colors")
        hint = QLabel(
            "Select View → Theme → Custom to apply these colors.")
        hint.setStyleSheet("color:#888;")
        f.addRow("", hint)
        self._color_btns: dict = {}
        for key, label, _default in _CUSTOM_COLORS:
            btn = QPushButton()
            btn.setFixedSize(64, 22)
            btn.setToolTip(f"Click to pick {label} color")
            btn.clicked.connect(
                lambda _, k=key: self._pick_custom_color(k))
            self._color_btns[key] = btn
            f.addRow(f"{label}:", btn)

    def _pick_custom_color(self, key: str) -> None:
        from PyQt6.QtWidgets import QColorDialog
        from PyQt6.QtGui import QColor
        btn = self._color_btns.get(key)
        if not btn:
            return
        stored = btn.property("hex_color") or "#888888"
        col = QColorDialog.getColor(QColor(stored), self, "Choose color")
        if col.isValid():
            h = col.name()
            btn.setProperty("hex_color", h)
            btn.setStyleSheet(
                f"background:{h};border:1px solid #555;"
                f"border-radius:2px;")

    def _build_appearance_layout_section(self, f: "QFormLayout") -> None:
        _section(f, "Layout")
        self._layout_locked = QCheckBox(
            "Lock UI layout (prevent accidental tab reorder)")
        f.addRow("", self._layout_locked)
        self._show_tooltips = QCheckBox("Show extended tooltips")
        self._show_tooltips.setChecked(True)
        f.addRow("", self._show_tooltips)
        self._clock_utc = QCheckBox(
            "Show UTC time in top bar (uncheck for local)")
        self._clock_utc.setChecked(True)
        f.addRow("", self._clock_utc)
        _section(f, "Status Bar")
        self._sb_show_grid = QCheckBox("Show grid square in status bar")
        self._sb_show_grid.setChecked(True)
        f.addRow("", self._sb_show_grid)
        self._sb_show_band = QCheckBox("Show current band in status bar")
        self._sb_show_band.setChecked(True)
        f.addRow("", self._sb_show_band)

    def _tab_appearance(self) -> "QWidget":
        w = _scrolled()
        f = QFormLayout(w)
        f.setSpacing(10)
        f.setContentsMargins(16, 16, 16, 16)
        self._build_appearance_theme_section(f)
        self._build_appearance_layout_section(f)
        return w

