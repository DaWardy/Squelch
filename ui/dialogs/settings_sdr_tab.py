from __future__ import annotations
"""SettingsDialog sdr tab — extracted from settings_dialog.py."""
from PyQt6.QtWidgets import (QWidget, QFormLayout, QScrollArea, QFrame,
    QLabel, QLineEdit, QComboBox, QSpinBox, QCheckBox, QHBoxLayout,
    QVBoxLayout, QPushButton, QGroupBox, QDoubleSpinBox)
from PyQt6.QtCore import Qt
from core.themes import get_theme as _sdr_get_theme


class _SettingsSdrTab:
    """Mixed into SettingsDialog."""

    def _tab_sdr_drivers(self) -> "QWidget":
        """SDR Hardware — install and check device drivers."""
        from PyQt6.QtWidgets import QTextEdit
        from PyQt6.QtCore import QTimer
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)
        _t = _sdr_get_theme(self.cfg.get("ui.theme", "Dark"))
        hdr = QLabel("SDR Hardware Drivers")
        hdr.setStyleSheet(f"font-weight:bold;color:{_t.accent};")
        lay.addWidget(hdr)
        sub = QLabel(
            "Install SoapySDR plugins for your SDR hardware. "
            "Requires conda / miniforge3.")
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color:{_t.fg_primary};")
        lay.addWidget(sub)
        lay.addWidget(self._build_sdr_hardware_group())
        self._build_sdr_action_area(lay)
        warn = QLabel(
            "RTL-SDR: after installing soapyrtlsdr, run Zadig "
            "(zadig.akeo.ie) and replace the USB driver with WinUSB. "
            "RSP2Pro: the SDRplay API Windows service must be running.")
        warn.setWordWrap(True)
        warn.setStyleSheet(
            f"color:{_t.warn_color};background:{_t.bg_secondary};padding:8px;"
            f"border:1px solid {_t.border};border-radius:3px;")
        lay.addWidget(warn)
        lay.addStretch()
        QTimer.singleShot(400, self._check_sdr_status)
        return w

    _SDR_DRIVERS = [
        ("soapyrtlsdr",   "RTL-SDR  (any RTL2832U dongle)",
         "RTL-SDR Blog V3/V4, Nooelec, etc.  Also needs Zadig WinUSB driver."),
        ("soapyhackrf",   "HackRF One  (1 MHz to 6 GHz TX/RX)",
         "Great Plains SDR transceiver."),
        ("soapysdrplay3", "SDRplay RSP2Pro / RSP1A / RSPdx / RSPduo",
         "Requires SDRplay API installed first: sdrplay.com/softwarehome"),
        ("soapyuhd",      "USRP B200 mini / B210  (Ettus Research)",
         "Professional full-duplex SDR, 70 MHz to 6 GHz."),
        ("soapyairspy",   "Airspy R2 / Airspy Mini",
         "High performance, 24 MHz to 1.8 GHz."),
        ("limesuite",     "LimeSDR / LimeSDR Mini",
         "Open source transceiver, 100 kHz to 3.8 GHz."),
    ]

    def _build_sdr_driver_checkboxes(self, gl: "QVBoxLayout") -> None:
        from PyQt6.QtWidgets import QFrame
        _t2 = _sdr_get_theme(self.cfg.get("ui.theme", "Dark"))
        cb_style = (
            f"QCheckBox{{font-weight:bold;font-size:13px;spacing:8px;padding:2px 0;"
            f"color:{_t2.fg_primary};}}"
            f"QCheckBox::indicator{{width:18px;height:18px;border:2px solid {_t2.border};"
            f"border-radius:3px;background:{_t2.bg_tertiary};}}"
            f"QCheckBox::indicator:hover{{border-color:{_t2.accent};}}"
            f"QCheckBox::indicator:checked{{background:{_t2.accent};border-color:{_t2.accent};}}"
            f"QCheckBox::indicator:disabled{{background:{_t2.bg_secondary};"
            f"border-color:{_t2.fg_muted};}}")
        self._sdr_checks = {}
        for pkg, label, note in self._SDR_DRIVERS:
            row = QVBoxLayout()
            row.setSpacing(4)
            row.setContentsMargins(0, 6, 0, 6)
            cb = QCheckBox(label)
            cb.setStyleSheet(cb_style)
            self._sdr_checks[pkg] = cb
            row.addWidget(cb)
            nl = QLabel("        " + note)
            nl.setWordWrap(True)
            nl.setStyleSheet(f"color:{_t2.fg_muted};font-size:11px;")
            row.addWidget(nl)
            gl.addLayout(row)
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet(f"color:{_t2.border};max-height:1px;")
            gl.addWidget(sep)

    def _build_sdr_select_row(self) -> "QHBoxLayout":
        _t3 = _sdr_get_theme(self.cfg.get("ui.theme", "Dark"))
        sel_btn_style = (
            f"QPushButton{{padding:6px 14px;font-weight:bold;"
            f"border:1px solid {_t3.border};border-radius:3px;"
            f"background:{_t3.bg_secondary};color:{_t3.fg_primary};}}"
            f"QPushButton:hover{{background:{_t3.bg_tertiary};"
            f"border-color:{_t3.accent};}}")
        b_all  = QPushButton("✓ Select All")
        b_none = QPushButton("✗ Clear")
        b_all.setStyleSheet(sel_btn_style)
        b_none.setStyleSheet(sel_btn_style)
        b_all.setMinimumWidth(110)
        b_none.setMinimumWidth(90)
        b_all.clicked.connect(
            lambda: [c.setChecked(True)  for c in self._sdr_checks.values()])
        b_none.clicked.connect(
            lambda: [c.setChecked(False) for c in self._sdr_checks.values()])
        row = QHBoxLayout()
        row.setContentsMargins(0, 6, 0, 0)
        row.addWidget(b_all)
        row.addWidget(b_none)
        row.addStretch()
        return row

    def _build_sdr_hardware_group(self) -> "QGroupBox":
        """Checkbox list of installable SDR drivers + select-all/clear row."""
        _t4 = _sdr_get_theme(self.cfg.get("ui.theme", "Dark"))
        grp = QGroupBox("Select your hardware:")
        grp.setStyleSheet(
            f"QGroupBox{{border:1px solid {_t4.border};border-radius:4px;"
            f"padding-top:12px;margin-top:6px;}}")
        gl = QVBoxLayout(grp)
        gl.setSpacing(10)
        self._build_sdr_driver_checkboxes(gl)
        gl.addLayout(self._build_sdr_select_row())
        return grp

    def _build_sdr_action_area(self, lay) -> None:
        """Install/Check buttons and log output area."""
        from PyQt6.QtWidgets import QTextEdit
        btn_row = QHBoxLayout()
        self._sdr_install_btn = QPushButton("Install Selected Drivers")
        self._sdr_install_btn.setFixedHeight(32)
        _t5 = _sdr_get_theme(self.cfg.get("ui.theme", "Dark"))
        self._sdr_install_btn.setStyleSheet(
            f"background:{_t5.tooltip_bg};color:{_t5.accent};"
            f"border:1px solid {_t5.accent};border-radius:4px;font-weight:bold;")
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
            f"background:{_t5.bg_primary};font-family:'Courier New';"
            f"color:{_t5.fg_primary};border:1px solid {_t5.border};")
        self._sdr_log.setPlainText(
            "Select hardware above and click Install, "
            "or click Check Status to see what is already installed.")
        lay.addWidget(self._sdr_log)

