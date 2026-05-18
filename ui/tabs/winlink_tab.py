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
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- ui/tabs/winlink_tab.py
Winlink / VARA tab.
VARA HF + FM modem status and control.
Pat and RMS Express launch.
ARES EmComm message templates.
RMS gateway selection by band/distance.
"""

import logging
from datetime import datetime, timezone

from PyQt6.QtWidgets import (
    QTextEdit,
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QGroupBox, QFrame, QPushButton,
    QComboBox, QTextEdit, QLineEdit, QFormLayout,
    QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QSizePolicy, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from ui.widgets.launch_bar import LaunchBar
from winlink.vara import VARAModem, VARAState
from winlink.templates import (
    TEMPLATE_LIST, ics213, ics214,
    winlink_wednesday, welfare_message, radiogram,
    WinlinkMessage)

log = logging.getLogger(__name__)

STATE_COLORS = {
    VARAState.DISCONNECTED: "#555555",
    VARAState.IDLE:         "#3fbe6f",
    VARAState.CONNECTING:   "#eeaa22",
    VARAState.CONNECTED:    "#44aaff",
    VARAState.BUSY:         "#ff8844",
    VARAState.ERROR:        "#cc4444",
}


class WinlinkTab(QWidget):
    def __init__(self, config, rig=None, parent=None):
        super().__init__(parent)
        self.cfg    = config
        self.rig    = rig
        self._vara_hf = VARAModem(is_fm=False)
        self._vara_fm = VARAModem(is_fm=True)
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
        tabs = QTabWidget()
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
            "color:#555;font-size:13px;"
            "font-family:'Courier New';")
        lay.addWidget(self._hf_lbl)

        lay.addWidget(_vsep())

        self._fm_lbl = QLabel("VARA FM: ●  Disconnected")
        self._fm_lbl.setStyleSheet(
            "color:#555;font-size:13px;"
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

    def _build_inbox_tab(self) -> QWidget:
        """Inbox/Outbox for stored Winlink messages."""
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)

        # Toolbar
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
        self._unread_lbl.setStyleSheet(
            "color:#3fbe6f;font-size:12px;")
        tb.addWidget(self._unread_lbl)
        lay.addLayout(tb)

        # Message list
        self._msg_list = QTableWidget(0, 4)
        self._msg_list.setHorizontalHeaderLabels([
            "From", "Subject", "Date", "Status"])
        h = self._msg_list.horizontalHeader()
        h.setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self._msg_list.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._msg_list.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self._msg_list.setAlternatingRowColors(True)
        self._msg_list.setStyleSheet(
            "QTableWidget{background:#0a0a0a;color:#aaa;"
            "font-size:12px;border:1px solid #1a1a1a;"
            "alternate-background-color:#0d0d0d;}"
            "QHeaderView::section{background:#141414;"
            "color:#666;border:none;font-size:12px;}")
        self._msg_list.clicked.connect(
            self._on_msg_select)
        self._msg_list.doubleClicked.connect(
            self._on_msg_open)
        lay.addWidget(self._msg_list, 1)

        # Preview pane
        self._msg_preview = QTextEdit()
        self._msg_preview.setReadOnly(True)
        self._msg_preview.setMaximumHeight(160)
        self._msg_preview.setStyleSheet(
            "background:#0a0a0a;color:#aaa;"
            "font-size:12px;font-family:'Courier New';"
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
            ";;All Files (*)")
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
            "font-size:13px;padding:4px 16px;")
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
        info.setStyleSheet("color:#444;font-size:12px;")
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
            "QTableWidget{background:#0a0a0a;color:#aaa;"
            "font-size:12px;font-family:'Courier New';"
            "alternate-background-color:#0d0d0d;"
            "border:1px solid #1a1a1a;}"
            "QHeaderView::section{background:#141414;"
            "color:#555;border:none;font-size:12px;}")
        lay.addWidget(self._gw_table)

        note = QLabel(
            "Gateway data from Winlink network (requires internet).\n"
            "Select a gateway and click the compose tab to connect.")
        note.setStyleSheet("color:#444;font-size:12px;")
        lay.addWidget(note)
        return w

    def _build_templates_tab(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        lay.addWidget(QLabel(
            "Select a template — it will pre-fill the Compose tab."))

        for name, desc in TEMPLATE_LIST:
            btn = QPushButton(f"  {name}")
            btn.setToolTip(desc)
            btn.setFixedHeight(34)
            btn.setStyleSheet(
                "QPushButton{text-align:left;"
                "padding:4px 12px;"
                "background:#0d0d0d;"
                "border:1px solid #1a1a1a;"
                "border-radius:3px;color:#aaa;}"
                "QPushButton:hover{"
                "background:#141414;color:#3fbe6f;"
                "border-color:#3fbe6f;}")
            btn.clicked.connect(
                lambda checked, n=name:
                    self._load_template(n))
            lay.addWidget(btn)

        lay.addStretch()

        # EmComm reference
        ref = QLabel(
            "EmComm notes:\n"
            "ICS-213 — Point-to-point messages between stations\n"
            "ICS-214 — Activity log submitted to EOC each period\n"
            "Radiogram — NTS traffic (welfare/priority)\n"
            "Winlink Wednesday — Weekly activity check-in\n"
            "Welfare — Let family know you're safe")
        ref.setStyleSheet(
            "color:#444;font-size:12px;"
            "font-family:'Courier New';")
        ref.setWordWrap(True)
        lay.addWidget(ref)
        return w

    # ── Actions ───────────────────────────────────────────────

    def _connect_hf(self):
        self._vara_hf.set_callsign(self.cfg.callsign)
        ok = self._vara_hf.connect()
        if ok:
            bw_text = self._hf_bw_combo.currentText()
            hz = int(bw_text.replace(" Hz", ""))
            self._vara_hf.set_bandwidth(hz)
        else:
            QMessageBox.warning(
                self, "VARA HF",
                "Could not connect to VARA HF.\n\n"
                "Make sure VARA HF is running.\n"
                "Use the launch bar above to start it.")

    def _connect_fm(self):
        self._vara_fm.set_callsign(self.cfg.callsign)
        ok = self._vara_fm.connect()
        if not ok:
            QMessageBox.warning(
                self, "VARA FM",
                "Could not connect to VARA FM.\n\n"
                "Make sure VARA FM is running.\n"
                "Use the launch bar above to start it.")

    def _on_vara_state(self, state: VARAState,
                        modem: str):
        color = STATE_COLORS.get(state, "#555")
        text  = f"VARA {modem}: ●  {state.value}"
        if modem == "HF":
            self._hf_lbl.setText(text)
            self._hf_lbl.setStyleSheet(
                f"color:{color};font-size:13px;"
                "font-family:'Courier New';")
            self._hf_state_lbl.setText(state.value)
            self._hf_state_lbl.setStyleSheet(
                f"color:{color};")
        else:
            self._fm_lbl.setText(text)
            self._fm_lbl.setStyleSheet(
                f"color:{color};font-size:13px;"
                "font-family:'Courier New';")
            self._fm_state_lbl.setText(state.value)
            self._fm_state_lbl.setStyleSheet(
                f"color:{color};")

    def _check_vara_status(self):
        if VARAModem.is_running(is_fm=False):
            self._hf_lbl.setText(
                "VARA HF: ●  Running (not connected)")
            self._hf_lbl.setStyleSheet(
                "color:#888;font-size:13px;"
                "font-family:'Courier New';")
        if VARAModem.is_running(is_fm=True):
            self._fm_lbl.setText(
                "VARA FM: ●  Running (not connected)")
            self._fm_lbl.setStyleSheet(
                "color:#888;font-size:13px;"
                "font-family:'Courier New';")

    def _send_message(self):
        to   = self._to_edit.text().strip()
        subj = self._subj_edit.text().strip()
        body = self._body_edit.toPlainText().strip()

        if not to or not body:
            QMessageBox.warning(
                self, "Missing Fields",
                "Please fill in the To and message body.")
            return

        via = self._via_combo.currentText()
        QMessageBox.information(
            self, "Message Queued",
            f"Message to {to} queued via {via}.\n\n"
            f"Subject: {subj}\n\n"
            f"Winlink send integration coming in v0.8.0.\n"
            f"For now, use Pat or RMS Express to send.\n"
            f"Launch from the bar above.")

    def _clear_compose(self):
        self._to_edit.clear()
        self._subj_edit.clear()
        self._body_edit.clear()

    def _load_template(self, name: str):
        """Load a template into the compose tab."""
        cs    = self.cfg.callsign or "N0CALL"
        grid  = self.cfg.grid or "AA00"
        city  = self.cfg.get("location.city", "")
        state = self.cfg.get("location.state", "")

        msg = None
        if name == "ICS-213 General Message":
            msg = ics213(
                incident    = "Exercise / Incident",
                from_name   = cs,
                from_pos    = "Radio Operator",
                to_name     = "EOC",
                to_pos      = "Emergency Coordinator",
                message     = "(enter your message here)",
                my_callsign = cs)
        elif name == "ICS-214 Activity Log":
            msg = ics214(
                incident    = "Exercise / Incident",
                unit_name   = cs,
                unit_leader = cs,
                period      = "0000-2359",
                activities  = ["(describe activities here)"],
                personnel   = [cs],
                my_callsign = cs)
        elif name == "Winlink Wednesday Check-in":
            msg = winlink_wednesday(
                my_callsign = cs,
                my_grid     = grid,
                my_name     = cs,
                my_city     = city,
                my_state    = state)
        elif name == "Welfare Message":
            msg = welfare_message(
                my_callsign = cs,
                my_name     = cs,
                to_name     = "(recipient name)",
                to_email    = "(email@example.com)",
                message     = "I am safe and in good health.")
        elif name == "ARRL Radiogram":
            msg = radiogram(
                precedence  = "ROUTINE",
                to_call     = "(destination callsign)",
                to_name     = "(recipient name)",
                to_address  = "(address)",
                to_phone    = "(phone)",
                message     = "(your message here)",
                from_call   = cs,
                from_name   = cs)

        if msg:
            self._to_edit.setText(msg.to)
            self._subj_edit.setText(msg.subject)
            self._body_edit.setPlainText(msg.body)

    def _refresh_gateways(self):
        """Fetch nearby RMS gateways from Winlink network."""
        self._gw_table.setRowCount(0)
        # Show loading state
        loading = QTableWidgetItem("Fetching gateways…")
        self._gw_table.insertRow(0)
        self._gw_table.setItem(0, 0, loading)

        import threading
        threading.Thread(
            target=self._fetch_gateways_bg,
            daemon=True).start()

    def _fetch_gateways_bg(self):
        """Background gateway fetch from Winlink API."""
        from PyQt6.QtCore import QTimer
        try:
            import requests
            lat = self.cfg.get("location.lat", 0.0) or 0.0
            lon = self.cfg.get("location.lon", 0.0) or 0.0

            # Winlink gateway list - use the public stations endpoint
            # Falls back to channel list if main API unavailable
            params = {
                "latitude":  lat,
                "longitude": lon,
                "distance":  200,
                "maxCount":  25,
                "mode":      0,     # 0=all modes
            }
            # Try primary API first
            resp = None
            for url in [
                "https://api.winlink.org/gateway/list",
                "https://cms.winlink.org/gateway/list",
            ]:
                try:
                    resp = requests.get(
                        url, params=params,
                        timeout=10,
                        headers={"Accept": "application/json"})
                    if resp.status_code == 200:
                        break
                except Exception:
                    continue
            if resp is None:
                raise Exception("All Winlink API endpoints failed")

            if resp.status_code == 200 and                len(resp.content) < 100_000:
                gateways = resp.json()
                QTimer.singleShot(0,
                    lambda g=gateways:
                        self._populate_gateways(g))
                return

        except Exception as e:
            log.debug(f"Gateway fetch: {e}")

        # Show fallback message if fetch fails
        QTimer.singleShot(0, self._gateways_unavailable)

    def _populate_gateways(self, gateways: list):
        """Populate the gateway table from API response."""
        import math
        self._gw_table.setRowCount(0)
        if not gateways:
            self._gateways_unavailable()
            return

        lat = self.cfg.get("location.lat", 0.0) or 0.0
        lon = self.cfg.get("location.lon", 0.0) or 0.0

        for gw in gateways[:25]:
            row = self._gw_table.rowCount()
            self._gw_table.insertRow(row)

            callsign = str(gw.get("Callsign", ""))
            freq     = gw.get("Frequency", 0)
            freq_str = (f"{float(freq)/1000:.3f} MHz"
                        if freq else "—")
            modes    = ", ".join(
                str(m) for m in
                gw.get("ServiceCodes", []))
            last     = str(gw.get(
                "LastHeard", ""))[:10]

            # Distance
            gw_lat = float(gw.get("Latitude",  0))
            gw_lon = float(gw.get("Longitude", 0))
            if lat and lon and gw_lat and gw_lon:
                dlat = math.radians(gw_lat - lat)
                dlon = math.radians(gw_lon - lon)
                a    = (math.sin(dlat/2)**2 +
                        math.cos(math.radians(lat)) *
                        math.cos(math.radians(gw_lat)) *
                        math.sin(dlon/2)**2)
                dist = f"{6371 * 2 * math.asin(math.sqrt(a)):.0f} km"
            else:
                dist = "—"

            for col, val in enumerate([
                    callsign, freq_str, modes or "VARA",
                    dist, last]):
                item = QTableWidgetItem(val)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter)
                self._gw_table.setItem(row, col, item)

    def _gateways_unavailable(self):
        self._gw_table.setRowCount(0)
        self._gw_table.insertRow(0)
        msg = QTableWidgetItem(
            "Gateway list unavailable — "
            "check internet connection")
        self._gw_table.setItem(0, 0, msg)


def _vsep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setStyleSheet("color:#1e1e1e;")
    f.setFixedWidth(1)
    return f
