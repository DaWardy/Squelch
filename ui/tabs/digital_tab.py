from __future__ import annotations
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
import sys
import logging
from datetime import datetime, timezone

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QGroupBox, QFrame, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QCheckBox, QTextEdit, QProgressBar,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont

from ui.widgets.launch_bar import LaunchBar
from digital.dsdplus import DSDPlusManager, DecodeEvent
from digital.op25_bridge import OP25Bridge

log = logging.getLogger(__name__)

IS_WINDOWS = sys.platform == "win32"

PROTOCOL_COLORS = {
    "P25":   "#3fbe6f",
    "DMR":   "#44aaff",
    "NXDN":  "#ffaa22",
    "YSF":   "#ff66aa",
    "DSTAR": "#aa66ff",
    "?":     "#555555",
}

PROTOCOL_INFO = {
    "P25": (
        "Project 25 (P25/APCO-25)\n\n"
        "Digital voice standard used by public safety,\n"
        "law enforcement, fire, EMS across North America.\n"
        "Phase 1: IMBE vocoder, FDMA channel plan\n"
        "Phase 2: AMBE+2 vocoder, TDMA efficiency\n\n"
        "Talkgroups: logical channels within a system\n"
        "WACN: Wide Area Communication Network ID\n"
        "SYSID: System identifier\n"
        "NAC: Network Access Code (like squelch tone)"
    ),
    "DMR": (
        "Digital Mobile Radio (DMR)\n\n"
        "ETSI standard used by commercial, amateur,\n"
        "and public safety radio worldwide.\n"
        "TDMA: 2 timeslots per 12.5 kHz channel\n"
        "Tiers: I (simplex), II (conventional),\n"
        "       III (trunked)\n\n"
        "Color Code: 0-15, similar to CTCSS\n"
        "Talkgroup: destination group address\n"
        "DMR-MARC, Brandmeister: amateur networks"
    ),
    "NXDN": (
        "NXDN (Nextedge Digital Narrowband)\n\n"
        "Kenwood/Icom proprietary digital protocol.\n"
        "FDMA, 6.25 or 12.5 kHz channels.\n"
        "Used in commercial and some public safety.\n"
        "Also marketed as IDAS (Icom) and NEXEDGE (Kenwood)\n\n"
        "RAN: Radio Access Number (like color code)\n"
        "Group ID: talkgroup equivalent"
    ),
    "YSF": (
        "Yaesu System Fusion (C4FM/YSF)\n\n"
        "Yaesu proprietary digital protocol.\n"
        "4-level FSK modulation (C4FM)\n"
        "Used in amateur radio, especially with\n"
        "Yaesu DR-series repeaters and handhelds.\n\n"
        "Wires-X: Yaesu internet linking system\n"
        "DN mode: Digital Narrow (data + voice)\n"
        "VW mode: Voice Wide (high quality audio)"
    ),
    "DSTAR": (
        "D-STAR (Digital Smart Technologies for Amateur Radio)\n\n"
        "ICOM/JARL digital protocol for amateur radio.\n"
        "GMSK modulation, 4800 bps voice.\n"
        "Integrated internet linking via reflectors.\n\n"
        "UR: To (destination) callsign\n"
        "MY: From (source) callsign\n"
        "RPT1/RPT2: Repeater routing callsigns\n"
        "Reflectors: DCS, REF, XRF, XLX linking"
    ),
}


