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
"""
Squelch -- ui/tabs/modes_tab.py
Unified digital modes tab.
FT8/FT4/WSPR: WSJT-X style band/freq selector + full auto-sequence UI.
JS8/PSK31/RTTY/CW/SSTV: Fldigi bridge UI.
Decode list, auto-sequence state display, QSO log feed.
"""

import logging
import threading
from core.themes import get_theme as _modes_get_theme
from ui.widgets.launch_bar import LaunchBar
from core.launcher import get_launcher
from core.guest_op import operating_callsign
from core.safety import get_safety
from ui.panel import SquelchPanel
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QComboBox, QGroupBox,
    QFrame, QSplitter, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QTextEdit, QLineEdit,
    QSpinBox, QProgressBar, QButtonGroup, QSizePolicy,
    QTabWidget, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QColor, QFont, QBrush

from modes.ft8 import FT8Engine, AutoSeqState, DecodedSignal
from modes.wspr import WSPREngine
from modes.fldigi_bridge import FldigiBridge, MODE_FREQS
from core.band_plan import DIGITAL_FREQS, BAND_EDGES
from core.constants import BAND_EDGES_R2 as BAND_EDGES, FT8_FREQUENCIES

log = logging.getLogger(__name__)

# Decode list column indices
COL_CALL  = 0
COL_GRID  = 1
COL_SNR   = 2
COL_DT    = 3
COL_FREQ  = 4
COL_DIST  = 5
COL_BEAR  = 6
COL_DXCC  = 7
COL_FLAG  = 8   # NEW / DUPE / BAND etc.

DECODE_HEADERS = [
    "Callsign","Grid","SNR","DT","Freq","Dist","Bear","DXCC","Flag"
]

# State colors
STATE_COLORS = {
    AutoSeqState.IDLE:          "#555555",
    AutoSeqState.CQ_SENT:       "#3fbe6f",
    AutoSeqState.WAITING_REPLY: "#aaaa22",
    AutoSeqState.REPLY_DECODED: "#44aaff",
    AutoSeqState.REPORT_SENT:   "#3fbe6f",
    AutoSeqState.WAITING_RRR:   "#aaaa22",
    AutoSeqState.RRR_SENT:      "#3fbe6f",
    AutoSeqState.LOGGING:       "#aa44ff",
    AutoSeqState.QSO_COMPLETE:  "#3fbe6f",
    AutoSeqState.NEXT_CALLER:   "#aaaaaa",
}

# FT8/FT4/WSPR bands available
WEAK_SIGNAL_BANDS = [
    "160m","80m","60m","40m","30m","20m",
    "17m","15m","12m","10m","6m","2m"
]


