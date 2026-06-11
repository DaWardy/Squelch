from __future__ import annotations
"""SettingsDialog sdr tab — extracted from settings_dialog.py."""
from PyQt6.QtWidgets import (QWidget, QFormLayout, QScrollArea, QFrame,
    QLabel, QLineEdit, QComboBox, QSpinBox, QCheckBox, QHBoxLayout,
    QVBoxLayout, QPushButton, QGroupBox, QDoubleSpinBox)
from PyQt6.QtCore import Qt


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
        hdr = QLabel("SDR Hardware Drivers")
        hdr.setStyleSheet("font-weight:bold;color:#3fbe6f;")
        lay.addWidget(hdr)
        sub = QLabel(
            "Install SoapySDR plugins for your SDR hardware. "
            "Requires conda / miniforge3.")
        sub.setWordWrap(True)
        sub.setStyleSheet("")
        lay.addWidget(sub)
        lay.addWidget(self._build_sdr_hardware_group())
        self._build_sdr_action_area(lay)
        warn = QLabel(
            "RTL-SDR: after installing soapyrtlsdr, run Zadig "
            "(zadig.akeo.ie) and replace the USB driver with WinUSB. "
            "RSP2Pro: the SDRplay API Windows service must be running.")
        warn.setWordWrap(True)
        warn.setStyleSheet(
            "color:#aa8800;background:#1a1600;padding:8px;"
            "border:1px solid #2a2000;border-radius:3px;")
        lay.addWidget(warn)
        lay.addStretch()
        QTimer.singleShot(400, self._check_sdr_status)
        return w

    def _build_sdr_hardware_group(self) -> "QGroupBox":
        """Checkbox list of installable SDR drivers + select-all/clear row."""
        from PyQt6.QtWidgets import QFrame
        DRIVERS = [
            ("soapyrtlsdr",  "RTL-SDR  (any RTL2832U dongle)",
             "RTL-SDR Blog V3/V4, Nooelec, etc.  Also needs Zadig WinUSB driver."),
            ("soapyhackrf",  "HackRF One  (1 MHz to 6 GHz TX/RX)",
             "Great Plains SDR transceiver."),
            ("soapysdrplay3", "SDRplay RSP2Pro / RSP1A / RSPdx / RSPduo",
             "Requires SDRplay API installed first: sdrplay.com/softwarehome"),
            ("soapyuhd",     "USRP B200 mini / B210  (Ettus Research)",
             "Professional full-duplex SDR, 70 MHz to 6 GHz."),
            ("soapyairspy",  "Airspy R2 / Airspy Mini",
             "High performance, 24 MHz to 1.8 GHz."),
            ("limesuite",    "LimeSDR / LimeSDR Mini",
             "Open source transceiver, 100 kHz to 3.8 GHz."),
        ]
        grp = QGroupBox("Select your hardware:")
        grp.setStyleSheet(
            "QGroupBox{border:1px solid #2a2a2a;border-radius:4px;"
            "padding-top:12px;margin-top:6px;}")
        gl = QVBoxLayout(grp)
        gl.setSpacing(10)
        self._sdr_checks = {}
        cb_style = (
            "QCheckBox{font-weight:bold;font-size:13px;spacing:8px;padding:2px 0;}"
            "QCheckBox::indicator{width:18px;height:18px;border:2px solid #888;"
            "border-radius:3px;background:#1a1a1a;}"
            "QCheckBox::indicator:hover{border-color:#3fbe6f;}"
            "QCheckBox::indicator:checked{background:#3fbe6f;border-color:#3fbe6f;}"
            "QCheckBox::indicator:disabled{background:#2a2a2a;border-color:#444;}")
        for pkg, label, note in DRIVERS:
            row = QVBoxLayout()
            row.setSpacing(4)
            row.setContentsMargins(0, 6, 0, 6)
            cb = QCheckBox(label)
            cb.setStyleSheet(cb_style)
            self._sdr_checks[pkg] = cb
            row.addWidget(cb)
            nl = QLabel("        " + note)
            nl.setWordWrap(True)
            nl.setStyleSheet("color:#aaaaaa;font-size:11px;")
            row.addWidget(nl)
            gl.addLayout(row)
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet("color:#333;max-height:1px;")
            gl.addWidget(sep)
        sel_row = QHBoxLayout()
        sel_row.setContentsMargins(0, 6, 0, 0)
        sel_btn_style = (
            "QPushButton{padding:6px 14px;font-weight:bold;"
            "border:1px solid #555;border-radius:3px;"
            "background:#2a2a2a;color:#ddd;}"
            "QPushButton:hover{background:#3a3a3a;border-color:#3fbe6f;}")
        b_all  = QPushButton("✓ Select All")
        b_none = QPushButton("✗ Clear")
        b_all.setStyleSheet(sel_btn_style)
        b_none.setStyleSheet(sel_btn_style)
        b_all.setMinimumWidth(110)
        b_none.setMinimumWidth(90)
        b_all.clicked.connect(
            lambda: [c.setChecked(True) for c in self._sdr_checks.values()])
        b_none.clicked.connect(
            lambda: [c.setChecked(False) for c in self._sdr_checks.values()])
        sel_row.addWidget(b_all)
        sel_row.addWidget(b_none)
        sel_row.addStretch()
        gl.addLayout(sel_row)
        return grp

    def _build_sdr_action_area(self, lay) -> None:
        """Install/Check buttons and log output area."""
        from PyQt6.QtWidgets import QTextEdit
        btn_row = QHBoxLayout()
        self._sdr_install_btn = QPushButton("Install Selected Drivers")
        self._sdr_install_btn.setFixedHeight(32)
        self._sdr_install_btn.setStyleSheet(
            "background:#1a3a1a;color:#3fbe6f;"
            "border:1px solid #3fbe6f;border-radius:4px;font-weight:bold;")
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
            "background:#080808;font-family:'Courier New';"
            "border:1px solid #1a1a1a;")
        self._sdr_log.setPlainText(
            "Select hardware above and click Install, "
            "or click Check Status to see what is already installed.")
        lay.addWidget(self._sdr_log)

