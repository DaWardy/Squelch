from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/tabs/modes_dx_mixin.py

Live DX-cluster spots panel for the Weak-Signal (Modes) tab, extracted from
modes_tab.py (HOUSE-CS complexity split).

`_ModesDXMixin` is mixed into `ModesTab`. Host-state dependencies:
  * self.cfg                 — Config (dx_cluster.auto_connect)
  * self.layout()            — the tab's root layout (panel is appended here)
  * self._current_band       — current band string (for the "Current" filter)
  * self._do_spot_tune()     — shared spot tune helper (lives on ModesTab; also
                               used by the SOTA/POTA code)
  * self._build_sota_pota_panel() — from _ModesSOTAMixin (DX panel builds it too)
  * self.window()/_tab_map   — to push spots to the Map tab
`_build_dx_panel()` is called from the host `_build`; it creates the DX widgets
plus `_dx_cluster`/`_dx_spots` state.
"""

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QTableWidget, QHeaderView,
)


class _ModesDXMixin:
    """DX-cluster spots panel + connection, spot ingest, filter, alert, tune."""

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
            "QTableWidget{font-family:'Courier New';}"
            "QHeaderView::section{border:none;}")
        self._dx_table.doubleClicked.connect(self._tune_to_dx_spot)
        return self._dx_table

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
        # Mirror into the unified Signal store (best-effort, thread-safe).
        try:
            from core.signal_ingest import ingest, signal_from_dx_spot
            ingest(signal_from_dx_spot(spot))
        except Exception:
            pass

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
            from PyQt6.QtGui import QBrush, QColor as _QC
            QApplication.beep()
            self._dx_status.setText(
                f"⚡ ALERT: {spot.dx_call}  "
                f"{spot.freq_khz/1000:.3f} MHz  {getattr(spot, 'mode', '')}")
            self._dx_status.setStyleSheet("color:#ffcc00;font-weight:bold;")
            # Highlight the matching row in the DX table amber
            amber = QBrush(_QC("#5a3800"))
            tbl = getattr(self, "_dx_table", None)
            if tbl:
                for row in range(tbl.rowCount()):
                    item = tbl.item(row, 0)
                    if item and item.text().upper() == call_upper:
                        for col in range(tbl.columnCount()):
                            cell = tbl.item(row, col)
                            if cell:
                                cell.setBackground(amber)
                        break

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
        # Push all spots to map (best-effort, deduped by callsign)
        try:
            mw = self.window()
            map_tab = getattr(mw, "_tab_map", {}).get("map") if mw else None
            if map_tab and hasattr(map_tab, "set_dx_spots"):
                import time as _time
                spot_dicts = [
                    {"callsign": s.dx_call,
                     "freq_hz":  int(s.freq_khz * 1000),
                     "band":     s.band,
                     "mode":     getattr(s, "mode", ""),
                     "snr":      getattr(s, "snr", 0),
                     "age_min":  round((_time.time() - s.timestamp) / 60)}
                    for s in self._dx_spots
                ]
                QTimer.singleShot(0, lambda d=spot_dicts: map_tab.set_dx_spots(d))
        except Exception:
            pass

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