class ModesTab(SquelchPanel, QWidget):
    panel_id    = "modes"
    panel_title = "Weak Signal"

    def __init__(self, rig, config, log_db=None, parent=None):
        super().__init__(parent)
        self.rig    = rig
        self.cfg    = config
        self.log_db = log_db

        # Engines
        self.ft8_engine   = FT8Engine(config, log_db)
        self.wspr_engine  = WSPREngine(config, rig, log_db)
        self.fldigi       = FldigiBridge(config, log_db)

        # Wire callbacks
        self.ft8_engine.on_decode(self._on_ft8_decode)
        self.ft8_engine.on_state_change(self._on_seq_state)
        self.ft8_engine.on_tx(self._on_ft8_tx)
        self.ft8_engine.on_qso_complete(self._on_qso_done)
        self.ft8_engine.on_wsjtx_status(self._on_wsjtx_status)
        self.wspr_engine.on_spot(self._on_wspr_spot)
        self.wspr_engine.on_status(self._on_wspr_status)
        self.fldigi.on_rx(self._on_fldigi_rx)

        self._current_mode  = "FT8"
        self._active_band   = "20m"
        self._sdr_tune_cb   = None   # set via set_sdr_tune_cb() from MainWindow
        self._cycle_timer   = QTimer(self)
        self._cycle_timer.setInterval(100)
        self._cycle_timer.timeout.connect(self._update_cycle)
        self._freq_history: list[int] = []

        self._build()
        self._build_dx_panel()
        self._wire()
        self._start_dx_cluster()

    # ── Build UI ──────────────────────────────────────────────────────────


    def save_state(self) -> dict:
        try:
            sizes = (self._main_splitter.sizes()
                     if hasattr(self, "_main_splitter") else [])
            return {
                "mode_tab":      self._mode_tabs.currentIndex(),
                "filter":        getattr(self, "_callsign_filter", ""),
                "splitter_sizes": sizes,
                "dx_watch":      getattr(self._dx_watch_edit, "text",
                                         lambda: "")(),
            }
        except Exception:
            return {}

    def restore_state(self, state: dict) -> None:
        try:
            if "mode_tab" in state:
                self._mode_tabs.setCurrentIndex(state["mode_tab"])
            if "dx_watch" in state and hasattr(self, "_dx_watch_edit"):
                self._dx_watch_edit.setText(state["dx_watch"])
            if "splitter_sizes" in state and hasattr(self, "_main_splitter"):
                sizes = state["splitter_sizes"]
                if isinstance(sizes, list) and len(sizes) == 2:
                    self._main_splitter.setSizes(sizes)
        except Exception:
            pass

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # Launch bar
        root.addWidget(LaunchBar("modes", self.cfg,
                                  rescan_callback=self._rescan_software))

        self._build_mode_tabs_bar(root)
        self._build_splitter_shell(root)

    def _build_mode_tabs_bar(self, root):
        # ── Mode selector tabs ────────────────────────────────────────────
        self._mode_tabs = QTabWidget()
        self._mode_tabs.setFixedHeight(42)
        self._mode_tabs.tabBar().setDocumentMode(True)
        self._mode_tabs.setStyleSheet("""
            QTabBar::tab{padding:6px 16px;
              background:#141414;border:none;
              border-bottom:2px solid transparent;}
            QTabBar::tab:selected{color:#3fbe6f;
              border-bottom:2px solid #3fbe6f;}
            QTabBar::tab:hover{}
            QTabWidget::pane{border:none;}
        """)
        for m in ["FT8","FT4","WSPR","JS8","PSK31","RTTY","CW","SSTV"]:
            self._mode_tabs.addTab(QWidget(), m)
        self._mode_tabs.currentChanged.connect(self._on_mode_tab)
        root.addWidget(self._mode_tabs)
        
        _t = _modes_get_theme(self.cfg.get("ui.theme", "Dark"))
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color:{_t.border};")
        root.addWidget(div)
        


    def _build_splitter_shell(self, root):
        # ── Main splitter: controls | decode list ────────────────────────
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.setStyleSheet(
            "QSplitter::handle{background:#1a1a1a;width:2px;}")
        
        # Left panel — wrap in scroll area so it never clips
        self._left_outer = QWidget()
        left_outer = self._left_outer
        left_outer.setMinimumWidth(260)
        left_outer.setMaximumWidth(400)
        left_outer_layout = QVBoxLayout(left_outer)
        left_outer_layout.setContentsMargins(0, 0, 0, 0)
        left_outer_layout.setSpacing(0)
        
        from PyQt6.QtWidgets import QScrollArea
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        left = QWidget()
        self._left_layout = QVBoxLayout(left)
        self._left_layout.setContentsMargins(6, 6, 6, 6)
        self._left_layout.setSpacing(6)
        left_scroll.setWidget(left)
        left_outer_layout.addWidget(left_scroll)

        # Populate left panel with section sub-methods
        self._build_band_freq_panel(self._left_layout)
        self._build_cycle_panel(self._left_layout)
        self._build_tx_settings(self._left_layout)
        self._build_session_stats(self._left_layout)
        self._left_layout.addStretch()
        self._fldigi_built = False
        root.addWidget(self._main_splitter)

    def _build_band_freq_panel(self, root):
        # ── Band + frequency selector (WSJT-X style) ──────────────────
        band_grp = QGroupBox("Band / Frequency")
        band_gl  = QGridLayout(band_grp)
        band_gl.setSpacing(4)
        
        band_gl.addWidget(QLabel("Band:"), 0, 0)
        self._band_combo = QComboBox()
        self._band_combo.addItems(WEAK_SIGNAL_BANDS)
        self._band_combo.setCurrentText("20m")
        self._band_combo.currentTextChanged.connect(self._on_band_change)
        band_gl.addWidget(self._band_combo, 0, 1)
        
        band_gl.addWidget(QLabel("Frequency:"), 1, 0)
        self._freq_label = QLabel("14.074.000 MHz")
        self._freq_label.setStyleSheet(
            "color:#3fbe6f; font-family:'Courier New'; ")
        band_gl.addWidget(self._freq_label, 1, 1)
        
        self._tune_btn = QPushButton("Tune Rig")
        self._tune_btn.setToolTip(
            "Set the rig to the calling frequency for this band/mode\n"
            "and key a steady carrier so you can tune your ATU.\n"
            "Transmits — make sure your antenna is connected.")
        self._tune_btn.setFixedHeight(26)
        self._tune_btn.clicked.connect(self._tune_rig)
        band_gl.addWidget(self._tune_btn, 2, 0, 1, 2)
        band_grp.setMinimumHeight(80)
        self._left_layout.addWidget(band_grp)
        
        # ── Cycle timer ───────────────────────────────────────────────
        cycle_grp = QGroupBox("Cycle")
        cycle_l   = QVBoxLayout(cycle_grp)
        self._cycle_bar = QProgressBar()
        self._cycle_bar.setRange(0, 100)
        self._cycle_bar.setValue(0)
        self._cycle_bar.setTextVisible(False)
        self._cycle_bar.setFixedHeight(8)
        self._cycle_bar.setStyleSheet(
            "QProgressBar{background:#111;border:1px solid #222;border-radius:2px;}"
            "QProgressBar::chunk{background:#3fbe6f;}")
        self._cycle_label = QLabel("RX  00:00")
        self._cycle_label.setStyleSheet(
            "color:#3fbe6f; font-family:'Courier New'; ")
        self._cycle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._wsjtx_lbl = QLabel("⚠ WSJT-X not connected — waiting for UDP…")
        self._wsjtx_lbl.setStyleSheet(
            "color:#ffaa44;font-size:10px;font-family:'Courier New';")
        self._wsjtx_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._wsjtx_lbl.setToolTip(
            "WSJT-X must be running and set to multicast UDP on port 2237.\n"
            "Launch WSJT-X, then go to File → Settings → Reporting and\n"
            "enable UDP server on 127.0.0.1:2237.")
        cycle_l.addWidget(self._cycle_bar)
        cycle_l.addWidget(self._cycle_label)
        cycle_l.addWidget(self._wsjtx_lbl)
        cycle_grp.setMinimumHeight(80)
        self._left_layout.addWidget(cycle_grp)
        


    def _build_cycle_panel(self, root):
        # ── Auto-sequence state ───────────────────────────────────────
        state_grp = QGroupBox("Auto-Sequence")
        state_l   = QVBoxLayout(state_grp)
        
        self._state_label = QLabel("● Idle — monitoring")
        
        # C-11 (Tyler): big, unmistakable ON-AIR indicator. FT8 auto-transmits,
        # so the operator must always be able to tell at a glance whether the
        # rig is actually keyed.
        self._onair_label = QLabel("RECEIVING")
        self._onair_label.setObjectName("onair")
        from PyQt6.QtCore import Qt as _Qt
        self._onair_label.setAlignment(_Qt.AlignmentFlag.AlignCenter)
        self._onair_label.setStyleSheet(
            "background:#0d2a14;color:#3fbe6f;font-weight:bold;"
            "border:1px solid #1f5a33;border-radius:4px;padding:5px;")
        self._state_label.setStyleSheet(
            "  font-weight:bold;")
        state_l.addWidget(self._onair_label)
        state_l.addWidget(self._state_label)
        
        self._qso_label = QLabel("No QSO in progress")
        self._qso_label.setStyleSheet(
            " ")
        state_l.addWidget(self._qso_label)
        
        self._tx_msg_label = QLabel("")
        self._tx_msg_label.setStyleSheet(
            "color:#3fbe6f; font-family:'Courier New'; ")
        self._tx_msg_label.setWordWrap(True)
        state_l.addWidget(self._tx_msg_label)
        
        # Control buttons
        btn_row1 = QHBoxLayout()
        self._cq_btn = QPushButton("CQ")
        self._cq_btn.setToolTip(
            "Start calling CQ — broadcasts your callsign and grid\n"
            "to invite contacts. Transmits on the next TX period.")
        self._cq_btn.setFixedHeight(30)
        self._cq_btn.setStyleSheet(
            "background:#1a3a1a;color:#3fbe6f;border:1px solid #3fbe6f;"
            "border-radius:4px;font-weight:bold;")
        self._cq_btn.clicked.connect(self._send_cq)
        
        self._halt_btn = QPushButton("Halt TX")
        self._halt_btn.setToolTip(
            "Immediately stop transmitting.\n"
            "Use this to abort a TX cycle at any time.")
        self._halt_btn.setFixedHeight(30)
        self._halt_btn.setStyleSheet(
            "background:#3a1a1a;color:#cc4444;border:1px solid #cc4444;"
            "border-radius:4px;")
        self._halt_btn.clicked.connect(self._halt_tx)
        btn_row1.addWidget(self._cq_btn)
        btn_row1.addWidget(self._halt_btn)
        state_l.addLayout(btn_row1)
        
        self._left_layout.addWidget(state_grp)
        


    def _build_tx_freq_controls(self, tx_gl) -> None:
        tx_gl.addWidget(QLabel("Power:"), 0, 0)
        self._power_spin = QSpinBox()
        self._power_spin.setRange(1, 100)
        self._power_spin.setValue(self.cfg.get("ft8.tx_power_dbm", 37))
        self._power_spin.setSuffix(" dBm")
        self._power_spin.setFixedWidth(80)
        tx_gl.addWidget(self._power_spin, 0, 1)
        tx_gl.addWidget(QLabel("TX Freq:"), 1, 0)
        self._tx_freq_spin = QSpinBox()
        self._tx_freq_spin.setRange(200, 3000)
        self._tx_freq_spin.setValue(1500)
        self._tx_freq_spin.setSuffix(" Hz")
        self._tx_freq_spin.setFixedWidth(80)
        tx_gl.addWidget(self._tx_freq_spin, 1, 1)

    def _build_tx_checkboxes(self, tx_gl) -> None:
        self._even_cb = QCheckBox("TX even periods")
        self._even_cb.setToolTip(
            "Transmit on even 15-second periods (00, 30s).\n"
            "Leave unchecked to use odd periods.\n"
            "Pick the opposite of the station you're working.")
        self._even_cb.setChecked(True)
        tx_gl.addWidget(self._even_cb, 2, 0, 1, 2)
        self._auto_seq_cb = QCheckBox("Auto-sequence")
        self._auto_seq_cb.setToolTip(
            "Let the software automatically step through the QSO\n"
            "exchange (signal report, R+report, 73).\n"
            "Recommended for beginners.")
        self._auto_seq_cb.setChecked(True)
        self._auto_seq_cb.toggled.connect(self.ft8_engine.set_auto_sequence)
        tx_gl.addWidget(self._auto_seq_cb, 3, 0, 1, 2)
        self._auto_cq_cb = QCheckBox("Auto CQ")
        self._auto_cq_cb.setToolTip(
            "Automatically repeat CQ calls until someone answers.\n"
            "Watch the band — don't leave it unattended while transmitting.")
        self._auto_cq_cb.setChecked(False)
        self._auto_cq_cb.toggled.connect(self.ft8_engine.set_auto_cq)
        tx_gl.addWidget(self._auto_cq_cb, 4, 0, 1, 2)
        self._hold_tx_cb = QCheckBox("Hold TX frequency")
        self._hold_tx_cb.setToolTip(
            "Keep your transmit frequency fixed instead of following\n"
            "the station you're answering.\n"
            "Helps avoid being covered by callers.")
        self._hold_tx_cb.setChecked(False)
        self._hold_tx_cb.toggled.connect(self.ft8_engine.set_hold_tx_freq)
        tx_gl.addWidget(self._hold_tx_cb, 5, 0, 1, 2)
        self._dx_only_cb = QCheckBox("DX only (skip domestic)")
        self._dx_only_cb.setToolTip(
            "Only respond to stations outside your own country.\n"
            "Useful for chasing DX.")
        self._dx_only_cb.setChecked(False)
        self._dx_only_cb.toggled.connect(self.ft8_engine.set_dx_only)
        tx_gl.addWidget(self._dx_only_cb, 6, 0, 1, 2)

    def _build_tx_settings(self, root):
        # ── TX settings ───────────────────────────────────────────────
        tx_grp = QGroupBox("TX Settings")
        tx_gl  = QGridLayout(tx_grp)
        tx_gl.setSpacing(4)
        self._build_tx_freq_controls(tx_gl)
        self._build_tx_checkboxes(tx_gl)
        tx_grp.setMinimumHeight(80)
        self._left_layout.addWidget(tx_grp)
        


    def _build_session_stats(self, root):
        # ── Session stats ─────────────────────────────────────────────
        stats_grp = QGroupBox("Session")
        stats_l   = QGridLayout(stats_grp)
        stats_l.setSpacing(3)
        
        def _stat(label, attr):
            lbl = QLabel(label)
            lbl.setStyleSheet(" ")
            val = QLabel("0")
            val.setStyleSheet(
                "color:#3fbe6f;  "
                "font-family:'Courier New';")
            setattr(self, attr, val)
            return lbl, val
        
        for row, (label, attr) in enumerate([
            ("QSOs this session:", "_stat_qsos"),
            ("DXCC worked:",       "_stat_dxcc"),
            ("New grids:",         "_stat_grids"),
            ("Decodes:",           "_stat_decodes"),
        ]):
            lbl, val = _stat(label, attr)
            stats_l.addWidget(lbl, row, 0)
            stats_l.addWidget(val, row, 1)
        
        self._left_layout.addWidget(stats_grp)
        self._left_layout.addStretch()
        



    def showEvent(self, event):
        super().showEvent(event)
        if not self._fldigi_built:
            self._fldigi_built = True
            self._build_fldigi_section()

    def _build_fldigi_section(self):
        self._fldigi_panel = self._build_fldigi_panel()
        self._left_layout.addWidget(self._fldigi_panel)
        self._fldigi_panel.hide()
        self._main_splitter.addWidget(self._left_outer)
        self._main_splitter.addWidget(self._build_decode_right_panel())
        self._main_splitter.setSizes([300, 700])
        # Start cycle timer

    def _build_decode_signals_section(self, rl: "QVBoxLayout") -> None:
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("Decoded Signals"))
        hdr.addStretch()
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Filter callsign…")
        self._filter_edit.setFixedWidth(130)
        self._filter_edit.textChanged.connect(self._filter_decodes)
        hdr.addWidget(self._filter_edit)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedHeight(24)
        self._clear_btn.clicked.connect(self._clear_decodes)
        hdr.addWidget(self._clear_btn)
        export_btn = QPushButton("⬇ Export")
        export_btn.setFixedHeight(24)
        export_btn.setToolTip(
            "Export all decoded signals to CSV or ADIF.\n"
            "ADIF can be imported into most log programs.")
        export_btn.clicked.connect(self._export_decodes)
        hdr.addWidget(export_btn)
        rl.addLayout(hdr)
        self._decode_table = QTableWidget(0, len(DECODE_HEADERS))
        self._decode_table.setHorizontalHeaderLabels(DECODE_HEADERS)
        self._decode_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive)
        self._decode_table.horizontalHeader().setSectionResizeMode(
            COL_DXCC, QHeaderView.ResizeMode.Stretch)
        self._decode_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self._decode_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._decode_table.setAlternatingRowColors(True)
        try:
            self._decode_table.setSortingEnabled(True)
        except Exception:
            pass
        self._decode_table.verticalHeader().setVisible(False)
        self._decode_table.setStyleSheet(
            "QTableWidget{background:#0d0d0d;gridline-color:#1a1a1a;"
            "font-family:'Courier New';alternate-background-color:#111111;"
            "selection-background-color:#1a3a1a;}"
            "QHeaderView::section{background:#141414;border:none;padding:3px;}")
        self._decode_table.doubleClicked.connect(self._on_decode_dblclick)
        rl.addWidget(self._decode_table, 3)

    def _build_activity_log_section(self, rl: "QVBoxLayout") -> None:
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("Activity / TX Log"))
        hdr.addStretch()
        clr = QPushButton("Clear")
        clr.setFixedHeight(22)
        clr.clicked.connect(lambda: self._activity_log.clear())
        hdr.addWidget(clr)
        rl.addLayout(hdr)
        self._activity_log = QTextEdit()
        self._activity_log.setReadOnly(True)
        self._activity_log.setMaximumHeight(120)
        self._activity_log.setStyleSheet(
            "background:#080808;color:#3fbe6f;"
            "font-family:'Courier New';border:1px solid #1a1a1a;")
        rl.addWidget(self._activity_log)

    def _build_decode_right_panel(self) -> "QWidget":
        """Right half of the modes splitter: decode table + activity log."""
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 8, 8, 8)
        rl.setSpacing(4)
        self._build_decode_signals_section(rl)
        self._build_activity_log_section(rl)
        return right


    def _build_fldigi_panel(self) -> QWidget:
        """Control panel shown when PSK31/RTTY/CW/SSTV is active."""
        panel = QGroupBox("Fldigi")
        layout = QVBoxLayout(panel)

        status_row = QHBoxLayout()
        self._fldigi_status = QLabel("● Not connected")
        self._fldigi_status.setStyleSheet(
            "  font-weight:bold;")
        self._fldigi_connect_btn = QPushButton("Launch Fldigi")
        self._fldigi_connect_btn.setFixedHeight(26)
        self._fldigi_connect_btn.clicked.connect(self._connect_fldigi)
        status_row.addWidget(self._fldigi_status)
        status_row.addWidget(self._fldigi_connect_btn)
        layout.addLayout(status_row)

        self._fldigi_tx_edit = QLineEdit()
        self._fldigi_tx_edit.setPlaceholderText(
            "Type message to transmit…")
        layout.addWidget(self._fldigi_tx_edit)

        btn_row = QHBoxLayout()
        self._fldigi_tx_btn = QPushButton("TX")
        self._fldigi_tx_btn.setFixedHeight(26)
        self._fldigi_tx_btn.clicked.connect(self._fldigi_tx)
        self._fldigi_rx_btn = QPushButton("RX")
        self._fldigi_rx_btn.setFixedHeight(26)
        self._fldigi_rx_btn.clicked.connect(self.fldigi.receive)
        btn_row.addWidget(self._fldigi_tx_btn)
        btn_row.addWidget(self._fldigi_rx_btn)
        layout.addLayout(btn_row)

        # SSTV image viewer — shown only in SSTV mode
        layout.addWidget(self._build_sstv_image_panel())
        return panel

    def _build_sstv_image_panel(self) -> QWidget:
        """SSTV received-image viewer — watches fldigi's image output folder."""
        from PyQt6.QtWidgets import QScrollArea, QFileDialog
        from PyQt6.QtGui import QPixmap
        from pathlib import Path
        import sys, os

        self._sstv_panel = QGroupBox("SSTV Image")
        self._sstv_panel.setVisible(False)
        sv = QVBoxLayout(self._sstv_panel)
        sv.setContentsMargins(4, 4, 4, 4)
        sv.setSpacing(4)

        self._sstv_image_lbl = QLabel("No image received yet")
        self._sstv_image_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sstv_image_lbl.setMinimumHeight(120)
        self._sstv_image_lbl.setStyleSheet(
            "background:#0a0a0a;border:1px solid #222;")
        sv.addWidget(self._sstv_image_lbl)

        btn_row = QHBoxLayout()
        open_btn = QPushButton("Open folder")
        open_btn.setFixedHeight(22)
        open_btn.setToolTip("Open fldigi's SSTV image folder in Explorer/Finder")
        open_btn.clicked.connect(self._sstv_open_folder)
        save_btn = QPushButton("Save copy…")
        save_btn.setFixedHeight(22)
        save_btn.clicked.connect(self._sstv_save)
        btn_row.addWidget(open_btn)
        btn_row.addWidget(save_btn)
        btn_row.addStretch()
        self._sstv_folder_lbl = QLabel("")
        self._sstv_folder_lbl.setStyleSheet("color:#555;font-size:9px;")
        sv.addLayout(btn_row)
        sv.addWidget(self._sstv_folder_lbl)

        # QFileSystemWatcher monitors fldigi SSTV image folder
        from PyQt6.QtCore import QFileSystemWatcher
        self._sstv_watcher = QFileSystemWatcher()
        self._sstv_watcher.directoryChanged.connect(self._sstv_refresh)
        self._sstv_image_path: "str | None" = None

        # Arm the watcher for the default fldigi image path
        if sys.platform == "win32":
            default = str(Path(os.environ.get("APPDATA", "~")) / "fldigi" / "images")
        else:
            default = str(Path.home() / ".fldigi" / "images")
        if Path(default).is_dir():
            self._sstv_watcher.addPath(default)
            self._sstv_folder_lbl.setText(default)
            self._sstv_refresh(default)

        return self._sstv_panel

    def _sstv_refresh(self, folder: str) -> None:
        """Scan folder for latest image and display it."""
        from pathlib import Path
        from PyQt6.QtGui import QPixmap
        p = Path(folder)
        images = sorted(
            [f for f in p.glob("*") if f.suffix.lower() in (".bmp", ".png", ".jpg")],
            key=lambda f: f.stat().st_mtime)
        if not images:
            return
        latest = str(images[-1])
        if latest == self._sstv_image_path:
            return
        self._sstv_image_path = latest
        px = QPixmap(latest)
        if not px.isNull():
            self._sstv_image_lbl.setPixmap(
                px.scaled(self._sstv_image_lbl.width() or 240,
                          200, Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation))

    def _sstv_open_folder(self) -> None:
        import sys, subprocess, os
        from pathlib import Path
        if sys.platform == "win32":
            d = str(Path(os.environ.get("APPDATA", "~")) / "fldigi" / "images")
        else:
            d = str(Path.home() / ".fldigi" / "images")
        try:
            if sys.platform == "win32":
                os.startfile(d)        # noqa: only on Windows
            elif sys.platform == "darwin":
                subprocess.Popen(["open", d])
            else:
                subprocess.Popen(["xdg-open", d])
        except Exception:
            pass

    def _sstv_save(self) -> None:
        from PyQt6.QtWidgets import QFileDialog
        if not self._sstv_image_path:
            return
        dst, _ = QFileDialog.getSaveFileName(
            self, "Save SSTV Image", "sstv_received.png",
            "Images (*.png *.bmp *.jpg)")
        if dst:
            import shutil
            shutil.copy2(self._sstv_image_path, dst)

    # ── Wire signals ──────────────────────────────────────────────────────

    def _build_dx_panel(self):
        """Live DX spots panel at bottom of Modes tab."""
        dx_grp = QGroupBox("DX Spots (cluster)")
        dx_grp.setMaximumHeight(160)
        dl = QVBoxLayout(dx_grp)
        dl.setContentsMargins(4, 4, 4, 4)
        dl.setSpacing(3)
        dl.addLayout(self._build_dx_controls_row())
        dl.addWidget(self._build_dx_table())
        self.layout().addWidget(dx_grp)
        self._dx_cluster = None
        self._dx_spots   = []
        self._build_sota_pota_panel()

    def _build_dx_controls_row(self) -> "QHBoxLayout":
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Band:"))
        self._dx_band = QComboBox()
        self._dx_band.addItems([
            "Current", "160m", "80m", "40m", "30m", "20m",
            "17m", "15m", "12m", "10m", "6m", "All"])
        self._dx_band.setFixedWidth(80)
        self._dx_band.currentTextChanged.connect(self._filter_dx_spots)
        ctrl.addWidget(self._dx_band)
        ctrl.addWidget(QLabel("Mode:"))
        self._dx_mode_filter = QComboBox()
        self._dx_mode_filter.addItems(["All", "FT8", "CW", "SSB", "FT4"])
        self._dx_mode_filter.setFixedWidth(60)
        self._dx_mode_filter.currentTextChanged.connect(self._filter_dx_spots)
        ctrl.addWidget(self._dx_mode_filter)
        ctrl.addWidget(QLabel("Alert:"))
        self._dx_watch_edit = QLineEdit()
        self._dx_watch_edit.setPlaceholderText("callsign/prefix, e.g. JA,P5,VK")
        self._dx_watch_edit.setFixedWidth(130)
        self._dx_watch_edit.setToolTip(
            "Comma-separated callsigns or prefixes to watch.\n"
            "When a matching spot arrives, a beep sounds and\n"
            "the spot is highlighted in the DX table.")
        ctrl.addWidget(self._dx_watch_edit)
        ctrl.addStretch()
        self._dx_status = QLabel("DX Cluster: not connected")
        self._dx_status.setStyleSheet("")
        ctrl.addWidget(self._dx_status)
        conn_btn = QPushButton("Connect")
        conn_btn.setFixedHeight(22)
        conn_btn.setFixedWidth(70)
        conn_btn.clicked.connect(self._toggle_dx_cluster)
        self._dx_conn_btn = conn_btn
        ctrl.addWidget(conn_btn)
        return ctrl

    def _build_dx_table(self) -> "QTableWidget":
        self._dx_table = QTableWidget(0, 5)
        self._dx_table.setHorizontalHeaderLabels(
            ["DX", "Freq", "Spotter", "Comment", "Time"])
        h = self._dx_table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._dx_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._dx_table.setFixedHeight(90)
        self._dx_table.setStyleSheet(
            "QTableWidget{background:#0a0a0a;font-family:'Courier New';"
            "border:1px solid #1a1a1a;}"
            "QHeaderView::section{background:#141414;border:none;}")
        self._dx_table.doubleClicked.connect(self._tune_to_dx_spot)
        return self._dx_table

    def _build_sota_pota_controls(self) -> "QHBoxLayout":
        ctrl = QHBoxLayout()
        self._sp_mode = QComboBox()
        self._sp_mode.addItems(["SOTA", "POTA", "Both"])
        self._sp_mode.setFixedWidth(80)
        self._sp_mode.currentTextChanged.connect(self._filter_sota_pota)
        ctrl.addWidget(QLabel("Show:"))
        ctrl.addWidget(self._sp_mode)
        self._sp_status = QLabel("Not started")
        ctrl.addStretch()
        ctrl.addWidget(self._sp_status)
        sp_start = QPushButton("▶ Start")
        sp_start.setFixedHeight(22)
        sp_start.setFixedWidth(60)
        sp_start.setToolTip(
            "Fetch SOTA/POTA activator spots\nUpdates every 5 minutes")
        sp_start.clicked.connect(self._start_sota_pota)
        ctrl.addWidget(sp_start)
        return ctrl

    def _build_sota_pota_table(self) -> "QTableWidget":
        t = QTableWidget(0, 5)
        t.setHorizontalHeaderLabels(
            ["Callsign", "Freq", "Mode", "Reference", "Name"])
        h = t.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setFixedHeight(88)
        t.setStyleSheet(
            "QTableWidget{background:#0a0a0a;border:1px solid #1a1a1a;}"
            "QHeaderView::section{background:#141414;border:none;}")
        t.doubleClicked.connect(self._tune_to_sota_pota)
        return t

    def _build_sota_pota_panel(self):
        """SOTA and POTA activator spots panel."""
        sp_grp = QGroupBox("SOTA / POTA Spots")
        sp_grp.setMaximumHeight(150)
        sl = QVBoxLayout(sp_grp)
        sl.setContentsMargins(4, 4, 4, 4)
        sl.setSpacing(3)
        sl.addLayout(self._build_sota_pota_controls())
        self._sp_table = self._build_sota_pota_table()
        sl.addWidget(self._sp_table)
        self.layout().addWidget(sp_grp)
        self._sota_spots = []
        self._pota_spots = []
        self._sota_client = None
        self._pota_client = None

    def _start_sota_pota(self):
        """Start fetching SOTA/POTA spots."""
        from network.sota_pota import SOTAClient, POTAClient
        from PyQt6.QtCore import QTimer

        if self._sota_client is None:
            self._sota_client = SOTAClient()
            self._sota_client.on_spots(
                lambda s: QTimer.singleShot(0,
                    lambda spots=s:
                        self._on_sota_spots(spots)))
            self._sota_client.start()

        if self._pota_client is None:
            self._pota_client = POTAClient()
            self._pota_client.on_spots(
                lambda s: QTimer.singleShot(0,
                    lambda spots=s:
                        self._on_pota_spots(spots)))
            self._pota_client.start()

        self._sp_status.setText(
            "Fetching…")
        self._sp_status.setStyleSheet(
            "")

    def _on_sota_spots(self, spots):
        self._sota_spots = spots
        self._filter_sota_pota()
        self._sp_status.setText(
            f"SOTA: {len(spots)}")
        self._sp_status.setStyleSheet(
            "color:#3fbe6f;")

    def _on_pota_spots(self, spots):
        self._pota_spots = spots
        self._filter_sota_pota()

    def _collect_sota_pota_spots(self, mode: str) -> list:
        """Return merged spot tuples for the selected mode ('SOTA'/'POTA'/'Both')."""
        spots = []
        if mode in ("SOTA", "Both"):
            for s in self._sota_spots:
                spots.append((s.callsign, f"{s.freq_mhz:.4f}",
                               s.mode, s.summit, s.summit_name, s.freq_mhz, "sota"))
        if mode in ("POTA", "Both"):
            for s in self._pota_spots:
                spots.append((s.callsign, f"{s.freq_mhz:.4f}",
                               s.mode, s.park, s.park_name, s.freq_mhz, "pota"))
        return spots

    def _filter_sota_pota(self, _=None):
        from PyQt6.QtWidgets import QTableWidgetItem
        from PyQt6.QtCore import Qt
        all_spots = self._collect_sota_pota_spots(self._sp_mode.currentText())
        self._sp_table.setRowCount(0)
        for spot_data in all_spots[:15]:
            row = self._sp_table.rowCount()
            self._sp_table.insertRow(row)
            for col, val in enumerate(spot_data[:5]):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._sp_table.setItem(row, col, item)

    def _tune_to_sota_pota(self, index):
        """Tune rig to SOTA/POTA spot frequency with mode inference + SDR sync."""
        row = index.row()
        freq_item = self._sp_table.item(row, 1)
        call_item = self._sp_table.item(row, 0)
        if not freq_item:
            return
        try:
            freq_hz = int(float(freq_item.text()) * 1_000_000)
            callsign = call_item.text() if call_item else ""
            # SOTA/POTA is usually SSB; mode col is index 2 if present
            mode_item = self._sp_table.item(row, 2)
            mode_str = mode_item.text() if mode_item else ""
            self._sp_table.selectRow(row)
            self._do_spot_tune(freq_hz, callsign, mode_str)
        except Exception:
            pass

    def _start_dx_cluster(self):
        """Auto-connect to DX cluster if configured."""
        if self.cfg.get("dx_cluster.auto_connect", False):
            QTimer.singleShot(2000, self._toggle_dx_cluster)

    def _toggle_dx_cluster(self):
        from network.dx_cluster import DXClusterClient
        if self._dx_cluster:
            self._dx_cluster.stop()
            self._dx_cluster = None
            self._dx_status.setText(
                "DX Cluster: disconnected")
            self._dx_conn_btn.setText("Connect")
            return

        self._dx_cluster = DXClusterClient(self.cfg)
        self._dx_cluster.on_spot(self._on_dx_spot)
        self._dx_status.setText("Connecting…")
        self._dx_cluster.start()
        # Check if connected after start
        QTimer.singleShot(1000, self._check_dx_connected)

    def _check_dx_connected(self):
        if self._dx_cluster:
            if getattr(self._dx_cluster, "_running", False):
                self._apply_dx_status("connected", "DX Cluster")
            else:
                self._dx_cluster = None  # clear so Connect button works on retry
                self._apply_dx_status("error", "")
                self._dx_status.setText("DX Cluster: connection failed — check settings")

    def _on_dx_status(self, status: str, node: str = ""):
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, lambda s=status, n=node:
            self._apply_dx_status(s, n))

    def _apply_dx_status(self, status: str, node: str):
        if status == "connected":
            self._dx_status.setText(
                f"DX Cluster: {node}")
            self._dx_status.setStyleSheet(
                "color:#3fbe6f;")
            self._dx_conn_btn.setText("Disconnect")
            self.cfg.set("dx_cluster.auto_connect", True)
        else:
            self._dx_status.setText(
                "DX Cluster: disconnected")
            self._dx_status.setStyleSheet(
                "")
            self._dx_conn_btn.setText("Connect")

    def _on_dx_spot(self, spot):
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0,
            lambda s=spot: self._add_dx_spot(s))

    def _add_dx_spot(self, spot):
        from PyQt6.QtWidgets import QTableWidgetItem
        # Remove duplicate DX call
        self._dx_spots = [
            s for s in self._dx_spots
            if s.dx_call != spot.dx_call]
        self._dx_spots.insert(0, spot)
        if len(self._dx_spots) > 100:
            self._dx_spots = self._dx_spots[:100]
        self._filter_dx_spots()
        self._check_dx_alert(spot)

    def _check_dx_alert(self, spot) -> None:
        """Beep and highlight if the spot matches the watch list."""
        watch_text = getattr(self, "_dx_watch_edit", None)
        if not watch_text:
            return
        raw = watch_text.text().strip()
        if not raw:
            return
        terms = [t.strip().upper() for t in raw.split(",") if t.strip()]
        call_upper = spot.dx_call.upper()
        matched = any(call_upper == t or call_upper.startswith(t)
                      for t in terms)
        if matched:
            from PyQt6.QtWidgets import QApplication
            QApplication.beep()
            self._dx_status.setText(
                f"⚡ ALERT: {spot.dx_call}  "
                f"{spot.freq_khz/1000:.3f} MHz  {getattr(spot, 'mode', '')}")
            self._dx_status.setStyleSheet("color:#ffcc00;font-weight:bold;")

    def _resolve_dx_band(self) -> str:
        """Return the band filter string: '' = all, otherwise e.g. '20m'."""
        band = self._dx_band.currentText()
        if band == "Current":
            return self._current_band or ""
        return "" if band == "All" else band

    def _add_dx_spot_row(self, spot) -> None:
        """Append one DX spot as a centred row in the DX table."""
        from PyQt6.QtWidgets import QTableWidgetItem
        from PyQt6.QtCore import Qt
        row = self._dx_table.rowCount()
        self._dx_table.insertRow(row)
        for col, val in enumerate([
                spot.dx_call, f"{spot.freq_khz:.1f}",
                spot.spotter, spot.comment[:30], spot.time_utc]):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._dx_table.setItem(row, col, item)

    def _filter_dx_spots(self):
        band = self._resolve_dx_band()
        mode = self._dx_mode_filter.currentText()
        self._dx_table.setRowCount(0)
        shown = 0
        for spot in self._dx_spots:
            if band and spot.band != band:
                continue
            if mode != "All" and spot.mode and spot.mode.upper() != mode.upper():
                continue
            self._add_dx_spot_row(spot)
            shown += 1
            if shown >= 10:
                break

    def set_sdr_tune_cb(self, cb) -> None:
        """Register a callback(freq_hz) to sync the SDR tab when a spot is clicked."""
        self._sdr_tune_cb = cb

    @staticmethod
    def _infer_rig_mode(mode_str: str, freq_hz: int) -> str:
        """Map a DX-spot mode string to a Hamlib rig-mode string."""
        from core.spot_tune import infer_rig_mode
        return infer_rig_mode(mode_str, freq_hz)

    def _do_spot_tune(self, freq_hz: int, callsign: str, mode_str: str) -> None:
        """Shared tune logic for DX, SOTA, and POTA spot double-click."""
        rig_mode = self._infer_rig_mode(mode_str, freq_hz)
        # Tune rig (or update VFO display if disconnected)
        if self.rig and self.rig.is_connected:
            try:
                self.rig.set_freq(freq_hz)
                self.rig.set_mode(rig_mode)
            except Exception:
                pass
        else:
            try:
                self._set_freq(freq_hz / 1e6)
            except Exception:
                pass
        # Sync SDR tab
        if callable(self._sdr_tune_cb):
            try:
                self._sdr_tune_cb(freq_hz)
            except Exception:
                pass
        # Status feedback
        freq_mhz = freq_hz / 1_000_000
        msg = (f"Tuned → {callsign}  {freq_mhz:.4f} MHz  {rig_mode}"
               if callsign else f"Tuned → {freq_mhz:.4f} MHz  {rig_mode}")
        if hasattr(self, "_dx_status"):
            self._dx_status.setText(msg)

    def _tune_to_dx_spot(self, index):
        """Double-click DX spot to tune rig + SDR with mode inference."""
        row = index.row()
        if row >= len(self._dx_spots):
            return
        spot = self._dx_spots[row]
        freq_hz = int(spot.freq_khz * 1000)
        self._dx_table.selectRow(row)
        self._do_spot_tune(freq_hz, getattr(spot, "dx_call", ""),
                           getattr(spot, "mode", ""))

    def _wire(self):
        self._band_combo.currentTextChanged.connect(self._on_band_change)
        self._tx_freq_spin.valueChanged.connect(
            self.ft8_engine.set_tx_freq)

    # ── Mode tab switching ────────────────────────────────────────────────

    def _rescan_software(self):
        """Re-check for running software instances."""
        try:
            self._ft8_engine.reconnect()
        except Exception:
            pass
        self._launch_bar.refresh()

    def _auto_launch_wsjtx(self):
        """Auto-launch WSJT-X when FT8/FT4/WSPR selected."""
        launcher = get_launcher(self.cfg)
        if not launcher.is_available("paths.wsjtx"):
            return
        # Check if already running
        import subprocess, sys
        try:
            if sys.platform == "win32":
                out = subprocess.run(
                    ["tasklist"], capture_output=True,
                    text=True).stdout.lower()
                if "wsjtx" in out:
                    return  # already running
            else:
                out = subprocess.run(
                    ["pgrep", "-x", "wsjtx"],
                    capture_output=True).returncode
                if out == 0:
                    return
        except Exception:
            pass
        launcher.launch("paths.wsjtx")

    def _on_mode_tab(self, idx: int):
        modes = ["FT8","FT4","WSPR","JS8","PSK31","RTTY","CW","SSTV"]
        self._current_mode = modes[idx]
        is_weak  = self._current_mode in ["FT8","FT4","WSPR","JS8"]
        is_fldigi = self._current_mode in ["PSK31","RTTY","CW","SSTV"]

        self._fldigi_panel.setVisible(is_fldigi)
        if hasattr(self, "_sstv_panel"):
            self._sstv_panel.setVisible(
                self._current_mode == "SSTV")
        self._auto_seq_cb.setEnabled(is_weak)
        self._auto_cq_cb.setEnabled(is_weak)
        if is_weak:
            self._auto_seq_cb.setToolTip(
                "Let the software automatically step through the QSO\n"
                "exchange (signal report, R+report, 73).\n"
                "Recommended for beginners.")
        else:
            self._auto_seq_cb.setToolTip(
                "Auto-sequence is only available for FT8, FT4, WSPR, and JS8.")

        # Update band/freq for this mode
        self._on_band_change(self._band_combo.currentText())

        # Start appropriate engine
        if self._current_mode in ["FT8","FT4"]:
            if not self.ft8_engine._running:
                self.ft8_engine.start(self._current_mode)
        elif self._current_mode == "WSPR":
            pass  # started manually via WSPR controls

        self._log_activity(f"Mode: {self._current_mode}")

    # ── Band / frequency ──────────────────────────────────────────────────

    def _on_band_change(self, band: str):
        self._current_band = band
        self._active_band = band
        mode  = self._current_mode
        freq  = self._get_mode_freq(mode, band)
        if freq:
            self.ft8_engine.band    = band
            self.ft8_engine.freq_hz = freq
            self._freq_label.setText(
                f"{freq/1e6:.6f} MHz")

    def _get_mode_freq(self, mode: str, band: str) -> int:
        """Get conventional frequency for mode+band."""
        freqs = DIGITAL_FREQS.get(mode, {})
        for b, hz in freqs:
            if b == band:
                return hz
        # Fallback to band start
        edges = BAND_EDGES.get(band)
        return edges[0] if edges else 0

    def _tune_rig(self):
        """Set IC-7100 to the selected band/mode frequency."""
        freq = self._get_mode_freq(
            self._current_mode, self._active_band)
        if freq and self.rig.is_connected:
            self.rig.set_freq(freq)
            self.rig.set_mode("PKTUSB")
            self._log_activity(
                f"Tuned rig → {freq/1e6:.4f} MHz PKTUSB")

    # ── Auto-sequence controls ────────────────────────────────────────────

    def _send_cq(self):
        # C-08 (Hank) / C-06 (Elena): never key the rig in Guest mode or an
        # unsafe state, even though this is already behind an explicit click.
        if not get_safety().can_transmit():
            self._log_activity(
                "CQ blocked — Demo Mode is ON (transmit disabled). "
                "Turn it off in the View menu.")
            return
        self.ft8_engine.send_cq()
        self._log_activity(
            f"CQ {operating_callsign(self.cfg)} {self.cfg.grid[:4]}")

    def _halt_tx(self):
        self.ft8_engine.halt_tx()
        self._log_activity("TX halted")

    # ── Fldigi ───────────────────────────────────────────────────────────

    def _connect_fldigi(self):
        self._fldigi_connect_btn.setEnabled(False)
        self._fldigi_status.setText("● Connecting…")

        def _try():
            ok = self.fldigi.connect(launch=True)
            QTimer.singleShot(0, lambda: self._fldigi_connected(ok))

        threading.Thread(target=_try, daemon=True).start()

    def _fldigi_connected(self, ok: bool):
        self._fldigi_connect_btn.setEnabled(not ok)
        if ok:
            self._fldigi_status.setText("● Connected")
            self._fldigi_status.setStyleSheet(
                "color:#3fbe6f;  font-weight:bold;")
            self.fldigi.set_mode(self._current_mode)
        else:
            self._fldigi_status.setText("● Failed — check Fldigi install")
            self._fldigi_status.setStyleSheet(
                "color:#cc4444;  font-weight:bold;")

    def _fldigi_tx(self):
        text = self._fldigi_tx_edit.text()
        if not text:
            return
        if not self.fldigi.is_connected:
            self._log_activity(
                "TX blocked — Fldigi not connected. "
                "Click 'Launch Fldigi' above.")
            self._fldigi_status.setText("● Not connected — launch Fldigi first")
            self._fldigi_status.setStyleSheet("color:#cc4444;")
            return
        # C-08 (Hank) / C-06 (Elena): block TX in Demo mode / unsafe state.
        if not get_safety().can_transmit():
            self._log_activity(
                "TX blocked — Demo Mode is ON (transmit disabled). "
                "Turn it off in the View menu.")
            return
        self.fldigi.transmit(text)
        self._log_activity(f"TX ({self._current_mode}): {text}")
        self._fldigi_tx_edit.clear()

    # ── FT8 engine callbacks ──────────────────────────────────────────────

    def _on_ft8_decode(self, decode: DecodedSignal):
        QTimer.singleShot(0, lambda d=decode: self._add_decode(d))
        # Push to RF Lab decode monitor (best-effort).
        try:
            mw = self.window()
            if mw and hasattr(mw, "_tab_map"):
                rf_lab = mw._tab_map.get("rf_lab")
                if rf_lab and hasattr(rf_lab, "append_decode"):
                    msg = (decode.message or "")[:80]
                    QTimer.singleShot(0, lambda d=decode, m=msg: rf_lab.append_decode(
                        "FT8", d.freq_hz,
                        callsign=d.callsign, message=m,
                        snr=float(d.snr), grid=d.grid))
        except Exception:
            pass
        # Also pin the heard station on the Map tab (if we can resolve its
        # location from the grid). Best-effort — never block decode display.
        try:
            mw = self.window()
            if mw and hasattr(mw, "_tab_map"):
                map_tab = mw._tab_map.get("map")
                if map_tab and hasattr(map_tab, "add_heard_station"):
                    from ui.tabs.map_tab import HeardSpot
                    QTimer.singleShot(0, lambda d=decode: (
                        map_tab.add_heard_station(
                            d.callsign,
                            HeardSpot(
                                callsign=d.callsign,
                                grid=getattr(d, "grid", ""),
                                source="FT8",
                                freq_mhz=getattr(d, "freq_hz", 0) / 1e6,
                                snr_db=getattr(d, "snr", 0)))))
        except Exception:
            pass

    def _on_seq_state(self, state: AutoSeqState, detail: str = ""):
        QTimer.singleShot(0, lambda s=state: self._apply_state(s))

    def _on_ft8_tx(self, message: str):
        QTimer.singleShot(0, lambda m=message: (
            self._tx_msg_label.setText(f"TX: {m}"),
            self._log_activity(f"TX: {m}")))

    def _on_qso_done(self, qso):
        QTimer.singleShot(0, lambda q=qso: self._handle_qso_done(q))

    def _on_wspr_spot(self, spot):
        QTimer.singleShot(0, lambda s=spot: (
            self._log_activity(f"WSPR spot: {s.display}"),
            setattr(self._stat_decodes, "text",
                    str(int(self._stat_decodes.text()) + 1))))
        # Push to RF Lab decode monitor and map (best-effort).
        try:
            mw = self.window()
            if mw and hasattr(mw, "_tab_map"):
                rf_lab = mw._tab_map.get("rf_lab")
                if rf_lab and hasattr(rf_lab, "append_decode"):
                    msg = f"{spot.callsign} {spot.grid} {spot.power_dbm}dBm"
                    QTimer.singleShot(0, lambda s=spot, m=msg: rf_lab.append_decode(
                        "WSPR", s.freq_hz,
                        callsign=s.callsign, message=m,
                        snr=float(s.snr), grid=s.grid))
                # Push to map if we have a grid → lat/lon
                map_tab = mw._tab_map.get("map")
                if map_tab and spot.grid and hasattr(map_tab, "set_wspr_spots"):
                    try:
                        from core.location import _grid_to_latlon
                        lat, lon = _grid_to_latlon(spot.grid.upper())
                        spot_dict = {
                            "callsign": spot.callsign,
                            "grid":     spot.grid,
                            "band":     spot.band,
                            "snr":      spot.snr,
                            "power_dbm": spot.power_dbm,
                            "dist_km":  int(spot.distance_km),
                            "lat":      lat,
                            "lon":      lon,
                        }
                        # Accumulate in the map's list
                        existing = list(map_tab._wspr_spots)
                        # Keep last 100 spots; deduplicate by callsign+band
                        key = f"{spot.callsign}_{spot.band}"
                        existing = [s for s in existing
                                    if f"{s['callsign']}_{s['band']}" != key]
                        existing.append(spot_dict)
                        if len(existing) > 100:
                            existing = existing[-100:]
                        QTimer.singleShot(
                            0, lambda s=existing: map_tab.set_wspr_spots(s))
                    except Exception:
                        pass
        except Exception:
            pass

    def _on_wsjtx_status(self, connected: bool):
        QTimer.singleShot(0, lambda c=connected: self._apply_wsjtx_status(c))

    def _apply_wsjtx_status(self, connected: bool):
        if not hasattr(self, "_wsjtx_lbl"):
            return
        if connected:
            self._wsjtx_lbl.setText("● WSJT-X connected")
            self._wsjtx_lbl.setStyleSheet(
                "color:#3fbe6f;font-size:10px;font-family:'Courier New';")
        else:
            self._wsjtx_lbl.setText("⚠ WSJT-X not connected — waiting for UDP…")
            self._wsjtx_lbl.setStyleSheet(
                "color:#ffaa44;font-size:10px;font-family:'Courier New';")

    def _on_wspr_status(self, msg: str):
        QTimer.singleShot(0, lambda m=msg:
            self._log_activity(f"WSPR: {m}"))

    def _on_fldigi_rx(self, text: str):
        QTimer.singleShot(0, lambda t=text:
            self._activity_log.insertPlainText(t))

    # ── UI updates ────────────────────────────────────────────────────────

    def _color_decode_item(self, item: QTableWidgetItem,
                           decode: DecodedSignal):
        """Apply foreground color (and optional bold) to a decode table cell."""
        if decode.worked:
            item.setForeground(QBrush(QColor("#444444")))
        elif decode.new_dxcc:
            item.setForeground(QBrush(QColor("#ffaa00")))
        elif decode.new_grid:
            item.setForeground(QBrush(QColor("#44aaff")))
        elif decode.is_reply_to == operating_callsign(self.cfg).upper():
            item.setForeground(QBrush(QColor("#3fbe6f")))
            item.setFont(QFont("Courier New", 11, QFont.Weight.Bold))

    def _add_decode(self, decode: DecodedSignal):
        """Add a decoded signal to the table."""
        row = self._decode_table.rowCount()
        self._decode_table.insertRow(row)
        items = [
            decode.callsign,
            decode.grid or "—",
            decode.display_snr,
            f"{decode.dt:+.1f}",
            decode.display_freq,
            decode.display_dist,
            f"{decode.bearing_deg:.0f}°" if decode.bearing_deg else "—",
            decode.dxcc or decode.country or "—",
            self._decode_flag(decode),
        ]
        for col, text in enumerate(items):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._color_decode_item(item, decode)
            self._decode_table.setItem(row, col, item)
        while self._decode_table.rowCount() > 200:
            self._decode_table.removeRow(0)
        self._stat_decodes.setText(
            str(int(self._stat_decodes.text()) + 1))

    def _decode_flag(self, decode: DecodedSignal) -> str:
        if decode.worked:
            return "DUPE"
        if decode.new_dxcc:
            return "NEW DXCC ★"
        if decode.new_grid:
            return "NEW GRID"
        if decode.new_band:
            return "NEW BAND"
        if decode.is_cq:
            return "CQ"
        if decode.is_reply_to == operating_callsign(self.cfg).upper():
            return "▶ YOU"
        return ""


    def _update_onair(self, state):
        """Reflect real TX state in the ON-AIR indicator (C-11, Tyler)."""
        name = getattr(state, "name", str(state)).upper()
        # Only show TRANSMITTING when the software state machine says TX AND
        # WSJT-X is actually connected (engine can enter TX states internally
        # without hardware if auto_cq fires while disconnected)
        wsjtx_up = getattr(self.ft8_engine, "_wsjtx_connected", False)
        transmitting = wsjtx_up and (
            "TX" in name or "SEND" in name or "CALLING" in name)
        if transmitting:
            self._onair_label.setText("ON THE AIR — TRANSMITTING")
            self._onair_label.setStyleSheet(
                "background:#3a0d0d;color:#ff5555;font-weight:bold;"
                "border:1px solid #aa2222;border-radius:4px;padding:5px;")
        else:
            self._onair_label.setText("RECEIVING")
            self._onair_label.setStyleSheet(
                "background:#0d2a14;color:#3fbe6f;font-weight:bold;"
                "border:1px solid #1f5a33;border-radius:4px;padding:5px;")

    def _apply_state(self, state: AutoSeqState):
        color = STATE_COLORS.get(state, "#555")
        self._state_label.setText(f"● {state.value}")
        self._state_label.setStyleSheet(
            f"color:{color};  font-weight:bold;")
        self._update_onair(state)
        qso = self.ft8_engine.current_qso
        if qso.their_call:
            self._qso_label.setText(
                f"Working: {qso.their_call}  {qso.their_grid}")
        else:
            self._qso_label.setText("No QSO in progress")

    def _handle_qso_done(self, qso):
        self._log_activity(
            f"QSO logged: {qso.call} "
            f"{qso.band} {qso.mode} "
            f"RST {qso.rst_rcvd}")
        count = int(self._stat_qsos.text()) + 1
        self._stat_qsos.setText(str(count))
        if self.log_db:
            stats = self.log_db.stats()
            self._stat_dxcc.setText(str(stats["dxcc_worked"]))
            self._stat_grids.setText(str(stats["grids_worked"]))

    def _update_cycle(self):
        """Update the cycle progress bar."""
        import time
        mode = self._current_mode
        if mode in ["FT8","FT4","WSPR"]:
            from modes.ft8 import CYCLE
            cycle_len = CYCLE.get(mode, 15.0)
            t = time.time() % cycle_len
            pct = int((t / cycle_len) * 100)
            self._cycle_bar.setValue(pct)
            remaining = cycle_len - t
            # Even/odd period
            total_cycles = int(time.time() / cycle_len)
            period = "EVEN" if total_cycles % 2 == 0 else "ODD"
            tx_rx = "TX" if (
                self.ft8_engine._in_tx) else "RX"
            self._cycle_label.setText(
                f"{tx_rx}  {period}  {remaining:.1f}s")

    def _on_decode_dblclick(self, index):
        """Double-click a decode to call that station."""
        row = index.row()
        call_item = self._decode_table.item(row, COL_CALL)
        if not call_item:
            return
        call = call_item.text()
        # Publish so {theircall} macro var is available immediately
        if self.cfg:
            self.cfg.set("session.dx_callsign", call)
        for decode in self.ft8_engine.decodes:
            if decode.callsign == call:
                self.ft8_engine.call_station(decode)
                self._log_activity(f"Calling: {call}")
                break


    def _export_decodes(self):
        """Export the current decode table to CSV or ADIF (C-10, Sam/Priya)."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        if self._decode_table.rowCount() == 0:
            QMessageBox.information(
                self, "Export Decodes",
                "No decoded signals to export yet.")
            return

        path, filt = QFileDialog.getSaveFileName(
            self, "Export Decoded Signals", "",
            "CSV (*.csv);;ADIF (*.adif *.adi);;All (*)")
        if not path:
            return
        try:
            if path.lower().endswith((".adif", ".adi")):
                self._export_decodes_adif(path)
            else:
                self._export_decodes_csv(path)
            QMessageBox.information(
                self, "Export Complete",
                f"Exported {self._decode_table.rowCount()} "
                f"signals to:\n{path}")
        except Exception as e:
            QMessageBox.warning(
                self, "Export Failed", str(e))

    def _export_decodes_csv(self, path: str):
        """Write decode table rows as CSV."""
        import csv
        from core.sanitize import csv_safe
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(DECODE_HEADERS)
            for row in range(self._decode_table.rowCount()):
                w.writerow([
                    csv_safe(self._decode_table.item(row, col).text()
                              if self._decode_table.item(row, col) else "")
                    for col in range(len(DECODE_HEADERS))])

    def _export_decodes_adif(self, path: str):
        """Write decode table rows as minimal ADIF (callsign + grid + freq)."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        date_s = now.strftime("%Y%m%d")
        time_s = now.strftime("%H%M%S")
        band   = self.cfg.get("rig.band", "20m")

        def _field(tag: str, val: str) -> str:
            return f"<{tag}:{len(val)}>{val}"

        lines = ["<PROGRAMID:7>Squelch", "<ADIF_VER:5>3.1.0", "<EOH>", ""]
        col = {h: i for i, h in enumerate(DECODE_HEADERS)}

        for row in range(self._decode_table.rowCount()):
            def cell(h):
                item = self._decode_table.item(row, col.get(h, 0))
                return item.text() if item else ""

            cs   = cell("Callsign").strip()
            grid = cell("Grid").strip()
            freq = cell("Freq").strip()
            if not cs:
                continue
            rec = " ".join([
                _field("CALL",    cs),
                _field("GRIDSQUARE", grid) if grid else "",
                _field("QSO_DATE", date_s),
                _field("TIME_ON",  time_s),
                _field("MODE",     "FT8"),
                _field("BAND",     band),
                _field("FREQ",     freq) if freq else "",
                "<EOR>",
            ])
            lines.append(rec)

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _filter_decodes(self, text: str):
        """Show/hide rows based on filter text."""
        for row in range(self._decode_table.rowCount()):
            item = self._decode_table.item(row, COL_CALL)
            if item:
                match = (not text or
                         text.upper() in item.text().upper())
                self._decode_table.setRowHidden(row, not match)

    def _clear_decodes(self):
        self._decode_table.setRowCount(0)
        self._stat_decodes.setText("0")
        self.ft8_engine._decodes.clear()

    def _set_freq(self, freq_mhz: float):
        """Tune the rig to freq_mhz when a DX spot or decoded call is clicked."""
        try:
            from core.launcher import get_rig_controller
            rig = get_rig_controller()
            if rig and rig.is_connected():
                rig.set_frequency(int(freq_mhz * 1e6))
        except Exception:
            pass  # Rig not connected — silently ignore

    def _log_activity(self, msg: str):
        from datetime import datetime, timezone
        t = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self._activity_log.append(f"{t}  {msg}")
        # Auto-scroll
        sb = self._activity_log.verticalScrollBar()
        sb.setValue(sb.maximum())
