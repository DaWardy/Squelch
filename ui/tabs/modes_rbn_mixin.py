from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/tabs/modes_rbn_mixin.py

RBN ("Am I being heard?") panel for the Weak-Signal (Modes) tab, extracted from
modes_tab.py (HOUSE-CS complexity split).

`_ModesRBNMixin` is mixed into `ModesTab`. Host-state dependencies:
  * self.cfg            — Config (callsign default via operating_callsign)
  * self.layout()       — the tab's root layout (panel is appended here)
`_build_rbn_panel()` is called from the host `_build`; it creates
`_rbn_grp`/`_rbn_client`/`_rbn_spots` and the panel widgets.
"""

from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QTableWidget, QHeaderView,
)


class _ModesRBNMixin:
    """RBN skimmer 'who hears me' panel + poll loop."""

    def _build_rbn_panel(self) -> None:
        """Collapsible panel showing which RBN skimmers hear our signal."""
        rbn_grp = QGroupBox("RBN — Am I Being Heard?")
        rbn_grp.setMaximumHeight(150)
        rbn_grp.setCheckable(True)
        rbn_grp.setChecked(False)
        rbn_grp.toggled.connect(self._on_rbn_toggle)
        rl = QVBoxLayout(rbn_grp)
        rl.setContentsMargins(4, 4, 4, 4)
        rl.setSpacing(3)
        rl.addLayout(self._build_rbn_controls_row())
        rl.addWidget(self._build_rbn_table())
        self.layout().addWidget(rbn_grp)
        self._rbn_grp     = rbn_grp
        self._rbn_client  = None
        self._rbn_spots: list = []

    def _build_rbn_controls_row(self) -> "QHBoxLayout":
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Call:"))
        self._rbn_call_edit = QLineEdit()
        self._rbn_call_edit.setPlaceholderText("your callsign")
        self._rbn_call_edit.setFixedWidth(90)
        self._rbn_call_edit.setToolTip(
            "Callsign to search for in the RBN skimmer feed.\n"
            "Defaults to your station callsign.")
        ctrl.addWidget(self._rbn_call_edit)
        ctrl.addWidget(QLabel("Mode:"))
        self._rbn_mode = QComboBox()
        self._rbn_mode.addItems(["CW", "RTTY", "FT8", "FT4"])
        self._rbn_mode.setFixedWidth(60)
        ctrl.addWidget(self._rbn_mode)
        ctrl.addStretch()
        self._rbn_status = QLabel("Expand to start polling")
        self._rbn_status.setStyleSheet("font-size:9px;")
        ctrl.addWidget(self._rbn_status)
        return ctrl

    def _build_rbn_table(self) -> "QTableWidget":
        self._rbn_table = QTableWidget(0, 5)
        self._rbn_table.setHorizontalHeaderLabels(
            ["Spotter", "Freq", "Mode", "SNR (dB)", "Time"])
        h = self._rbn_table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._rbn_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._rbn_table.setFixedHeight(88)
        self._rbn_table.setStyleSheet(
            "QTableWidget{font-family:'Courier New';}"
            "QHeaderView::section{border:none;}")
        return self._rbn_table

    def _on_rbn_toggle(self, checked: bool) -> None:
        from core.guest_op import operating_callsign
        if checked:
            call = self._rbn_call_edit.text().strip()
            if not call:
                call = operating_callsign(self.cfg) or ""
                self._rbn_call_edit.setText(call)
            if call:
                self._start_rbn(call)
        else:
            self._stop_rbn()

    def _start_rbn(self, callsign: str) -> None:
        from network.dx_cluster import RBNClient
        from PyQt6.QtCore import QTimer
        if self._rbn_client:
            self._rbn_client.stop()
        self._rbn_client = RBNClient(self.cfg)
        self._rbn_client.on_spot(
            lambda s: QTimer.singleShot(0,
                lambda spot=s: self._on_rbn_spot(spot)))
        mode = self._rbn_mode.currentText()
        self._rbn_client.start(callsign, mode)
        self._rbn_status.setText(f"Polling RBN for {callsign} ({mode}) …")

    def _stop_rbn(self) -> None:
        if self._rbn_client:
            self._rbn_client.stop()
            self._rbn_client = None
        self._rbn_status.setText("Stopped")

    def _on_rbn_spot(self, spot) -> None:
        from PyQt6.QtWidgets import QTableWidgetItem
        from PyQt6.QtCore import Qt
        # Deduplicate by spotter+freq
        key = (spot.spotter, spot.freq_hz)
        self._rbn_spots = [s for s in self._rbn_spots
                           if (s.spotter, s.freq_hz) != key]
        self._rbn_spots.insert(0, spot)
        if len(self._rbn_spots) > 40:
            self._rbn_spots = self._rbn_spots[:40]
        self._rbn_table.setRowCount(0)
        for s in self._rbn_spots:
            row = self._rbn_table.rowCount()
            self._rbn_table.insertRow(row)
            snr_str = f"+{s.snr}" if s.snr and s.snr >= 0 else str(s.snr or "—")
            for col, val in enumerate([
                    s.spotter, f"{s.freq_hz/1000:.1f}",
                    s.mode, snr_str, s.time_utc]):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._rbn_table.setItem(row, col, item)
        n = len(self._rbn_spots)
        best = max((s.snr for s in self._rbn_spots if s.snr), default=None)
        best_str = f", best SNR +{best} dB" if best is not None else ""
        self._rbn_status.setText(
            f"Heard by {n} skimmer{'s' if n != 1 else ''}{best_str}")
