from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/tabs/rig_cw_mixin.py

CW keyer (F1-F8 Morse macros, WPM, WinKeyer USB hardware) for the Rig tab,
extracted from rig_tab.py (HOUSE-CS complexity split).

`_RigCWMixin` is mixed into `RigTab`. It relies on host-class state:
  * self._rig_root   — the rig tab's root QVBoxLayout
  * self.cfg         — Config (macros, callsign)
  * self.rig         — RigController (Hamlib CW path)
`self._cw_macro_mgr` and `self._winkeyer` are created in `_build_cw_section`
(no __init__ dependency).
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QComboBox,
)


class _RigCWMixin:
    """CW keyer collapsible section + WinKeyer hardware + F1-F8 macros."""

    def _build_cw_section(self, inner):
        # ── CW Keyer (collapsible) ───────────────────────────────────────
        from core.macros import MacroManager
        from core.guest_op import operating_callsign
        from ui.tabs.rig_tab import _collapse_btn
        self._cw_macro_mgr = MacroManager(self.cfg)
        self._winkeyer: "object | None" = None

        self._cw_toggle = _collapse_btn("CW Keyer")
        self._cw_toggle.toggled.connect(lambda c: self._cw_body.setVisible(c))
        self._rig_root.addWidget(self._cw_toggle)

        self._cw_body = QWidget()
        self._cw_body.setVisible(False)
        cw_vlay = QVBoxLayout(self._cw_body)
        cw_vlay.setContentsMargins(8, 4, 8, 4)
        cw_vlay.setSpacing(4)

        # F1-F8 macro button row
        macro_row = QHBoxLayout()
        macro_row.setSpacing(3)
        self._cw_macro_btns: list = []
        for i in range(1, 9):
            key  = f"f{i}"
            m    = self._cw_macro_mgr.get(key)
            btn  = QPushButton(m["label"])
            btn.setFixedHeight(22)
            btn.setToolTip(m["text"] or "(empty)")
            btn.clicked.connect(lambda _, k=key: self._cw_macro_click(k))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda _, k=key: self._cw_macro_edit(k))
            btn.setStyleSheet(
                "background:#1a1a1a;border:1px solid #333;border-radius:2px;"
                "font-size:10px;padding:0 3px;")
            macro_row.addWidget(btn)
            self._cw_macro_btns.append((key, btn))
        cw_vlay.addLayout(macro_row)

        # Text input + WPM + Send/Stop
        send_row = QHBoxLayout()
        self._cw_text = QLineEdit()
        _cs = operating_callsign(self.cfg) or "MYCALL"
        self._cw_text.setPlaceholderText(
            f"CQ CQ DE {_cs}  or any text to send in Morse")
        self._cw_text.setFont(QFont("Courier New", 12))
        self._cw_text.returnPressed.connect(self._send_cw)
        send_row.addWidget(self._cw_text, 1)
        send_row.addWidget(QLabel("WPM:"))
        self._cw_wpm = QSpinBox()
        self._cw_wpm.setRange(5, 60)
        self._cw_wpm.setValue(20)
        self._cw_wpm.setFixedWidth(65)
        self._cw_wpm.setToolTip("CW speed in words per minute")
        self._cw_wpm.valueChanged.connect(self._cw_wpm_changed)
        send_row.addWidget(self._cw_wpm)
        send_btn = QPushButton("▶ Send")
        send_btn.setFixedHeight(28)
        send_btn.setToolTip("Send CW text via Hamlib or WinKeyer (press Enter)")
        send_btn.clicked.connect(self._send_cw)
        send_row.addWidget(send_btn)
        stop_btn = QPushButton("■ Stop")
        stop_btn.setFixedHeight(28)
        stop_btn.setToolTip("Stop CW transmission immediately")
        stop_btn.clicked.connect(self._stop_cw)
        send_row.addWidget(stop_btn)
        cw_vlay.addLayout(send_row)

        # WinKeyer hardware row
        wk_row = QHBoxLayout()
        wk_row.addWidget(QLabel("WinKeyer:"))
        self._wk_port = QComboBox()
        self._wk_port.setEditable(True)
        self._wk_port.setFixedWidth(90)
        self._wk_port.setToolTip("Serial port for WinKeyer USB (e.g. COM3)")
        self._populate_wk_ports()
        wk_row.addWidget(self._wk_port)
        self._wk_btn = QPushButton("Connect")
        self._wk_btn.setFixedWidth(72)
        self._wk_btn.setFixedHeight(22)
        self._wk_btn.clicked.connect(self._wk_toggle)
        wk_row.addWidget(self._wk_btn)
        self._wk_status = QLabel("Not connected")
        self._wk_status.setStyleSheet("color:#555;font-size:9px;")
        wk_row.addWidget(self._wk_status, 1)
        cw_vlay.addLayout(wk_row)
        self._rig_root.addWidget(self._cw_body)

    def _populate_wk_ports(self) -> None:
        """Fill WinKeyer port combo with available serial ports."""
        try:
            import serial.tools.list_ports as _lp   # type: ignore
            self._wk_port.clear()
            for p in _lp.comports():
                self._wk_port.addItem(p.device)
        except Exception:
            pass   # pyserial not installed — user can type a port manually

    def _wk_toggle(self) -> None:
        """Connect or disconnect the WinKeyer."""
        from core.winkeyer import WinKeyerClient
        if self._winkeyer and self._winkeyer.is_connected:
            self._winkeyer.disconnect()
            self._winkeyer = None
            self._wk_btn.setText("Connect")
            self._wk_status.setText("Not connected")
            self._wk_status.setStyleSheet("color:#555;font-size:9px;")
            return
        port = self._wk_port.currentText().strip()
        if not port:
            return
        wk = WinKeyerClient()
        if wk.connect(port):
            wk.set_speed(self._cw_wpm.value())
            self._winkeyer = wk
            self._wk_btn.setText("Disconnect")
            self._wk_status.setText(f"● {port}")
            self._wk_status.setStyleSheet("color:#3fbe6f;font-size:9px;")
        else:
            self._wk_status.setText("Connection failed")
            self._wk_status.setStyleSheet("color:#cc4444;font-size:9px;")

    def _cw_wpm_changed(self, wpm: int) -> None:
        if self.rig.is_connected:
            self.rig.set_cw_wpm(wpm)
        if self._winkeyer and self._winkeyer.is_connected:
            self._winkeyer.set_speed(wpm)

    def _cw_macro_click(self, key: str) -> None:
        """Expand macro and load into CW text field."""
        from core.macros import MacroManager
        from core.guest_op import operating_callsign
        mgr  = MacroManager(self.cfg)
        text = mgr.expand(key, mycall=operating_callsign(self.cfg) or "MYCALL")
        self._cw_text.setText(text)
        self._send_cw()

    def _cw_macro_edit(self, key: str) -> None:
        """Right-click → edit macro label and text."""
        from PyQt6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox
        from core.macros import MacroManager
        mgr = MacroManager(self.cfg)
        m   = mgr.get(key)
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Edit {key.upper()} macro")
        f = QFormLayout(dlg)
        lbl_edit = QLineEdit(m["label"])
        lbl_edit.setMaxLength(6)
        txt_edit = QLineEdit(m["text"])
        txt_edit.setMinimumWidth(260)
        f.addRow("Label:", lbl_edit)
        f.addRow("Text:", txt_edit)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        f.addRow(btns)
        if dlg.exec():
            mgr.set(key, lbl_edit.text().strip(), txt_edit.text())
            # Refresh the button label/tooltip
            for k, btn in self._cw_macro_btns:
                if k == key:
                    btn.setText(lbl_edit.text().strip() or key.upper())
                    btn.setToolTip(txt_edit.text())

    def _send_cw(self):
        """Send CW via WinKeyer (preferred) or Hamlib."""
        text = self._cw_text.text().strip()
        if not text:
            return
        # License-class TX gate (covers this send AND the F1-F8 CW macros,
        # which route through here). GUI-thread, so the confirm dialog is safe.
        from ui.tx_confirm import confirm_tx
        if not confirm_tx(self, self.cfg, self.rig.state.freq_hz):
            return
        # WinKeyer hardware path (preferred)
        if self._winkeyer and self._winkeyer.is_connected:
            self._winkeyer.send_text(text)
            self._cw_text.clear()
            return
        # Hamlib rig path
        if not self.rig.is_connected:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "CW Keyer",
                                "Connect rig or WinKeyer first.")
            return
        wpm  = self._cw_wpm.value()
        sent = self.rig.send_cw(text, wpm)
        if sent:
            self._cw_text.clear()
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "CW Send",
                                "CW send failed — rig must be in CW mode.")

    def _stop_cw(self):
        """Abort CW transmission on WinKeyer and Hamlib."""
        if self._winkeyer and self._winkeyer.is_connected:
            self._winkeyer.stop()
        if self.rig.is_connected:
            self.rig.stop_cw()
