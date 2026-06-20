from __future__ import annotations
"""SettingsDialog station tab — extracted from settings_dialog.py."""
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



class _SettingsStationTab:
    """Mixed into SettingsDialog."""

    def _build_station_identity_section(self, f: "QFormLayout") -> None:
        self._callsign = QLineEdit()
        self._callsign.setMaxLength(12)
        self._callsign.setPlaceholderText("e.g. W1AW")
        self._callsign.setToolTip("Your FCC callsign. Used in all transmissions.")
        f.addRow("Callsign:", self._callsign)
        self._op_name = QLineEdit()
        self._op_name.setMaxLength(50)
        self._op_name.setPlaceholderText("e.g. John")
        f.addRow("Operator Name:", self._op_name)
        self._grid = QLineEdit()
        self._grid.setMaxLength(8)
        self._grid.setPlaceholderText("e.g. DM79rr")
        self._grid.setToolTip("Maidenhead grid square. Used in FT8, beacons, logs.")
        f.addRow("Grid Square:", self._grid)
        self._itu_region = QComboBox()
        self._itu_region.addItems([
            "Region 2 — Americas (default)",
            "Region 1 — Europe / Africa / Middle East",
            "Region 3 — Asia / Pacific",
        ])
        self._itu_region.setToolTip("ITU region determines band edges for the band plan.")
        f.addRow("ITU Region:", self._itu_region)
        self._license = QComboBox()
        self._license.addItems(["Technician", "General", "Extra", "Other / Non-US"])
        self._license.setToolTip("Shows privilege overlays on the band plan.")
        f.addRow("License Class:", self._license)

    def _build_station_event_callsign_section(self, f: "QFormLayout") -> None:
        f.addRow(_sep())
        _section(f, "Portable / Event Operation")
        self._event_callsign = QLineEdit()
        self._event_callsign.setMaxLength(15)
        self._event_callsign.setPlaceholderText(
            "e.g. W1AW/5  or  W100AW  — leave blank for normal operation")
        self._event_callsign.setToolTip(
            "Portable, mobile, or special-event callsign.\n"
            "Overrides your station callsign for ALL TX modes\n"
            "(FT8, FT4, WSPR, CW, PSK, Winlink …).\n"
            "Clear this field to return to your normal callsign.")
        f.addRow("Event/Portable Call:", self._event_callsign)
        hint = QLabel(
            "Examples: /P portable  /M mobile  /5 different district  "
            "W100AW centennial event")
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size:10px;")
        f.addRow("", hint)

    def _build_station_contest_section(self, f: "QFormLayout") -> None:
        f.addRow(_sep())
        self._station_call = QLineEdit()
        self._station_call.setMaxLength(12)
        self._station_call.setPlaceholderText("Leave blank to use main callsign")
        self._station_call.setToolTip(
            "Station callsign if different from operator "
            "(e.g. club station K4ABC with op W1AW)")
        f.addRow("Station Callsign:", self._station_call)
        self._contest_exchange = QLineEdit()
        self._contest_exchange.setMaxLength(30)
        self._contest_exchange.setPlaceholderText("e.g. CO or 003 or 5NN001")
        f.addRow("Contest Exchange:", self._contest_exchange)

    def _build_station_goals_section(self, f: "QFormLayout") -> None:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        f.addRow(sep)
        self._daily_goal = QSpinBox()
        self._daily_goal.setRange(0, 9999)
        self._daily_goal.setSpecialValueText("No goal")
        self._daily_goal.setSuffix(" QSOs")
        self._daily_goal.setToolTip(
            "Daily QSO goal shown in the log stats bar.\n"
            "Set to 0 to disable.")
        self._daily_goal.lineEdit().setReadOnly(False)
        f.addRow("Daily QSO goal:", self._daily_goal)

    def _build_station_rig_section(self, f: "QFormLayout") -> None:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        f.addRow(sep)
        self._smeter_cal = QSpinBox()
        self._smeter_cal.setRange(-20, 20)
        self._smeter_cal.setValue(0)
        self._smeter_cal.setSuffix(" dB")
        self._smeter_cal.setToolTip(
            "S-meter calibration offset in dB.\n"
            "If your rig reads 3 dB high, enter -3.\n"
            "Applies to the calibrated S-meter display in the Rig tab.\n"
            "Standard reference: S9 = -73 dBm (50 Ω, HF).")
        f.addRow("S-meter cal:", self._smeter_cal)

    def _tab_station(self) -> "QWidget":
        w = _scrolled()
        f = QFormLayout(w)
        f.setSpacing(10)
        f.setContentsMargins(16, 16, 16, 16)
        self._build_station_identity_section(f)
        self._build_station_event_callsign_section(f)
        self._build_station_contest_section(f)
        self._build_station_goals_section(f)
        self._build_station_rig_section(f)
        return w

