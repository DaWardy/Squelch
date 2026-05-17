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
from ui.widgets.launch_bar import LaunchBar
from core.launcher import get_launcher
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


class ModesTab(QWidget):
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
        self.wspr_engine.on_spot(self._on_wspr_spot)
        self.wspr_engine.on_status(self._on_wspr_status)
        self.fldigi.on_rx(self._on_fldigi_rx)

        self._current_mode  = "FT8"
        self._active_band   = "20m"
        self._cycle_timer   = QTimer(self)
        self._cycle_timer.setInterval(100)
        self._cycle_timer.timeout.connect(self._update_cycle)
        self._freq_history: list[int] = []

        self._build()
        self._wire()

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Launch bar ───────────────────────────────────────────────────
        self._launch_bar = LaunchBar(
            "modes", self.cfg,
            rescan_callback=self._rescan_software)
        root.addWidget(self._launch_bar)

        # ── Mode selector tabs ────────────────────────────────────────────
        self._mode_tabs = QTabWidget()
        self._mode_tabs.setFixedHeight(42)
        self._mode_tabs.tabBar().setDocumentMode(True)
        self._mode_tabs.setStyleSheet("""
            QTabBar::tab{padding:6px 16px;font-size:11px;
              background:#141414;color:#666;border:none;
              border-bottom:2px solid transparent;}
            QTabBar::tab:selected{color:#3fbe6f;
              border-bottom:2px solid #3fbe6f;}
            QTabBar::tab:hover{color:#aaa;}
            QTabWidget::pane{border:none;}
        """)
        for m in ["FT8","FT4","WSPR","JS8","PSK31","RTTY","CW","SSTV"]:
            self._mode_tabs.addTab(QWidget(), m)
        self._mode_tabs.currentChanged.connect(self._on_mode_tab)
        root.addWidget(self._mode_tabs)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color:#1a1a1a;")
        root.addWidget(div)

        # ── Main splitter: controls | decode list ────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(
            "QSplitter::handle{background:#1a1a1a;width:2px;}")

        # Left panel — controls
        left = QWidget()
        left.setMinimumWidth(280)
        left.setMaximumWidth(360)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(6)

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
            "color:#3fbe6f; font-family:'Courier New'; font-size:13px;")
        band_gl.addWidget(self._freq_label, 1, 1)

        self._tune_btn = QPushButton("Tune Rig")
        self._tune_btn.setFixedHeight(26)
        self._tune_btn.setToolTip(
            "Set IC-7100 to this band's FT8/WSPR frequency")
        self._tune_btn.clicked.connect(self._tune_rig)
        band_gl.addWidget(self._tune_btn, 2, 0, 1, 2)
        left_layout.addWidget(band_grp)

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
            "color:#3fbe6f; font-family:'Courier New'; font-size:12px;")
        self._cycle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cycle_l.addWidget(self._cycle_bar)
        cycle_l.addWidget(self._cycle_label)
        left_layout.addWidget(cycle_grp)

        # ── Auto-sequence state ───────────────────────────────────────
        state_grp = QGroupBox("Auto-Sequence")
        state_l   = QVBoxLayout(state_grp)

        self._state_label = QLabel("● Idle — monitoring")
        self._state_label.setStyleSheet(
            "color:#555; font-size:11px; font-weight:bold;")
        state_l.addWidget(self._state_label)

        self._qso_label = QLabel("No QSO in progress")
        self._qso_label.setStyleSheet(
            "color:#444; font-size:10px;")
        state_l.addWidget(self._qso_label)

        self._tx_msg_label = QLabel("")
        self._tx_msg_label.setStyleSheet(
            "color:#3fbe6f; font-family:'Courier New'; font-size:10px;")
        self._tx_msg_label.setWordWrap(True)
        state_l.addWidget(self._tx_msg_label)

        # Control buttons
        btn_row1 = QHBoxLayout()
        self._cq_btn = QPushButton("CQ")
        self._cq_btn.setFixedHeight(30)
        self._cq_btn.setStyleSheet(
            "background:#1a3a1a;color:#3fbe6f;border:1px solid #3fbe6f;"
            "border-radius:4px;font-weight:bold;font-size:12px;")
        self._cq_btn.clicked.connect(self._send_cq)

        self._halt_btn = QPushButton("Halt TX")
        self._halt_btn.setFixedHeight(30)
        self._halt_btn.setStyleSheet(
            "background:#3a1a1a;color:#cc4444;border:1px solid #cc4444;"
            "border-radius:4px;font-size:11px;")
        self._halt_btn.clicked.connect(self._halt_tx)
        btn_row1.addWidget(self._cq_btn)
        btn_row1.addWidget(self._halt_btn)
        state_l.addLayout(btn_row1)

        left_layout.addWidget(state_grp)

        # ── TX settings ───────────────────────────────────────────────
        tx_grp = QGroupBox("TX Settings")
        tx_gl  = QGridLayout(tx_grp)
        tx_gl.setSpacing(4)

        tx_gl.addWidget(QLabel("Power:"), 0, 0)
        self._power_spin = QSpinBox()
        self._power_spin.setRange(1, 100)
        self._power_spin.setValue(
            self.cfg.get("ft8.tx_power_dbm", 37))
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

        self._even_cb = QCheckBox("TX even periods")
        self._even_cb.setChecked(True)
        tx_gl.addWidget(self._even_cb, 2, 0, 1, 2)

        self._auto_seq_cb = QCheckBox("Auto-sequence")
        self._auto_seq_cb.setChecked(True)
        self._auto_seq_cb.toggled.connect(
            self.ft8_engine.set_auto_sequence)
        tx_gl.addWidget(self._auto_seq_cb, 3, 0, 1, 2)

        self._auto_cq_cb = QCheckBox("Auto CQ")
        self._auto_cq_cb.setChecked(False)
        self._auto_cq_cb.toggled.connect(
            self.ft8_engine.set_auto_cq)
        tx_gl.addWidget(self._auto_cq_cb, 4, 0, 1, 2)

        self._hold_tx_cb = QCheckBox("Hold TX frequency")
        self._hold_tx_cb.setChecked(False)
        self._hold_tx_cb.toggled.connect(
            self.ft8_engine.set_hold_tx_freq)
        tx_gl.addWidget(self._hold_tx_cb, 5, 0, 1, 2)

        self._dx_only_cb = QCheckBox("DX only (skip domestic)")
        self._dx_only_cb.setChecked(False)
        self._dx_only_cb.toggled.connect(
            self.ft8_engine.set_dx_only)
        tx_gl.addWidget(self._dx_only_cb, 6, 0, 1, 2)

        left_layout.addWidget(tx_grp)

        # ── Session stats ─────────────────────────────────────────────
        stats_grp = QGroupBox("Session")
        stats_l   = QGridLayout(stats_grp)
        stats_l.setSpacing(3)

        def _stat(label, attr):
            lbl = QLabel(label)
            lbl.setStyleSheet("color:#555; font-size:10px;")
            val = QLabel("0")
            val.setStyleSheet(
                "color:#3fbe6f; font-size:11px; "
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

        left_layout.addWidget(stats_grp)
        left_layout.addStretch()

        # ── Fldigi panel (shown for PSK31/RTTY/CW/SSTV) ──────────────
        self._fldigi_panel = self._build_fldigi_panel()
        left_layout.addWidget(self._fldigi_panel)
        self._fldigi_panel.hide()

        splitter.addWidget(left)

        # Right panel — decode list + activity
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 8, 8, 8)
        right_layout.setSpacing(4)

        # Decode list header
        decode_hdr = QHBoxLayout()
        decode_hdr.addWidget(QLabel("Decoded Signals"))
        decode_hdr.addStretch()

        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Filter callsign…")
        self._filter_edit.setFixedWidth(130)
        self._filter_edit.textChanged.connect(self._filter_decodes)
        decode_hdr.addWidget(self._filter_edit)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedHeight(24)
        self._clear_btn.clicked.connect(self._clear_decodes)
        decode_hdr.addWidget(self._clear_btn)
        right_layout.addLayout(decode_hdr)

        # Decode table
        self._decode_table = QTableWidget(0, len(DECODE_HEADERS))
        self._decode_table.setHorizontalHeaderLabels(DECODE_HEADERS)
        self._decode_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self._decode_table.horizontalHeader().setSectionResizeMode(
            COL_DXCC, QHeaderView.ResizeMode.Stretch)
        self._decode_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self._decode_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._decode_table.setAlternatingRowColors(True)
        self._decode_table.setSortingEnabled(True)
        self._decode_table.verticalHeader().setVisible(False)
        self._decode_table.setStyleSheet("""
            QTableWidget{background:#0d0d0d;color:#aaa;
              gridline-color:#1a1a1a;font-size:11px;
              font-family:'Courier New';
              alternate-background-color:#111111;
              selection-background-color:#1a3a1a;}
            QHeaderView::section{background:#141414;color:#666;
              border:none;font-size:10px;padding:3px;}
        """)
        self._decode_table.doubleClicked.connect(self._on_decode_dblclick)
        right_layout.addWidget(self._decode_table, 3)

        # Activity log
        activity_hdr = QHBoxLayout()
        activity_hdr.addWidget(QLabel("Activity / TX Log"))
        activity_hdr.addStretch()
        clr = QPushButton("Clear")
        clr.setFixedHeight(22)
        clr.clicked.connect(lambda: self._activity_log.clear())
        activity_hdr.addWidget(clr)
        right_layout.addLayout(activity_hdr)

        self._activity_log = QTextEdit()
        self._activity_log.setReadOnly(True)
        self._activity_log.setMaximumHeight(120)
        self._activity_log.setStyleSheet(
            "background:#080808; color:#3fbe6f; "
            "font-family:'Courier New'; font-size:10px; "
            "border:1px solid #1a1a1a;")
        right_layout.addWidget(self._activity_log)

        splitter.addWidget(right)
        splitter.setSizes([300, 700])
        root.addWidget(splitter)

        # Start cycle timer
        self._cycle_timer.start()

    def _build_fldigi_panel(self) -> QWidget:
        """Control panel shown when PSK31/RTTY/CW/SSTV is active."""
        panel = QGroupBox("Fldigi")
        layout = QVBoxLayout(panel)

        status_row = QHBoxLayout()
        self._fldigi_status = QLabel("● Not connected")
        self._fldigi_status.setStyleSheet(
            "color:#888; font-size:11px; font-weight:bold;")
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

        return panel

    # ── Wire signals ──────────────────────────────────────────────────────

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
        self._auto_seq_cb.setEnabled(is_weak)
        self._auto_cq_cb.setEnabled(is_weak)

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
        self.ft8_engine.send_cq()
        self._log_activity(
            f"CQ {self.cfg.callsign} {self.cfg.grid[:4]}")

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
                "color:#3fbe6f; font-size:11px; font-weight:bold;")
            self.fldigi.set_mode(self._current_mode)
        else:
            self._fldigi_status.setText("● Failed — check Fldigi install")
            self._fldigi_status.setStyleSheet(
                "color:#cc4444; font-size:11px; font-weight:bold;")

    def _fldigi_tx(self):
        text = self._fldigi_tx_edit.text()
        if text and self.fldigi.is_connected:
            self.fldigi.transmit(text)
            self._log_activity(f"TX ({self._current_mode}): {text}")
            self._fldigi_tx_edit.clear()

    # ── FT8 engine callbacks ──────────────────────────────────────────────

    def _on_ft8_decode(self, decode: DecodedSignal):
        QTimer.singleShot(0, lambda d=decode: self._add_decode(d))

    def _on_seq_state(self, state: AutoSeqState):
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

    def _on_wspr_status(self, msg: str):
        QTimer.singleShot(0, lambda m=msg:
            self._log_activity(f"WSPR: {m}"))

    def _on_fldigi_rx(self, text: str):
        QTimer.singleShot(0, lambda t=text:
            self._activity_log.insertPlainText(t))

    # ── UI updates ────────────────────────────────────────────────────────

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
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter)
            # Color coding
            if decode.worked:
                item.setForeground(QBrush(QColor("#444444")))
            elif decode.new_dxcc:
                item.setForeground(QBrush(QColor("#ffaa00")))
            elif decode.new_grid:
                item.setForeground(QBrush(QColor("#44aaff")))
            elif decode.is_reply_to == self.cfg.callsign.upper():
                item.setForeground(QBrush(QColor("#3fbe6f")))
                item.setFont(QFont("Courier New", 11,
                                   QFont.Weight.Bold))
            self._decode_table.setItem(row, col, item)

        # Keep last 200 rows
        while self._decode_table.rowCount() > 200:
            self._decode_table.removeRow(0)

        # Update decode count
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
        if decode.is_reply_to == self.cfg.callsign.upper():
            return "▶ YOU"
        return ""

    def _apply_state(self, state: AutoSeqState):
        color = STATE_COLORS.get(state, "#555")
        self._state_label.setText(f"● {state.value}")
        self._state_label.setStyleSheet(
            f"color:{color}; font-size:11px; font-weight:bold;")
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
        # Find the decode
        call = call_item.text()
        for decode in self.ft8_engine.decodes:
            if decode.callsign == call:
                self.ft8_engine.call_station(decode)
                self._log_activity(f"Calling: {call}")
                break

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

    def _log_activity(self, msg: str):
        from datetime import datetime, timezone
        t = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self._activity_log.append(f"{t}  {msg}")
        # Auto-scroll
        sb = self._activity_log.verticalScrollBar()
        sb.setValue(sb.maximum())
