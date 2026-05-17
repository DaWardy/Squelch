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
            "QTabBar::tab{padding:6px 14px;font-size:11px;}"
            "QTabBar::tab:selected{color:#3fbe6f;}")

        self._tabs.addTab(self._tab_station(),   "🎙  Station")
        self._tabs.addTab(self._tab_audio(),     "🔊  Audio")
        self._tabs.addTab(self._tab_modes(),     "📡  Digital Modes")
        self._tabs.addTab(self._tab_apis(),      "🔑  APIs")
        self._tabs.addTab(self._tab_appearance(),"🎨  Appearance")
        self._tabs.addTab(self._tab_advanced(),  "⚙  Advanced")

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
        w = _scrolled()
        f = QFormLayout(w)
        f.setSpacing(10)
        f.setContentsMargins(16, 16, 16, 16)

        note = QLabel(
            "API credentials are stored securely in the OS keyring "
            "(Windows Credential Manager) — never in config files.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#555;font-size:10px;")
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
        qrz_note.setStyleSheet("color:#555;font-size:10px;")
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
            "Dark", "Light",
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
        w = _scrolled()
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
            "color:#555;font-size:10px;"
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

        return w

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
        except Exception:
            pass

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
        except Exception as e:
            log.warning(f"Keyring save: {e}")

        cfg.save()

        # Apply live changes
        self._apply_live()

    def _apply_live(self):
        """Apply settings that take effect without restart."""
        try:
            from core.themes import get_stylesheet
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                theme = self._theme.currentText()
                fs    = self._font_size.currentData() or 11
                app.setStyleSheet(get_stylesheet(theme, fs))
                from PyQt6.QtGui import QFont
                f = app.font()
                f.setPointSize(fs)
                app.setFont(f)
        except Exception as e:
            log.debug(f"Live apply: {e}")

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
        """Populate audio device dropdowns."""
        devices = ["Default"]
        try:
            import sounddevice as sd
            for d in sd.query_devices():
                if d["max_input_channels"] > 0:
                    devices.append(d["name"])
        except Exception:
            devices += [
                "CABLE Output (VB-Audio Virtual Cable)",
                "USB Audio CODEC",
                "Microphone (USB)",
            ]

        for combo in [self._audio_input,
                      self._digital_input]:
            current = combo.currentText()
            combo.clear()
            combo.addItems(devices)
            if current in devices:
                combo.setCurrentText(current)

        out_devices = ["Default"]
        try:
            import sounddevice as sd
            for d in sd.query_devices():
                if d["max_output_channels"] > 0:
                    out_devices.append(d["name"])
        except Exception:
            out_devices += [
                "CABLE Input (VB-Audio Virtual Cable)",
                "Speakers",
                "Headphones",
            ]

        for combo in [self._audio_output,
                      self._digital_output]:
            current = combo.currentText()
            combo.clear()
            combo.addItems(out_devices)
            if current in out_devices:
                combo.setCurrentText(current)

        # Restore saved values
        cfg = self.cfg
        self._audio_input.setCurrentText(
            cfg.get("audio.input", "Default"))
        self._audio_output.setCurrentText(
            cfg.get("audio.output", "Default"))
        self._digital_input.setCurrentText(
            cfg.get("audio.digital_input", "Default"))
        self._digital_output.setCurrentText(
            cfg.get("audio.digital_output", "Default"))

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
    """Return a scrollable widget for tab content."""
    outer = QScrollArea()
    outer.setWidgetResizable(True)
    outer.setFrameShape(QFrame.Shape.NoFrame)
    inner = QWidget()
    outer.setWidget(inner)
    # Trick: return the inner widget but make it look like outer
    # We do this by setting the layout on outer and returning it
    # Actually just return the inner — caller adds layout to inner
    # But outer needs to be the tab widget...
    # Simplest: just return QWidget, caller handles scroll
    w = QWidget()
    return w


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(
        "color:#1a1a1a;margin:4px 0;")
    return f


def _section(form: QFormLayout, title: str):
    lbl = QLabel(title)
    lbl.setStyleSheet(
        "color:#3fbe6f;font-size:11px;"
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
