"""Squelch — ui/dialogs/log_stats_dialog.py
Read-only QSO log analytics: band, mode, year, and entity breakdowns
rendered as proportional bar charts using pure Qt widgets.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTabWidget, QWidget, QScrollArea, QDialogButtonBox,
    QProgressBar, QFrame
)
from PyQt6.QtCore import Qt

from core.log_db import LogDB


class LogStatsDialog(QDialog):
    def __init__(self, db: LogDB, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Log Analytics"))
        self.resize(540, 440)
        self._db = db
        self._build()

    # ── build ──────────────────────────────────────────────────────────────

    def _build(self):
        lay = QVBoxLayout(self)
        total = self._db.total_qsos()
        header = QLabel(
            self.tr(f"<b>Total QSOs: {total}</b>  ·  "
                    f"DXCC: {self._db.dxcc_count()}  ·  "
                    f"Grids: {self._db.grids_worked()}  ·  "
                    f"WAS: {self._db.was_count()}"))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(sep)

        tabs = QTabWidget()
        tabs.addTab(self._chart_tab(self._db.qsos_by_band()),   self.tr("Band"))
        tabs.addTab(self._chart_tab(self._db.qsos_by_mode()),   self.tr("Mode"))
        tabs.addTab(self._chart_tab(self._db.qsos_by_year(),
                                    ascending=True),             self.tr("Year"))
        tabs.addTab(self._chart_tab(self._db.top_entities()),   self.tr("Entity"))
        lay.addWidget(tabs)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.accept)
        lay.addWidget(btns)

    # ── chart helpers ──────────────────────────────────────────────────────

    def _chart_tab(self, data: list[tuple[str, int]],
                   ascending: bool = False) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        vlay = QVBoxLayout(inner)
        vlay.setSpacing(4)
        vlay.setContentsMargins(8, 8, 8, 8)
        if not data:
            vlay.addWidget(QLabel(self.tr("No data.")))
        else:
            max_val = max(v for _, v in data)
            rows = data if ascending else data
            for label, count in rows:
                vlay.addLayout(self._bar_row(label, count, max_val))
        vlay.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _bar_row(self, label: str, count: int, max_val: int) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)

        lbl = QLabel(label)
        lbl.setFixedWidth(90)
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight
                         | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(lbl)

        bar = QProgressBar()
        bar.setRange(0, max(max_val, 1))
        bar.setValue(count)
        bar.setTextVisible(False)
        bar.setFixedHeight(18)
        row.addWidget(bar, 1)

        cnt = QLabel(str(count))
        cnt.setFixedWidth(50)
        row.addWidget(cnt)
        return row
