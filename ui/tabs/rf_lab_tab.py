from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- ui/tabs/rf_lab_tab.py
RF Lab / Education mode — Emergency Monitor tab.

Provides a frequency watchlist focused on:
- Emergency monitoring (NOAA weather, Aviation guard, Marine Ch.16, EMS)
- Signal identification and education
- SDR-only use without ham radio rig control

TX capability for USRP/HackRF is accessed through the SDR tab's transmit
controls. This tab is a pure receive/monitor panel.
"""

import logging
from typing import Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QLineEdit, QComboBox, QGroupBox, QSplitter, QFrame, QMessageBox,
    QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from ui.panel import SquelchPanel
from ui.tabs.rf_lab_data import BUILTIN_FREQS as _BUILTIN_FREQS
from ui.tabs.rf_lab_data import CATEGORY_COLORS as _CATEGORY_COLORS

log = logging.getLogger(__name__)

_COL_NAME  = 0
_COL_FREQ  = 1
_COL_CAT   = 2
_COL_DESC  = 3
_COL_TUNE  = 4


class RFLabTab(SquelchPanel, QWidget):
    """Emergency Monitor / RF Education frequency watchlist panel."""

    panel_id    = "rf_lab"
    panel_title = "RF Lab"

    # Emitted when user clicks Tune — receiver wires this to SDR tab
    tune_requested = pyqtSignal(int)   # Hz

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._custom_freqs: list[tuple[int, str, str, str]] = []
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())
        root.addWidget(self._build_toolbar())
        root.addWidget(self._build_table(), 1)
        root.addWidget(self._build_status_bar())

    def _build_header(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("rf_lab_header")
        bar.setStyleSheet(
            "QFrame#rf_lab_header{"
            "border-bottom:1px solid #2a2a2a;padding:6px 12px;}")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 6, 12, 6)

        title = QLabel("🔬  RF Lab — Emergency Monitor")
        title.setStyleSheet("font-weight:bold;font-size:13px;")
        lay.addWidget(title)

        lay.addStretch()

        note = QLabel(
            "Click <b>Tune</b> to send any frequency to the SDR tab for monitoring.")
        note.setWordWrap(False)
        note.setStyleSheet("color:#888;font-size:10px;")
        lay.addWidget(note)
        return bar

    def _build_toolbar(self) -> QFrame:
        bar = QFrame()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(6)

        filter_lbl = QLabel("Filter:")
        filter_lbl.setStyleSheet("color:#aaa;")
        lay.addWidget(filter_lbl)

        self._cat_filter = QComboBox()
        self._cat_filter.addItem("All categories")
        for cat in sorted(_CATEGORY_COLORS):
            self._cat_filter.addItem(cat)
        self._cat_filter.currentTextChanged.connect(self._apply_filter)
        lay.addWidget(self._cat_filter)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search name or frequency…")
        self._search_edit.setMaximumWidth(200)
        self._search_edit.textChanged.connect(self._apply_filter)
        lay.addWidget(self._search_edit)

        lay.addStretch()

        add_btn = QPushButton("+ Add Custom")
        add_btn.setToolTip("Add a custom frequency to the watchlist")
        add_btn.clicked.connect(self._add_custom_freq)
        lay.addWidget(add_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.setToolTip("Remove selected custom frequency")
        remove_btn.clicked.connect(self._remove_selected)
        lay.addWidget(remove_btn)

        return bar

    def _build_table(self) -> QTableWidget:
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Name", "Frequency", "Category", "Description", ""])
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_NAME, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_FREQ, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_CAT, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_DESC, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_TUNE, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(_COL_TUNE, 70)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setDefaultSectionSize(28)
        self._table.setAlternatingRowColors(True)
        self._populate_table()
        return self._table

    def _build_status_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(24)
        bar.setObjectName("rf_lab_status")
        bar.setStyleSheet(
            "QFrame#rf_lab_status{"
            "border-top:1px solid #2a2a2a;padding:0 8px;}")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(8, 0, 8, 0)
        self._status_lbl = QLabel(
            f"{len(_BUILTIN_FREQS)} monitoring frequencies loaded  "
            "|  TX available via SDR tab (USRP/HackRF only)")
        self._status_lbl.setStyleSheet("color:#888;font-size:10px;")
        lay.addWidget(self._status_lbl)
        return bar

    # ── Table population ──────────────────────────────────────────────────

    def _populate_table(self):
        all_freqs = list(_BUILTIN_FREQS) + self._custom_freqs
        self._table.setRowCount(0)
        cat_filter = self._cat_filter.currentText() if hasattr(self, "_cat_filter") else "All categories"
        search = self._search_edit.text().lower() if hasattr(self, "_search_edit") else ""

        for hz, name, cat, desc in all_freqs:
            if cat_filter not in ("All categories", "") and cat != cat_filter:
                continue
            freq_str = f"{hz / 1e6:.3f} MHz"
            if search and search not in name.lower() and search not in freq_str.lower():
                continue
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._set_row(row, hz, name, cat, desc)

    def _set_row(self, row: int, hz: int, name: str, cat: str, desc: str):
        color = _CATEGORY_COLORS.get(cat, "#aaaaaa")
        freq_str = f"{hz / 1e6:.3f} MHz"

        for col, text in [(0, name), (1, freq_str), (2, cat), (3, desc)]:
            item = QTableWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, hz)
            if col == _COL_CAT:
                item.setForeground(QColor(color))
            self._table.setItem(row, col, item)

        tune_btn = QPushButton("Tune →")
        tune_btn.setFixedHeight(22)
        tune_btn.setStyleSheet(
            "QPushButton{background:#1a3a1a;border:1px solid #3fbe6f;"
            "border-radius:3px;padding:0 6px;font-size:10px;}"
            "QPushButton:hover{background:#2a5a2a;}")
        tune_btn.setToolTip(f"Send {freq_str} to SDR tab")
        tune_btn.clicked.connect(lambda _, f=hz: self._tune(f))
        self._table.setCellWidget(row, _COL_TUNE, tune_btn)

    # ── Actions ───────────────────────────────────────────────────────────

    def _tune(self, hz: int):
        self.tune_requested.emit(hz)
        freq_mhz = hz / 1e6
        self._status_lbl.setText(
            f"Tuned SDR to {freq_mhz:.3f} MHz  |  "
            "Switch to SDR tab to monitor")
        sdr_tab = self._find_sdr_tab()
        if sdr_tab:
            sdr_tab._set_freq(hz)
            self._switch_to_sdr()

    def _find_sdr_tab(self):
        try:
            mw = self.window()
            return getattr(mw, "_tab_map", {}).get("sdr")
        except Exception:
            return None

    def _switch_to_sdr(self):
        try:
            mw = self.window()
            tabs = getattr(mw, "tabs", None)
            sdr = getattr(mw, "_tab_map", {}).get("sdr")
            if tabs and sdr:
                idx = tabs.indexOf(sdr)
                if idx >= 0 and tabs.isTabVisible(idx):
                    tabs.setCurrentIndex(idx)
        except Exception:
            pass

    def _apply_filter(self):
        self._populate_table()

    def _add_custom_freq(self):
        dlg = _AddFreqDialog(self)
        if dlg.exec():
            hz, name, cat, desc = dlg.result()
            self._custom_freqs.append((hz, name, cat, desc))
            self._populate_table()
            total = len(_BUILTIN_FREQS) + len(self._custom_freqs)
            self._status_lbl.setText(
                f"{total} monitoring frequencies loaded  |  "
                "TX available via SDR tab (USRP/HackRF only)")

    def _remove_selected(self):
        rows = self._table.selectedItems()
        if not rows:
            return
        row = self._table.currentRow()
        name_item = self._table.item(row, _COL_NAME)
        hz_item   = self._table.item(row, _COL_FREQ)
        if not name_item:
            return
        name = name_item.text()
        hz = name_item.data(Qt.ItemDataRole.UserRole)
        # Only remove custom entries
        before = len(self._custom_freqs)
        self._custom_freqs = [
            f for f in self._custom_freqs if not (f[0] == hz and f[1] == name)]
        if len(self._custom_freqs) == before:
            self._status_lbl.setText("Built-in frequencies cannot be removed.")
            return
        self._populate_table()

    # ── Persistence ───────────────────────────────────────────────────────

    def save_state(self) -> dict:
        return {
            "custom_freqs": [
                {"hz": hz, "name": name, "cat": cat, "desc": desc}
                for hz, name, cat, desc in self._custom_freqs
            ]
        }

    def restore_state(self, state: dict) -> None:
        self._custom_freqs = [
            (int(f["hz"]), f.get("name", ""), f.get("cat", "Custom"), f.get("desc", ""))
            for f in state.get("custom_freqs", [])
        ]
        if self._custom_freqs:
            self._populate_table()


class _AddFreqDialog(QDialog):
    """Dialog for adding a custom monitoring frequency."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Custom Frequency")
        self.setMinimumWidth(360)
        lay = QVBoxLayout(self)
        form = QFormLayout()

        self._freq_spin = QDoubleSpinBox()
        self._freq_spin.setRange(0.1, 6000.0)
        self._freq_spin.setDecimals(4)
        self._freq_spin.setSuffix(" MHz")
        self._freq_spin.setValue(144.200)
        form.addRow("Frequency:", self._freq_spin)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. 2m Calling")
        self._name_edit.setMaxLength(24)
        form.addRow("Name:", self._name_edit)

        self._cat_combo = QComboBox()
        for cat in sorted(_CATEGORY_COLORS):
            self._cat_combo.addItem(cat)
        self._cat_combo.setCurrentText("Custom")
        form.addRow("Category:", self._cat_combo)

        self._desc_edit = QLineEdit()
        self._desc_edit.setPlaceholderText("Optional description")
        self._desc_edit.setMaxLength(80)
        form.addRow("Description:", self._desc_edit)

        lay.addLayout(form)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._validate_and_accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _validate_and_accept(self):
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Name required", "Please enter a name.")
            return
        self.accept()

    def result(self) -> tuple[int, str, str, str]:
        hz = int(self._freq_spin.value() * 1e6)
        name = self._name_edit.text().strip()
        cat = self._cat_combo.currentText()
        desc = self._desc_edit.text().strip()
        return hz, name, cat, desc
