"""SettingsDialog appearance tab — extracted from settings_dialog.py."""
from __future__ import annotations
from PyQt6.QtWidgets import (QWidget, QFormLayout, QScrollArea, QFrame,
    QLabel, QLineEdit, QComboBox, QSpinBox, QCheckBox, QHBoxLayout,
    QVBoxLayout, QPushButton, QGroupBox, QDoubleSpinBox)
from PyQt6.QtCore import Qt

def _scrolled() -> QWidget:
    """Return a plain widget (most tabs don't need scrolling)."""
    return QWidget()


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(
        "color:#1a1a1a;margin:4px 0;")
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

    def _tab_appearance(self) -> QWidget:
        w = _scrolled()
        f = QFormLayout(w)
        f.setSpacing(10)
        f.setContentsMargins(16, 16, 16, 16)

        _section(f, "Theme")
        self._theme = QComboBox()
        self._theme.addItems([
            "System", "Dark", "Light",
            "High Contrast", "Night"])
        self._theme.setToolTip(
            "Night mode uses deep red to preserve dark adaptation.")
        f.addRow("Theme:", self._theme)

        _section(f, "Font")
        self._font_size = QComboBox()
        for size, label in [
            (10, "Small (10pt)"),
            (11, "Normal (11pt) — default"),
            (13, "Large (13pt)"),
            (15, "X-Large (15pt)"),
            (18, "XX-Large (18pt)"),
        ]:
            self._font_size.addItem(label, size)
        self._font_size.setToolTip(
            "Affects all labels, tooltips, and help text. "
            "Larger sizes for accessibility.")
        f.addRow("Font Size:", self._font_size)

        self._units = QComboBox()
        self._units.addItem("Metric (km, meters)", "metric")
        self._units.addItem("Imperial (miles, feet)", "imperial")
        self._units.setToolTip(
            "Units for distances and altitudes shown across the app "
            "(Local RF, log, satellites, map).")
        f.addRow("Units:", self._units)

        _section(f, "Layout")
        self._layout_locked = QCheckBox(
            "Lock UI layout (prevent accidental tab reorder)")
        f.addRow("", self._layout_locked)

        self._show_tooltips = QCheckBox(
            "Show extended tooltips")
        self._show_tooltips.setChecked(True)
        f.addRow("", self._show_tooltips)

        self._clock_utc = QCheckBox(
            "Show UTC time in top bar (uncheck for local)")
        self._clock_utc.setChecked(True)
        f.addRow("", self._clock_utc)

        _section(f, "Status Bar")
        self._sb_show_grid = QCheckBox(
            "Show grid square in status bar")
        self._sb_show_grid.setChecked(True)
        f.addRow("", self._sb_show_grid)

        self._sb_show_band = QCheckBox(
            "Show current band in status bar")
        self._sb_show_band.setChecked(True)
        f.addRow("", self._sb_show_band)

        return w

