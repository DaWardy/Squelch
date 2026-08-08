from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- ui/tabs/signal_browser_tab.py
Signal Browser (ROADMAP Phase 1, SIG-BROWSER).

A read-only table over the unified Signal store: every signal captured by any
pillar (APRS / FT8 / WSPR / DX cluster / SDR bookmarks / future DF) in one
searchable place. Display logic lives in the Qt-free core.signal_browser
presenter (unit-tested); this tab is a thin shell.

Double-click a row to tune the SDR to that frequency (when wired).
"""

import logging
from typing import Any, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QLineEdit, QComboBox, QFileDialog, QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from ui.panel import SquelchPanel
from core.signal_model import get_signal_store
from core.signal_browser import (
    COLUMNS, format_row, filter_signals, summary_line,
)

log = logging.getLogger(__name__)

_FREQ_COL = 1   # COLUMNS index of the frequency column (for tune)
_MAX_ROWS = 2000


class SignalBrowserTab(SquelchPanel, QWidget):
    """Searchable, read-only browser over the unified Signal store."""

    panel_id    = "signals"
    panel_title = "Signal Log"

    # Emitted (Hz) on double-click — receiver wires this to the SDR tab.
    tune_requested = pyqtSignal(int)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._store = get_signal_store()
        self._all: list = []      # last queried signals
        self._shown: list = []    # currently displayed (post-filter), row-aligned
        self._sdr_tune_cb: Callable | None = None
        self._build()
        self._refresh()

    # ── Build ─────────────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)
        root.addLayout(self._build_controls())
        root.addWidget(self._build_table(), 1)
        self._summary = QLabel("")
        self._summary.setStyleSheet("font-size:11px;")
        root.addWidget(self._summary)

    def _build_controls(self) -> "QHBoxLayout":
        row = QHBoxLayout()
        row.addWidget(QLabel("Search:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText(
            "callsign / emitter / mode / text / freq…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._apply_filter)
        row.addWidget(self._search, 1)

        row.addWidget(QLabel("Source:"))
        self._source = QComboBox()
        self._source.addItem("All")
        self._source.setFixedWidth(110)
        self._source.currentTextChanged.connect(self._apply_filter)
        row.addWidget(self._source)

        refresh = QPushButton("↻ Refresh")
        refresh.setToolTip("Reload signals from the store")
        refresh.clicked.connect(self._refresh)
        row.addWidget(refresh)

        export = QPushButton("⬇ Export CSV")
        export.setToolTip("Export the currently shown signals to CSV")
        export.clicked.connect(self._export_csv)
        row.addWidget(export)

        export_map = QPushButton("🗺 Export Map")
        export_map.setToolTip("Export signals that have a location to KML "
                              "(Google Earth) or GPX (GPS tools)")
        export_map.clicked.connect(self._export_map)
        row.addWidget(export_map)
        return row

    def _build_table(self) -> "QTableWidget":
        self._table = QTableWidget(0, len(COLUMNS))
        self._table.setHorizontalHeaderLabels(COLUMNS)
        self._table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        h = self._table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(len(COLUMNS) - 1, QHeaderView.ResizeMode.Stretch)
        self._table.doubleClicked.connect(self._on_double_click)
        from PyQt6.QtCore import Qt as _Qt
        self._table.setContextMenuPolicy(_Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._row_menu)
        self._table.setStyleSheet(
            "QTableWidget{font-family:'Courier New';}"
            "QHeaderView::section{border:none;}")
        return self._table

    def _row_menu(self, pos) -> None:
        """Right-click a signal row → tag/note it or delete it."""
        from PyQt6.QtWidgets import QMenu, QInputDialog
        row = self._table.rowAt(pos.y())
        if not (0 <= row < len(self._shown)):
            return
        sig = self._shown[row]
        menu = QMenu(self)
        tag_act = menu.addAction("Add tag / note…")
        del_act = menu.addAction("Delete signal")
        chosen = menu.exec(self._table.viewport().mapToGlobal(pos))
        if chosen == tag_act:
            text, ok = QInputDialog.getText(
                self, "Tag / note",
                "Tags or note (comma-separated):",
                text=getattr(sig, "tags", "") or "")
            if ok:
                self._store.set_tags(int(getattr(sig, "id", 0) or 0), text)
                self._refresh()
        elif chosen == del_act:
            self._store.delete(int(getattr(sig, "id", 0) or 0))
            self._refresh()

    # ── Wiring ────────────────────────────────────────────────────────────

    def set_sdr_tune_cb(self, cb: Callable) -> None:
        """Wire the SDR tune callback (called from MainWindow)."""
        self._sdr_tune_cb = cb

    # ── Data ──────────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        try:
            self._all = self._store.recent(_MAX_ROWS)
        except Exception as exc:
            log.debug("signal browser refresh failed: %s", exc)
            self._all = []
        self._repopulate_source_combo()
        self._apply_filter()

    def _repopulate_source_combo(self) -> None:
        current = self._source.currentText()
        sources = sorted({s.source for s in self._all if s.source})
        self._source.blockSignals(True)
        self._source.clear()
        self._source.addItem("All")
        for src in sources:
            self._source.addItem(src)
        idx = self._source.findText(current)
        self._source.setCurrentIndex(idx if idx >= 0 else 0)
        self._source.blockSignals(False)

    def _apply_filter(self) -> None:
        src = self._source.currentText()
        rows = self._all if src in ("", "All") else [
            s for s in self._all if s.source == src]
        rows = filter_signals(rows, self._search.text())
        self._shown = rows
        self._populate(rows)
        self._summary.setText(summary_line(rows))

    def _populate(self, signals: list) -> None:
        self._table.setRowCount(0)
        for sig in signals:
            r = self._table.rowCount()
            self._table.insertRow(r)
            for col, val in enumerate(format_row(sig)):
                item = QTableWidgetItem(val)
                if col in (_FREQ_COL, 5, 6, 7):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(r, col, item)

    # ── Interactions ──────────────────────────────────────────────────────

    def _on_double_click(self, index) -> None:
        row = index.row()
        if not (0 <= row < len(self._shown)):
            return
        hz = int(getattr(self._shown[row], "freq_hz", 0) or 0)
        if hz <= 0:
            return
        self.tune_requested.emit(hz)
        if self._sdr_tune_cb:
            try:
                self._sdr_tune_cb(hz)
            except Exception as exc:
                log.debug("signal browser tune failed: %s", exc)

    def _export_csv(self) -> None:
        if not self._shown:
            QMessageBox.information(self, "Export CSV", "No signals to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export signals", "signals.csv", "CSV files (*.csv)")
        if not path:
            return
        try:
            from core.sanitize import csv_safe
            import csv
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(COLUMNS)
                for sig in self._shown:
                    w.writerow([csv_safe(c) for c in format_row(sig)])
            self._summary.setText(f"Exported {len(self._shown)} signals → {path}")
        except Exception as exc:
            QMessageBox.warning(self, "Export CSV", f"Export failed: {exc}")

    def _export_map(self) -> None:
        located = [s for s in self._shown
                   if (getattr(s, "lat", 0.0) or getattr(s, "lon", 0.0))]
        if not located:
            QMessageBox.information(
                self, "Export Map",
                "No shown signals have a location (lat/lon) to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export located signals", "signals.kml",
            "Google Earth KML (*.kml);;GPS Exchange GPX (*.gpx)")
        if not path:
            return
        try:
            from core.geo_export import signals_to_kml, signals_to_gpx, save
            content = (signals_to_gpx(located) if path.lower().endswith(".gpx")
                       else signals_to_kml(located))
            if save(path, content):
                self._summary.setText(
                    f"Exported {len(located)} located signals → {path}")
            else:
                QMessageBox.warning(self, "Export Map", "Export failed.")
        except Exception as exc:
            QMessageBox.warning(self, "Export Map", f"Export failed: {exc}")

    def showEvent(self, event):
        super().showEvent(event)
        # Refresh when the tab becomes visible so it reflects new captures.
        QTimer.singleShot(0, self._refresh)

    # ── State persistence ─────────────────────────────────────────────────

    def save_state(self) -> dict[str, Any]:
        try:
            return {
                "search": self._search.text(),
                "source": self._source.currentText(),
            }
        except Exception:
            return {}

    def restore_state(self, state: dict[str, Any]) -> None:
        try:
            if "search" in state:
                self._search.setText(state["search"] or "")
            if state.get("source"):
                idx = self._source.findText(state["source"])
                if idx >= 0:
                    self._source.setCurrentIndex(idx)
        except Exception:
            pass
