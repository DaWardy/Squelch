from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/tabs/rig_memory_mixin.py

Memory channels (store / recall / clear / CSV export / CHIRP import bank) for
the Rig tab, extracted from rig_tab.py (HOUSE-CS complexity split).

`_RigMemoryMixin` is mixed into `RigTab`. It relies on host-class state:
  * self._rig_root     — the rig tab's root QVBoxLayout
  * self.rig           — RigController
  * self._memories     — {slot: (hz, mode, label)} (init in RigTab.__init__;
                         also persisted by RigTab.save_state/restore_state)
  * self.freq_display  — frequency readout widget (current _freq_hz)
  * self._set_freq     — host method to tune the displayed/connected frequency
  * self._set_mode_ui  — host method to reflect a mode in the UI
`self._mem_table` is created in `_build_memory_section`.
"""

import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
)

log = logging.getLogger(__name__)


class _RigMemoryMixin:
    """Memory-channel collapsible section + store/recall/clear/export/import."""

    def _build_memory_section(self, inner):
        # ── Memory channels (collapsible) ─────────────────────────────────
        from ui.tabs.rig_tab import _collapse_btn
        self._mem_toggle = _collapse_btn("Memory Channels")
        self._mem_toggle.toggled.connect(
            lambda c: self._mem_body.setVisible(c))
        self._rig_root.addWidget(self._mem_toggle)

        self._mem_body = QWidget()
        self._mem_body.setVisible(False)
        mem_layout = QVBoxLayout(self._mem_body)
        mem_layout.setContentsMargins(8, 4, 8, 4)
        mem_layout.setSpacing(4)

        self._mem_table = QTableWidget(0, 4)
        self._mem_table.setHorizontalHeaderLabels(
            ["Slot", "Frequency", "Mode", "Label"])
        self._mem_table.setFixedHeight(140)
        self._mem_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch)
        self._mem_table.setStyleSheet(
            "QTableWidget{background:#111;"
            "gridline-color:#222;}"
            "QHeaderView::section{background:#1a1a1a;"
            "border:none;}")
        self._mem_table.cellDoubleClicked.connect(self._mem_recall)
        mem_layout.addWidget(self._mem_table)

        mem_btn_row = QHBoxLayout()
        mem_store = QPushButton("Store current")
        mem_store.setFixedHeight(24)
        mem_store.clicked.connect(self._mem_store)
        mem_recall_btn = QPushButton("Recall selected")
        mem_recall_btn.setFixedHeight(24)
        mem_recall_btn.clicked.connect(
            lambda: self._mem_recall(
                self._mem_table.currentRow(), 0))
        mem_clear = QPushButton("Clear selected")
        mem_clear.setFixedHeight(24)
        mem_clear.clicked.connect(self._mem_clear)
        mem_export = QPushButton("Export CSV")
        mem_export.setFixedHeight(24)
        mem_export.clicked.connect(self._mem_export_csv)
        chirp_btn = QPushButton("Import CHIRP…")
        chirp_btn.setFixedHeight(24)
        chirp_btn.setToolTip(
            "Import channels from a CHIRP-exported CSV file\n"
            "into the memory channel bank.")
        chirp_btn.clicked.connect(self._mem_import_chirp)
        for b in (mem_store, mem_recall_btn, mem_clear,
                  mem_export, chirp_btn):
            b.setStyleSheet(
                "background:#1a1a1a;border:1px solid #333;"
                "border-radius:3px;")
        mem_btn_row.addWidget(mem_store)
        mem_btn_row.addWidget(mem_recall_btn)
        mem_btn_row.addWidget(mem_clear)
        mem_btn_row.addWidget(mem_export)
        mem_btn_row.addWidget(chirp_btn)
        mem_btn_row.addStretch()
        mem_layout.addLayout(mem_btn_row)
        self._rig_root.addWidget(self._mem_body)

    def _mem_store(self):
        hz    = self.freq_display._freq_hz
        mode  = self.rig.state.mode or "USB"
        slot  = self._mem_table.rowCount() + 1
        label = f"M{slot:02d}"
        self._memories[slot] = (hz, mode, label)
        self._mem_table.insertRow(self._mem_table.rowCount())
        r = self._mem_table.rowCount() - 1
        self._mem_table.setItem(r, 0, QTableWidgetItem(f"M{slot:02d}"))
        self._mem_table.setItem(r, 1,
            QTableWidgetItem(f"{hz/1e6:.6f} MHz"))
        self._mem_table.setItem(r, 2, QTableWidgetItem(mode))
        self._mem_table.setItem(r, 3, QTableWidgetItem(label))

    def _mem_recall(self, row: int, _col: int):
        if row < 0 or row >= self._mem_table.rowCount():
            return
        try:
            freq_txt = self._mem_table.item(row, 1).text()
            hz = int(float(freq_txt.split()[0]) * 1_000_000)
            mode = self._mem_table.item(row, 2).text()
            self._set_freq(hz)
            self._set_mode_ui(mode)
            if self.rig.is_connected:
                self.rig.set_mode(mode)
        except Exception as e:
            log.warning(f"Memory recall: {e}")

    def _mem_clear(self):
        row = self._mem_table.currentRow()
        if row >= 0:
            self._mem_table.removeRow(row)

    def _mem_import_chirp(self) -> None:
        """Import memory channels from a CHIRP-exported CSV file."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        path, _ = QFileDialog.getOpenFileName(
            self, "Import CHIRP CSV", "",
            "CSV files (*.csv);;All files (*)")
        if not path:
            return
        try:
            from network.chirp_import import parse_chirp_csv
            repeaters = parse_chirp_csv(path)
        except Exception as e:
            QMessageBox.warning(self, "CHIRP Import",
                                f"Failed to parse CSV:\n{e}")
            return
        added = 0
        for rep in repeaters:
            freq_hz = int(rep.output_mhz * 1_000_000)
            mode    = rep.mode or "FM"
            label   = (rep.callsign or "").strip()[:12] or f"CH{added+1}"
            slot    = max(self._memories.keys(), default=0) + 1
            self._memories[slot] = (freq_hz, mode, label)
            r = self._mem_table.rowCount()
            self._mem_table.insertRow(r)
            self._mem_table.setItem(r, 0, QTableWidgetItem(f"M{slot:02d}"))
            self._mem_table.setItem(r, 1,
                QTableWidgetItem(f"{rep.output_mhz:.6f} MHz"))
            self._mem_table.setItem(r, 2, QTableWidgetItem(mode))
            self._mem_table.setItem(r, 3, QTableWidgetItem(label))
            added += 1
        QMessageBox.information(self, "CHIRP Import",
                                f"Imported {added} channel(s) from CHIRP CSV.")

    def _mem_export_csv(self):
        """Export memory channels to a CSV file."""
        from PyQt6.QtWidgets import QFileDialog
        import csv
        from pathlib import Path
        from core.sanitize import csv_safe
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Memory Channels", "rig_memories.csv",
            "CSV files (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Slot", "Frequency MHz", "Mode", "Label"])
                for slot, (hz, mode, label) in sorted(self._memories.items()):
                    w.writerow([
                        f"M{slot:02d}",
                        f"{hz/1e6:.6f}",
                        csv_safe(mode),
                        csv_safe(label),
                    ])
            log.info(f"Exported {len(self._memories)} memory channels to {path}")
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Export Failed", str(e))
