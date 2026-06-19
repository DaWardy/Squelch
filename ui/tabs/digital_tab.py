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
from core.themes import get_theme
from datetime import datetime, timezone

from ui.panel import SquelchPanel
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QGroupBox, QFrame, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QCheckBox, QTextEdit,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor

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


class DigitalTab(SquelchPanel, QWidget):
    panel_id    = "digital"
    panel_title = "Voice Digital"

    def __init__(self, config, rig=None, parent=None):
        super().__init__(parent)
        self.cfg   = config
        self.rig   = rig

        # Decoder backends
        self._dsdplus = DSDPlusManager(config)
        self._op25    = OP25Bridge(config)
        self._active_backend = None

        # Session statistics counters
        self._stats: dict[str, int] = {
            "total": 0, "P25": 0, "DMR": 0,
            "NXDN": 0, "YSF": 0, "DSTAR": 0, "encrypted": 0,
        }
        self._session_start = datetime.now(timezone.utc)

        # Wire callbacks
        self._dsdplus.on_decode(self._on_decode)
        self._dsdplus.on_status(self._on_dsd_status)
        self._op25.on_status(self._on_op25_status)

        self._build()

        # Check for running decoders after UI is ready
        QTimer.singleShot(1000, self._auto_connect)

    # ── Panel state persistence ───────────────────────────────────────────

    def save_state(self) -> dict:
        try:
            return {
                "splitter_sizes": (self._splitter.sizes()
                                   if hasattr(self, "_splitter") else []),
            }
        except Exception:
            return {}

    def restore_state(self, state: dict) -> None:
        try:
            if "splitter_sizes" in state and hasattr(self, "_splitter"):
                sizes = state["splitter_sizes"]
                if isinstance(sizes, list) and len(sizes) == 2:
                    self._splitter.setSizes(sizes)
        except Exception:
            pass

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
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setStyleSheet(
            "QSplitter::handle{background:#1a1a1a;width:3px;}")

        # Left: decode log
        left = self._build_decode_log()
        self._splitter.addWidget(left)

        # Right: info panels
        right = self._build_info_panels()
        right.setMaximumWidth(320)
        self._splitter.addWidget(right)

        self._splitter.setSizes([700, 300])
        root.addWidget(self._splitter, 1)

        # Macro toolbar + TX panel at bottom
        root.addWidget(self._build_macro_toolbar())
        root.addWidget(self._build_tx_panel())


    def _build_tx_panel(self) -> "QFrame":
        """HRD-style digital TX text box."""
        from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QPlainTextEdit,
                                      QPushButton, QLabel, QComboBox)
        _t = get_theme(self.cfg.get("ui.theme", "Dark"))
        bar = QFrame()
        bar.setFrameShape(QFrame.Shape.StyledPanel)
        bar.setStyleSheet(
            f"QFrame{{background:{_t.meter_bg};"
            f"border-top:1px solid {_t.accent};"
            f"border-bottom:1px solid {_t.accent};}}")
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(6, 4, 6, 4)
        hl.setSpacing(6)

        lbl = QLabel("TX:")
        lbl.setStyleSheet(f"color:{_t.accent};font-weight:bold;min-width:24px;")
        hl.addWidget(lbl)

        self._tx_text = QPlainTextEdit()
        self._tx_text.setMaximumHeight(52)
        self._tx_text.setPlaceholderText(
            "Type message to transmit  (Enter = Send,  Shift+Enter = newline)")
        self._tx_text.setStyleSheet(
            f"QPlainTextEdit{{background:{_t.bg_primary};"
            f"color:{_t.fg_primary};"
            f"border:1px solid {_t.border_focus};border-radius:3px;"
            f"font-family:'Courier New';font-size:11px;padding:2px;}}")
        self._tx_text.installEventFilter(self)
        hl.addWidget(self._tx_text, 1)

        self._tx_mode = QComboBox()
        self._tx_mode.addItems(["Auto", "fldigi", "DSD+", "JS8Call"])
        self._tx_mode.setMaximumWidth(90)
        self._tx_mode.setToolTip("Route TX to: Auto=active decoder, fldigi, JS8Call")
        hl.addWidget(self._tx_mode)

        send_btn = QPushButton("Send")
        send_btn.setMinimumWidth(70)
        send_btn.setToolTip("Send text to active decoder bridge  (Enter)")
        send_btn.setStyleSheet(
            "QPushButton{background:#1a4a1a;color:#3fbe6f;"
            "border:1px solid #3fbe6f;border-radius:3px;padding:4px 10px;}"
            "QPushButton:hover{background:#2a6a2a;}")
        send_btn.clicked.connect(self._send_tx_text)
        hl.addWidget(send_btn)

        clr_btn = QPushButton("X")
        clr_btn.setMaximumWidth(28)
        clr_btn.setToolTip("Clear TX buffer")
        clr_btn.setStyleSheet(
            "QPushButton{background:#2a1010;color:#cc4444;"
            "border:1px solid #663333;border-radius:3px;}")
        clr_btn.clicked.connect(self._tx_text.clear)
        hl.addWidget(clr_btn)

        self._tx_status = QLabel("Ready")
        self._tx_status.setStyleSheet(f"color:{_t.fg_secondary};font-size:10px;min-width:80px;")
        hl.addWidget(self._tx_status)
        return bar

    def _build_macro_toolbar(self) -> "QFrame":
        """F1-F8 macro buttons. Right-click any button to edit label/text."""
        from PyQt6.QtWidgets import QFrame, QHBoxLayout, QPushButton
        from core.macros import MacroManager
        _t = get_theme(self.cfg.get("ui.theme", "Dark"))
        self._macro_mgr = MacroManager(self.cfg)
        bar = QFrame()
        bar.setFrameShape(QFrame.Shape.NoFrame)
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(6, 2, 6, 2)
        hl.setSpacing(4)
        self._macro_btns: list[QPushButton] = []
        for i, (key, macro) in enumerate(self._macro_mgr.all_macros(), start=1):
            btn = QPushButton(f"F{i}: {macro['label']}")
            tip_text = macro["text"] or "(empty — right-click to set)"
            btn.setToolTip(f"{tip_text}\n\nRight-click to edit label / text")
            btn.setFixedHeight(24)
            btn.setStyleSheet(
                f"QPushButton{{background:{_t.bg_alt};color:{_t.fg_primary};"
                f"border:1px solid {_t.border};border-radius:3px;font-size:10px;}}"
                f"QPushButton:hover{{background:{_t.header_bg};}}"
            )
            btn.clicked.connect(lambda _=False, k=key: self._on_macro_btn(k))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda pos, k=key, b=btn: self._edit_macro(k, b))
            self._macro_btns.append(btn)
            hl.addWidget(btn)
        hl.addStretch()
        return bar

    def _on_macro_btn(self, key: str) -> None:
        """Expand and send a macro."""
        macro = self._macro_mgr.get(key)
        text = self._macro_mgr.expand(macro["text"], auto_increment_serial=True)
        if text and hasattr(self, "_tx_text"):
            self._tx_text.setPlainText(text)
            self._send_tx_text()

    def _edit_macro(self, key: str, btn: "QPushButton") -> None:
        """Right-click handler — open inline edit dialog for a macro."""
        from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout,
                                      QLineEdit, QPlainTextEdit, QVBoxLayout)
        macro = self._macro_mgr.get(key)
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Edit macro {key.upper()}")
        dlg.setMinimumWidth(420)
        vl = QVBoxLayout(dlg)
        form = QFormLayout()
        lbl_edit = QLineEdit(macro["label"])
        txt_edit = QPlainTextEdit(macro["text"])
        txt_edit.setMaximumHeight(80)
        txt_edit.setPlaceholderText(
            "Use {mycall} {theircall} {freq} {mode} {serial} {name}")
        form.addRow("Label:", lbl_edit)
        form.addRow("Text:", txt_edit)
        vl.addLayout(form)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        vl.addWidget(bb)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            label = lbl_edit.text().strip() or key.upper()
            text  = txt_edit.toPlainText()
            self._macro_mgr.set(key, label, text)
            idx = int(key[1]) - 1  # f1 → 0
            btn.setText(f"F{idx+1}: {label}")
            btn.setToolTip(text or "(empty)")

    def eventFilter(self, obj, event):
        """Enter in TX box sends; Shift+Enter inserts newline."""
        from PyQt6.QtCore import QEvent, Qt
        if (obj is getattr(self, "_tx_text", None) and
                event.type() == QEvent.Type.KeyPress):
            if (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and
                    not (event.modifiers() &
                         Qt.KeyboardModifier.ShiftModifier)):
                self._send_tx_text()
                return True
        return super().eventFilter(obj, event)

    @staticmethod
    def _try_fldigi_send(txt: str) -> bool:
        try:
            from modes.fldigi_bridge import FldigiBridge
            bridge = FldigiBridge.instance()
            if bridge and bridge.is_connected:
                bridge.transmit(txt)
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _try_js8call_send(txt: str) -> bool:
        try:
            import socket, json as _json
            with socket.create_connection(("127.0.0.1", 2237), timeout=2) as s:
                s.sendall((_json.dumps(
                    {"type": "TX.SEND_MESSAGE", "value": txt, "params": {}}
                ) + "\n").encode())
            return True
        except Exception:
            pass
        return False

    def _send_tx_text(self):
        """Route TX box text to the active decoder bridge."""
        text = getattr(self, "_tx_text", None)
        if text is None:
            return
        txt = text.toPlainText().strip()
        if not txt:
            return
        try:
            from core.safety import get_app_state
            st = get_app_state()
            if st and getattr(st, "demo_mode", False):
                self._tx_status.setText("Blocked - Demo Mode")
                return
        except Exception:
            pass
        mode = self._tx_mode.currentText()
        sent = (mode in ("Auto", "fldigi") and self._try_fldigi_send(txt)) or \
               (mode in ("Auto", "JS8Call") and self._try_js8call_send(txt))
        if sent:
            self._tx_status.setText(f"Sent {len(txt)} chars")
            self._tx_text.clear()
        else:
            self._tx_status.setText("No active TX bridge")

    def _build_status_indicators(self, lay: "QHBoxLayout") -> None:
        _t = get_theme(self.cfg.get("ui.theme", "Dark"))
        self._decoder_lbl = QLabel("● No decoder running")
        self._decoder_lbl.setStyleSheet("font-family:'Courier New';")
        lay.addWidget(self._decoder_lbl)
        lay.addWidget(_vsep(_t.border))
        self._protocol_lbl = QLabel("—")
        self._protocol_lbl.setStyleSheet(
            f"color:{_t.accent};font-weight:bold;font-family:'Courier New';")
        lay.addWidget(self._protocol_lbl)
        lay.addWidget(_vsep(_t.border))
        self._tg_lbl = QLabel("TG: —")
        self._tg_lbl.setStyleSheet("font-family:'Courier New';")
        lay.addWidget(self._tg_lbl)
        lay.addWidget(_vsep(_t.border))
        self._enc_lbl = QLabel("")
        self._enc_lbl.setStyleSheet(f"color:{_t.error_color};font-weight:bold;")
        lay.addWidget(self._enc_lbl)

    def _build_status_audio_control(self, lay: "QHBoxLayout") -> None:
        lay.addStretch()
        self._route_lbl = QLabel("")
        self._route_lbl.setStyleSheet(
            "font-size:10px;font-family:'Courier New';color:#888;")
        lay.addWidget(self._route_lbl)
        lay.addWidget(_vsep())
        audio_in = (
            self.cfg.get("audio.digital_input", "") or "not set"
        ) if self.cfg else "—"
        self._audio_lbl = QLabel(f"🎙 {audio_in}")
        self._audio_lbl.setStyleSheet(
            "font-size:10px;font-family:'Courier New';"
            "color:#888;text-decoration:underline;cursor:pointer;")
        self._audio_lbl.setToolTip(
            "Decode audio input device\nClick to open Audio Settings")
        self._audio_lbl.mousePressEvent = lambda _: self._open_audio_settings()
        lay.addWidget(self._audio_lbl)
        lay.addWidget(_vsep())
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(55)
        clear_btn.setFixedHeight(24)
        clear_btn.clicked.connect(self._clear_log)
        lay.addWidget(clear_btn)

    def _build_status_bar(self) -> "QFrame":
        _t = get_theme(self.cfg.get("ui.theme", "Dark"))
        bar = QFrame()
        bar.setFixedHeight(36)
        bar.setStyleSheet(
            f"background:{_t.bg_secondary};border-bottom:1px solid {_t.border};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(12)
        self._build_status_indicators(lay)
        self._build_status_audio_control(lay)
        return bar

    def _build_decode_header(self) -> "QHBoxLayout":
        hdr = QHBoxLayout()
        title = QLabel("Digital Decode Log")
        title.setStyleSheet("font-weight:bold;")
        hdr.addWidget(title)
        hdr.addStretch()
        self._proto_filter = QComboBox()
        self._proto_filter.setToolTip(
            "Filter decoded calls by protocol\n"
            "All: show P25, DMR, NXDN, YSF, D-STAR")
        self._proto_filter.addItems(
            ["All protocols", "P25", "DMR", "NXDN", "YSF", "D-STAR"])
        self._proto_filter.setFixedWidth(130)
        self._proto_filter.currentTextChanged.connect(self._apply_filter)
        hdr.addWidget(self._proto_filter)
        self._hide_enc = QCheckBox("Hide encrypted")
        self._hide_enc.setToolTip(
            "Hide encrypted calls from the decode log\n"
            "Encrypted audio cannot be decoded")
        self._hide_enc.toggled.connect(self._apply_filter)
        hdr.addWidget(self._hide_enc)
        return hdr

    def _build_decode_table(self) -> "QTableWidget":
        _t = get_theme(self.cfg.get("ui.theme", "Dark"))
        t = QTableWidget(0, 6)
        t.setHorizontalHeaderLabels(
            ["Time", "Protocol", "TG/Dest", "Source", "Info", "Enc"])
        hv = t.horizontalHeader()
        hv.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hv.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setAlternatingRowColors(True)
        t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        t.setStyleSheet(
            f"QTableWidget{{background:{_t.bg_primary};gridline-color:{_t.border};"
            f"alternate-background-color:{_t.bg_alt};"
            f"font-family:'Courier New';border:1px solid {_t.border};}}"
            f"QHeaderView::section{{background:{_t.header_bg};border:none;padding:3px;}}")
        t.clicked.connect(self._on_row_click)
        return t

    def _build_decode_log(self) -> "QWidget":
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)
        lay.addLayout(self._build_decode_header())
        self._table = self._build_decode_table()
        lay.addWidget(self._table)
        self._no_decoder_msg = QLabel(
            "No digital voice decoder running.\n\n"
            "Windows: Launch DSD+ from the bar above\n"
            "Linux:   Launch OP25 from the bar above\n\n"
            "Audio routing:\n"
            "  SDR tab → Route to Digital tab\n"
            "  or IC-7100 USB audio → VB-Cable → DSD+")
        self._no_decoder_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_decoder_msg.setStyleSheet("")
        self._no_decoder_msg.setWordWrap(True)
        lay.addWidget(self._no_decoder_msg)
        return w

    def _build_active_call_panel(self) -> "QGroupBox":
        call_grp = QGroupBox("Active Call")
        cl = QVBoxLayout(call_grp)
        self._call_proto = QLabel("Protocol: —")
        self._call_tg    = QLabel("Talkgroup: —")
        self._call_src   = QLabel("Source: —")
        self._call_enc   = QLabel("")
        self._call_dur   = QLabel("Duration: —")
        for lbl in [self._call_proto, self._call_tg,
                    self._call_src, self._call_enc, self._call_dur]:
            lbl.setStyleSheet("font-family:'Courier New';")
            cl.addWidget(lbl)
        return call_grp

    def _build_protocol_info_panel(self) -> "QGroupBox":
        _t = get_theme(self.cfg.get("ui.theme", "Dark"))
        info_grp = QGroupBox("Protocol Reference")
        il = QVBoxLayout(info_grp)
        self._proto_selector = QComboBox()
        self._proto_selector.addItems(["P25", "DMR", "NXDN", "YSF", "D-STAR"])
        self._proto_selector.currentTextChanged.connect(self._show_protocol_info)
        il.addWidget(self._proto_selector)
        self._proto_info = QTextEdit()
        self._proto_info.setReadOnly(True)
        self._proto_info.setStyleSheet(
            f"background:{_t.bg_primary};font-family:'Courier New';"
            f"border:1px solid {_t.border};")
        self._proto_info.setMaximumHeight(200)
        il.addWidget(self._proto_info)
        return info_grp

    def _build_session_stats_panel(self) -> "QGroupBox":
        stats_grp = QGroupBox("Session Statistics")
        sl = QVBoxLayout(stats_grp)
        self._stats_lbl = QLabel("")
        self._stats_lbl.setStyleSheet("font-family:'Courier New';")
        sl.addWidget(self._stats_lbl)
        self._refresh_stats()
        return stats_grp

    def _refresh_stats(self) -> None:
        started = self._session_start.strftime("%H:%Mz")
        self._stats_lbl.setText(
            f"Calls decoded:    {self._stats['total']}\n"
            f"P25 calls:        {self._stats['P25']}\n"
            f"DMR calls:        {self._stats['DMR']}\n"
            f"Encrypted:        {self._stats['encrypted']}\n"
            f"Session started:  {started}"
        )

    def _build_info_panels(self) -> "QWidget":
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 6, 6, 6)
        lay.setSpacing(6)
        lay.addWidget(self._build_active_call_panel())
        lay.addWidget(self._build_protocol_info_panel())
        self._show_protocol_info("P25")
        lay.addWidget(self._build_session_stats_panel())
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
            audio_in = self.cfg.get("audio.digital_input", "") or "system default"
            self._set_decoder_status(
                f"DSD+ running  ·  input: {audio_in}", "#3fbe6f")
            self._no_decoder_msg.hide()
        elif status == "stopped":
            if self._active_backend == "dsdplus":
                self._active_backend = None
            self._set_decoder_status("DSD+ stopped", "#888")
            # Show helpful hint on unexpected stop
            self._no_decoder_msg.setText(
                "DSD+ stopped.\n\n"
                "Common causes:\n"
                "  • Wrong audio device — set in Settings → Audio → Decode Input\n"
                "  • Missing Visual C++ Redistributable (Windows)\n"
                "  • DSDPlus.cfg audio device index mismatch\n\n"
                "Check DSDPlus FMP/FMP folder for error logs.\n"
                "Audio routing: Settings → Audio → Decode Input")
            self._no_decoder_msg.show()
        elif status == "error":
            self._set_decoder_status(
                "DSD+ error — verify path in Settings → Paths", "#cc4444")

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

    def _update_statusbar_decode(self, event: "DecodeEvent", color: str) -> None:
        self._protocol_lbl.setText(event.protocol)
        self._protocol_lbl.setStyleSheet(
            f"color:{color};font-weight:bold;font-family:'Courier New';")
        self._tg_lbl.setText(f"TG: {event.talkgroup or '—'}")
        self._enc_lbl.setText("🔒 ENCRYPTED" if event.encrypted else "")

    def _update_call_panel_decode(self, event: "DecodeEvent") -> None:
        self._call_proto.setText(f"Protocol: {event.protocol}")
        self._call_tg.setText(f"Talkgroup: {event.talkgroup or '—'}")
        self._call_src.setText(f"Source: {event.source_id or '—'}")
        self._call_enc.setText(
            "🔒 Encrypted — audio unavailable" if event.encrypted else "")
        self._call_enc.setStyleSheet(
            "color:#cc4444;" if event.encrypted else "color:#3fbe6f;")

    def _add_decode_row(self, event: "DecodeEvent"):
        """Add a decode event to the table."""
        proto_filter = self._proto_filter.currentText()
        if proto_filter != "All protocols" and event.protocol != proto_filter:
            return
        if self._hide_enc.isChecked() and event.encrypted:
            return

        row = self._table.rowCount()
        if row > 500:
            self._table.removeRow(0)
            row = self._table.rowCount()
        self._table.insertRow(row)

        ts    = datetime.fromtimestamp(event.timestamp,
                                       tz=timezone.utc).strftime("%H:%M:%S")
        color = PROTOCOL_COLORS.get(event.protocol, "#555")
        cells = [ts, event.protocol, event.talkgroup or "—",
                 event.source_id or "—", event.raw_line[:60],
                 "🔒" if event.encrypted else ""]
        for col, val in enumerate(cells):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if col == 1:
                item.setForeground(QColor(color))
            self._table.setItem(row, col, item)
        self._table.scrollToBottom()

        self._update_statusbar_decode(event, color)
        self._update_call_panel_decode(event)
        self._no_decoder_msg.hide()

        # Live stats
        self._stats["total"] += 1
        self._stats[event.protocol] = self._stats.get(event.protocol, 0) + 1
        if event.encrypted:
            self._stats["encrypted"] += 1
        if hasattr(self, "_stats_lbl"):
            self._refresh_stats()

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

    def _open_audio_settings(self):
        """Open Settings dialog scrolled to Audio tab."""
        try:
            from ui.dialogs.settings_dialog import SettingsDialog
            dlg = SettingsDialog(self.cfg, parent=self.window())
            dlg._tabs.setCurrentIndex(1)   # Audio tab is index 1
            if dlg.exec():
                # Refresh audio label with new setting
                audio_in = self.cfg.get("audio.digital_input", "") or "not set"
                self._audio_lbl.setText(f"🎙 {audio_in}")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Open audio settings: {e}")

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
        _t = get_theme(self.cfg.get("ui.theme", "Dark"))
        self._route_lbl.setStyleSheet(f"color:{_t.accent};")


def _vsep(border: str = "#2a2a2a") -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setStyleSheet(f"color:{border};")
    f.setFixedWidth(1)
    return f
