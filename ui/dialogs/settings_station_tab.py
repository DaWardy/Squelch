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

    def _build_station_location_section(self, f: "QFormLayout") -> None:
        from core import gps
        f.addRow(_sep())
        _section(f, "Location source")
        self._gps_source = QComboBox()
        self._gps_source.addItem("Manual entry", "manual")
        self._gps_source.addItem("Windows location", "windows")
        self._gps_source.addItem("GPS serial (NMEA)", "serial")
        self._gps_source.setToolTip(
            "Where the station grid/lat-lon comes from.\n"
            "Manual: type it above.  Windows: ask the OS for a one-shot fix.\n"
            "GPS serial: read NMEA sentences from a connected receiver.")
        self._gps_source.currentIndexChanged.connect(self._gps_source_changed)
        f.addRow("Source:", self._gps_source)

        port_row = QHBoxLayout()
        self._gps_port = QComboBox()
        self._gps_port.setEditable(True)
        self._gps_port.setMinimumWidth(120)
        self._gps_port.setToolTip("Serial port of the GPS receiver (e.g. COM5).")
        port_refresh = QPushButton("↻")
        port_refresh.setFixedWidth(32)
        port_refresh.setToolTip("Rescan serial ports")
        port_refresh.clicked.connect(self._gps_refresh_ports)
        port_row.addWidget(self._gps_port, 1)
        port_row.addWidget(port_refresh)
        f.addRow("Serial port:", port_row)

        self._gps_baud = QComboBox()
        for b in gps.COMMON_BAUDS:
            self._gps_baud.addItem(str(b), b)
        self._gps_baud.setCurrentText(str(gps.DEFAULT_BAUD))
        f.addRow("Baud rate:", self._gps_baud)

        self._gps_auto_grid = QCheckBox("Auto-update grid from GPS fixes")
        self._gps_auto_grid.setChecked(True)
        self._gps_auto_grid.setToolTip(
            "When on, a new fix updates the station grid/lat-lon automatically.")
        f.addRow("", self._gps_auto_grid)

        fix_row = QHBoxLayout()
        self._gps_getfix_btn = QPushButton("Get fix")
        self._gps_getfix_btn.setToolTip(
            "Read a single position now from the selected source.")
        self._gps_getfix_btn.clicked.connect(self._gps_get_fix)
        fix_row.addWidget(self._gps_getfix_btn)
        fix_row.addStretch()
        f.addRow("", fix_row)

        self._gps_status = QLabel("No fix yet.")
        self._gps_status.setWordWrap(True)
        self._gps_status.setStyleSheet("font-size:11px;")
        f.addRow("", self._gps_status)
        self._gps_refresh_ports()

    def _build_station_rig_section(self, f: "QFormLayout") -> None:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        f.addRow(sep)
        self._k_index_alarm = QSpinBox()
        self._k_index_alarm.setRange(0, 9)
        self._k_index_alarm.setValue(0)
        self._k_index_alarm.setSpecialValueText("Off")
        self._k_index_alarm.setToolTip(
            "Sound an alert when K-index reaches or exceeds this value.\n"
            "K ≥ 4 = elevated activity; K ≥ 5 = storm G1.\n"
            "Set to 0 to disable.")
        f.addRow("K-index alarm:", self._k_index_alarm)
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
        self._build_station_location_section(f)
        self._build_station_event_callsign_section(f)
        self._build_station_contest_section(f)
        self._build_station_goals_section(f)
        self._build_station_rig_section(f)
        return w

    # ── Location source handlers ──────────────────────────────────────────

    def _gps_refresh_ports(self) -> None:
        from core import gps
        cur = self._gps_port.currentText().strip()
        self._gps_port.clear()
        ports = gps.list_serial_ports()
        self._gps_port.addItems(ports)
        if cur:
            self._gps_port.setCurrentText(cur)
        if not ports and not cur:
            self._gps_port.setEditText("")

    def _gps_source_changed(self, *_a) -> None:
        is_serial = self._gps_source.currentData() == "serial"
        self._gps_port.setEnabled(is_serial)
        self._gps_baud.setEnabled(is_serial)
        src = self._gps_source.currentData()
        self._gps_getfix_btn.setEnabled(src in ("serial", "windows"))

    def _gps_set_status(self, text: str, ok: bool = True) -> None:
        from core.themes import get_theme
        t = get_theme(self.cfg.get("ui.theme", "Dark"))
        color = t.accent if ok else t.fg_muted
        self._gps_status.setStyleSheet(f"font-size:11px;color:{color};")
        self._gps_status.setText(text)

    def _gps_get_fix(self) -> None:
        src = self._gps_source.currentData()
        self._gps_set_status("Requesting a fix…")
        if src == "windows":
            from core.gps import WindowsLocationWorker
            self._gps_worker = WindowsLocationWorker(self)
            self._gps_worker.fix_received.connect(self._on_gps_settings_fix)
            self._gps_worker.error_occurred.connect(self._on_gps_settings_error)
            self._gps_worker.request_fix(timeout_s=10.0)
        elif src == "serial":
            from core.gps import SerialGPSReader
            port = self._gps_port.currentText().strip()
            baud = self._gps_baud.currentData() or 4800
            self._gps_tmp_reader = SerialGPSReader(self)
            self._gps_tmp_reader.fix_received.connect(self._on_gps_settings_fix)
            self._gps_tmp_reader.error_occurred.connect(
                self._on_gps_settings_error)
            if not self._gps_tmp_reader.start(port, int(baud)):
                self._on_gps_settings_error("Could not open serial port")

    def _on_gps_settings_fix(self, fix) -> None:
        """Slot (main thread) — write a one-shot fix into config + the grid box."""
        reader = getattr(self, "_gps_tmp_reader", None)
        if reader is not None:
            reader.stop()
            self._gps_tmp_reader = None
        try:
            from core.location import _latlon_to_grid
            grid = _latlon_to_grid(fix.lat, fix.lon)
            self.cfg.set("location.lat", float(fix.lat))
            self.cfg.set("location.lon", float(fix.lon))
            self.cfg.grid = grid
            self.cfg.save()
            self._grid.setText(grid)
            self._gps_set_status(
                f"Fix: {fix.lat:.5f}, {fix.lon:.5f}  →  {grid}")
        except Exception as e:
            self._on_gps_settings_error(f"Fix handling failed: {e}")

    def _on_gps_settings_error(self, msg: str) -> None:
        reader = getattr(self, "_gps_tmp_reader", None)
        if reader is not None:
            reader.stop()
            self._gps_tmp_reader = None
        self._gps_set_status(msg, ok=False)

