from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/tabs/modes_sota_mixin.py

SOTA / POTA activator-spots panel for the Weak-Signal (Modes) tab, extracted
from modes_tab.py (HOUSE-CS complexity split).

`_ModesSOTAMixin` is mixed into `ModesTab`. Host-state dependencies:
  * self.layout()        — the tab's root layout (panel is appended here)
  * self._do_spot_tune() — shared spot tune helper (lives on ModesTab; also
                           used by the DX-cluster code)
`_build_sota_pota_panel()` is called from the host `_build` (and from
`_build_dx_panel`); it creates `_sp_table`/`_sota_*`/`_pota_*` state.
"""

from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTableWidget, QHeaderView,
)


class _ModesSOTAMixin:
    """SOTA/POTA spots panel + fetch clients + filter/tune."""

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
        t.setStyleSheet("QHeaderView::section{border:none;}")
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
