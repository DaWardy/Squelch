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

"""
Squelch -- ui/tabs/rig_tab.py
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
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QComboBox, QGroupBox,
    QFrame, QSpinBox, QDoubleSpinBox, QProgressBar,
    QMessageBox, QCheckBox, QButtonGroup,
    QSizePolicy, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont, QWheelEvent

from ui.widgets.freq_display import FreqDisplay
from ui.widgets.spectrum_widget import SpectrumWidget
from core.rig import RigController, RigStatus, SMETER_LABELS
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


class RigTab(QWidget):
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

        self._build()
        self._wire()
        self._populate_ports()
        self._populate_rig_models()

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build(self):
        # Wrap everything in a scroll area so nothing gets clipped
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")

        inner = QWidget()
        root  = QVBoxLayout(inner)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0,0,0,0)
        outer.addWidget(scroll)

        # ── VFO + Status ──────────────────────────────────────────────────
        row1 = QHBoxLayout()

        vfo_grp = QGroupBox("VFO A")
        vfl = QVBoxLayout(vfo_grp)
        vfl.setSpacing(4)

        self.freq_display = FreqDisplay()
        # Enable mousewheel stepping
        self.freq_display.wheelEvent = self._wheel_on_vfo
        vfl.addWidget(self.freq_display)

        # Band/segment info
        self._band_info = QLabel("20m  |  Digital  |  General+")
        self._band_info.setStyleSheet("color:#555; font-size:10px;")
        vfl.addWidget(self._band_info)

        # Step size buttons
        step_lbl = QLabel("Step:")
        step_lbl.setStyleSheet("color:#555; font-size:10px;")
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
            btn.setStyleSheet("""
                QPushButton{font-size:9px;border:1px solid #222;
                  border-radius:3px;background:#111;color:#666;padding:0 4px;}
                QPushButton:checked{background:#1a3a1a;color:#3fbe6f;
                  border-color:#3fbe6f;}
                QPushButton:hover{background:#1e2e1e;color:#aaa;}
            """)
            btn.clicked.connect(
                lambda _, idx=i, s=hz: self._set_step(idx, s))
            self._step_btns.append(btn)
            self._step_grp.addButton(btn)
            step_row.addWidget(btn)
        step_row.addStretch()
        vfl.addLayout(step_row)

        # Arrow controls + band jump
        arrow_row = QHBoxLayout()
        arrow_row.setSpacing(4)

        def _abtn(label, tip, cb):
            b = QPushButton(label)
            b.setFixedSize(34, 28)
            b.setToolTip(tip)
            b.setStyleSheet("""
                QPushButton{font-size:13px;border:1px solid #2a2a2a;
                  border-radius:4px;background:#141414;color:#888;}
                QPushButton:hover{background:#1e3a1e;color:#3fbe6f;}
                QPushButton:pressed{background:#0a1a0a;}
            """)
            b.clicked.connect(cb)
            return b

        arrow_row.addWidget(_abtn("⏮", "Jump to band start",
                                  self._jump_band_start))
        arrow_row.addWidget(_abtn("◄", "Step down",
                                  self._step_down))
        arrow_row.addWidget(_abtn("▼", "Fine tune down (1 Hz)",
                                  lambda: self._nudge(-1)))
        arrow_row.addWidget(_abtn("▲", "Fine tune up (1 Hz)",
                                  lambda: self._nudge(1)))
        arrow_row.addWidget(_abtn("►", "Step up",
                                  self._step_up))
        arrow_row.addWidget(_abtn("⏭", "Jump to band end",
                                  self._jump_band_end))

        arrow_row.addSpacing(12)
        arrow_row.addWidget(QLabel("Band:"))

        self._band_jump_combo = QComboBox()
        self._band_jump_combo.setFixedWidth(70)
        self._band_jump_combo.setStyleSheet(
            "font-size:10px;background:#1a1a1a;color:#aaa;border:1px solid #333;")
        self._populate_band_combo()
        arrow_row.addWidget(self._band_jump_combo)

        go_btn = QPushButton("Go")
        go_btn.setFixedSize(36, 24)
        go_btn.setToolTip(
            "Jump to conventional frequency for this band and active mode")
        go_btn.setStyleSheet("""
            QPushButton{font-size:10px;border:1px solid #3fbe6f;
              border-radius:3px;background:#1a3a1a;color:#3fbe6f;}
            QPushButton:hover{background:#2a4a2a;}
        """)
        go_btn.clicked.connect(self._band_go)
        arrow_row.addWidget(go_btn)
        arrow_row.addStretch()
        vfl.addLayout(arrow_row)
        row1.addWidget(vfo_grp, 3)

        # Status panel
        stat_grp = QGroupBox("Status")
        stl = QVBoxLayout(stat_grp)
        stl.setSpacing(4)
        self.status_lbl = QLabel("● Disconnected")
        self.status_lbl.setStyleSheet(
            "color:#888; font-size:13px; font-weight:bold;")
        self.port_lbl = QLabel("Port: —")
        self.port_lbl.setStyleSheet("color:#666; font-size:10px;")
        self.model_lbl = QLabel("")
        self.model_lbl.setStyleSheet("color:#555; font-size:10px;")

        sm_lbl = QLabel("S-Meter")
        sm_lbl.setStyleSheet("color:#555; font-size:10px;")
        self.smeter_bar = QProgressBar()
        self.smeter_bar.setRange(0, 13)
        self.smeter_bar.setValue(0)
        self.smeter_bar.setTextVisible(False)
        self.smeter_bar.setFixedHeight(10)
        self.smeter_bar.setStyleSheet(
            "QProgressBar{border:1px solid #222;border-radius:2px;background:#0a0a0a;}"
            "QProgressBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #3fbe6f,stop:0.6 #aacc22,stop:0.85 #ee8822,stop:1 #ee2222);}")
        self.smeter_val = QLabel("S0")
        self.smeter_val.setStyleSheet("color:#777; font-size:10px;")
        sm_row = QHBoxLayout()
        sm_row.addWidget(self.smeter_bar)
        sm_row.addWidget(self.smeter_val)

        stl.addWidget(self.status_lbl)
        stl.addWidget(self.port_lbl)
        stl.addWidget(self.model_lbl)
        stl.addWidget(sm_lbl)
        stl.addLayout(sm_row)
        stl.addStretch()
        row1.addWidget(stat_grp, 2)
        root.addLayout(row1)

        # ── Mode buttons ──────────────────────────────────────────────────
        mode_grp = QGroupBox("Mode")
        ml = QHBoxLayout(mode_grp)
        ml.setSpacing(4)
        self._mode_btns = {}
        self._mode_btn_grp = QButtonGroup(self)
        self._mode_btn_grp.setExclusive(True)
        for label, hamlib_mode, tip in MODE_BUTTONS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedSize(46, 28)
            btn.setToolTip(tip)
            btn.setStyleSheet("""
                QPushButton{font-size:11px;border:1px solid #2a2a2a;
                  border-radius:4px;background:#141414;color:#888;}
                QPushButton:checked{background:#1a3a1a;color:#3fbe6f;
                  border-color:#3fbe6f;font-weight:bold;}
                QPushButton:hover{background:#1e2e1e;color:#aaa;}
            """)
            btn.clicked.connect(
                lambda _, m=hamlib_mode: self._on_mode_btn(m))
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
        self._auto_mode_cb.setStyleSheet("color:#666; font-size:10px;")
        self._auto_mode_cb.toggled.connect(
            lambda c: setattr(self, '_auto_mode', c))
        ml.addWidget(self._auto_mode_cb)
        ml.addStretch()
        root.addWidget(mode_grp)

        # ── Controls: PTT / Power / Preamp / ATT / Filter ────────────────
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)

        self.ptt_btn = QPushButton("● TX")
        self.ptt_btn.setCheckable(True)
        self.ptt_btn.setFixedSize(64, 36)
        self.ptt_btn.setStyleSheet("""
            QPushButton{border:2px solid #883333;border-radius:5px;
              color:#cc4444;font-size:13px;font-weight:bold;background:#1a0808;}
            QPushButton:checked{background:#cc2222;color:#fff;
              border-color:#ff4444;}
            QPushButton:hover{background:#2a1010;}
        """)
        ctrl_row.addWidget(_grp("PTT", self.ptt_btn))

        self.power_spin = QSpinBox()
        self.power_spin.setRange(1, 100)
        self.power_spin.setValue(100)
        self.power_spin.setSuffix(" %")
        self.power_spin.setFixedWidth(72)
        self.power_spin.setSingleStep(5)
        self.power_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Only scroll when focused
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
        root.addLayout(ctrl_row)

        # ── Scanner (collapsible) ─────────────────────────────────────────
        self._scan_toggle = _collapse_btn("Scanner")
        self._scan_toggle.toggled.connect(
            lambda c: self._scan_body.setVisible(c))
        root.addWidget(self._scan_toggle)

        self._scan_body = QWidget()
        self._scan_body.setVisible(False)
        scan_layout = QGridLayout(self._scan_body)
        scan_layout.setContentsMargins(8, 4, 8, 4)
        scan_layout.setSpacing(6)

        scan_layout.addWidget(QLabel("Mode:"), 0, 0)
        self._scan_mode = QComboBox()
        self._scan_mode.addItems(
            ["Sweep", "Band", "Channel list", "Memory"])
        self._scan_mode.setFixedWidth(120)
        scan_layout.addWidget(self._scan_mode, 0, 1)

        scan_layout.addWidget(QLabel("From:"), 1, 0)
        self._scan_from = QLineEdit("14.000")
        self._scan_from.setFixedWidth(90)
        scan_layout.addWidget(self._scan_from, 1, 1)

        scan_layout.addWidget(QLabel("To:"), 1, 2)
        self._scan_to = QLineEdit("14.350")
        self._scan_to.setFixedWidth(90)
        scan_layout.addWidget(self._scan_to, 1, 3)

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

        scan_btn_row = QHBoxLayout()
        self._scan_start = QPushButton("▶  Start Scan")
        self._scan_start.setFixedHeight(28)
        self._scan_start.setStyleSheet(
            "background:#1a3a1a;color:#3fbe6f;border:1px solid #3fbe6f;"
            "border-radius:4px;font-size:11px;")
        self._scan_start.clicked.connect(self._start_scan)

        self._scan_stop = QPushButton("■  Stop")
        self._scan_stop.setFixedHeight(28)
        self._scan_stop.setEnabled(False)
        self._scan_stop.clicked.connect(self._stop_scan)

        self._scan_lock = QPushButton("⊘  Lock current")
        self._scan_lock.setFixedHeight(28)
        self._scan_lock.setToolTip("Add current frequency to lockout list")

        self._scan_status = QLabel("Idle")
        self._scan_status.setStyleSheet("color:#555; font-size:10px;")

        scan_btn_row.addWidget(self._scan_start)
        scan_btn_row.addWidget(self._scan_stop)
        scan_btn_row.addWidget(self._scan_lock)
        scan_btn_row.addWidget(self._scan_status)
        scan_btn_row.addStretch()
        scan_layout.addLayout(scan_btn_row, 2, 0, 1, 6)
        root.addWidget(self._scan_body)

        # ── Memory channels (collapsible) ─────────────────────────────────
        self._mem_toggle = _collapse_btn("Memory Channels")
        self._mem_toggle.toggled.connect(
            lambda c: self._mem_body.setVisible(c))
        root.addWidget(self._mem_toggle)

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
            "QTableWidget{background:#111;color:#aaa;"
            "gridline-color:#222;font-size:11px;}"
            "QHeaderView::section{background:#1a1a1a;color:#666;"
            "border:none;font-size:10px;}")
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
        for b in (mem_store, mem_recall_btn, mem_clear):
            b.setStyleSheet(
                "font-size:10px;background:#1a1a1a;border:1px solid #333;"
                "border-radius:3px;color:#aaa;")
        mem_btn_row.addWidget(mem_store)
        mem_btn_row.addWidget(mem_recall_btn)
        mem_btn_row.addWidget(mem_clear)
        mem_btn_row.addStretch()
        mem_layout.addLayout(mem_btn_row)
        root.addWidget(self._mem_body)

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
              font-weight:bold;font-size:12px;padding:5px;}
            QPushButton:hover{background:#2a4a2a;}
            QPushButton:disabled{background:#111;color:#444;border-color:#333;}
        """)
        cgl.addWidget(self.connect_btn, 1, 3)

        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setEnabled(False)
        self.disconnect_btn.setFixedWidth(90)
        cgl.addWidget(self.disconnect_btn, 0, 4)

        root.addWidget(conn_grp)

        # ── Spectrum / Waterfall (collapsible) ────────────────────────────
        self._spec_toggle = _collapse_btn("Spectrum / Waterfall")
        self._spec_toggle.setChecked(True)
        self._spec_toggle.toggled.connect(
            lambda c: self._spectrum_widget.setVisible(c)
            if self._spectrum_widget else None)
        root.addWidget(self._spec_toggle)

        self._spectrum_widget = SpectrumWidget(config=self.cfg)
        self._spectrum_widget.freq_clicked.connect(self._on_spec_freq)
        root.addWidget(self._spectrum_widget)

        root.addStretch()

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

    def _start_scan(self):
        if not self.rig.is_connected:
            QMessageBox.warning(self, "Scanner",
                                "Connect the rig before scanning.")
            return
        try:
            lo = int(float(self._scan_from.text()) * 1_000_000)
            hi = int(float(self._scan_to.text()) * 1_000_000)
        except ValueError:
            QMessageBox.warning(self, "Scanner",
                                "Invalid frequency range.")
            return

        self._scan_lo  = lo
        self._scan_hi  = hi
        self._scan_cur = lo
        self._scan_running = True
        interval = int(self._scan_dwell.value() * 1000)
        self._scan_timer.setInterval(interval)
        self._scan_timer.start()
        self._scan_start.setEnabled(False)
        self._scan_stop.setEnabled(True)
        self._scan_status.setText("Scanning…")
        self._scan_status.setStyleSheet("color:#3fbe6f; font-size:10px;")

    def _stop_scan(self):
        self._scan_running = False
        self._scan_timer.stop()
        self._scan_start.setEnabled(True)
        self._scan_stop.setEnabled(False)
        self._scan_status.setText("Idle")
        self._scan_status.setStyleSheet("color:#555; font-size:10px;")

    def _scan_step(self):
        if not self._scan_running:
            return
        self._scan_cur += self._step_hz
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
            f"color:{col}; font-size:13px; font-weight:bold;")

        connected = self.rig.is_connected
        self.connect_btn.setEnabled(not connected)
        self.connect_btn.setText("Connect")
        self.disconnect_btn.setEnabled(connected)

        if state.port:
            self.port_lbl.setText(f"Port: {state.port}")

        if connected:
            self.freq_display.set_freq(state.freq_hz)
            self.freq_display.set_band(state.band)
            self.freq_display.set_tx(state.ptt)
            self._set_mode_ui(state.mode)
            self._refresh_band_info(state.freq_hz)
            if self._spectrum_widget:
                self._spectrum_widget.set_center_freq(state.freq_hz)
                if not self._spectrum_widget._running:
                    self._spectrum_widget.start()
        else:
            if (self._spectrum_widget and
                    self._spectrum_widget._running):
                self._spectrum_widget.stop()

        s = max(0, min(13, state.s_meter))
        self.smeter_bar.setValue(s)
        self.smeter_val.setText(
            SMETER_LABELS[s] if s < len(SMETER_LABELS) else "S9+")

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
                "color:#cc4444; font-size:10px;")
            return
        self._band_info.setStyleSheet("color:#555; font-size:10px;")

    # ── Port / model population ───────────────────────────────────────────

    def _populate_ports(self):
        self.port_combo.clear()
        self.port_combo.addItem("AUTO  —  auto-detect")
        ports = RigController.list_ports()
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

    def _populate_rig_models(self):
        self.model_combo.clear()
        self.model_combo.addItem("— Select rig model —")
        ports   = RigController.list_ports()
        detected = None
        for p in ports:
            desc = (p["description"] or "").upper()
            for name, model, baud, hints in RIG_MODELS:
                if any(h.upper() in desc for h in hints):
                    detected = name
                    break
            if detected:
                break
        for name, *_ in RIG_MODELS:
            self.model_combo.addItem(name)
        if detected:
            idx = next(
                (i+1 for i,(n,*_) in enumerate(RIG_MODELS)
                 if n == detected), 0)
            if idx:
                self.model_combo.setCurrentIndex(idx)
                self.model_lbl.setText(f"Detected: {detected}")

    def _on_model_select(self, idx: int):
        if idx <= 0:
            return
        _, model, baud, _ = RIG_MODELS[idx - 1]
        self.baud_combo.setCurrentText(str(baud))
        if model:
            self.cfg.set("rig.hamlib_model", model)

    def _on_connect(self):
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
        QPushButton{background:#111;border:none;color:#555;
          font-size:10px;text-align:left;padding:2px 6px;}
        QPushButton:checked{color:#3fbe6f;}
        QPushButton:hover{color:#aaa;}
    """)
    btn.toggled.connect(
        lambda c, b=btn, t=title: b.setText(
            f"{'▼' if c else '▶'}  {t}"))
    return btn
