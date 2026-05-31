"""SettingsDialog modes tab — extracted from settings_dialog.py."""
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



class _SettingsModesTab:
    """Mixed into SettingsDialog."""

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