class DigitalTab(QWidget):
    def __init__(self, config, rig=None, parent=None):
        super().__init__(parent)
        self.cfg   = config
        self.rig   = rig

        # Decoder backends
        self._dsdplus = DSDPlusManager(config)
        self._op25    = OP25Bridge(config)
        self._active_backend = None

        # Wire callbacks
        self._dsdplus.on_decode(self._on_decode)
        self._dsdplus.on_status(self._on_dsd_status)
        self._op25.on_status(self._on_op25_status)

        self._build()

        # Check for running decoders after UI is ready
        QTimer.singleShot(1000, self._auto_connect)

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Launch bar
        self._launch_bar = LaunchBar(
            "digital", self.cfg,
            rescan_callback=self._rescan)
        root.addWidget(self._launch_bar)

        # Status bar
        root.addWidget(self._build_status_bar())

        # Main content splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(
            "QSplitter::handle{background:#1a1a1a;width:3px;}")

        # Left: decode log
        left = self._build_decode_log()
        splitter.addWidget(left)

        # Right: info panels
        right = self._build_info_panels()
        right.setMaximumWidth(320)
        splitter.addWidget(right)

        splitter.setSizes([700, 300])
        root.addWidget(splitter, 1)

    def _build_status_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(36)
        bar.setStyleSheet(
            "background:#0d0d0d;"
            "border-bottom:1px solid #1a1a1a;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(12)

        self._decoder_lbl = QLabel("● No decoder running")
        self._decoder_lbl.setStyleSheet(
            ""
            "font-family:'Courier New';")
        lay.addWidget(self._decoder_lbl)

        lay.addWidget(_vsep())

        self._protocol_lbl = QLabel("—")
        self._protocol_lbl.setStyleSheet(
            "color:#3fbe6f;"
            "font-weight:bold;font-family:'Courier New';")
        lay.addWidget(self._protocol_lbl)

        lay.addWidget(_vsep())

        self._tg_lbl = QLabel("TG: —")
        self._tg_lbl.setStyleSheet(
            ""
            "font-family:'Courier New';")
        lay.addWidget(self._tg_lbl)

        lay.addWidget(_vsep())

        self._enc_lbl = QLabel("")
        self._enc_lbl.setStyleSheet(
            "color:#cc4444;"
            "font-weight:bold;")
        lay.addWidget(self._enc_lbl)

        lay.addStretch()

        # Audio routing indicator
        self._route_lbl = QLabel("Audio: Not routed")
        self._route_lbl.setStyleSheet(
            "")
        lay.addWidget(self._route_lbl)

        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(55)
        clear_btn.setFixedHeight(24)
        clear_btn.clicked.connect(self._clear_log)
        lay.addWidget(clear_btn)

        return bar

    def _build_decode_log(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Digital Decode Log")
        title.setStyleSheet(
            "font-weight:bold;")
        hdr.addWidget(title)
        hdr.addStretch()

        # Protocol filter
        self._proto_filter = QComboBox()
        self._proto_filter.setToolTip(
            "Filter decoded calls by protocol\n"
            "All: show P25, DMR, NXDN, YSF, D-STAR")
        self._proto_filter.addItems([
            "All protocols",
            "P25", "DMR", "NXDN", "YSF", "D-STAR"])
        self._proto_filter.setFixedWidth(130)
        self._proto_filter.currentTextChanged.connect(
            self._apply_filter)
        hdr.addWidget(self._proto_filter)

        # Hide encrypted
        self._hide_enc = QCheckBox("Hide encrypted")
        self._hide_enc.setToolTip(
            "Hide encrypted calls from the decode log\n"
            "Encrypted audio cannot be decoded")
        self._hide_enc.toggled.connect(self._apply_filter)
        hdr.addWidget(self._hide_enc)

        lay.addLayout(hdr)

        # Decode table
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels([
            "Time", "Protocol", "TG/Dest",
            "Source", "Info", "Enc"])
        hdr_view = self._table.horizontalHeader()
        hdr_view.setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        hdr_view.setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self._table.setStyleSheet(
            "QTableWidget{"
            "background:#0a0a0a;"
            "gridline-color:#1a1a1a;"
            "alternate-background-color:#0d0d0d;"
            "font-family:'Courier New';"
            "border:1px solid #1a1a1a;}"
            "QHeaderView::section{"
            "background:#141414;"
            "border:none;padding:3px;}")
        self._table.setAlternatingRowColors(True)
        self._table.clicked.connect(self._on_row_click)
        lay.addWidget(self._table)

        # No decoder placeholder
        self._no_decoder_msg = QLabel(
            "No digital voice decoder running.\n\n"
            "Windows: Launch DSD+ from the bar above\n"
            "Linux:   Launch OP25 from the bar above\n\n"
            "Audio routing:\n"
            "  SDR tab → Route to Digital tab\n"
            "  or IC-7100 USB audio → VB-Cable → DSD+")
        self._no_decoder_msg.setAlignment(
            Qt.AlignmentFlag.AlignCenter)
        self._no_decoder_msg.setStyleSheet(
            "")
        self._no_decoder_msg.setWordWrap(True)
        lay.addWidget(self._no_decoder_msg)

        return w

    def _build_info_panels(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 6, 6, 6)
        lay.setSpacing(6)

        # Active call panel
        call_grp = QGroupBox("Active Call")
        cl = QVBoxLayout(call_grp)

        self._call_proto = QLabel("Protocol: —")
        self._call_tg    = QLabel("Talkgroup: —")
        self._call_src   = QLabel("Source: —")
        self._call_enc   = QLabel("")
        self._call_dur   = QLabel("Duration: —")

        for lbl in [self._call_proto, self._call_tg,
                    self._call_src, self._call_enc,
                    self._call_dur]:
            lbl.setStyleSheet(
                ""
                "font-family:'Courier New';")
            cl.addWidget(lbl)
        lay.addWidget(call_grp)

        # Protocol info / education panel
        info_grp = QGroupBox("Protocol Reference")
        il = QVBoxLayout(info_grp)

        self._proto_selector = QComboBox()
        self._proto_selector.addItems([
            "P25", "DMR", "NXDN", "YSF", "D-STAR"])
        self._proto_selector.currentTextChanged.connect(
            self._show_protocol_info)
        il.addWidget(self._proto_selector)

        self._proto_info = QTextEdit()
        self._proto_info.setReadOnly(True)
        self._proto_info.setStyleSheet(
            "background:#0a0a0a;"
            "font-family:'Courier New';"
            "border:1px solid #1a1a1a;")
        self._proto_info.setMaximumHeight(200)
        il.addWidget(self._proto_info)
        lay.addWidget(info_grp)

        # Show initial protocol info
        self._show_protocol_info("P25")

        # Stats
        stats_grp = QGroupBox("Session Statistics")
        sl = QVBoxLayout(stats_grp)
        self._stats_lbl = QLabel(
            "Calls decoded:    0\n"
            "P25 calls:        0\n"
            "DMR calls:        0\n"
            "Encrypted:        0\n"
            "Session started:  —")
        self._stats_lbl.setStyleSheet(
            ""
            "font-family:'Courier New';")
        sl.addWidget(self._stats_lbl)
        lay.addWidget(stats_grp)

        lay.addStretch()
        return w

    # ── Decoder management ────────────────────────────────────────────────

    def _auto_connect(self):
        """Check if OP25 is already running (Linux)."""
        if self._op25.available():
            self._op25.start_polling()
            self._active_backend = "op25"
            self._set_decoder_status(
                "OP25 connected", "#3fbe6f")

    def _rescan(self):
        """Re-check for running decoders."""
        self._auto_connect()
        self._launch_bar.refresh()

    def _on_dsd_status(self, status: str):
        QTimer.singleShot(0,
            lambda s=status: self._apply_dsd_status(s))

    def _apply_dsd_status(self, status: str):
        if status == "running":
            self._active_backend = "dsdplus"
            self._set_decoder_status(
                "DSD+ running", "#3fbe6f")
            self._no_decoder_msg.hide()
        elif status == "stopped":
            if self._active_backend == "dsdplus":
                self._active_backend = None
            self._set_decoder_status(
                "DSD+ stopped", "#888")
        elif status == "error":
            self._set_decoder_status(
                "DSD+ error — check path", "#cc4444")

    def _on_op25_status(self, status):
        QTimer.singleShot(0,
            lambda s=status: self._apply_op25_status(s))

    def _apply_op25_status(self, status):
        if status.running:
            self._no_decoder_msg.hide()
            self._protocol_lbl.setText("P25")
            self._tg_lbl.setText(
                f"TG: {status.talkgroup or '—'}")
            if status.encrypted:
                self._enc_lbl.setText("🔒 ENC")
            else:
                self._enc_lbl.setText("")

    def _set_decoder_status(self, text: str, color: str):
        self._decoder_lbl.setText(f"● {text}")
        self._decoder_lbl.setStyleSheet(
            f"color:{color};"
            "font-family:'Courier New';")

    # ── Decode events ─────────────────────────────────────────────────────

    def _on_decode(self, event: DecodeEvent):
        """Called from DSD+ thread — dispatch to UI thread."""
        QTimer.singleShot(0,
            lambda e=event: self._add_decode_row(e))

    def _add_decode_row(self, event: DecodeEvent):
        """Add a decode event to the table."""
        # Apply filters
        proto_filter = self._proto_filter.currentText()
        if (proto_filter != "All protocols" and
                event.protocol != proto_filter):
            return
        if self._hide_enc.isChecked() and event.encrypted:
            return

        # Add row
        row = self._table.rowCount()
        if row > 500:
            self._table.removeRow(0)
            row = self._table.rowCount()

        self._table.insertRow(row)

        ts = datetime.fromtimestamp(
            event.timestamp,
            tz=timezone.utc).strftime("%H:%M:%S")

        color = PROTOCOL_COLORS.get(event.protocol, "#555")
        cells = [
            ts,
            event.protocol,
            event.talkgroup or "—",
            event.source_id  or "—",
            event.raw_line[:60],
            "🔒" if event.encrypted else "",
        ]
        for col, val in enumerate(cells):
            item = QTableWidgetItem(val)
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter)
            if col == 1:
                item.setForeground(QColor(color))
            self._table.setItem(row, col, item)

        self._table.scrollToBottom()

        # Update status bar
        self._protocol_lbl.setText(event.protocol)
        self._protocol_lbl.setStyleSheet(
            f"color:{color};"
            "font-weight:bold;font-family:'Courier New';")
        self._tg_lbl.setText(
            f"TG: {event.talkgroup or '—'}")
        self._enc_lbl.setText(
            "🔒 ENCRYPTED" if event.encrypted else "")

        # Update active call panel
        self._call_proto.setText(
            f"Protocol: {event.protocol}")
        self._call_tg.setText(
            f"Talkgroup: {event.talkgroup or '—'}")
        self._call_src.setText(
            f"Source: {event.source_id or '—'}")
        self._call_enc.setText(
            "🔒 Encrypted — audio unavailable"
            if event.encrypted else "")
        self._call_enc.setStyleSheet(
            "color:#cc4444;" if event.encrypted
            else "color:#3fbe6f;")

        self._no_decoder_msg.hide()

    def _on_row_click(self, index):
        """Show detail for clicked row."""
        row = index.row()
        if row < 0:
            return
        raw = self._table.item(row, 4)
        if raw:
            log.debug(f"Selected: {raw.text()}")

    def _apply_filter(self):
        """Re-apply protocol and encryption filters."""
        proto = self._proto_filter.currentText()
        hide_enc = self._hide_enc.isChecked()
        for row in range(self._table.rowCount()):
            proto_item = self._table.item(row, 1)
            enc_item   = self._table.item(row, 5)
            if not proto_item:
                continue
            row_proto = proto_item.text()
            is_enc    = bool(enc_item and enc_item.text())
            hide = (
                (proto != "All protocols" and
                 row_proto != proto) or
                (hide_enc and is_enc))
            self._table.setRowHidden(row, hide)

    def _clear_log(self):
        self._table.setRowCount(0)
        self._no_decoder_msg.show()

    # ── Protocol info ─────────────────────────────────────────────────────

    def _show_protocol_info(self, proto: str):
        # Map D-STAR display name
        key = "DSTAR" if proto == "D-STAR" else proto
        info = PROTOCOL_INFO.get(key, f"{proto}\n\nNo info available.")
        self._proto_info.setPlainText(info)

    # ── Audio routing from SDR ────────────────────────────────────────────

    def receive_iq_samples(self, iq, sample_rate: int,
                            center_hz: int):
        """
        Called when SDR tab routes audio here.
        Future: pipe to decoder for software decode.
        Currently: update routing indicator.
        """
        self._route_lbl.setText(
            f"Audio: SDR → {center_hz/1e6:.3f}MHz")
        self._route_lbl.setStyleSheet(
            "color:#3fbe6f;")


def _vsep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setStyleSheet("color:#1e1e1e;")
    f.setFixedWidth(1)
    return f
