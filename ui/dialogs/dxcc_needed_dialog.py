from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Searchable DXCC entity list: worked vs. needed.

Opens from Log tab Awards panel. Shows all 340 DXCC entities with
worked/confirmed status from the log database. Searchable by name,
prefix, or continent. Default view: needed entities only.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialogButtonBox, QComboBox,
)
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtCore import Qt


_COL_NAME   = 0
_COL_PREFIX = 1
_COL_CONT   = 2
_COL_CQ     = 3
_COL_STATUS = 4

_CONT_LABELS = ["All continents", "AF", "AN", "AS", "EU", "NA", "OC", "SA"]


class DXCCNeededDialog(QDialog):
    """Modal showing all DXCC entities with worked/confirmed/needed status."""

    def __init__(self, worked: set, confirmed: set, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("DXCC Entity Status"))
        self.setMinimumSize(640, 520)
        self._worked    = worked
        self._confirmed = confirmed
        self._all: list = []
        self._build()
        self._load_entities()
        self._repopulate()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(6)

        # Stats bar
        total = 340
        need  = max(0, total - len(self._worked))
        self._stats_label = QLabel(
            f"Worked: {len(self._worked)} / {total}  ·  "
            f"Confirmed: {len(self._confirmed)}  ·  "
            f"Needed: {need}")
        lay.addWidget(self._stats_label)

        # Filter row
        fr = QHBoxLayout()
        self._filter = QLineEdit()
        self._filter.setPlaceholderText(self.tr("Search entity or prefix…"))
        self._filter.textChanged.connect(self._repopulate)
        fr.addWidget(self._filter, 3)

        self._cont_combo = QComboBox()
        self._cont_combo.addItems(_CONT_LABELS)
        self._cont_combo.currentIndexChanged.connect(self._repopulate)
        fr.addWidget(self._cont_combo, 1)
        lay.addLayout(fr)

        self._needed_cb = QCheckBox(self.tr("Show needed only"))
        self._needed_cb.setChecked(True)
        self._needed_cb.toggled.connect(self._repopulate)
        lay.addWidget(self._needed_cb)

        # Table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Entity", "Prefix", "Cont", "CQ", "Status"])
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        lay.addWidget(self._table)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _load_entities(self):
        try:
            from network.cty_data import get_cty
            cty = get_cty()
            if cty._entities:
                self._all = sorted(
                    cty._entities.values(),
                    key=lambda e: e.name)
        except Exception:
            pass

    def _repopulate(self):
        txt       = self._filter.text().strip().upper()
        cont      = self._cont_combo.currentText()
        need_only = self._needed_cb.isChecked()

        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)

        for ent in self._all:
            w = ent.name in self._worked
            if need_only and w:
                continue
            if cont not in ("All continents", "") and ent.continent != cont:
                continue
            if txt and txt not in ent.name.upper() and txt not in ent.prefix.upper():
                continue
            self._add_row(ent, w)

        self._table.setSortingEnabled(True)

    def _add_row(self, ent, worked: bool):
        c = self._confirmed
        is_conf = ent.name in c
        if worked and is_conf:
            status = self.tr("✓ Confirmed")
            color  = QColor("#33aa55")
        elif worked:
            status = self.tr("✓ Worked")
            color  = QColor("#88cc44")
        else:
            status = self.tr("— Needed")
            color  = QColor("#cc4444")

        row = self._table.rowCount()
        self._table.insertRow(row)
        for col, val in enumerate([
            ent.name, ent.prefix, ent.continent,
            str(ent.cq_zone), status,
        ]):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter
                                  if col > 0
                                  else Qt.AlignmentFlag.AlignLeft
                                  | Qt.AlignmentFlag.AlignVCenter)
            if col == _COL_STATUS:
                item.setForeground(QBrush(color))
            self._table.setItem(row, col, item)
