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

from __future__ import annotations
"""Squelch -- ui/tabs/rig_tab.py
Rig control tab.
- Click-to-edit VFO with unit selector (Hz/kHz/MHz)
- Step size buttons + arrow controls + mousewheel
- Band jump (context-aware by active mode)
- Mode buttons with auto-mode by frequency
- PTT / Power / Preamp / ATT / Filter+BW
- Collapsible scanner (sweep, channel, band)
- Collapsible memory channels (IC-7100 M01-M99)
- Popular rig auto-detect
- Collapsible spectrum/waterfall
"""

import logging
import os
from ui.panel import SquelchPanel
from PyQt6.QtWidgets import (
    QLineEdit,
    QSpinBox,
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QComboBox, QGroupBox,
    QFrame, QSpinBox, QDoubleSpinBox, QProgressBar,
    QMessageBox, QCheckBox, QButtonGroup,
    QSizePolicy, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QWheelEvent

from ui.widgets.freq_display import FreqDisplay
from ui.widgets.spectrum_widget import SpectrumWidget
from ui.tabs.rig_rotor_mixin import _RigRotorMixin
from ui.tabs.rig_voice_mixin import _RigVoiceMixin
from ui.tabs.rig_cw_mixin import _RigCWMixin
from core.rig import RigController, RigStatus, SMETER_LABELS
from core.themes import get_theme as _get_rig_theme
from core.band_plan import (
    suggested_mode, band_at_freq, DIGITAL_FREQS, BAND_EDGES
)

log = logging.getLogger(__name__)

# ── Rig model database ────────────────────────────────────────────────────
RIG_MODELS = [
    # (display_name, hamlib_model, default_baud, usb_hints)
    ("ICOM IC-7100",     370,  19200, ["CP210","IC-7100"]),
    ("ICOM IC-7300",     373,  19200, ["CP210","IC-7300"]),
    ("ICOM IC-7610",     376,  19200, ["CP210","IC-7610"]),
    ("ICOM IC-9700",     369,  19200, ["CP210","IC-9700"]),
    ("ICOM IC-705",      388,  19200, ["CP210","IC-705"]),
    ("ICOM IC-7400",     345,  19200, ["CP210"]),
    ("ICOM IC-7600",     366,  19200, ["CP210"]),
    ("Yaesu FT-991A",   1035,  38400, ["CP210","FT-991","FTDI"]),
    ("Yaesu FT-DX10",   1062,  38400, ["CP210","FT-DX10"]),
    ("Yaesu FT-DX3000", 1021,  38400, ["FTDI"]),
    ("Yaesu FT-817/818",1033,   9600, ["FTDI"]),
    ("Yaesu FT-891",    1039,  38400, ["FTDI","FT-891"]),
    ("Kenwood TS-590S",  229, 115200, ["FTDI","CP210","TS-590"]),
    ("Kenwood TS-890S",  243, 115200, ["FTDI","CP210","TS-890"]),
    ("Kenwood TS-2000",  202,   9600, ["FTDI"]),
    ("Elecraft K3/K3S", 1351,  38400, ["FTDI","Elecraft","K3"]),
    ("Elecraft KX3",    1353,  38400, ["FTDI","KX3"]),
    ("Elecraft K4",     1356,  38400, ["FTDI","K4"]),
    ("Xiegu G90",       None,  19200, ["CP210","G90"]),
    ("Xiegu X6100",     None,  19200, ["CP210","X6100"]),
    ("Lab599 TX-500",   None, 115200, ["CP210","TX-500"]),
    # Audio interfaces — no CAT, Hamlib model = None
    ("SignaLink USB",    None,      0, ["SignaLink","USB Audio CODEC"]),
    ("RigBlaster",       None,      0, ["RigBlaster","USB Audio"]),
    ("Generic USB Audio",None,      0, ["USB Audio","CODEC"]),
    ("Explorer QRZ-1",   None,      0, ["QRZ","TYT","TH-UV88"]),
    ("Baofeng UV-5R",    None,      0, ["Baofeng","UV-5R","UV-82"]),
]

# Mode buttons: (label, hamlib_mode, tooltip)
MODE_BUTTONS = [
    ("USB",  "USB",     "Upper Sideband — HF phone 10 MHz and above"),
    ("LSB",  "LSB",     "Lower Sideband — HF phone below 10 MHz"),
    ("FM",   "FM",      "FM narrow — VHF/UHF, repeaters"),
    ("WFM",  "WFM",     "Wide FM — broadcast receive"),
    ("AM",   "AM",      "AM — broadcast, 10m AM calling"),
    ("CW",   "CW",      "CW — Morse code"),
    ("RTTY", "RTTY",    "RTTY — Radio Teletype"),
    ("PKT",  "PKTUSB",  "Digital — FT8, WSPR, PSK31 etc."),
    ("DV",   "DV",      "D-STAR digital voice"),
]

MODE_TO_BTN = {
    "USB":"USB","LSB":"LSB","FM":"FM","WFM":"WFM","AM":"AM",
    "CW":"CW","CW-R":"CW","RTTY":"RTTY","RTTY-R":"RTTY",
    "PKTUSB":"PKT","PKTLSB":"PKT","PKTFM":"PKT","DV":"DV",
}

MODE_FOR_DIGITAL = {
    "FT8":"PKTUSB","FT4":"PKTUSB","WSPR":"PKTUSB",
    "JS8":"PKTUSB","PSK31":"PKTUSB","RTTY":"RTTY",
}

# Filter bandwidth per mode (Hz), FIL1/2/3
FILTER_BW = {
    "USB":    {1:3000,  2:2400,  3:1800},
    "LSB":    {1:3000,  2:2400,  3:1800},
    "CW":     {1:500,   2:250,   3:100},
    "RTTY":   {1:500,   2:350,   3:250},
    "FM":     {1:15000, 2:10000, 3:7000},
    "WFM":    {1:150000,2:100000,3:75000},
    "AM":     {1:6000,  2:4000,  3:3000},
    "PKTUSB": {1:3000,  2:2400,  3:1800},
    "PKTLSB": {1:3000,  2:2400,  3:1800},
    "DV":     {1:6000,  2:4000,  3:3000},
}

# Step sizes in Hz
STEP_SIZES = [1, 10, 100, 1_000, 5_000, 10_000, 100_000, 1_000_000]
STEP_LABELS = ["1 Hz","10 Hz","100 Hz","1 kHz","5 kHz","10 kHz","100 kHz","1 MHz"]

# Conventional band entry frequencies per mode
BAND_ENTRY = {
    "USB":    {"160m":1860000,"80m":3850000,"40m":7200000,"20m":14225000,
               "17m":18130000,"15m":21300000,"12m":24950000,"10m":28400000,
               "6m":50125000,"2m":144200000,"70cm":432100000},
    "LSB":    {"160m":1860000,"80m":3850000,"40m":7200000},
    "FM":     {"6m":52525000,"2m":146520000,"70cm":446000000},
    "CW":     {"160m":1810000,"80m":3550000,"40m":7030000,"20m":14030000,
               "17m":18080000,"15m":21030000,"12m":24900000,"10m":28030000,
               "6m":50090000,"2m":144050000},
    "PKTUSB": {"160m":1840000,"80m":3573000,"40m":7074000,"20m":14074000,
               "17m":18100000,"15m":21074000,"12m":24915000,"10m":28074000,
               "6m":50313000},
    "WSPR":   {"160m":1836600,"80m":3568600,"40m":7038600,"30m":10138700,
               "20m":14095600,"17m":18104600,"15m":21094600,"10m":28124600},
}


class RigTab(_RigRotorMixin, _RigVoiceMixin, _RigCWMixin, SquelchPanel, QWidget):
    panel_id    = "rig"
    panel_title = "Rig"

    def __init__(self, rig: RigController, config, parent=None):
        super().__init__(parent)
        self.rig  = rig
        self.cfg  = config
        self._auto_mode     = True
        self._step_hz       = 1_000        # default 1 kHz
        self._step_idx      = 3
        self._scan_running  = False
        self._scan_timer    = QTimer(self)
        self._scan_timer.timeout.connect(self._scan_step)
        self._memories      = {}           # slot -> (hz, mode, label)
        self._spectrum_widget = None
        self._rotor: "object | None" = None   # RotorController (lazy import)

        self._build()
        self._wire()
        self._populate_ports()
        # Restore saved port
        saved_port = self.cfg.get("rig.port", "")
        if saved_port:
            idx = self.port_combo.findText(saved_port)
            if idx >= 0:
                self.port_combo.setCurrentIndex(idx)
            else:
                # Port not in list — add and select it
                self.port_combo.addItem(saved_port)
                self.port_combo.setCurrentText(saved_port)
        self._populate_rig_models()

    # ── Build UI ──────────────────────────────────────────────────────────


    def save_state(self) -> dict:
        try:
            def _vis(attr):
                w = getattr(self, attr, None)
                return bool(w and w.isVisible())
            return {
                "freq_hz":       self.freq_display._freq_hz,
                "step_label":    getattr(self, "_step_label", "1 kHz"),
                "band":          getattr(self, "_current_band", ""),
                "cw_open":       _vis("_cw_body"),
                "voice_open":    _vis("_voice_body"),
                "scanner_open":  _vis("_scan_body"),
                "memory_open":   _vis("_mem_body"),
                "spectrum_open": _vis("_spectrum_widget"),
                "rotor_open":    _vis("_rotor_body"),
                # Persist memory channels as list of [slot, hz, mode, label]
                "memories": [
                    [slot, hz, mode, label]
                    for slot, (hz, mode, label) in self._memories.items()
                ],
            }
        except Exception:
            return {}

    def restore_state(self, state: dict) -> None:
        try:
            if "freq_hz" in state and state["freq_hz"]:
                self._set_freq(state["freq_hz"])
            for key, body_attr, toggle_attr in [
                ("cw_open",       "_cw_body",       "_cw_toggle"),
                ("voice_open",    "_voice_body",     "_voice_toggle"),
                ("scanner_open",  "_scan_body",      "_scan_toggle"),
                ("memory_open",   "_mem_body",       "_mem_toggle"),
                ("spectrum_open", "_spectrum_widget", "_spec_toggle"),
                ("rotor_open",    "_rotor_body",      "_rotor_toggle"),
            ]:
                if key not in state:
                    continue
                body = getattr(self, body_attr, None)
                toggle = getattr(self, toggle_attr, None)
                if body:
                    body.setVisible(bool(state[key]))
                if toggle and hasattr(toggle, "setChecked"):
                    toggle.setChecked(bool(state[key]))
            # Restore memory channels
            for entry in state.get("memories", []):
                try:
                    slot, hz, mode, label = entry
                    self._memories[slot] = (hz, mode, label)
                    r = self._mem_table.rowCount()
                    self._mem_table.insertRow(r)
                    self._mem_table.setItem(r, 0, QTableWidgetItem(f"M{slot:02d}"))
                    self._mem_table.setItem(r, 1,
                        QTableWidgetItem(f"{hz/1e6:.6f} MHz"))
                    self._mem_table.setItem(r, 2, QTableWidgetItem(mode))
                    self._mem_table.setItem(r, 3, QTableWidgetItem(label))
                except Exception:
                    pass
        except Exception:
            pass

    def _build(self):
        # ── Build UI ──────────────────────────────────────────────────────
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        inner = QWidget()
        self._rig_root = QVBoxLayout(inner)
        root = self._rig_root
        self._rig_root.setSpacing(6)
        self._rig_root.setContentsMargins(6, 6, 6, 6)
        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._build_vfo_section(inner)
        self._build_vfo_ab_section(inner)
        self._build_mode_section(inner)
        self._build_cw_section(inner)
        self._build_voice_section(inner)
        self._build_scanner_section(inner)
        self._build_memory_section(inner)
        self._build_rotor_section(inner)
        self._build_connection_section(inner)
        self._build_spectrum_section(inner)

        root.addStretch()

    def _build_vfo_section(self, inner):
        row1 = QHBoxLayout()
        row1.addWidget(self._build_vfo_group(), 3)
        row1.addWidget(self._build_status_group(), 2)
        self._rig_root.addLayout(row1)
        self._rig_root.addWidget(self._build_quick_dial_row())

    def _build_quick_dial_row(self) -> QWidget:
        """Row of 8 quick-dial buttons for one-click frequency/mode tuning."""
        w   = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        self._qdial_btns = []
        # Load quick-dials from cfg; default to common digital calling freqs
        defaults = [
            {"label": "FT8 20m", "hz": 14_074_000, "mode": "PKTUSB"},
            {"label": "FT8 40m", "hz": 7_074_000,  "mode": "PKTUSB"},
            {"label": "FT8 80m", "hz": 3_573_000,  "mode": "PKTUSB"},
            {"label": "FT4 20m", "hz": 14_080_000, "mode": "PKTUSB"},
            {"label": "CW 20m",  "hz": 14_020_000, "mode": "CW"},
            {"label": "SSB 20m", "hz": 14_225_000, "mode": "USB"},
            {"label": "WSPR 30m", "hz": 10_138_700, "mode": "PKTUSB"},
            {"label": "WWV",     "hz": 10_000_000, "mode": "AM"},
        ]
        saved = self.cfg.get("rig.quick_dials", None)
        dials = saved if isinstance(saved, list) and len(saved) == 8 else defaults
        for i, d in enumerate(dials):
            btn = QPushButton(d.get("label", f"Q{i+1}"))
            btn.setFixedHeight(22)
            btn.setToolTip(
                f"{d.get('label', '')}  {d.get('hz', 0)/1e6:.4f} MHz  "
                f"{d.get('mode', '')}\nRight-click to edit")
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda _, idx=i: self._qdial_edit(idx))
            btn.clicked.connect(
                lambda _, dd=d: self._qdial_tune(dd))
            btn.setStyleSheet(
                "QPushButton{background:#1a1a1a;border:1px solid #333;"
                "border-radius:3px;font-size:9px;padding:0 3px;}"
                "QPushButton:hover{border-color:#555;}")
            lay.addWidget(btn)
            self._qdial_btns.append((btn, d))
        self._qdial_data = dials
        return w

    def _qdial_tune(self, d: dict) -> None:
        """Tune rig to a quick-dial frequency+mode."""
        hz   = int(d.get("hz", 0))
        mode = (d.get("mode", "") or "").upper()
        if hz <= 0:
            return
        self._set_freq(hz)
        if mode and self.rig.is_connected:
            try:
                self.rig.set_mode(mode)
            except Exception:
                pass

    def _qdial_edit(self, idx: int) -> None:
        """Right-click → edit a quick-dial entry."""
        from PyQt6.QtWidgets import (QDialog, QFormLayout, QLineEdit,
                                     QDialogButtonBox, QDoubleSpinBox)
        d   = self._qdial_data[idx]
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Edit Quick-Dial Q{idx+1}")
        f   = QFormLayout(dlg)
        lbl_e = QLineEdit(d.get("label", ""))
        lbl_e.setMaxLength(10)
        hz_e  = QDoubleSpinBox()
        hz_e.setRange(0.001, 6000.0)
        hz_e.setDecimals(4)
        hz_e.setSuffix(" MHz")
        hz_e.setValue(d.get("hz", 14_074_000) / 1e6)
        mode_e = QLineEdit(d.get("mode", "USB"))
        mode_e.setMaxLength(8)
        f.addRow("Label:", lbl_e)
        f.addRow("Frequency:", hz_e)
        f.addRow("Mode:", mode_e)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        f.addRow(btns)
        if not dlg.exec():
            return
        new_d = {
            "label": lbl_e.text().strip() or f"Q{idx+1}",
            "hz":    int(hz_e.value() * 1_000_000),
            "mode":  mode_e.text().strip().upper() or "USB",
        }
        self._qdial_data[idx] = new_d
        btn, _ = self._qdial_btns[idx]
        btn.setText(new_d["label"])
        btn.setToolTip(
            f"{new_d['label']}  {new_d['hz']/1e6:.4f} MHz  {new_d['mode']}\n"
            "Right-click to edit")
        btn.clicked.disconnect()
        btn.clicked.connect(lambda _, dd=new_d: self._qdial_tune(dd))
        self._qdial_btns[idx] = (btn, new_d)
        # Persist
        self.cfg.set("rig.quick_dials", self._qdial_data)

    def _build_vfo_group(self) -> QGroupBox:
        vfo_grp = QGroupBox("VFO A")
        vfl = QVBoxLayout(vfo_grp)
        vfl.setSpacing(4)
        self.freq_display = FreqDisplay()
        self.freq_display.wheelEvent = self._wheel_on_vfo
        vfl.addWidget(self.freq_display)
        self._band_info = QLabel("20m  |  Digital  |  General+")
        self._band_info.setStyleSheet(" ")
        vfl.addWidget(self._band_info)
        self._build_vfo_step_row(vfl)
        self._build_vfo_arrow_row(vfl)
        return vfo_grp

    def _build_vfo_step_row(self, vfl) -> None:
        step_lbl = QLabel("Step:")
        step_lbl.setStyleSheet(" ")
        step_row = QHBoxLayout()
        step_row.setSpacing(2)
        step_row.addWidget(step_lbl)
        self._step_btns = []
        self._step_grp  = QButtonGroup(self)
        self._step_grp.setExclusive(True)
        for i, (hz, lbl) in enumerate(zip(STEP_SIZES, STEP_LABELS)):
            btn = QPushButton(lbl)
            btn.setCheckable(True)
            btn.setChecked(i == self._step_idx)
            btn.setFixedHeight(20)
            btn.setStyleSheet(
                "QPushButton{border:1px solid palette(mid);"
                "border-radius:3px;padding:0 4px;}"
                "QPushButton:checked{background:#1a7a3f;color:#ffffff;"
                "border-color:#1a7a3f;}"
                "QPushButton:hover{border-color:palette(highlight);}")
            btn.clicked.connect(lambda _, idx=i, s=hz: self._set_step(idx, s))
            self._step_btns.append(btn)
            self._step_grp.addButton(btn)
            step_row.addWidget(btn)
        step_row.addStretch()
        vfl.addLayout(step_row)

    def _build_vfo_arrow_row(self, vfl) -> None:
        arrow_row = QHBoxLayout()
        arrow_row.setSpacing(4)
        _ta = _get_rig_theme(self.cfg.get("ui.theme", "Dark"))
        _abtn_ss = (
            f"QPushButton{{border:1px solid {_ta.border};"
            f"border-radius:4px;background:{_ta.bg_tertiary};"
            f"color:{_ta.fg_primary};}}"
            f"QPushButton:hover{{background:{_ta.bg_secondary};"
            f"color:{_ta.accent};}}"
            f"QPushButton:pressed{{background:{_ta.bg_primary};}}"
        )
        def _abtn(label, tip, cb):
            b = QPushButton(label)
            b.setFixedSize(34, 28)
            b.setToolTip(tip)
            b.setStyleSheet(_abtn_ss)
            b.clicked.connect(cb)
            return b
        # Single horizontal axis: left = lower freq, right = higher; magnitude
        # shrinks toward centre — band edge (⏮⏭) → step (⏪⏩) → fine 1 Hz (◄►).
        tune_lbl = QLabel("Tune:")
        tune_lbl.setStyleSheet(" ")
        arrow_row.addWidget(tune_lbl)
        arrow_row.addWidget(_abtn("⏮", "Jump to band start (lowest frequency)",
                                  self._jump_band_start))
        arrow_row.addWidget(_abtn("⏪", "Step down (− selected step size)",
                                  self._step_down))
        arrow_row.addWidget(_abtn("◄", "Fine tune down (− 1 Hz)",
                                  lambda: self._nudge(-1)))
        arrow_row.addWidget(_abtn("►", "Fine tune up (+ 1 Hz)",
                                  lambda: self._nudge(1)))
        arrow_row.addWidget(_abtn("⏩", "Step up (+ selected step size)",
                                  self._step_up))
        arrow_row.addWidget(_abtn("⏭", "Jump to band end (highest frequency)",
                                  self._jump_band_end))
        arrow_row.addSpacing(12)
        arrow_row.addWidget(QLabel("Band:"))
        self._band_jump_combo = QComboBox()
        self._band_jump_combo.setFixedWidth(70)
        _t = _get_rig_theme(self.cfg.get("ui.theme", "Dark"))
        self._band_jump_combo.setStyleSheet(
            f"background:{_t.bg_secondary};border:1px solid {_t.border};")
        self._populate_band_combo()
        arrow_row.addWidget(self._band_jump_combo)
        go_btn = QPushButton("Go")
        go_btn.setFixedSize(36, 24)
        go_btn.setToolTip("Jump to conventional frequency for this band and active mode")
        go_btn.setStyleSheet(
            "QPushButton{border:1px solid #3fbe6f;"
            "border-radius:3px;background:#1a3a1a;color:#3fbe6f;}"
            "QPushButton:hover{background:#2a4a2a;}")
        go_btn.clicked.connect(self._band_go)
        arrow_row.addWidget(go_btn)
        arrow_row.addStretch()
        vfl.addLayout(arrow_row)

    def _build_status_group(self) -> QGroupBox:
        stat_grp = QGroupBox("Status")
        stl = QVBoxLayout(stat_grp)
        stl.setSpacing(4)
        self.status_lbl = QLabel("● Disconnected")
        self.status_lbl.setStyleSheet("  font-weight:bold;")
        from ui.widgets.smeter import SMeterWidget
        self.smeter = SMeterWidget()
        self.smeter.setToolTip(
            "Calibrated signal-strength meter.\n"
            "S0–S4 green · S5–S7 yellow · S8–S9 amber · S9+ red\n"
            "S9 = −73 dBm  (standard 50 Ω HF reference)")
        # Legacy aliases so existing _apply_state code keeps working
        self.smeter_bar = self.smeter   # same widget
        self.smeter_val = self.smeter   # same widget
        stl.addWidget(self.status_lbl)
        stl.addWidget(self.smeter)
        stl.addStretch()
        return stat_grp
    


    def _build_vfo_a_col(self, vab) -> None:
        _t = _get_rig_theme(self.cfg.get("ui.theme", "Dark"))
        va_col = QVBoxLayout()
        va_hdr = QHBoxLayout()
        self._vfo_a_ind = QLabel("▶ A")   # ▶ = active/TX indicator
        self._vfo_a_ind.setStyleSheet(f"font-weight:bold; color:{_t.accent};")
        self._vfo_a_ind.setToolTip("VFO A — current TX VFO")
        va_hdr.addWidget(self._vfo_a_ind)
        va_hdr.addStretch()
        self._vfo_a_lbl = QLabel("—")
        self._vfo_a_lbl.setStyleSheet(
            "font-size:15px; font-weight:bold; font-family:monospace;")
        self._vfo_a_lbl.setToolTip("VFO A frequency")
        va_col.addLayout(va_hdr)
        va_col.addWidget(self._vfo_a_lbl)
        vab.addLayout(va_col, 2)

    def _build_vfo_b_col(self, vab) -> None:
        _t = _get_rig_theme(self.cfg.get("ui.theme", "Dark"))
        vb_col = QVBoxLayout()
        vb_hdr = QHBoxLayout()
        self._vfo_b_ind = QLabel("  B")
        self._vfo_b_ind.setStyleSheet(f"color:{_t.fg_secondary};")
        self._vfo_b_ind.setToolTip("VFO B — RX only (▶ = TX in split mode)")
        vb_hdr.addWidget(self._vfo_b_ind)
        vb_hdr.addStretch()
        self._vfo_b_lbl = QLabel("—")
        self._vfo_b_lbl.setStyleSheet(
            f"font-size:15px; font-weight:bold; "
            f"font-family:monospace; color:{_t.fg_secondary};")
        self._vfo_b_lbl.setToolTip("VFO B frequency — TX in split mode")
        vb_col.addLayout(vb_hdr)
        vb_col.addWidget(self._vfo_b_lbl)
        vab.addLayout(vb_col, 2)

    def _build_vfo_ab_section(self, inner):
            # ── VFO A/B + Split (C-03, Hank) ─────────────────────────────────
            # TX VFO is shown clearly — critical for "no unexpected TX" (C-08).
            vfo_ab_grp = QGroupBox("VFO A / B")
            vab = QHBoxLayout(vfo_ab_grp)
            vab.setSpacing(8)
            self._build_vfo_a_col(vab)
            ctrl_col = QVBoxLayout()
            ctrl_col.setSpacing(4)
            swap_btn = QPushButton("A↔B")
            swap_btn.setToolTip("Swap VFO A and VFO B frequencies")
            swap_btn.setFixedHeight(26)
            swap_btn.clicked.connect(self._swap_vfo)
            self._split_btn = QPushButton("Split OFF")
            self._split_btn.setCheckable(True)
            self._split_btn.setToolTip(
                "Split: receive on VFO A, transmit on VFO B.\n"
                "TX VFO indicator updates to show B when active.")
            self._split_btn.setFixedHeight(26)
            self._split_btn.toggled.connect(self._on_split_toggle)
            ctrl_col.addWidget(swap_btn)
            ctrl_col.addWidget(self._split_btn)
            ctrl_col.addStretch()
            vab.addLayout(ctrl_col, 1)
            self._build_vfo_b_col(vab)
            self._rig_root.addWidget(vfo_ab_grp)
    


    def _build_mode_section(self, inner):
        self._rig_root.addWidget(self._build_mode_buttons_group())
        self._build_rig_controls_row()
        self._build_vfo_b_row()

    def _build_mode_buttons_group(self) -> QGroupBox:
        mode_grp = QGroupBox("Mode")
        ml = QHBoxLayout(mode_grp)
        ml.setSpacing(4)
        self._mode_btns = {}
        self._mode_btn_grp = QButtonGroup(self)
        self._mode_btn_grp.setExclusive(True)
        _t = _get_rig_theme(self.cfg.get("ui.theme", "Dark"))
        _mode_btn_ss = (
            f"QPushButton{{border:1px solid {_t.border};"
            f"border-radius:4px;background:{_t.bg_tertiary};"
            f"color:{_t.fg_primary};}}"
            f"QPushButton:checked{{background:{_t.bg_secondary};"
            f"color:{_t.accent};border-color:{_t.accent};font-weight:bold;}}"
            f"QPushButton:hover{{background:{_t.bg_secondary};}}"
        )
        for label, hamlib_mode, tip in MODE_BUTTONS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedSize(46, 28)
            btn.setToolTip(tip)
            btn.setStyleSheet(_mode_btn_ss)
            btn.clicked.connect(lambda _, m=hamlib_mode: self._on_mode_btn(m))
            self._mode_btns[label] = btn
            self._mode_btn_grp.addButton(btn)
            ml.addWidget(btn)
        ml.addSpacing(10)
        self._auto_mode_cb = QCheckBox("Auto")
        self._auto_mode_cb.setChecked(True)
        self._auto_mode_cb.setToolTip(
            "Auto-switch mode by frequency:\n"
            "LSB below 10 MHz, USB above,\n"
            "FM on VHF/UHF, PKT on digital freqs")
        self._auto_mode_cb.setStyleSheet(" ")
        self._auto_mode_cb.toggled.connect(
            lambda c: setattr(self, '_auto_mode', c))
        ml.addWidget(self._auto_mode_cb)
        ml.addStretch()
        return mode_grp

    def _build_rig_controls_row(self) -> None:
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)
        self.ptt_btn = QPushButton("● TX")
        self.ptt_btn.setCheckable(True)
        self.ptt_btn.setFixedSize(64, 36)
        self.ptt_btn.setToolTip(
            "Push-to-talk — toggles transmit\n"
            "Hold Space while Rig tab is focused for PTT\n"
            "Demo Mode and AppState FSM block unintended TX")
        self.ptt_btn.setStyleSheet(
            "QPushButton{border:2px solid #883333;border-radius:5px;"
            "color:#cc4444;font-weight:bold;background:#1a0808;}"
            "QPushButton:checked{background:#cc2222;color:#fff;"
            "border-color:#ff4444;}"
            "QPushButton:hover{background:#2a1010;}")
        ctrl_row.addWidget(_grp("PTT", self.ptt_btn))
        self.power_spin = QSpinBox()
        self.power_spin.setRange(1, 100)
        self.power_spin.setValue(100)
        self.power_spin.setSuffix(" %")
        self.power_spin.setFixedWidth(72)
        self.power_spin.setSingleStep(5)
        self.power_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        orig_wheel = self.power_spin.wheelEvent
        self.power_spin.wheelEvent = lambda e: (
            orig_wheel(e) if self.power_spin.hasFocus() else e.ignore())
        ctrl_row.addWidget(_grp("Power", self.power_spin))
        self.preamp_combo = QComboBox()
        self.preamp_combo.addItems(["Off", "Preamp 1", "Preamp 2"])
        self.preamp_combo.setFixedWidth(88)
        ctrl_row.addWidget(_grp("Preamp", self.preamp_combo))
        self.att_combo = QComboBox()
        self.att_combo.addItems(["Off", "6 dB", "12 dB", "18 dB"])
        self.att_combo.setFixedWidth(70)
        ctrl_row.addWidget(_grp("ATT", self.att_combo))
        self.filter_combo = QComboBox()
        self._update_filter_labels("USB")
        self.filter_combo.setFixedWidth(110)
        ctrl_row.addWidget(_grp("Filter / BW", self.filter_combo))
        ctrl_row.addStretch()
        self._rig_root.addLayout(ctrl_row)

    def _build_vfo_b_row(self) -> None:
        """Build VFO-A/B selector, swap, split, and RIT controls row."""
        vfo_row = QHBoxLayout()
        self._vfo_a_btn = QPushButton("VFO-A")
        self._vfo_a_btn.setFixedHeight(28)
        self._vfo_a_btn.setCheckable(True)
        self._vfo_a_btn.setChecked(True)
        self._vfo_a_btn.setToolTip("Select VFO A")
        self._vfo_a_btn.clicked.connect(lambda: self._select_vfo("A"))
        vfo_row.addWidget(self._vfo_a_btn)
        self._vfo_b_btn = QPushButton("VFO-B")
        self._vfo_b_btn.setFixedHeight(28)
        self._vfo_b_btn.setCheckable(True)
        self._vfo_b_btn.setToolTip("Select VFO B")
        self._vfo_b_btn.clicked.connect(lambda: self._select_vfo("B"))
        vfo_row.addWidget(self._vfo_b_btn)
        swap_btn = QPushButton("⇄ Swap")
        swap_btn.setFixedHeight(28)
        swap_btn.setFixedWidth(70)
        swap_btn.setToolTip("Swap VFO A and VFO B")
        swap_btn.clicked.connect(self._swap_vfo)
        vfo_row.addWidget(swap_btn)
        vfo_row.addSpacing(10)
        self._split_btn = QPushButton("Split")
        self._split_btn.setFixedHeight(28)
        self._split_btn.setCheckable(True)
        self._split_btn.setToolTip(
            "Split operation\nRX on VFO-A, TX on VFO-B\n"
            "Tune VFO-B for DX pileup offset")
        vfo_row.addWidget(self._split_btn)
        vfo_row.addSpacing(10)
        vfo_row.addWidget(QLabel("RIT:"))
        self._rit_spin = QSpinBox()
        self._rit_spin.setRange(-9999, 9999)
        self._rit_spin.setValue(0)
        self._rit_spin.setSuffix(" Hz")
        self._rit_spin.setFixedWidth(90)
        self._rit_spin.setToolTip(
            "RIT/XIT offset (Hz)\nReceive incremental tuning\n0 = disabled")
        self._rit_spin.valueChanged.connect(self._set_rit)
        vfo_row.addWidget(self._rit_spin)
        rit_clear = QPushButton("×")
        rit_clear.setFixedSize(26, 26)
        rit_clear.setToolTip("Clear RIT")
        rit_clear.clicked.connect(lambda: self._rit_spin.setValue(0))
        vfo_row.addWidget(rit_clear)
        vfo_row.addStretch()
        self._rig_root.addLayout(vfo_row)
    


    def _build_scanner_section(self, inner):
        self._scan_toggle = _collapse_btn("Scanner")
        self._scan_toggle.toggled.connect(
            lambda c: self._scan_body.setVisible(c))
        self._rig_root.addWidget(self._scan_toggle)
        self._scan_body = self._build_scanner_body()
        self._rig_root.addWidget(self._scan_body)

    def _build_scanner_body(self) -> QWidget:
        body = QWidget()
        body.setVisible(False)
        scan_layout = QGridLayout(body)
        scan_layout.setContentsMargins(8, 4, 8, 4)
        scan_layout.setSpacing(6)
        self._build_scan_params_grid(scan_layout)
        self._build_scan_btn_row(scan_layout)
        return body

    def _build_scan_params_grid(self, scan_layout) -> None:
        scan_layout.addWidget(QLabel("Mode:"), 0, 0)
        self._scan_mode = QComboBox()
        self._scan_mode.addItems(["Sweep", "Band", "Channel list", "Memory"])
        self._scan_mode.setFixedWidth(120)
        scan_layout.addWidget(self._scan_mode, 0, 1)
        scan_layout.addWidget(QLabel("Dwell (s):"), 0, 2)
        self._scan_dwell = QDoubleSpinBox()
        self._scan_dwell.setRange(0.1, 60.0)
        self._scan_dwell.setValue(2.0)
        self._scan_dwell.setSingleStep(0.5)
        self._scan_dwell.setFixedWidth(70)
        scan_layout.addWidget(self._scan_dwell, 0, 3)
        scan_layout.addWidget(QLabel("Squelch:"), 0, 4)
        self._scan_sql = QSpinBox()
        self._scan_sql.setRange(-120, 0)
        self._scan_sql.setValue(-80)
        self._scan_sql.setSuffix(" dBm")
        self._scan_sql.setFixedWidth(80)
        scan_layout.addWidget(self._scan_sql, 0, 5)
        scan_layout.addWidget(QLabel("From:"), 1, 0)
        self._scan_from = QLineEdit("14.000")
        self._scan_from.setFixedWidth(90)
        scan_layout.addWidget(self._scan_from, 1, 1)
        scan_layout.addWidget(QLabel("To:"), 1, 2)
        self._scan_to = QLineEdit("14.350")
        self._scan_to.setFixedWidth(90)
        scan_layout.addWidget(self._scan_to, 1, 3)
        scan_layout.addWidget(QLabel("Step:"), 1, 4)
        self._scan_step = QComboBox()
        self._scan_step.addItems([
            "100 Hz", "500 Hz", "1 kHz", "2.5 kHz",
            "5 kHz", "6.25 kHz", "10 kHz", "12.5 kHz",
            "25 kHz", "50 kHz", "100 kHz"])
        self._scan_step.setCurrentText("5 kHz")
        self._scan_step.setToolTip(
            "Frequency step between scan stops.\n"
            "Match to channel spacing:\n"
            "  FM voice: 12.5 or 25 kHz\n"
            "  HF: 1-5 kHz\n"
            "  AM broadcast: 10 kHz")
        self._scan_step.setFixedWidth(90)
        scan_layout.addWidget(self._scan_step, 1, 5)

    def _build_scan_btn_row(self, scan_layout) -> None:
        scan_btn_row = QHBoxLayout()
        self._scan_start = QPushButton("▶  Start Scan")
        self._scan_start.setFixedHeight(28)
        self._scan_start.setStyleSheet(
            "background:#1a3a1a;color:#3fbe6f;border:1px solid #3fbe6f;"
            "border-radius:4px;")
        self._scan_start.clicked.connect(self._start_scan)
        self._scan_stop = QPushButton("■  Stop")
        self._scan_stop.setFixedHeight(28)
        self._scan_stop.setEnabled(False)
        self._scan_stop.clicked.connect(self._stop_scan)
        self._scan_lock = QPushButton("⊘  Lock current")
        self._scan_lock.setFixedHeight(28)
        self._scan_lock.setToolTip("Add current frequency to lockout list")
        self._scan_status = QLabel("Idle")
        self._scan_status.setStyleSheet(" ")
        scan_btn_row.addWidget(self._scan_start)
        scan_btn_row.addWidget(self._scan_stop)
        scan_btn_row.addWidget(self._scan_lock)
        scan_btn_row.addWidget(self._scan_status)
        scan_btn_row.addStretch()
        scan_layout.addLayout(scan_btn_row, 2, 0, 1, 6)
    


    def _build_memory_section(self, inner):
            # ── Memory channels (collapsible) ─────────────────────────────────
            self._mem_toggle = _collapse_btn("Memory Channels")
            self._mem_toggle.toggled.connect(
                lambda c: self._mem_body.setVisible(c))
            self._rig_root.addWidget(self._mem_toggle)
    
            self._mem_body = QWidget()
            self._mem_body.setVisible(False)
            mem_layout = QVBoxLayout(self._mem_body)
            mem_layout.setContentsMargins(8, 4, 8, 4)
            mem_layout.setSpacing(4)
    
            self._mem_table = QTableWidget(0, 4)
            self._mem_table.setHorizontalHeaderLabels(
                ["Slot", "Frequency", "Mode", "Label"])
            self._mem_table.setFixedHeight(140)
            self._mem_table.horizontalHeader().setSectionResizeMode(
                3, QHeaderView.ResizeMode.Stretch)
            self._mem_table.setStyleSheet(
                "QTableWidget{background:#111;"
                "gridline-color:#222;}"
                "QHeaderView::section{background:#1a1a1a;"
                "border:none;}")
            self._mem_table.cellDoubleClicked.connect(self._mem_recall)
            mem_layout.addWidget(self._mem_table)
    
            mem_btn_row = QHBoxLayout()
            mem_store = QPushButton("Store current")
            mem_store.setFixedHeight(24)
            mem_store.clicked.connect(self._mem_store)
            mem_recall_btn = QPushButton("Recall selected")
            mem_recall_btn.setFixedHeight(24)
            mem_recall_btn.clicked.connect(
                lambda: self._mem_recall(
                    self._mem_table.currentRow(), 0))
            mem_clear = QPushButton("Clear selected")
            mem_clear.setFixedHeight(24)
            mem_clear.clicked.connect(self._mem_clear)
            mem_export = QPushButton("Export CSV")
            mem_export.setFixedHeight(24)
            mem_export.clicked.connect(self._mem_export_csv)
            chirp_btn = QPushButton("Import CHIRP…")
            chirp_btn.setFixedHeight(24)
            chirp_btn.setToolTip(
                "Import channels from a CHIRP-exported CSV file\n"
                "into the memory channel bank.")
            chirp_btn.clicked.connect(self._mem_import_chirp)
            for b in (mem_store, mem_recall_btn, mem_clear,
                      mem_export, chirp_btn):
                b.setStyleSheet(
                    "background:#1a1a1a;border:1px solid #333;"
                    "border-radius:3px;")
            mem_btn_row.addWidget(mem_store)
            mem_btn_row.addWidget(mem_recall_btn)
            mem_btn_row.addWidget(mem_clear)
            mem_btn_row.addWidget(mem_export)
            mem_btn_row.addWidget(chirp_btn)
            mem_btn_row.addStretch()
            mem_layout.addLayout(mem_btn_row)
            self._rig_root.addWidget(self._mem_body)

    def _build_connection_section(self, inner):
            # ── Connection ────────────────────────────────────────────────────
            conn_grp = QGroupBox("Connection")
            cgl = QGridLayout(conn_grp)
            cgl.setSpacing(6)
    
            cgl.addWidget(QLabel("Rig:"), 0, 0)
            self.model_combo = QComboBox()
            self.model_combo.setMinimumWidth(180)
            cgl.addWidget(self.model_combo, 0, 1)
    
            cgl.addWidget(QLabel("Baud:"), 0, 2)
            self.baud_combo = QComboBox()
            self.baud_combo.setToolTip(
                "Serial baud rate\n"
                "IC-7100: set to 19200\n"
                "Must match radio Menu 072 (CI-V USB Baud)")
            self.baud_combo.addItems([
                "1200","2400","4800","9600",
                "19200","38400","57600","115200"])
            self.baud_combo.setCurrentText("19200")
            self.baud_combo.setFixedWidth(80)
            cgl.addWidget(self.baud_combo, 0, 3)
    
            cgl.addWidget(QLabel("Port:"), 1, 0)
            self.port_combo = QComboBox()
            self.port_combo.setEditable(True)
            self.port_combo.setMinimumWidth(180)
            self.port_combo.setToolTip(
                "COM port for CAT control\n"
                "IC-7100: look for CP210x in Device Manager\n"
                "You can also type a port name (e.g. COM7)")
            self.port_combo.currentTextChanged.connect(
                self._on_port_change)
            cgl.addWidget(self.port_combo, 1, 1)
    
            self.refresh_btn = QPushButton("↺")
            self.refresh_btn.setFixedWidth(28)
            self.refresh_btn.setToolTip("Refresh port list")
            cgl.addWidget(self.refresh_btn, 1, 2)
    
            self.connect_btn = QPushButton("Connect")
            self.connect_btn.setFixedWidth(90)
            self.connect_btn.setStyleSheet("""
                QPushButton{background:#1a3a1a;color:#3fbe6f;
                  border:1px solid #3fbe6f;border-radius:4px;
                  font-weight:bold;padding:5px;}
                QPushButton:hover{background:#2a4a2a;}
                QPushButton:disabled{background:#111;border-}
            """)
            cgl.addWidget(self.connect_btn, 1, 3)
    
            self.disconnect_btn = QPushButton("Disconnect")
            self.disconnect_btn.setEnabled(False)
            self.disconnect_btn.setFixedWidth(90)
            cgl.addWidget(self.disconnect_btn, 0, 4)
    
            self._rig_root.addWidget(conn_grp)
    
            # ── Spectrum / Waterfall (collapsible) ────────────────────────────


    def _build_spectrum_section(self, inner):
            # ── Spectrum / Waterfall (collapsible) ────────────────────────────
            self._spec_toggle = _collapse_btn("Spectrum / Waterfall")
            self._spec_toggle.setChecked(True)
            self._spec_toggle.toggled.connect(
                lambda c: self._spectrum_widget.setVisible(c)
                if self._spectrum_widget else None)
            self._rig_root.addWidget(self._spec_toggle)
    
            self._spectrum_widget = SpectrumWidget(config=self.cfg)
            self._spectrum_widget.freq_clicked.connect(self._on_spec_freq)
            self._rig_root.addWidget(self._spectrum_widget)
    
            self._rig_root.addStretch()
    
            # Initialise VFO TX indicator (simplex by default)
            self._update_vfo_tx_indicator(split=False)



    # ── Wire signals ──────────────────────────────────────────────────────

    def _wire(self):
        self.freq_display.freq_changed.connect(self._on_freq)
        self.ptt_btn.toggled.connect(self._on_ptt)
        self.preamp_combo.currentIndexChanged.connect(self._on_preamp)
        self.att_combo.currentIndexChanged.connect(self._on_att)
        self.filter_combo.currentIndexChanged.connect(self._on_filter)
        self.model_combo.currentIndexChanged.connect(self._on_model_select)
        self.connect_btn.clicked.connect(self._on_connect)
        self.disconnect_btn.clicked.connect(self.rig.disconnect)
        self.refresh_btn.clicked.connect(self._populate_ports)
        self.rig.on_state_change(self._on_rig_state)

    # ── Frequency control ─────────────────────────────────────────────────

    def _set_freq(self, hz: int):
        hz = max(1_000, min(450_000_000, hz))
        self.freq_display.set_freq(hz)
        if self.rig.is_connected:
            self.rig.set_freq(hz)
        self._refresh_band_info(hz)
        if self._auto_mode:
            mode = suggested_mode(hz)
            self._set_mode_ui(mode)
            if self.rig.is_connected:
                self.rig.set_mode(mode)
        if self._spectrum_widget:
            self._spectrum_widget.set_center_freq(hz)
        # Publish freq so macro {freq} stays current
        if self.cfg:
            self.cfg.set("session.vfo_a_mhz", f"{hz / 1_000_000:.6f}")

    @pyqtSlot(int)
    def _on_freq(self, hz: int):
        self._set_freq(hz)

    def _on_spec_freq(self, hz: int):
        if self.rig.is_connected:
            self._set_freq(hz)

    def _step_up(self):
        self._set_freq(self.freq_display._freq_hz + self._step_hz)

    def _step_down(self):
        self._set_freq(self.freq_display._freq_hz - self._step_hz)

    def _nudge(self, direction: int):
        self._set_freq(self.freq_display._freq_hz + direction)

    def _set_step(self, idx: int, hz: int):
        self._step_idx = idx
        self._step_hz  = hz

    def _wheel_on_vfo(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta > 0:
            self._step_up()
        elif delta < 0:
            self._step_down()
        event.accept()

    def _jump_band_start(self):
        band = band_at_freq(self.freq_display._freq_hz)
        if band:
            self._set_freq(band.freq_lo)

    def _jump_band_end(self):
        band = band_at_freq(self.freq_display._freq_hz)
        if band:
            self._set_freq(band.freq_hi)

    def _band_go(self):
        band_name = self._band_jump_combo.currentText()
        mode      = self.rig.state.mode or "USB"
        # Look up conventional frequency for this band+mode
        entry_map = BAND_ENTRY.get(mode, BAND_ENTRY.get("USB", {}))
        hz = entry_map.get(band_name)
        if not hz:
            # Fall back to band start
            from core.band_plan import BAND_EDGES
            edges = BAND_EDGES.get(band_name)
            if edges:
                hz = edges[0]
        if hz:
            self._set_freq(hz)

    def _populate_band_combo(self):
        from core.band_plan import BAND_EDGES
        self._band_jump_combo.clear()
        for band in BAND_EDGES:
            self._band_jump_combo.addItem(band)
        # Default to 20m
        idx = self._band_jump_combo.findText("20m")
        if idx >= 0:
            self._band_jump_combo.setCurrentIndex(idx)

    # ── Mode control ──────────────────────────────────────────────────────

    def _on_mode_btn(self, hamlib_mode: str):
        # Disable auto-mode when user manually picks a mode
        self._auto_mode_cb.blockSignals(True)
        self._auto_mode_cb.setChecked(False)
        self._auto_mode_cb.blockSignals(False)
        self._auto_mode = False
        self._update_filter_labels(hamlib_mode)
        if self.rig.is_connected:
            self.rig.set_mode(hamlib_mode)
        self._update_bw_marker(hamlib_mode)
        # Publish mode so macro {mode} stays current
        if self.cfg:
            self.cfg.set("session.mode", hamlib_mode)

    def _set_mode_ui(self, hamlib_mode: str):
        target = MODE_TO_BTN.get(hamlib_mode, "USB")
        for label, btn in self._mode_btns.items():
            btn.blockSignals(True)
            btn.setChecked(label == target)
            btn.blockSignals(False)
        self._update_filter_labels(hamlib_mode)
        self._update_bw_marker(hamlib_mode)

    def _update_filter_labels(self, mode: str):
        bw  = FILTER_BW.get(mode, FILTER_BW["USB"])
        cur = self.filter_combo.currentIndex()
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItems([
            f"FIL1  {bw[1]:,} Hz",
            f"FIL2  {bw[2]:,} Hz",
            f"FIL3  {bw[3]:,} Hz",
        ])
        self.filter_combo.setCurrentIndex(max(0, cur))
        self.filter_combo.blockSignals(False)

    def _update_bw_marker(self, mode: str = None):
        if not self._spectrum_widget:
            return
        mode = mode or self.rig.state.mode or "USB"
        fil  = self.filter_combo.currentIndex() + 1
        bw   = FILTER_BW.get(mode, FILTER_BW["USB"]).get(fil, 2400)
        self._spectrum_widget.set_bandwidth_hz(bw)

    # ── Controls ──────────────────────────────────────────────────────────

    @pyqtSlot(bool)
    def _on_ptt(self, tx: bool):
        if self.rig.is_connected:
            self.rig.set_ptt(tx)

    @pyqtSlot(int)
    def _on_preamp(self, idx: int):
        if self.rig.is_connected:
            self.rig.set_preamp(idx)

    @pyqtSlot(int)
    def _on_att(self, idx: int):
        if self.rig.is_connected:
            self.rig.set_attenuator([0, 6, 12, 18][idx])

    @pyqtSlot(int)
    def _on_filter(self, idx: int):
        if self.rig.is_connected:
            self.rig.set_filter(idx + 1)
        self._update_bw_marker()

    # ── Scanner ───────────────────────────────────────────────────────────

    def _on_backend_change(self, backend: str):
        """Switch between rigctld and FLRig backends."""
        use_flrig = "FLRig" in backend
        self.cfg.set("rig.backend", "flrig" if use_flrig else "hamlib")
        self.cfg.save()

    def _select_vfo(self, vfo: str):
        """Switch active VFO."""
        self._vfo_a_btn.setChecked(vfo == "A")
        self._vfo_b_btn.setChecked(vfo == "B")
        if self.rig.is_connected:
            self.rig.set_vfo(vfo)

    def _swap_vfo(self):
        """Swap VFO A and B and update the displays."""
        if self.rig.is_connected:
            self.rig.swap_vfo()
            self._refresh_vfo_displays()

    def _on_split_toggle(self, enabled: bool):
        """Enable/disable split TX. TX VFO indicator updates to show B."""
        if self.rig.is_connected:
            self.rig.set_split(enabled)
        self._split_btn.setText("Split ON" if enabled else "Split OFF")
        self._split_btn.setStyleSheet(
            "background:#1a3a1a;color:#3fbe6f;border-color:#3fbe6f;"
            if enabled else "")
        self._update_vfo_tx_indicator(split=enabled)

    def _update_vfo_tx_indicator(self, split: bool = False):
        """Show clearly which VFO is TX (▶ marker) — critical for C-08."""
        _t = _get_rig_theme(self.cfg.get("ui.theme", "Dark"))
        if split:
            self._vfo_a_ind.setText("  A")
            self._vfo_a_ind.setStyleSheet(f"color:{_t.fg_secondary};")
            self._vfo_a_ind.setToolTip("VFO A — RX only in split mode")
            self._vfo_b_ind.setText("▶ B TX")
            self._vfo_b_ind.setStyleSheet(
                f"font-weight:bold; color:{_t.warn_color};")
            self._vfo_b_ind.setToolTip("VFO B — TRANSMIT in split mode")
            self._vfo_b_lbl.setStyleSheet(
                f"font-size:15px; font-weight:bold; "
                f"font-family:monospace; color:{_t.warn_color};")
        else:
            self._vfo_a_ind.setText("▶ A TX")
            self._vfo_a_ind.setStyleSheet(
                f"font-weight:bold; color:{_t.accent};")
            self._vfo_a_ind.setToolTip("VFO A — TRANSMIT (simplex)")
            self._vfo_b_ind.setText("  B")
            self._vfo_b_ind.setStyleSheet(f"color:{_t.fg_secondary};")
            self._vfo_b_ind.setToolTip("VFO B — standby")
            self._vfo_b_lbl.setStyleSheet(
                f"font-size:15px; font-weight:bold; "
                f"font-family:monospace; color:{_t.fg_secondary};")

    def _refresh_vfo_displays(self):
        """Update VFO A and B frequency labels from the rig (or cache)."""
        try:
            freq_a = self.rig.state.freq_hz
            hz = freq_a or 0
            mhz_a = f"{hz / 1_000_000:.6f} MHz"
            self._vfo_a_lbl.setText(mhz_a)
        except Exception:
            self._vfo_a_lbl.setText("—")
        try:
            if self.rig.is_connected:
                import threading
                def _get_b():
                    fb = self.rig.get_vfo_b_freq()
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(
                        0, lambda: self._vfo_b_lbl.setText(
                            f"{fb / 1_000_000:.6f} MHz" if fb else "—"))
                threading.Thread(target=_get_b, daemon=True).start()
        except Exception:
            pass

    def _set_rit(self, hz: int):
        """Set RIT offset."""
        if self.rig.is_connected:
            self.rig.set_rit(hz)

    def _start_scan(self):
        if not self.rig.is_connected:
            QMessageBox.warning(self, "Scanner",
                                "Connect the rig before scanning.")
            return
        mode = self._scan_mode.currentText()

        if mode == "Memory":
            channels = sorted(self._memories.items())   # [(slot, (hz,mode,label))]
            if not channels:
                QMessageBox.warning(self, "Scanner",
                                    "No memory channels stored.\n"
                                    "Use the Memory Channels section to add some.")
                return
            self._scan_channel_list = [(hz, m, lbl)
                                       for _, (hz, m, lbl) in channels]
            self._scan_channel_idx  = 0
            self._scan_list_mode    = True

        elif mode == "Channel list":
            raw = self._scan_from.text().strip()
            freqs = []
            for tok in raw.replace(";", ",").split(","):
                tok = tok.strip()
                if not tok:
                    continue
                try:
                    freqs.append((int(float(tok) * 1_000_000), "", tok))
                except ValueError:
                    pass
            if not freqs:
                QMessageBox.warning(self, "Scanner",
                                    "Enter comma-separated frequencies in MHz in the 'From' field.")
                return
            self._scan_channel_list = freqs
            self._scan_channel_idx  = 0
            self._scan_list_mode    = True

        else:  # Sweep / Band
            try:
                lo = int(float(self._scan_from.text()) * 1_000_000)
                hi = int(float(self._scan_to.text()) * 1_000_000)
            except ValueError:
                QMessageBox.warning(self, "Scanner", "Invalid frequency range.")
                return
            self._scan_lo  = lo
            self._scan_hi  = hi
            self._scan_cur = lo
            self._scan_list_mode = False
            try:
                step_txt = self._scan_step.currentText()
                if "kHz" in step_txt:
                    step_hz = int(float(step_txt.replace(" kHz", "")) * 1_000)
                elif "Hz" in step_txt:
                    step_hz = int(step_txt.replace(" Hz", ""))
                else:
                    step_hz = 5_000
            except Exception:
                step_hz = 5_000
            self._scan_step_hz = step_hz

        self._scan_running = True
        interval = int(self._scan_dwell.value() * 1000)
        self._scan_timer.setInterval(interval)
        self._scan_timer.start()
        self._scan_start.setEnabled(False)
        self._scan_stop.setEnabled(True)
        self._scan_status.setText("Scanning…")
        self._scan_status.setStyleSheet(
            f"color:{_get_rig_theme(self.cfg.get('ui.theme', 'Dark')).accent}; ")

    def _stop_scan(self):
        self._scan_running = False
        self._scan_timer.stop()
        self._scan_start.setEnabled(True)
        self._scan_stop.setEnabled(False)
        self._scan_status.setText("Idle")
        self._scan_status.setStyleSheet(" ")

    def _scan_squelch_open(self) -> bool:
        """Return True when the rig signal exceeds the scan SQL threshold."""
        try:
            sql_dbm = self._scan_sql.value()       # dBm threshold (e.g. -80)
            s_level = self.rig.state.s_meter       # 0-13
            # Convert S-level to approximate dBm using the standard scale
            from ui.widgets.smeter import _DBM
            level_dbm = _DBM[max(0, min(13, s_level))]
            return level_dbm >= sql_dbm
        except Exception:
            return False   # can't read → don't block scanning

    def _scan_step(self):
        if not self._scan_running:
            return
        # Squelch gate: if signal is above threshold, hold on this channel
        if self.rig.is_connected and self._scan_squelch_open():
            self._scan_status.setText(
                self._scan_status.text() + "  🔴 SIGNAL")
            return  # stay on current frequency

        if getattr(self, "_scan_list_mode", False):
            # Memory / Channel-list mode: advance through channel list
            channels = self._scan_channel_list
            if not channels:
                self._stop_scan()
                return
            idx = getattr(self, "_scan_channel_idx", 0) % len(channels)
            self._scan_channel_idx = (idx + 1) % len(channels)
            hz, mode_str, label = channels[idx]
            self._set_freq(hz)
            if mode_str and self.rig.is_connected:
                from core.spot_tune import infer_rig_mode
                try:
                    self.rig.set_mode(infer_rig_mode(mode_str, hz))
                except Exception:
                    pass
            self._scan_status.setText(
                f"Ch {idx+1}/{len(channels)}  {hz/1e6:.4f} MHz"
                + (f"  {label}" if label and label != str(hz/1e6) else ""))
        else:
            step = getattr(self, "_scan_step_hz", self._step_hz)
            self._scan_cur += step
            if self._scan_cur > self._scan_hi:
                self._scan_cur = self._scan_lo
            self._set_freq(self._scan_cur)
            self._scan_status.setText(
                f"Scanning  {self._scan_cur/1e6:.4f} MHz")

    # ── Memory channels ───────────────────────────────────────────────────

    def _mem_store(self):
        hz    = self.freq_display._freq_hz
        mode  = self.rig.state.mode or "USB"
        slot  = self._mem_table.rowCount() + 1
        label = f"M{slot:02d}"
        self._memories[slot] = (hz, mode, label)
        self._mem_table.insertRow(self._mem_table.rowCount())
        r = self._mem_table.rowCount() - 1
        self._mem_table.setItem(r, 0, QTableWidgetItem(f"M{slot:02d}"))
        self._mem_table.setItem(r, 1,
            QTableWidgetItem(f"{hz/1e6:.6f} MHz"))
        self._mem_table.setItem(r, 2, QTableWidgetItem(mode))
        self._mem_table.setItem(r, 3, QTableWidgetItem(label))

    def _mem_recall(self, row: int, _col: int):
        if row < 0 or row >= self._mem_table.rowCount():
            return
        try:
            freq_txt = self._mem_table.item(row, 1).text()
            hz = int(float(freq_txt.split()[0]) * 1_000_000)
            mode = self._mem_table.item(row, 2).text()
            self._set_freq(hz)
            self._set_mode_ui(mode)
            if self.rig.is_connected:
                self.rig.set_mode(mode)
        except Exception as e:
            log.warning(f"Memory recall: {e}")

    def _mem_clear(self):
        row = self._mem_table.currentRow()
        if row >= 0:
            self._mem_table.removeRow(row)

    def _mem_import_chirp(self) -> None:
        """Import memory channels from a CHIRP-exported CSV file."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        path, _ = QFileDialog.getOpenFileName(
            self, "Import CHIRP CSV", "",
            "CSV files (*.csv);;All files (*)")
        if not path:
            return
        try:
            from network.chirp_import import parse_chirp_csv
            repeaters = parse_chirp_csv(path)
        except Exception as e:
            QMessageBox.warning(self, "CHIRP Import",
                                f"Failed to parse CSV:\n{e}")
            return
        added = 0
        for rep in repeaters:
            freq_hz = int(rep.output_mhz * 1_000_000)
            mode    = rep.mode or "FM"
            label   = (rep.callsign or "").strip()[:12] or f"CH{added+1}"
            slot    = max(self._memories.keys(), default=0) + 1
            self._memories[slot] = (freq_hz, mode, label)
            r = self._mem_table.rowCount()
            self._mem_table.insertRow(r)
            self._mem_table.setItem(r, 0, QTableWidgetItem(f"M{slot:02d}"))
            self._mem_table.setItem(r, 1,
                QTableWidgetItem(f"{rep.output_mhz:.6f} MHz"))
            self._mem_table.setItem(r, 2, QTableWidgetItem(mode))
            self._mem_table.setItem(r, 3, QTableWidgetItem(label))
            added += 1
        QMessageBox.information(self, "CHIRP Import",
                                f"Imported {added} channel(s) from CHIRP CSV.")

    def _mem_export_csv(self):
        """Export memory channels to a CSV file."""
        from PyQt6.QtWidgets import QFileDialog
        import csv
        from pathlib import Path
        from core.sanitize import csv_safe
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Memory Channels", "rig_memories.csv",
            "CSV files (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Slot", "Frequency MHz", "Mode", "Label"])
                for slot, (hz, mode, label) in sorted(self._memories.items()):
                    w.writerow([
                        f"M{slot:02d}",
                        f"{hz/1e6:.6f}",
                        csv_safe(mode),
                        csv_safe(label),
                    ])
            log.info(f"Exported {len(self._memories)} memory channels to {path}")
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Export Failed", str(e))

    # ── Rig state callback ────────────────────────────────────────────────

    def _on_rig_state(self, state):
        QTimer.singleShot(0, lambda s=state: self._apply_state(s))

    def _apply_state(self, state):
        STATUS = {
            RigStatus.DISCONNECTED: ("● Disconnected", "#777"),
            RigStatus.CONNECTING:   ("● Connecting…",  "#aaaa22"),
            RigStatus.CONNECTED:    ("● Connected",    "#3fbe6f"),
            RigStatus.ERROR:        ("● Error",        "#cc4444"),
            RigStatus.PTT_TX:       ("● TX",           "#ff4444"),
        }
        txt, col = STATUS.get(state.status, ("● Unknown","#777"))
        self.status_lbl.setText(txt)
        self.status_lbl.setStyleSheet(
            f"color:{col};  font-weight:bold;")

        connected = self.rig.is_connected
        self.connect_btn.setEnabled(not connected)
        self.connect_btn.setText("Connect")
        self.disconnect_btn.setEnabled(connected)

        if connected:
            self.freq_display.set_freq(state.freq_hz)
            self.freq_display.set_band(state.band)
            self.freq_display.set_tx(state.ptt)
            self._set_mode_ui(state.mode)
            self._refresh_band_info(state.freq_hz)
            # Update VFO A label from live state; B updated periodically
            try:
                hz = state.freq_hz or 0
                self._vfo_a_lbl.setText(
                    f"{hz / 1_000_000:.6f} MHz" if hz else "—")
            except Exception:
                pass
            if self._spectrum_widget:
                self._spectrum_widget.set_center_freq(state.freq_hz)
                if not self._spectrum_widget._running:
                    self._spectrum_widget.start()
        else:
            if (self._spectrum_widget and
                    self._spectrum_widget._running):
                self._spectrum_widget.stop()

        s = max(0, min(13, state.s_meter))
        cal = int(self.cfg.get("rig.smeter_cal_db", 0) or 0)
        self.smeter.set_level(s, cal)

        self.ptt_btn.blockSignals(True)
        self.ptt_btn.setChecked(state.ptt)
        self.ptt_btn.blockSignals(False)

        if state.status == RigStatus.PTT_TX and self._scan_running:
            self._stop_scan()

    # ── Band info ─────────────────────────────────────────────────────────

    def _refresh_band_info(self, hz: int):
        band = band_at_freq(hz)
        if band:
            seg = band.segment_at(hz)
            seg_txt = seg.mode_notes if seg else "Mixed"
            lic_txt = seg.license if seg else ""
            self._band_info.setText(
                f"{band.name}  |  {seg_txt}  |  {lic_txt}")
        else:
            self._band_info.setText("Out of amateur band")
            self._band_info.setStyleSheet(
                "color:#cc4444; ")
            return
        self._band_info.setStyleSheet(" ")

    # ── Port / model population ───────────────────────────────────────────

    def _on_port_change(self, port: str):
        """Save selected port to config."""
        if port and not port.startswith("──"):
            self.cfg.set("rig.port", port)
            self.cfg.save()

    def _populate_ports(self):
        self.port_combo.clear()
        # Always show common Windows ports first
        common_ports = [
            "AUTO  —  auto-detect",
            "COM1", "COM2", "COM3", "COM4",
            "COM5", "COM6", "COM7", "COM8",
            "COM9", "COM10", "COM11", "COM12",
        ]
        for p in common_ports:
            self.port_combo.addItem(p)

        # Try to detect actual ports via pyserial
        try:
            ports = RigController.list_ports()
            if ports:
                self.port_combo.insertSeparator(
                    self.port_combo.count())
                detected_lbl = "── Detected ports ──"
                self.port_combo.addItem(detected_lbl)
                self.port_combo.model().item(
                    self.port_combo.count()-1
                ).setEnabled(False)
        except Exception:
            ports = []
        for p in ports:
            label = p["port"]
            if p["description"]:
                label += f"  —  {p['description'][:42]}"
            self.port_combo.addItem(label)
            if p["likely_rig"]:
                idx = self.port_combo.count() - 1
                self.port_combo.setItemData(
                    idx, "#3fbe6f",
                    Qt.ItemDataRole.ForegroundRole)

    def _detect_rig_model(self) -> str | None:
        """Return the first RIG_MODELS name whose hints match an attached port, or None."""
        try:
            for p in RigController.list_ports():
                desc = (p.get("description") or "").upper()
                for name, _model, _baud, hints in RIG_MODELS:
                    if any(h.upper() in desc for h in hints):
                        return name
        except Exception:
            pass
        return None

    def _add_grouped_models(self):
        """Populate model_combo with manufacturer group separators."""
        MFR_MAP = {
            "SignaLink": "Audio Interfaces",
            "RigBlaster": "Audio Interfaces",
            "Generic":    "Audio Interfaces",
            "Explorer":   "Handheld / No CAT",
            "Baofeng":    "Handheld / No CAT",
        }
        GRP_ORDER = [
            "ICOM", "Yaesu", "Kenwood", "Elecraft", "Xiegu",
            "Lab599", "Audio Interfaces", "Handheld / No CAT",
        ]
        groups: dict[str, list[str]] = {}
        for name, _model, _baud, _hints in RIG_MODELS:
            grp = MFR_MAP.get(name.split()[0], name.split()[0])
            groups.setdefault(grp, []).append(name)
        for grp in GRP_ORDER:
            if grp not in groups:
                continue
            self.model_combo.insertSeparator(self.model_combo.count())
            self.model_combo.addItem(f"── {grp} ──")
            self.model_combo.model().item(
                self.model_combo.count() - 1).setEnabled(False)
            for name in groups[grp]:
                self.model_combo.addItem(name)

    def _populate_rig_models(self):
        self.model_combo.clear()
        self.model_combo.addItem("— Select rig model —")
        detected = self._detect_rig_model()
        self._add_grouped_models()
        # Restore saved model or select detected
        saved = self.cfg.get("rig.model_name", "")
        if saved:
            idx = self.model_combo.findText(saved)
            if idx > 0:
                self.model_combo.setCurrentIndex(idx)
        elif detected:
            idx = self.model_combo.findText(detected)
            if idx > 0:
                self.model_combo.setCurrentIndex(idx)
                try:
                    self.model_lbl.setText(f"Detected: {detected}")
                except AttributeError:
                    pass

    def _on_model_select(self, idx: int):
        if idx <= 0:
            return
        name = self.model_combo.currentText()
        if name.startswith("──") or not name:
            return
        # Find in RIG_MODELS
        match = next(
            ((m, b) for n, m, b, _ in RIG_MODELS
             if n == name), None)
        if not match:
            return
        model, baud = match
        if baud > 0:
            self.baud_combo.setCurrentText(str(baud))
        if model:
            self.cfg.set("rig.hamlib_model", model)
        self.cfg.set("rig.model_name", name)
        self.cfg.save()

    def _on_connect(self):
        # Check selected backend
        backend = self.cfg.get("rig.backend", "hamlib")
        if backend == "flrig":
            from modes.flrig_bridge import FLRigBridge
            if not FLRigBridge.is_running():
                QMessageBox.warning(
                    self, "FLRig Not Running",
                    "Start FLRig first, then connect.\n\n"
                    "File → Paths & Executables → FLRig")
                return
            # Use FLRig bridge
            bridge = FLRigBridge(self.cfg)
            if bridge.connect():
                self.rig._proc_bridge = bridge
                self.rig.state.status = RigStatus.CONNECTED
                self.rig._notify()
            return
        # Standard hamlib/rigctld path
        self._on_connect_standard()

    def _on_connect_standard(self):
        raw  = self.port_combo.currentText().strip()
        port = ("AUTO" if not raw or raw.startswith("AUTO")
                else raw.split("  ")[0].strip())
        try:
            self.cfg.set("rig.baud",
                         int(self.baud_combo.currentText()))
        except ValueError:
            pass
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("Connecting…")
        ok = self.rig.connect(port)
        if not ok:
            self.connect_btn.setEnabled(True)
            self.connect_btn.setText("Connect")
            QMessageBox.warning(
                self, "Connection Failed",
                self.rig.state.error_msg or
                "Could not connect. Check cable, driver, and Hamlib.")


# ── Helpers ───────────────────────────────────────────────────────────────

def _grp(title: str, widget: QWidget) -> QGroupBox:
    g = QGroupBox(title)
    l = QHBoxLayout(g)
    l.setContentsMargins(4, 2, 4, 2)
    l.addWidget(widget)
    return g


def _collapse_btn(title: str) -> QPushButton:
    btn = QPushButton(f"▶  {title}")
    btn.setCheckable(True)
    btn.setChecked(False)
    btn.setStyleSheet("""
        QPushButton{background:#111;border:none;
          text-align:left;padding:2px 6px;}
        QPushButton:checked{color:#3fbe6f;}
        QPushButton:hover{}
    """)
    btn.toggled.connect(
        lambda c, b=btn, t=title: b.setText(
            f"{'▼' if c else '▶'}  {t}"))
    return btn
