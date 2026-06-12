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
import logging
from datetime import datetime, timezone

from ui.panel import SquelchPanel
from PyQt6.QtWidgets import (
    QTextEdit,
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QGroupBox, QFrame, QPushButton,
    QComboBox, QTextEdit, QLineEdit, QFormLayout,
    QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QSizePolicy, QCheckBox, QTreeWidget, QTreeWidgetItem)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

from ui.widgets.launch_bar import LaunchBar
from winlink.vara import VARAModem, VARAState
from winlink.templates import (
    TEMPLATE_LIST, TEMPLATE_CATEGORIES,
    ics213, ics214, winlink_wednesday,
    welfare, radiogram, WinlinkMessage)

log = logging.getLogger(__name__)

STATE_COLORS = {
    VARAState.DISCONNECTED: "#555555",
    VARAState.IDLE:         "#3fbe6f",
    VARAState.CONNECTING:   "#eeaa22",
    VARAState.CONNECTED:    "#44aaff",
    VARAState.BUSY:         "#ff8844",
    VARAState.ERROR:        "#cc4444",
}


def _vsep():
    """Vertical separator line."""
    from PyQt6.QtWidgets import QFrame
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setStyleSheet("color:#1a1a1a;")
    return f


class WinlinkTab(SquelchPanel, QWidget):
    panel_id    = "winlink"
    panel_title = "Winlink"

    def __init__(self, config, rig=None, parent=None):
        super().__init__(parent)
        self.cfg    = config
        self.rig    = rig
        self._vara_hf  = VARAModem(is_fm=False)
        self._vara_fm  = VARAModem(is_fm=True)
        self._running  = True
        self._compose_msg: WinlinkMessage = None

        # Wire VARA callbacks
        self._vara_hf.on_state(
            lambda s: QTimer.singleShot(0,
                lambda st=s: self._on_vara_state(st, "HF")))
        self._vara_fm.on_state(
            lambda s: QTimer.singleShot(0,
                lambda st=s: self._on_vara_state(st, "FM")))

        self._build()
        QTimer.singleShot(1000, self._check_vara_status)

    # ── Build ─────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Launch bar
        self._launch_bar = LaunchBar(
            "winlink", self.cfg,
            rescan_callback=self._check_vara_status)
        root.addWidget(self._launch_bar)

        # Status bar
        root.addWidget(self._build_status_bar())

        # Main content tabs
        self._tabs = QTabWidget()
        tabs = self._tabs
        tabs.addTab(self._build_compose_tab(),  "✉  Compose")
        tabs.addTab(self._build_vara_tab(),     "📡  VARA Status")
        tabs.addTab(self._build_gateway_tab(),  "🗼  Gateways")
        tabs.addTab(self._build_templates_tab(),"📋  Templates")
        root.addWidget(tabs, 1)

    def _build_status_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(36)
        bar.setStyleSheet(
            "background:#0d0d0d;"
            "border-bottom:1px solid #1a1a1a;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 4, 10, 4)

        self._hf_lbl = QLabel("VARA HF: ●  Disconnected")
        self._hf_lbl.setStyleSheet(
            ""
            "font-family:'Courier New';")
        lay.addWidget(self._hf_lbl)

        lay.addWidget(_vsep())

        self._fm_lbl = QLabel("VARA FM: ●  Disconnected")
        self._fm_lbl.setStyleSheet(
            ""
            "font-family:'Courier New';")
        lay.addWidget(self._fm_lbl)

        lay.addStretch()

        # Quick connect buttons
        hf_btn = QPushButton("Connect HF")
        hf_btn.setFixedHeight(24)
        hf_btn.setFixedWidth(90)
        hf_btn.setToolTip(
            "Connect to VARA HF modem\n"
            "VARA HF must be running first\n"
            "TCP port 8300 (control) / 8301 (data)")
        hf_btn.clicked.connect(self._connect_hf)
        lay.addWidget(hf_btn)

        fm_btn = QPushButton("Connect FM")
        fm_btn.setFixedHeight(24)
        fm_btn.setFixedWidth(90)
        fm_btn.setToolTip(
            "Connect to VARA FM modem\n"
            "VARA FM must be running first\n"
            "TCP port 8400 (control) / 8401 (data)")
        fm_btn.clicked.connect(self._connect_fm)
        lay.addWidget(fm_btn)

        return bar

    def _build_inbox_toolbar(self) -> "QHBoxLayout":
        tb = QHBoxLayout()
        folder_combo = QComboBox()
        folder_combo.addItems(
            ["📥 Inbox", "📤 Outbox",
             "📨 Sent", "📝 Drafts"])
        folder_combo.currentTextChanged.connect(
            self._refresh_inbox)
        self._folder_combo = folder_combo
        tb.addWidget(folder_combo)

        import_btn = QPushButton("📂 Import")
        import_btn.setToolTip(
            "Import messages from file\n"
            "Supports .b2f and text formats")
        import_btn.clicked.connect(self._import_messages)
        tb.addWidget(import_btn)

        delete_btn = QPushButton("🗑 Delete")
        delete_btn.setToolTip("Delete selected message")
        delete_btn.clicked.connect(self._delete_message)
        tb.addWidget(delete_btn)

        tb.addStretch()
        self._unread_lbl = QLabel("")
        self._unread_lbl.setStyleSheet("color:#3fbe6f;")
        tb.addWidget(self._unread_lbl)
        return tb

    def _build_inbox_message_list(self) -> "QTableWidget":
        t = QTableWidget(0, 4)
        t.setHorizontalHeaderLabels(
            ["From", "Subject", "Date", "Status"])
        h = t.horizontalHeader()
        h.setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        t.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        t.setAlternatingRowColors(True)
        t.setStyleSheet(
            "QTableWidget{background:#0a0a0a;"
            "border:1px solid #1a1a1a;"
            "alternate-background-color:#0d0d0d;}"
            "QHeaderView::section{background:#141414;"
            "border:none;}")
        t.clicked.connect(self._on_msg_select)
        t.doubleClicked.connect(self._on_msg_open)
        return t

    def _build_inbox_tab(self) -> "QWidget":
        """Inbox/Outbox for stored Winlink messages."""
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)

        lay.addLayout(self._build_inbox_toolbar())

        self._msg_list = self._build_inbox_message_list()
        lay.addWidget(self._msg_list, 1)

        self._msg_preview = QTextEdit()
        self._msg_preview.setReadOnly(True)
        self._msg_preview.setMaximumHeight(160)
        self._msg_preview.setStyleSheet(
            "background:#0a0a0a;"
            "font-family:'Courier New';"
            "border:1px solid #1a1a1a;")
        self._msg_preview.setPlaceholderText(
            "Click a message to preview it here…")
        lay.addWidget(self._msg_preview)
        return w

    def _refresh_inbox(self, _=None):
        """Reload message list from store."""
        folder_text = self._folder_combo.currentText()
        folder_map  = {
            "📥 Inbox":  "inbox",
            "📤 Outbox": "outbox",
            "📨 Sent":   "sent",
            "📝 Drafts": "drafts",
        }
        folder = folder_map.get(folder_text, "inbox")
        msgs   = self._msg_store.folder(folder)

        self._msg_list.setRowCount(0)
        for msg in sorted(msgs,
                          key=lambda m: m.date_utc,
                          reverse=True):
            row = self._msg_list.rowCount()
            self._msg_list.insertRow(row)
            bold = msg.status == "unread"
            for col, val in enumerate([
                    msg.from_ or "(unknown)",
                    msg.subject,
                    msg.date_utc[:16],
                    msg.status]):
                item = QTableWidgetItem(val)
                if bold:
                    from PyQt6.QtGui import QFont
                    f = item.font()
                    f.setBold(True)
                    item.setFont(f)
                self._msg_list.setItem(row, col, item)
                # Store mid in first column
                if col == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        msg.mid)

        unread = self._msg_store.unread_count
        if unread:
            self._unread_lbl.setText(
                f"{unread} unread")
        else:
            self._unread_lbl.setText("")

    def _on_msg_select(self, index):
        row = index.row()
        mid_item = self._msg_list.item(row, 0)
        if not mid_item:
            return
        mid = mid_item.data(Qt.ItemDataRole.UserRole)
        msg = self._msg_store.get(mid)
        if not msg:
            return
        self._msg_store.mark_read(mid)
        self._msg_preview.setPlainText(
            f"From:    {msg.from_}\n"
            f"To:      {msg.to}\n"
            f"Subject: {msg.subject}\n"
            f"Date:    {msg.date_utc}\n"
            f"Status:  {msg.status}\n"
            f"{'─'*40}\n"
            f"{msg.body}")
        self._refresh_inbox()

    def _on_msg_open(self, index):
        """Open message in compose tab for reply."""
        row = index.row()
        mid_item = self._msg_list.item(row, 0)
        if not mid_item:
            return
        mid = mid_item.data(Qt.ItemDataRole.UserRole)
        msg = self._msg_store.get(mid)
        if not msg:
            return
        # Pre-fill compose tab for reply
        self._to_edit.setText(msg.from_)
        self._subj_edit.setText(
            f"Re: {msg.subject}")
        self._body_edit.setPlainText(
            f"\n\n--- Original message ---\n"
            f"{msg.body[:500]}")
        self._tabs.setCurrentIndex(1)  # Compose tab

    def _delete_message(self):
        rows = self._msg_list.selectedItems()
        if not rows:
            return
        mid = rows[0].data(Qt.ItemDataRole.UserRole)
        self._msg_store.delete(mid)
        self._msg_preview.clear()
        self._refresh_inbox()

    def _import_messages(self):
        from PyQt6.QtWidgets import QFileDialog
        from pathlib import Path as _Path
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Winlink Messages",
            "",
            "Message Files (*.b2f *.txt *.msg *.mbox)"
            "All Files (*)")
        if not path:
            return
        count = self._msg_store.import_adif_message(
            _Path(path))
        if count:
            self._refresh_inbox()
            QMessageBox.information(
                self, "Import Complete",
                f"Imported {count} message(s).")
        else:
            QMessageBox.warning(
                self, "Import",
                "No messages found in file.\n"
                "Supported: plain text, mbox format.")

    def _build_compose_tab(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        # Address bar
        form = QFormLayout()
        self._to_edit = QLineEdit()
        self._to_edit.setPlaceholderText(
            "callsign@winlink.org or gateway callsign")
        form.addRow("To:", self._to_edit)

        self._subj_edit = QLineEdit()
        self._subj_edit.setPlaceholderText("Subject")
        form.addRow("Subject:", self._subj_edit)

        lay.addLayout(form)

        # Body
        self._body_edit = QTextEdit()
        self._body_edit.setPlaceholderText(
            "Message body…\n\n"
            "Use the Templates tab to load an EmComm template.")
        self._body_edit.setFont(
            QFont("Courier New", 11))
        lay.addWidget(self._body_edit, 1)

        # Action buttons
        btn_row = QHBoxLayout()

        via_lbl = QLabel("Via:")
        btn_row.addWidget(via_lbl)
        self._via_combo = QComboBox()
        self._via_combo.setToolTip(
            "Select how to send the message\n"
            "VARA HF: HF radio (long distance)\n"
            "VARA FM: VHF/UHF to local gateway\n"
            "Pat: open-source client (auto-selects)")
        self._via_combo.addItems([
            "VARA HF", "VARA FM", "Pat (auto)", "RMS Express"])
        self._via_combo.setFixedWidth(130)
        btn_row.addWidget(self._via_combo)

        btn_row.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_compose)
        btn_row.addWidget(clear_btn)

        send_btn = QPushButton("📤  Send")
        send_btn.setStyleSheet(
            "background:#1a3a1a;color:#3fbe6f;"
            "border:1px solid #3fbe6f;border-radius:4px;"
            "padding:4px 16px;")
        send_btn.setToolTip(
            "Send message via selected modem\n"
            "VARA must be connected and a gateway selected")
        send_btn.clicked.connect(self._send_message)
        btn_row.addWidget(send_btn)
        lay.addLayout(btn_row)

        # Info strip
        info = QLabel(
            "Winlink delivers messages even when internet is down. "
            "Messages route through RF gateways to the Winlink network.")
        info.setWordWrap(True)
        info.setStyleSheet("")
        lay.addWidget(info)

        return w

    def _build_vara_tab(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # VARA HF panel
        hf_grp = QGroupBox("VARA HF")
        hl = QFormLayout(hf_grp)
        self._hf_state_lbl  = QLabel("Disconnected")
        self._hf_ver_lbl    = QLabel("—")
        self._hf_bw_combo   = QComboBox()
        self._hf_bw_combo.addItems(
            ["200 Hz", "500 Hz", "2300 Hz", "2750 Hz"])
        self._hf_bw_combo.setCurrentText("500 Hz")
        hl.addRow("Status:", self._hf_state_lbl)
        hl.addRow("Version:", self._hf_ver_lbl)
        hl.addRow("Bandwidth:", self._hf_bw_combo)

        hf_btns = QHBoxLayout()
        hf_conn = QPushButton("Connect")
        hf_conn.clicked.connect(self._connect_hf)
        hf_disc = QPushButton("Disconnect")
        hf_disc.clicked.connect(self._vara_hf.disconnect)
        hf_btns.addWidget(hf_conn)
        hf_btns.addWidget(hf_disc)
        hl.addRow("", hf_btns)
        lay.addWidget(hf_grp)

        # VARA FM panel
        fm_grp = QGroupBox("VARA FM")
        fl = QFormLayout(fm_grp)
        self._fm_state_lbl = QLabel("Disconnected")
        self._fm_ver_lbl   = QLabel("—")
        fl.addRow("Status:", self._fm_state_lbl)
        fl.addRow("Version:", self._fm_ver_lbl)

        fm_btns = QHBoxLayout()
        fm_conn = QPushButton("Connect")
        fm_conn.clicked.connect(self._connect_fm)
        fm_disc = QPushButton("Disconnect")
        fm_disc.clicked.connect(self._vara_fm.disconnect)
        fm_btns.addWidget(fm_conn)
        fm_btns.addWidget(fm_disc)
        fl.addRow("", fm_btns)
        lay.addWidget(fm_grp)

        lay.addWidget(QLabel(
            "VARA must be launched first (use the launch bar above).\n"
            "VARA HF: TCP port 8300    VARA FM: TCP port 8400"))

        lay.addStretch()
        return w

    def _build_gateway_tab(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("RMS Gateways near your location:"))
        hdr.addStretch()
        refresh = QPushButton("↺ Refresh")
        refresh.setFixedWidth(80)
        refresh.clicked.connect(self._refresh_gateways)
        hdr.addWidget(refresh)
        lay.addLayout(hdr)

        self._gw_table = QTableWidget(0, 5)
        self._gw_table.setHorizontalHeaderLabels([
            "Callsign", "Frequency", "Mode",
            "Distance", "Last Heard"])
        h = self._gw_table.horizontalHeader()
        h.setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._gw_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._gw_table.setAlternatingRowColors(True)
        self._gw_table.setStyleSheet(
            "QTableWidget{background:#0a0a0a;"
            "font-family:'Courier New';"
            "alternate-background-color:#0d0d0d;"
            "border:1px solid #1a1a1a;}"
            "QHeaderView::section{background:#141414;"
            "border:none;}")
        lay.addWidget(self._gw_table)

        note = QLabel(
            "Gateway data from Winlink network (requires internet).\n"
            "Select a gateway and click the compose tab to connect.")
        note.setStyleSheet("")
        lay.addWidget(note)
        return w

    def _build_p2p_connection_group(self) -> QGroupBox:
        """QGroupBox with callsign/frequency/mode fields and connect button."""
        conn_grp = QGroupBox("P2P Connection")
        cgl = QFormLayout(conn_grp)
        cgl.setSpacing(8)

        self._p2p_call = QLineEdit()
        self._p2p_call.setPlaceholderText(
            "e.g. W4XYZ  (other station callsign)")
        self._p2p_call.setMaxLength(12)
        self._p2p_call.setToolTip(
            "Callsign of the station you want to connect to\n"
            "They must be on the same frequency and have VARA running")
        cgl.addRow("Their Callsign:", self._p2p_call)

        self._p2p_freq = QLineEdit()
        self._p2p_freq.setPlaceholderText("e.g. 14.109.0")
        self._p2p_freq.setToolTip(
            "Agreed frequency in MHz\n"
            "Common P2P frequencies: 14.109.0 (20m), "
            "7.171.0 (40m), 3.601.0 (80m)")
        cgl.addRow("Frequency (MHz):", self._p2p_freq)

        self._p2p_mode = QComboBox()
        self._p2p_mode.addItems([
            "VARA HF  (HF radio, 1 kHz - 30 MHz)",
            "VARA FM  (VHF/UHF, 2m/70cm)"])
        cgl.addRow("Mode:", self._p2p_mode)

        p2p_conn_btn = QPushButton("🔗 Connect P2P")
        p2p_conn_btn.setToolTip(
            "Initiate a peer-to-peer Winlink session\n"
            "Other station must be listening on same frequency")
        p2p_conn_btn.clicked.connect(self._connect_p2p)
        cgl.addRow("", p2p_conn_btn)
        return conn_grp

    def _build_p2p_message_group(self) -> QGroupBox:
        """QGroupBox with subject, body, template selector, and send button."""
        msg_grp = QGroupBox("P2P Message")
        mgl = QVBoxLayout(msg_grp)

        mf = QFormLayout()
        self._p2p_subj = QLineEdit()
        self._p2p_subj.setPlaceholderText("Message subject")
        mf.addRow("Subject:", self._p2p_subj)
        mgl.addLayout(mf)

        self._p2p_body = QTextEdit()
        self._p2p_body.setPlaceholderText(
            "Type your message here…\n\n"
            "P2P messages go directly to the other station\n"
            "without passing through any Winlink server.")
        self._p2p_body.setMinimumHeight(120)
        self._p2p_body.setStyleSheet(
            "background:#0a0a0a;border:1px solid #1a1a1a;")
        mgl.addWidget(self._p2p_body)

        tmpl_row = QHBoxLayout()
        tmpl_row.addWidget(QLabel("From template:"))
        self._p2p_tmpl = QComboBox()
        self._p2p_tmpl.addItem("— select —")
        try:
            from winlink.templates import TEMPLATE_LIST
            for name, _fn, _desc in TEMPLATE_LIST:
                self._p2p_tmpl.addItem(name)
        except Exception:
            pass
        self._p2p_tmpl.currentTextChanged.connect(self._p2p_load_template)
        tmpl_row.addWidget(self._p2p_tmpl, 1)
        mgl.addLayout(tmpl_row)

        p2p_send_btn = QPushButton("📤 Queue for P2P Send")
        p2p_send_btn.setToolTip(
            "Queue message to send when P2P connection opens")
        p2p_send_btn.clicked.connect(self._queue_p2p_message)
        mgl.addWidget(p2p_send_btn)
        return msg_grp

    def _build_p2p_tab(self) -> QWidget:
        """
        Peer-to-peer messaging — direct station-to-station
        without going through an RMS gateway.
        Both stations must have a common frequency and
        compatible modem (VARA HF or VARA FM).
        """
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        info = QLabel(
            "📡  Peer-to-peer Winlink — direct station-to-station, "
            "no gateway required. "
            "Both stations tune to the same frequency and initiate "
            "from their respective Winlink clients.")
        info.setWordWrap(True)
        info.setStyleSheet(
            "background:#0d0d0d;padding:8px;"
            "border:1px solid #1a1a1a;border-radius:4px;")
        lay.addWidget(info)
        lay.addWidget(self._build_p2p_connection_group())
        lay.addWidget(self._build_p2p_message_group())

        ref = QLabel(
            "Common P2P frequencies:\n"
            "  80m:   3.601.0 MHz   (night/regional)\n"
            "  40m:   7.171.0 MHz   (regional)\n"
            "  20m:  14.109.0 MHz   (day/long-distance)\n"
            "  17m:  18.109.0 MHz\n"
            "  2m:  144.990 MHz     (local, VARA FM)")
        ref.setStyleSheet(
            "font-family:'Courier New';"
            "background:#080808;padding:8px;"
            "border:1px solid #111;border-radius:3px;")
        lay.addWidget(ref)
        lay.addStretch()
        return w

    def _connect_p2p(self):
        """Initiate P2P connection to another station."""
        call = self._p2p_call.text().strip().upper()
        freq = self._p2p_freq.text().strip()
        if not call:
            QMessageBox.warning(
                self, "P2P Connect",
                "Enter the other station's callsign.")
            return
        mode_text = self._p2p_mode.currentText()
        is_fm     = "FM" in mode_text
        port      = 8400 if is_fm else 8300
        QMessageBox.information(
            self, "P2P Connect",
            f"P2P to {call} on {freq} MHz via "
            f"{'VARA FM' if is_fm else 'VARA HF'}\n\n"
            f"In VARA: select 'Connect P2P'\n"
            f"Enter call: {call}\n"
            f"Frequency: {freq} MHz\n\n"
            f"Squelch VARA port: {port}")

    def _p2p_load_template(self, name: str):
        """Load selected template into P2P body."""
        if name.startswith("—"):
            return
        try:
            from winlink.templates import TEMPLATE_LIST
            cs = self.cfg.callsign if self.cfg else ""
            for tname, fn, _ in TEMPLATE_LIST:
                if tname == name:
                    msg = fn(my_callsign=cs)
                    self._p2p_subj.setText(msg.subject)
                    self._p2p_body.setPlainText(msg.body)
                    break
        except Exception as e:
            log.debug(f"P2P template: {e}")

    def _queue_p2p_message(self):
        """Add message to P2P outbox."""
        call = self._p2p_call.text().strip().upper()
        subj = self._p2p_subj.text().strip()
        body = self._p2p_body.toPlainText().strip()
        if not call or not body:
            QMessageBox.warning(
                self, "P2P Message",
                "Enter callsign and message body.")
            return
        from winlink.message_store import (
            get_message_store, WinlinkMsg)
        import time
        store = get_message_store()
        msg   = WinlinkMsg(
            mid      = f"p2p_{int(time.time())}",
            folder   = "outbox",
            to       = call,
            from_    = self.cfg.callsign if self.cfg else "",
            subject  = subj or f"P2P - {call}",
            body     = body,
            date_utc = "",
            status   = "pending",
            via      = "P2P")
        store.add(msg)
        QMessageBox.information(
            self, "P2P Queued",
            f"Message queued for {call}.\n"
            f"It will be sent when P2P connection opens.")
        self._p2p_body.clear()
        self._p2p_subj.clear()

    def _build_tmpl_tree(self) -> "QWidget":
        """Left panel: category/template tree."""
        left = QWidget()
        left.setMaximumWidth(220)
        ll   = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(QLabel("Templates"))
        self._tmpl_tree = QTreeWidget()
        self._tmpl_tree.setHeaderHidden(True)
        self._tmpl_tree.setStyleSheet(
            "QTreeWidget{background:#080808;border:1px solid #1a1a1a;}"
            "QTreeWidget::item:selected{background:#1a2a1a;color:#3fbe6f;}")
        self._tmpl_tree.currentItemChanged.connect(self._on_tmpl_select)
        ll.addWidget(self._tmpl_tree, 1)
        try:
            from winlink.templates import TEMPLATE_CATEGORIES
            for cat in TEMPLATE_CATEGORIES:
                cat_item = QTreeWidgetItem([f"{cat.icon}  {cat.name}"])
                cat_item.setForeground(0, QColor("#3fbe6f"))
                for name, fn, desc in cat.templates:
                    t_item = QTreeWidgetItem([name])
                    t_item.setData(0, Qt.ItemDataRole.UserRole, (fn, desc))
                    t_item.setToolTip(0, desc)
                    cat_item.addChild(t_item)
                self._tmpl_tree.addTopLevelItem(cat_item)
                cat_item.setExpanded(True)
        except Exception as e:
            log.debug(f"Template tree: {e}")
        return left

    def _build_tmpl_preview_panel(self) -> "QWidget":
        """Right panel: description, preview, insert button."""
        right = QWidget()
        rl    = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self._tmpl_desc = QLabel("Select a template →")
        self._tmpl_desc.setStyleSheet("")
        rl.addWidget(self._tmpl_desc)
        self._tmpl_preview = QTextEdit()
        self._tmpl_preview.setReadOnly(True)
        self._tmpl_preview.setStyleSheet(
            "background:#080808;font-family:'Courier New';"
            "border:1px solid #1a1a1a;")
        rl.addWidget(self._tmpl_preview, 1)
        insert_btn = QPushButton("📋 Insert into Compose")
        insert_btn.setToolTip(
            "Copy this template into the Compose tab\n"
            "Edit the fields there before sending")
        insert_btn.clicked.connect(self._insert_template)
        rl.addWidget(insert_btn)
        return right

    def _build_templates_tab(self) -> "QWidget":
        """Template library — category tree on left, preview on right."""
        w   = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(6)
        lay.addWidget(self._build_tmpl_tree())
        lay.addWidget(self._build_tmpl_preview_panel(), 1)
        self._current_tmpl_fn = None
        return w

    def _on_tmpl_select(self, item, prev=None):
        """Preview selected template."""
        if item is None:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        fn, desc = data
        self._current_tmpl_fn = fn
        self._tmpl_desc.setText(desc)
        try:
            cs  = self.cfg.callsign if self.cfg else ""
            msg = fn(my_callsign=cs)
            preview = (
                f"To:      {msg.to}\n"
                f"Subject: {msg.subject}\n"
                f"{'─'*40}\n"
                f"{msg.body}")
            self._tmpl_preview.setPlainText(preview)
        except Exception as e:
            self._tmpl_preview.setPlainText(
                f"[Preview error: {e}]")


    # ── Missing methods added (QA gate caught these) ──────────────────────

    def _connect_hf(self):
        """Connect VARA HF modem to the configured RMS gateway."""
        try:
            self._vara_hf.connect()
            self._set_status("VARA HF connecting…", "#ee8822")
        except Exception as e:
            self._set_status(f"VARA HF connect failed: {e}", "#ee4444")

    def _connect_fm(self):
        """Connect VARA FM modem to the configured RMS gateway."""
        try:
            self._vara_fm.connect()
            self._set_status("VARA FM connecting…", "#ee8822")
        except Exception as e:
            self._set_status(f"VARA FM connect failed: {e}", "#ee4444")

    def _clear_compose(self):
        """Clear the compose form."""
        try:
            self._to_edit.clear()
            self._subj_edit.clear()
            self._body_edit.clear()
        except Exception:
            pass

    def _send_message(self):
        """Queue and send the composed message via the selected modem."""
        try:
            to   = self._to_edit.text().strip()
            subj = self._subj_edit.text().strip()
            body = self._body_edit.toPlainText().strip()
            via  = self._via_combo.currentText() if hasattr(
                self, "_via_combo") else "VARA HF"
            if not to or not subj:
                self._set_status(
                    "Fill in To: and Subject: before sending.", "#ee4444")
                return
            modem = self._vara_fm if "FM" in via else self._vara_hf
            if not getattr(modem, "is_connected", False):
                self._set_status(
                    f"{via} not connected — connect first "
                    "in the VARA Status tab.", "#ee4444")
                return
            modem.send_message(to=to, subject=subj, body=body)
            self._set_status(f"Message queued → {to}", "#3fbe6f")
            self._clear_compose()
        except Exception as e:
            self._set_status(f"Send failed: {e}", "#ee4444")

    def _refresh_gateways(self):
        """Fetch RMS gateway list near the operator's location."""
        import threading
        self._set_status("Fetching gateways…", "#888888")
        try:
            lat = self.cfg.get("location.lat", 0.0)
            lon = self.cfg.get("location.lon", 0.0)
        except Exception:
            lat, lon = 0.0, 0.0

        def _fetch():
            try:
                from winlink.gateways import fetch_rms_gateways
                gws = fetch_rms_gateways(lat, lon)
            except Exception:
                gws = []
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._populate_gateways(gws))
        threading.Thread(target=_fetch, daemon=True,
                         name="GWFetch").start()

    def _populate_gateways(self, gateways: list):
        """Fill the gateway table with fetched data."""
        try:
            self._gw_table.setRowCount(0)
            for gw in gateways:
                r = self._gw_table.rowCount()
                self._gw_table.insertRow(r)
                from PyQt6.QtWidgets import QTableWidgetItem
                for col, val in enumerate([
                    gw.get("callsign", ""),
                    gw.get("frequency", ""),
                    gw.get("mode", ""),
                    gw.get("distance", ""),
                    gw.get("last_heard", ""),
                ]):
                    self._gw_table.setItem(
                        r, col, QTableWidgetItem(str(val)))
            if gateways:
                self._set_status(
                    f"{len(gateways)} gateways found", "#3fbe6f")
            else:
                self._set_status(
                    "No gateways found (check location settings)",
                    "#888888")
        except Exception as e:
            self._set_status(f"Gateway list error: {e}", "#ee4444")

    def _on_vara_state(self, state: str, label: str = ""):
        """Called when VARA modem reports a state change."""
        self._set_status(state)
        connected = state.lower() in ('connected', 'linked')
        for btn in getattr(self, '_tx_buttons', []):
            try:
                btn.setEnabled(connected)
            except RuntimeError:
                pass

    def _check_vara_status(self):
        """Poll VARA modem state every 5s and update the status indicator.
        DO NOT REMOVE — called from __init__ via QTimer; app crashes without it."""
        try:
            hf_ok = getattr(self._vara_hf, "is_connected", False)
            fm_ok = getattr(self._vara_fm, "is_connected", False)
            if callable(hf_ok):
                hf_ok = hf_ok()
            if callable(fm_ok):
                fm_ok = fm_ok()
            if hf_ok:
                self._set_status("VARA HF connected", "#3fbe6f")
            elif fm_ok:
                self._set_status("VARA FM connected", "#3fbe6f")
            else:
                self._set_status("Not connected", "#777777")
        except Exception:
            pass
        if getattr(self, "_running", True):
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(5000, self._check_vara_status)

    def _set_status(self, msg: str, color: str = "#888888"):
        """Update the VARA connection status label."""
        lbl = getattr(self, '_status_lbl', None)
        if lbl is None:
            return
        try:
            lbl.setText(msg)
            lbl.setStyleSheet(f"color:{color};")
        except RuntimeError:
            pass

    def _insert_template(self):
        """Insert selected template into Compose tab."""
        if not self._current_tmpl_fn:
            return
        try:
            cs  = self.cfg.callsign if self.cfg else ""
            msg = self._current_tmpl_fn(my_callsign=cs)
            self._to_edit.setText(msg.to)
            self._subj_edit.setText(msg.subject)
            self._body_edit.setPlainText(msg.body)
            # Switch to Compose tab
            parent = self._tabs
            for i in range(parent.count()):
                if "Compose" in parent.tabText(i):
                    parent.setCurrentIndex(i)
                    break
        except Exception as e:
            QMessageBox.warning(
                self, "Template Error",
                f"Could not insert template:\n{e}")


