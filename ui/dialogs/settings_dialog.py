from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- ui/dialogs/settings_dialog.py
Full in-app settings editor.
Organized into tabbed sections:
  Station, Audio, Digital Modes, APIs,
  Appearance, Paths, Advanced
"""

import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QWidget, QFormLayout, QLabel, QLineEdit,
    QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox,
    QPushButton, QDialogButtonBox, QGroupBox,
    QScrollArea, QFrame, QSlider, QFileDialog,
    QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

log = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """
    Full settings editor — all user-configurable options
    in one organized dialog. Changes applied on OK.
    """

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.cfg    = config
        self._dirty = False
        self.setWindowTitle("Settings — Squelch")
        self.setMinimumSize(640, 520)
        self.resize(720, 580)
        self._build()
        self._load_all()

    # ── Build ─────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            "QTabBar::tab{padding:6px 14px;}"
            "QTabBar::tab:selected{color:#3fbe6f;}")

        self._tabs.addTab(self._tab_station(),   "🎙  Station")
        self._tabs.addTab(self._tab_audio(),     "🔊  Audio")
        self._tabs.addTab(self._tab_modes(),     "📡  Digital Modes")
        self._tabs.addTab(self._tab_apis(),      "🔑  APIs")
        self._tabs.addTab(self._tab_appearance(),"🎨  Appearance")
        self._tabs.addTab(self._tab_advanced(),  "⚙  Advanced")
        self._tabs.addTab(self._tab_sdr_drivers(),"📻  SDR Hardware")

        root.addWidget(self._tabs, 1)

        # Reset / OK / Cancel
        btn_row = QHBoxLayout()
        reset = QPushButton("Reset to Defaults")
        reset.clicked.connect(self._reset_defaults)
        btn_row.addWidget(reset)
        btn_row.addStretch()
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply)
        btns.accepted.connect(self._save_and_accept)
        btns.rejected.connect(self.reject)
        btns.button(
            QDialogButtonBox.StandardButton.Apply
        ).clicked.connect(self._apply)
        btn_row.addWidget(btns)
        root.addLayout(btn_row)

    # ── Tab: Station ──────────────────────────────────────────

    def _tab_station(self) -> QWidget:
        w = _scrolled()
        f = QFormLayout(w)
        f.setSpacing(10)
        f.setContentsMargins(16, 16, 16, 16)

        # Callsign
        self._callsign = QLineEdit()
        self._callsign.setMaxLength(12)
        self._callsign.setPlaceholderText("e.g. NR6U")
        self._callsign.setToolTip(
            "Your FCC callsign. Used in all transmissions.")
        f.addRow("Callsign:", self._callsign)

        # Operator name
        self._op_name = QLineEdit()
        self._op_name.setMaxLength(50)
        self._op_name.setPlaceholderText("e.g. John")
        f.addRow("Operator Name:", self._op_name)

        # Grid square
        self._grid = QLineEdit()
        self._grid.setMaxLength(8)
        self._grid.setPlaceholderText("e.g. DM79rr")
        self._grid.setToolTip(
            "Maidenhead grid square. Used in FT8, beacons, logs.")
        f.addRow("Grid Square:", self._grid)

        # ITU Region
        self._itu_region = QComboBox()
        self._itu_region.addItems([
            "Region 2 — Americas (default)",
            "Region 1 — Europe / Africa / Middle East",
            "Region 3 — Asia / Pacific",
        ])
        self._itu_region.setToolTip(
            "ITU region determines band edges for the band plan.")
        f.addRow("ITU Region:", self._itu_region)

        # License class
        self._license = QComboBox()
        self._license.addItems([
            "Technician", "General", "Extra",
            "Other / Non-US"])
        self._license.setToolTip(
            "Shows privilege overlays on the band plan.")
        f.addRow("License Class:", self._license)

        f.addRow(_sep())

        # Station callsign vs operator callsign
        self._station_call = QLineEdit()
        self._station_call.setMaxLength(12)
        self._station_call.setPlaceholderText(
            "Leave blank to use main callsign")
        self._station_call.setToolTip(
            "Station callsign if different from operator "
            "(e.g. club station K4ABC with op NR6U)")
        f.addRow("Station Callsign:", self._station_call)

        self._contest_exchange = QLineEdit()
        self._contest_exchange.setMaxLength(30)
        self._contest_exchange.setPlaceholderText(
            "e.g. CO or 003 or 5NN001")
        f.addRow("Contest Exchange:", self._contest_exchange)

        return w

    # ── Tab: Audio ────────────────────────────────────────────

    def _tab_audio(self) -> QWidget:
        w = _scrolled()
        f = QFormLayout(w)
        f.setSpacing(10)
        f.setContentsMargins(16, 16, 16, 16)

        _section(f, "Digital Mode Audio (FT8/FT4/WSPR)")

        # Refresh device list
        self._refresh_audio_btn = QPushButton(
            "↺ Refresh Device List")
        self._refresh_audio_btn.setFixedWidth(180)
        self._refresh_audio_btn.clicked.connect(
            self._refresh_audio_devices)
        f.addRow("", self._refresh_audio_btn)

        self._audio_input = QComboBox()
        self._audio_input.setEditable(True)
        self._audio_input.setToolTip(
            "Input from radio to PC (e.g. VB-Cable / SignaLink)")
        f.addRow("Audio Input:", self._audio_input)

        self._audio_output = QComboBox()
        self._audio_output.setEditable(True)
        self._audio_output.setToolTip(
            "Output from PC to radio")
        f.addRow("Audio Output:", self._audio_output)

        self._audio_sample_rate = QComboBox()
        self._audio_sample_rate.addItems([
            "48000 Hz (recommended)",
            "44100 Hz",
            "96000 Hz",
        ])
        f.addRow("Sample Rate:", self._audio_sample_rate)

        f.addRow(_sep())
        _section(f, "Digital Voice Audio (DSD+ / OP25)")

        self._digital_input = QComboBox()
        self._digital_input.setEditable(True)
        self._digital_input.setToolTip(
            "Audio from SDR or rig for P25/DMR decode")
        f.addRow("Decode Input:", self._digital_input)

        self._digital_output = QComboBox()
        self._digital_output.setEditable(True)
        self._digital_output.setToolTip(
            "Speaker output for decoded voice")
        f.addRow("Voice Output:", self._digital_output)

        # Populate with known devices
        self._refresh_audio_devices()

        return w

    # ── Tab: Digital Modes ────────────────────────────────────

    def _tab_modes(self) -> QWidget:
        w = _scrolled()
        f = QFormLayout(w)
        f.setSpacing(10)
        f.setContentsMargins(16, 16, 16, 16)

        _section(f, "WSJT-X / FT8")

        self._auto_launch_wsjtx = QCheckBox(
            "Auto-launch WSJT-X when FT8/FT4/WSPR selected")
        self._auto_launch_wsjtx.setChecked(True)
        f.addRow("", self._auto_launch_wsjtx)

        self._auto_log_ft8 = QCheckBox(
            "Auto-log FT8 QSOs from WSJT-X")
        self._auto_log_ft8.setChecked(True)
        f.addRow("", self._auto_log_ft8)

        self._wsjtx_udp_port = QSpinBox()
        self._wsjtx_udp_port.setRange(1024, 65535)
        self._wsjtx_udp_port.setValue(2237)
        self._wsjtx_udp_port.setToolTip(
            "UDP port WSJT-X broadcasts on (default 2237)")
        f.addRow("WSJT-X UDP Port:", self._wsjtx_udp_port)

        self._cq_timeout_cycles = QSpinBox()
        self._cq_timeout_cycles.setRange(1, 10)
        self._cq_timeout_cycles.setValue(2)
        self._cq_timeout_cycles.setToolTip(
            "Return to IDLE if no response after N CQ cycles")
        f.addRow("CQ Timeout (cycles):", self._cq_timeout_cycles)

        f.addRow(_sep())
        _section(f, "PTT / Safety")

        self._ptt_timeout = QSpinBox()
        self._ptt_timeout.setRange(30, 600)
        self._ptt_timeout.setValue(180)
        self._ptt_timeout.setSuffix(" seconds")
        self._ptt_timeout.setToolTip(
            "Maximum TX time before PTT watchdog releases")
        f.addRow("PTT Timeout:", self._ptt_timeout)

        self._tx_inhibit = QCheckBox(
            "TX Inhibit (receive only — never transmit)")
        self._tx_inhibit.setToolTip(
            "Prevents all transmissions. Useful for monitoring.")
        f.addRow("", self._tx_inhibit)

        f.addRow(_sep())
        _section(f, "Logging")

        self._log_dupes = QCheckBox(
            "Warn on duplicate callsign within same band/mode")
        self._log_dupes.setChecked(True)
        f.addRow("", self._log_dupes)

        self._rst_default_ssb = QLineEdit("59")
        self._rst_default_ssb.setMaxLength(3)
        self._rst_default_ssb.setFixedWidth(60)
        f.addRow("Default RST (SSB/FM):", self._rst_default_ssb)

        self._rst_default_cw = QLineEdit("599")
        self._rst_default_cw.setMaxLength(3)
        self._rst_default_cw.setFixedWidth(60)
        f.addRow("Default RST (CW):", self._rst_default_cw)

        return w

    # ── Tab: APIs ─────────────────────────────────────────────

    def _tab_apis(self) -> QWidget:
        # APIs tab needs scrolling - many credential fields
        from PyQt6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        w = QWidget()
        scroll.setWidget(w)
        f = QFormLayout(w)
        f.setSpacing(10)
        f.setContentsMargins(16, 16, 16, 16)

        note = QLabel(
            "API credentials are stored securely in the OS keyring "
            "(Windows Credential Manager) — never in config files.")
        note.setWordWrap(True)
        note.setStyleSheet("")
        f.addRow("", note)

        f.addRow(_sep())
        _section(f, "QRZ.com")

        self._qrz_user = QLineEdit()
        self._qrz_user.setPlaceholderText("QRZ username / callsign")
        f.addRow("Username:", self._qrz_user)

        self._qrz_pass = QLineEdit()
        self._qrz_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._qrz_pass.setPlaceholderText("QRZ password")
        f.addRow("Password:", self._qrz_pass)

        qrz_note = QLabel(
            "QRZ XML API requires a QRZ subscription. "
            "Used for callsign lookup during FT8 operation.")
        qrz_note.setStyleSheet("")
        qrz_note.setWordWrap(True)
        f.addRow("", qrz_note)

        f.addRow(_sep())
        _section(f, "HamQTH (free alternative to QRZ)")

        self._hamqth_user = QLineEdit()
        self._hamqth_user.setPlaceholderText("HamQTH callsign")
        f.addRow("Callsign:", self._hamqth_user)

        self._hamqth_pass = QLineEdit()
        self._hamqth_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._hamqth_pass.setPlaceholderText("HamQTH password")
        f.addRow("Password:", self._hamqth_pass)

        f.addRow(_sep())
        _section(f, "HamAlert")

        self._hamalert_key = QLineEdit()
        self._hamalert_key.setPlaceholderText("API key from hamalert.org")
        f.addRow("API Key:", self._hamalert_key)

        f.addRow(_sep())
        _section(f, "RadioReference Premium")

        self._rr_user = QLineEdit()
        self._rr_user.setPlaceholderText("RadioReference username")
        f.addRow("Username:", self._rr_user)

        self._rr_key = QLineEdit()
        self._rr_key.setPlaceholderText("RadioReference API key")
        f.addRow("API Key:", self._rr_key)

        f.addRow(_sep())
        _section(f, "LoTW (ARRL Logbook of the World)")

        self._lotw_user = QLineEdit()
        self._lotw_user.setPlaceholderText("LoTW callsign")
        f.addRow("Callsign:", self._lotw_user)

        self._lotw_pass = QLineEdit()
        self._lotw_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._lotw_pass.setPlaceholderText("LoTW password")
        f.addRow("Password:", self._lotw_pass)

        self._auto_upload_lotw = QCheckBox(
            "Auto-upload QSOs to LoTW after logging")
        f.addRow("", self._auto_upload_lotw)

        f.addRow(_sep())
        _section(f, "ClubLog")

        self._clublog_email = QLineEdit()
        self._clublog_email.setPlaceholderText("ClubLog email")
        f.addRow("Email:", self._clublog_email)

        self._clublog_pass = QLineEdit()
        self._clublog_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._clublog_pass.setPlaceholderText("ClubLog password")
        f.addRow("Password:", self._clublog_pass)

        f.addRow(_sep())
        _section(f, "RepeaterBook (Local RF)")

        self._rb_token = QLineEdit()
        self._rb_token.setEchoMode(QLineEdit.EchoMode.Password)
        self._rb_token.setPlaceholderText("RepeaterBook API token")
        f.addRow("API token:", self._rb_token)
        rb_note = QLabel(
            "As of March 2026 RepeaterBook requires an approved API token. "
            "Apply (free for non-commercial use) at "
            "repeaterbook.com/api/token_request.php, then paste the token "
            "here. Without it, Local RF cannot fetch repeaters.")
        rb_note.setWordWrap(True)
        f.addRow("", rb_note)

        return w

    # ── Tab: Appearance ───────────────────────────────────────

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

    # ── Tab: Advanced ─────────────────────────────────────────

    def _tab_advanced(self) -> QWidget:
        from PyQt6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        w = QWidget()
        scroll.setWidget(w)
        f = QFormLayout(w)
        f.setSpacing(10)
        f.setContentsMargins(16, 16, 16, 16)

        _section(f, "Logging")
        self._log_level = QComboBox()
        self._log_level.addItems([
            "INFO (normal)",
            "DEBUG (verbose — for troubleshooting)",
            "WARNING (quiet)",
        ])
        f.addRow("Log Level:", self._log_level)

        self._log_max_size = QSpinBox()
        self._log_max_size.setRange(1, 100)
        self._log_max_size.setValue(5)
        self._log_max_size.setSuffix(" MB")
        f.addRow("Max Log Size:", self._log_max_size)

        _section(f, "Network")
        self._api_timeout = QSpinBox()
        self._api_timeout.setRange(3, 60)
        self._api_timeout.setValue(10)
        self._api_timeout.setSuffix(" seconds")
        f.addRow("API Timeout:", self._api_timeout)

        self._grayline_interval = QSpinBox()
        self._grayline_interval.setRange(10, 300)
        self._grayline_interval.setValue(60)
        self._grayline_interval.setSuffix(" seconds")
        self._grayline_interval.setToolTip(
            "How often to update the gray line on the map")
        f.addRow("Gray Line Update:", self._grayline_interval)

        _section(f, "Data")
        self._data_dir_lbl = QLabel(
            str(self.cfg._path.parent))
        self._data_dir_lbl.setStyleSheet(
            ""
            "font-family:'Courier New';")
        f.addRow("Data Directory:", self._data_dir_lbl)

        open_data_btn = QPushButton("Open in Explorer")
        open_data_btn.setFixedWidth(140)
        open_data_btn.clicked.connect(self._open_data_dir)
        f.addRow("", open_data_btn)

        _section(f, "Privacy")
        self._share_spotting = QCheckBox(
            "Allow Squelch to appear in PSKReporter spots")
        f.addRow("", self._share_spotting)

        self._anon_telemetry = QCheckBox(
            "Send anonymous crash reports to help improve Squelch")
        self._anon_telemetry.setChecked(False)
        f.addRow("", self._anon_telemetry)

        return scroll

    # ── Load / Save ───────────────────────────────────────────

    def _load_all(self):
        """Populate all fields from config and keyring."""
        cfg = self.cfg

        # Station
        self._callsign.setText(cfg.callsign or "")
        self._op_name.setText(
            cfg.get("station.op_name", ""))
        self._grid.setText(cfg.grid or "")
        region_map = {"1": 1, "2": 0, "3": 2}
        self._itu_region.setCurrentIndex(
            region_map.get(
                str(cfg.get("station.itu_region", "2")), 0))
        lic_map = {
            "technician": 0, "general": 1,
            "extra": 2, "other": 3}
        self._license.setCurrentIndex(
            lic_map.get(
                cfg.get("station.license", "").lower(), 1))
        self._station_call.setText(
            cfg.get("station.station_callsign", ""))
        self._contest_exchange.setText(
            cfg.get("station.contest_exchange", ""))

        # Modes
        self._auto_launch_wsjtx.setChecked(
            cfg.get("modes.auto_launch_wsjtx", True))
        self._auto_log_ft8.setChecked(
            cfg.get("modes.auto_log_ft8", True))
        self._wsjtx_udp_port.setValue(
            cfg.get("modes.wsjtx_udp_port", 2237))
        self._cq_timeout_cycles.setValue(
            cfg.get("modes.cq_timeout_cycles", 2))
        self._ptt_timeout.setValue(
            cfg.get("safety.ptt_timeout_s", 180))
        self._tx_inhibit.setChecked(
            cfg.get("safety.tx_inhibit", False))
        self._log_dupes.setChecked(
            cfg.get("log.warn_dupes", True))

        # Appearance
        themes = ["Dark", "Light", "High Contrast", "Night"]
        theme  = cfg.get("ui.theme", "Dark")
        self._theme.setCurrentIndex(
            themes.index(theme) if theme in themes else 0)

        saved_fs = cfg.get("ui.font_size", 11)
        font_sizes = [10, 11, 13, 15, 18]
        self._font_size.setCurrentIndex(
            font_sizes.index(saved_fs)
            if saved_fs in font_sizes else 1)
        # Units pref
        u = cfg.get("ui.units", "metric")
        ui_idx = self._units.findData(u)
        if ui_idx >= 0:
            self._units.setCurrentIndex(ui_idx)

        self._layout_locked.setChecked(
            cfg.get("ui.layout_locked", False))
        self._clock_utc.setChecked(
            cfg.get("ui.clock_utc", True))

        # Advanced
        level_map = {
            "INFO": 0, "DEBUG": 1, "WARNING": 2}
        self._log_level.setCurrentIndex(
            level_map.get(
                cfg.get("advanced.log_level", "INFO"), 0))
        self._api_timeout.setValue(
            cfg.get("advanced.api_timeout_s", 10))
        self._grayline_interval.setValue(
            cfg.get("advanced.grayline_interval_s", 60))

        # APIs — load from keyring
        try:
            from core.credentials import get_store
            store = get_store(cfg.get("profile.name", "default"))
            self._qrz_user.setText(
                cfg.get("apis.qrz_user", ""))
            self._hamqth_user.setText(
                cfg.get("apis.hamqth_user", ""))
            self._rr_user.setText(
                cfg.get("apis.rr_user", ""))
            self._lotw_user.setText(
                cfg.get("apis.lotw_user", ""))
            self._clublog_email.setText(
                cfg.get("apis.clublog_email", ""))
            self._rb_token.setText(
                store.retrieve("repeaterbook_token") or "")
        except Exception:
            pass

    def _tab_sdr_drivers(self) -> "QWidget":
        """SDR Hardware — install and check device drivers."""
        from PyQt6.QtWidgets import (
            QScrollArea, QGroupBox, QVBoxLayout, QHBoxLayout,
            QCheckBox, QPushButton, QLabel, QTextEdit)
        from PyQt6.QtCore import QTimer

        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        hdr = QLabel("SDR Hardware Drivers")
        hdr.setStyleSheet(
            "font-weight:bold;color:#3fbe6f;")
        lay.addWidget(hdr)

        sub = QLabel(
            "Install SoapySDR plugins for your SDR hardware. "
            "Requires conda / miniforge3.")
        sub.setWordWrap(True)
        sub.setStyleSheet("")
        lay.addWidget(sub)

        grp = QGroupBox("Select your hardware:")
        grp.setStyleSheet(
            "QGroupBox{"
            "border:1px solid #2a2a2a;border-radius:4px;"
            "padding-top:12px;margin-top:6px;}")
        gl = QVBoxLayout(grp)
        gl.setSpacing(10)

        self._sdr_checks = {}
        DRIVERS = [
            ("soapyrtlsdr",
             "RTL-SDR  (any RTL2832U dongle)",
             "RTL-SDR Blog V3/V4, Nooelec, etc.  "
             "Also needs Zadig WinUSB driver."),
            ("soapyhackrf",
             "HackRF One  (1 MHz to 6 GHz TX/RX)",
             "Great Plains SDR transceiver."),
            ("soapysdrplay3",
             "SDRplay RSP2Pro / RSP1A / RSPdx / RSPduo",
             "Requires SDRplay API installed first: sdrplay.com/softwarehome"),
            ("soapyuhd",
             "USRP B200 mini / B210  (Ettus Research)",
             "Professional full-duplex SDR, 70 MHz to 6 GHz."),
            ("soapyairspy",
             "Airspy R2 / Airspy Mini",
             "High performance, 24 MHz to 1.8 GHz."),
            ("limesuite",
             "LimeSDR / LimeSDR Mini",
             "Open source transceiver, 100 kHz to 3.8 GHz."),
        ]

        for pkg, label, note in DRIVERS:
            row = QVBoxLayout()
            row.setSpacing(2)
            cb = QCheckBox(label)
            cb.setStyleSheet("font-weight:bold;")
            self._sdr_checks[pkg] = cb
            row.addWidget(cb)
            nl = QLabel("    " + note)
            nl.setStyleSheet("")
            row.addWidget(nl)
            gl.addLayout(row)

        sel_row = QHBoxLayout()
        b_all  = QPushButton("Select All")
        b_none = QPushButton("Clear")
        b_all.setFixedWidth(90)
        b_none.setFixedWidth(70)
        b_all.clicked.connect(
            lambda: [c.setChecked(True)
                     for c in self._sdr_checks.values()])
        b_none.clicked.connect(
            lambda: [c.setChecked(False)
                     for c in self._sdr_checks.values()])
        sel_row.addWidget(b_all)
        sel_row.addWidget(b_none)
        sel_row.addStretch()
        gl.addLayout(sel_row)
        lay.addWidget(grp)

        btn_row = QHBoxLayout()
        self._sdr_install_btn = QPushButton("Install Selected Drivers")
        self._sdr_install_btn.setFixedHeight(32)
        self._sdr_install_btn.setStyleSheet(
            "background:#1a3a1a;color:#3fbe6f;"
            "border:1px solid #3fbe6f;border-radius:4px;"
            "font-weight:bold;")
        self._sdr_install_btn.clicked.connect(self._install_sdr_drivers)
        btn_row.addWidget(self._sdr_install_btn)

        self._sdr_check_btn = QPushButton("Check Status")
        self._sdr_check_btn.setFixedHeight(32)
        self._sdr_check_btn.clicked.connect(self._check_sdr_status)
        btn_row.addWidget(self._sdr_check_btn)
        lay.addLayout(btn_row)

        self._sdr_log = QTextEdit()
        self._sdr_log.setReadOnly(True)
        self._sdr_log.setMaximumHeight(160)
        self._sdr_log.setStyleSheet(
            "background:#080808;"
            "font-family:\'Courier New\';"
            "border:1px solid #1a1a1a;")
        self._sdr_log.setPlainText(
            "Select hardware above and click Install, "
            "or click Check Status to see what is already installed.")
        lay.addWidget(self._sdr_log)

        warn = QLabel(
            "RTL-SDR: after installing soapyrtlsdr, run Zadig "
            "(zadig.akeo.ie) and replace the USB driver with WinUSB. "
            "RSP2Pro: the SDRplay API Windows service must be running.")
        warn.setWordWrap(True)
        warn.setStyleSheet(
            "color:#aa8800;"
            "background:#1a1600;padding:8px;"
            "border:1px solid #2a2000;border-radius:3px;")
        lay.addWidget(warn)
        lay.addStretch()

        QTimer.singleShot(400, self._check_sdr_status)
        return w

    def _conda_exe(self) -> str:
        import shutil
        from pathlib import Path as P
        for name in ["conda", "mamba", "micromamba"]:
            f = shutil.which(name)
            if f:
                return f
        for p in [
            P.home() / "miniforge3" / "Scripts" / "conda.exe",
            P.home() / "miniconda3"  / "Scripts" / "conda.exe",
            P("C:/miniforge3/Scripts/conda.exe"),
            P("C:/miniconda3/Scripts/conda.exe"),
        ]:
            if p.exists():
                return str(p)
        return ""

    def _sdr_log_append(self, text: str):
        try:
            self._sdr_log.append(text)
        except RuntimeError:
            pass

    def _check_sdr_status(self):
        import sys, subprocess, sysconfig
        from pathlib import Path as P

        lines = []
        vpy = sys.executable
        r = subprocess.run(
            [vpy, "-c",
             "import SoapySDR; d=SoapySDR.Device.enumerate();"
             "print(SoapySDR.getAPIVersion(), len(d), 'device(s)')"],
            capture_output=True, text=True)
        if r.returncode == 0:
            lines.append("SoapySDR core: OK  " + r.stdout.strip())
        else:
            lines.append("SoapySDR core: NOT INSTALLED")
            lines.append("  Run fix_soapysdr.bat or python installer.py")

        try:
            site = P(sysconfig.get_path("purelib"))
        except Exception:
            site = P(sys.prefix) / "Lib" / "site-packages"

        lines.append("")
        lines.append("Device plugins:")
        plugin_map = {
            "soapyrtlsdr":   ("SoapyRTLSDR",   "RTL-SDR"),
            "soapyhackrf":   ("SoapyHackRF",   "HackRF"),
            "soapysdrplay3": ("SoapySDRPlay",  "SDRplay RSP"),
            "soapyuhd":      ("SoapyUHD",      "USRP"),
            "soapyairspy":   ("SoapyAirspy",   "Airspy"),
            "limesuite":     ("SoapyLMS7",     "LimeSDR"),
        }
        for pkg, (stem, hw) in plugin_map.items():
            found = list(site.glob(stem + "*.pyd"))
            if found:
                lines.append("  [installed]  " + hw + " - " + found[0].name)
                if pkg in self._sdr_checks:
                    self._sdr_checks[pkg].setChecked(False)
            else:
                lines.append("  [ missing ]  " + hw)
        try:
            self._sdr_log.setPlainText("\n".join(lines))
        except RuntimeError:
            pass

    def _install_sdr_drivers(self):
        import subprocess, threading, shutil, sysconfig
        from pathlib import Path as P

        selected = [p for p, cb in self._sdr_checks.items()
                    if cb.isChecked()]
        if not selected:
            self._sdr_log.setPlainText(
                "No drivers selected. "
                "Check the boxes for your hardware first.")
            return

        conda = self._conda_exe()
        if not conda:
            self._sdr_log.setPlainText(
                "conda not found.\n\n"
                "Install miniforge3 from:\n"
                "  github.com/conda-forge/miniforge/releases\n\n"
                "Or run manually:\n"
                "  conda install -c conda-forge " + " ".join(selected))
            return

        self._sdr_install_btn.setEnabled(False)
        self._sdr_install_btn.setText("Installing...")
        self._sdr_log.setPlainText(
            "Running: conda install -c conda-forge "
            + " ".join(selected) + "\n\nPlease wait...")

        def _run():
            try:
                result = subprocess.run(
                    [conda, "install", "-c", "conda-forge",
                     "-y", "--quiet"] + selected,
                    capture_output=True, text=True)

                if result.returncode == 0:
                    # Copy plugin .pyd files into venv
                    try:
                        site = P(sysconfig.get_path("purelib"))
                    except Exception:
                        import sys
                        site = P(sys.prefix) / "Lib" / "site-packages"

                    conda_sp = None
                    for root in [
                        P.home() / "miniforge3" / "Lib" / "site-packages",
                        P.home() / "miniconda3"  / "Lib" / "site-packages",
                        P("C:/miniforge3/Lib/site-packages"),
                        P("C:/miniconda3/Lib/site-packages"),
                    ]:
                        if root.exists():
                            conda_sp = root
                            break

                    stem_map = {
                        "soapyrtlsdr":   "SoapyRTLSDR",
                        "soapyhackrf":   "SoapyHackRF",
                        "soapysdrplay3": "SoapySDRPlay",
                        "soapyuhd":      "SoapyUHD",
                        "soapyairspy":   "SoapyAirspy",
                        "limesuite":     "SoapyLMS7",
                    }
                    copied = []
                    if conda_sp:
                        for pkg in selected:
                            stem = stem_map.get(pkg, pkg)
                            for pyd in conda_sp.glob(stem + "*.pyd"):
                                try:
                                    shutil.copy2(pyd, site / pyd.name)
                                    copied.append(pyd.name)
                                except Exception:
                                    pass

                    msg = "Installation complete.\n\n"
                    if copied:
                        msg += "Copied to venv:\n"
                        msg += "\n".join("  " + f for f in copied)
                        msg += "\n\nRestart Squelch to use new drivers."
                    else:
                        msg += "conda install succeeded but no .pyd files "
                        msg += "found to copy.\nRun fix_soapysdr.bat."
                else:
                    msg = ("conda install failed.\n\n"
                           + (result.stderr or result.stdout)[:400])
            except Exception as exc:
                msg = "Error: " + str(exc)

            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda m=msg: _done(m))

        def _done(msg):
            try:
                self._sdr_log.setPlainText(msg)
                self._sdr_install_btn.setEnabled(True)
                self._sdr_install_btn.setText("Install Selected Drivers")
                self._check_sdr_status()
            except RuntimeError:
                pass

        threading.Thread(target=_run, daemon=True).start()


    def _apply(self):
        """Save all settings without closing."""
        cfg = self.cfg

        # Station
        cs = self._callsign.text().strip().upper()
        if cs:
            cfg.callsign = cs
        cfg.set("station.op_name",
                self._op_name.text().strip())
        grid = self._grid.text().strip().upper()
        if grid:
            cfg.grid = grid
        region_map = {0: "2", 1: "1", 2: "3"}
        cfg.set("station.itu_region",
                region_map.get(
                    self._itu_region.currentIndex(), "2"))
        lic_labels = ["technician", "general",
                      "extra", "other"]
        cfg.set("station.license",
                lic_labels[self._license.currentIndex()])
        cfg.set("station.station_callsign",
                self._station_call.text().strip().upper())
        cfg.set("station.contest_exchange",
                self._contest_exchange.text().strip())

        # Audio
        cfg.set("audio.input",
                self._audio_input.currentText())
        cfg.set("audio.output",
                self._audio_output.currentText())
        cfg.set("audio.digital_input",
                self._digital_input.currentText())
        cfg.set("audio.digital_output",
                self._digital_output.currentText())

        # Modes
        cfg.set("modes.auto_launch_wsjtx",
                self._auto_launch_wsjtx.isChecked())
        cfg.set("modes.auto_log_ft8",
                self._auto_log_ft8.isChecked())
        cfg.set("modes.wsjtx_udp_port",
                self._wsjtx_udp_port.value())
        cfg.set("modes.cq_timeout_cycles",
                self._cq_timeout_cycles.value())
        cfg.set("safety.ptt_timeout_s",
                self._ptt_timeout.value())
        cfg.set("safety.tx_inhibit",
                self._tx_inhibit.isChecked())
        cfg.set("log.warn_dupes",
                self._log_dupes.isChecked())

        # Appearance
        cfg.set("ui.theme",
                self._theme.currentText())
        cfg.set("ui.font_size",
                self._font_size.currentData())
        cfg.set("ui.units",
                self._units.currentData() or "metric")
        cfg.set("ui.layout_locked",
                self._layout_locked.isChecked())
        cfg.set("ui.clock_utc",
                self._clock_utc.isChecked())

        # Advanced
        levels = ["INFO", "DEBUG", "WARNING"]
        cfg.set("advanced.log_level",
                levels[self._log_level.currentIndex()])
        cfg.set("advanced.api_timeout_s",
                self._api_timeout.value())
        cfg.set("advanced.grayline_interval_s",
                self._grayline_interval.value())

        # APIs — save to config (passwords to keyring)
        cfg.set("apis.qrz_user",
                self._qrz_user.text().strip())
        cfg.set("apis.hamqth_user",
                self._hamqth_user.text().strip())
        cfg.set("apis.rr_user",
                self._rr_user.text().strip())
        cfg.set("apis.lotw_user",
                self._lotw_user.text().strip())
        cfg.set("apis.clublog_email",
                self._clublog_email.text().strip())

        # Store passwords in keyring
        try:
            from core.credentials import get_store
            profile = cfg.get("profile.name", "default")
            store   = get_store(profile)
            if self._qrz_pass.text():
                store.store("qrz_password",
                            self._qrz_pass.text())
            if self._hamqth_pass.text():
                store.store("hamqth_password",
                            self._hamqth_pass.text())
            if self._lotw_pass.text():
                store.store("lotw_password",
                            self._lotw_pass.text())
            if self._clublog_pass.text():
                store.store("clublog_password",
                            self._clublog_pass.text())
            if self._rb_token.text():
                store.store("repeaterbook_token",
                            self._rb_token.text())
        except Exception as e:
            log.warning(f"Keyring save: {e}")

        cfg.save()

        # Apply live changes
        self._apply_live()

    def _apply_live(self):
        """Apply theme and font immediately — called on Apply/OK."""
        try:
            from core.themes import get_stylesheet
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtGui import QFont
            try:
                from PyQt6 import sip
            except ImportError:
                import sip
            app = QApplication.instance()
            if not app:
                return
            # Guard against C++ object already deleted
            if sip.isdeleted(self):
                return
            try:
                if sip.isdeleted(self._theme):
                    return
                theme = self._theme.currentText()
                if sip.isdeleted(self._font_size):
                    return
                fs = self._font_size.currentData() or 11
            except (RuntimeError, AttributeError):
                return
            app.setStyleSheet(get_stylesheet(theme, fs))
            f = QFont()
            f.setPointSize(fs)
            app.setFont(f)
        except Exception as e:
            log.debug(f"Live apply: {e}")

    def _set_font_recursive(self, widget, font):
        """
        No longer used — font size is applied via QSS in _apply_live.
        Kept as stub to avoid AttributeError from any call sites.
        """
        pass

    def _save_and_accept(self):
        self._apply()
        self.accept()

    def _reset_defaults(self):
        reply = QMessageBox.question(
            self, "Reset Settings",
            "Reset all settings to defaults?\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            from core.config import Config
            defaults = Config._load_example(self.cfg)
            for key, val in _flatten(defaults).items():
                self.cfg.set(key, val)
            self._load_all()

    def _refresh_audio_devices(self):
        """Populate audio device dropdowns from sounddevice."""
        # Common virtual audio devices always listed
        # even if sounddevice can't enumerate
        common_inputs = [
            "Default",
            "CABLE Output (VB-Audio Virtual Cable)",
            "USB Audio CODEC",
            "Microphone (USB)",
            "Stereo Mix",
        ]
        common_outputs = [
            "Default",
            "CABLE Input (VB-Audio Virtual Cable)",
            "Speakers (USB Audio CODEC)",
            "Speakers",
            "Headphones",
        ]

        in_devices  = list(common_inputs)
        out_devices = list(common_outputs)
        detected    = False

        try:
            import sounddevice as sd
            devs = sd.query_devices()
            for d in devs:
                name = d["name"]
                if d["max_input_channels"] > 0:
                    if name not in in_devices:
                        in_devices.append(name)
                if d["max_output_channels"] > 0:
                    if name not in out_devices:
                        out_devices.append(name)
            detected = True
        except Exception as e:
            # sounddevice not installed or no audio
            pass

        # Populate dropdowns
        for combo, devices in [
            (self._audio_input,   in_devices),
            (self._digital_input, in_devices),
        ]:
            saved = combo.currentText()
            combo.clear()
            combo.addItems(devices)
            # Restore or default
            if saved in devices:
                combo.setCurrentText(saved)

        for combo, devices in [
            (self._audio_output,   out_devices),
            (self._digital_output, out_devices),
        ]:
            saved = combo.currentText()
            combo.clear()
            combo.addItems(devices)
            if saved in devices:
                combo.setCurrentText(saved)

        # Restore saved config values
        cfg = self.cfg
        saved_in  = cfg.get("audio.input", "")
        saved_out = cfg.get("audio.output", "")
        saved_din = cfg.get("audio.digital_input", "")
        saved_dout= cfg.get("audio.digital_output", "")

        for combo, val in [
            (self._audio_input,    saved_in),
            (self._audio_output,   saved_out),
            (self._digital_input,  saved_din),
            (self._digital_output, saved_dout),
        ]:
            if val:
                # Add if not in list (was set manually before)
                if combo.findText(val) < 0:
                    combo.addItem(val)
                combo.setCurrentText(val)

        if not detected:
            self._refresh_audio_btn.setText(
                "↺ Refresh (sounddevice not installed)")
            self._refresh_audio_btn.setStyleSheet(
                "")
        else:
            total = len(in_devices) + len(out_devices)
            self._refresh_audio_btn.setText(
                f"↺ Device list ({total} found)")
            self._refresh_audio_btn.setStyleSheet("")

    def _open_data_dir(self):
        import subprocess, sys
        path = str(self.cfg._path.parent)
        if sys.platform == "win32":
            subprocess.Popen(
                ["explorer", path], shell=False)  # nosec B603
        else:
            subprocess.Popen(
                ["xdg-open", path], shell=False)  # nosec B603


# ── Helpers ───────────────────────────────────────────────────────────────

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
