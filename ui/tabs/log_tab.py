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

"""
Squelch -- ui/tabs/log_tab.py
QSO logbook tab. Sortable table, awards tracking,
ADIF import/export, LoTW/QRZ queue, manual entry,
callsign lookup integration.
"""

import logging
from pathlib import Path
from datetime import datetime, timezone
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QLineEdit,
    QComboBox, QSplitter, QFrame, QMessageBox,
    QFileDialog, QDialog, QFormLayout, QDialogButtonBox,
    QProgressBar, QSpinBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QColor, QBrush, QFont

from core.log_db import LogDB, QSO, get_log_db
from core.validator import callsign_soft, grid_square_soft

log = logging.getLogger(__name__)

# Column indices
C_DATE  = 0
C_TIME  = 1
C_CALL  = 2
C_BAND  = 3
C_MODE  = 4
C_RST_S = 5
C_RST_R = 6
C_GRID  = 7
C_DXCC  = 8
C_LOTW  = 9
C_QRZ   = 10
C_DIST  = 11

HEADERS = [
    "Date","Time","Callsign","Band","Mode",
    "RST Sent","RST Rcvd","Grid","DXCC",
    "LoTW","QRZ","Dist km"
]

STATUS_COLORS = {
    "none":      QColor("#333333"),
    "pending":   QColor("#555500"),
    "queued":    QColor("#005555"),
    "uploaded":  QColor("#005500"),
    "confirmed": QColor("#00aa00"),
    "error":     QColor("#550000"),
}

STATUS_LABELS = {
    "none":      "—",
    "pending":   "⏳",
    "queued":    "📤",
    "uploaded":  "✓",
    "confirmed": "✅",
    "error":     "❌",
}


class LogTab(QWidget):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.cfg    = config
        self.log_db = get_log_db()
        self._all_qsos: list[QSO] = []
        self._build()
        self._load_log()
        # Refresh every 30 seconds for new auto-logged QSOs
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(30_000)
        self._refresh_timer.timeout.connect(self._load_log)
        self._refresh_timer.start()

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── Stats bar ─────────────────────────────────────────────────────
        stats = QHBoxLayout()
        self._stat_widgets = {}
        for key, label in [
            ("total",  "Total QSOs"),
            ("dxcc",   "DXCC"),
            ("was",    "WAS"),
            ("grids",  "Grids"),
            ("lotw",   "LoTW ✅"),
        ]:
            grp = QGroupBox(label)
            grp.setFixedHeight(56)
            gl = QVBoxLayout(grp)
            val = QLabel("0")
            val.setStyleSheet(
                "color:#3fbe6f;font-size:18px;"
                "font-weight:bold;font-family:'Courier New';")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            gl.addWidget(val)
            self._stat_widgets[key] = val
            stats.addWidget(grp)
        root.addLayout(stats)

        # ── Search / filter bar ───────────────────────────────────────────
        filter_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText(self.tr("Search callsign…"))
        self._search.textChanged.connect(self._apply_filter)
        self._search.setMaxLength(15)
        filter_row.addWidget(self._search, 2)

        self._band_filter = QComboBox()
        self._band_filter.addItems([
            self.tr("All bands"),
            "160m","80m","40m","30m","20m",
            "17m","15m","12m","10m","6m","2m","70cm"
        ])
        self._band_filter.currentTextChanged.connect(
            self._apply_filter)
        filter_row.addWidget(self._band_filter)

        self._mode_filter = QComboBox()
        self._mode_filter.addItems([
            self.tr("All modes"),
            "FT8","FT4","WSPR","JS8","SSB","CW",
            "PSK31","RTTY","FM","AM","SSTV"
        ])
        self._mode_filter.currentTextChanged.connect(
            self._apply_filter)
        filter_row.addWidget(self._mode_filter)

        refresh_btn = QPushButton(self.tr("↺ Refresh"))
        refresh_btn.setFixedWidth(90)
        refresh_btn.clicked.connect(self._load_log)
        filter_row.addWidget(refresh_btn)
        root.addLayout(filter_row)

        # ── QSO table ─────────────────────────────────────────────────────
        self._table = QTableWidget(0, len(HEADERS))
        self._table.setHorizontalHeaderLabels(HEADERS)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(
            C_DXCC, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet("""
            QTableWidget{
              background:#0d0d0d;color:#aaa;
              gridline-color:#1a1a1a;font-size:11px;
              font-family:'Courier New';
              alternate-background-color:#111;
              selection-background-color:#1a3a1a;}
            QHeaderView::section{
              background:#141414;color:#666;
              border:none;font-size:10px;padding:3px;}
        """)
        root.addWidget(self._table, 4)

        # ── Action buttons ────────────────────────────────────────────────
        btn_row = QHBoxLayout()

        add_btn = QPushButton(self.tr("+ Manual Entry"))
        add_btn.clicked.connect(self._manual_entry)
        btn_row.addWidget(add_btn)

        adif_exp = QPushButton(self.tr("Export ADIF"))
        adif_exp.clicked.connect(self._export_adif)
        btn_row.addWidget(adif_exp)

        adif_imp = QPushButton(self.tr("Import ADIF"))
        adif_imp.clicked.connect(self._import_adif)
        btn_row.addWidget(adif_imp)

        lotw_btn = QPushButton(self.tr("Upload LoTW queue"))
        lotw_btn.clicked.connect(self._show_lotw_queue)
        btn_row.addWidget(lotw_btn)

        qrz_btn = QPushButton(self.tr("Upload QRZ queue"))
        qrz_btn.clicked.connect(self._show_qrz_queue)
        btn_row.addWidget(qrz_btn)

        btn_row.addStretch()

        self._queue_label = QLabel("")
        self._queue_label.setStyleSheet(
            "color:#666; font-size:10px;")
        btn_row.addWidget(self._queue_label)

        root.addLayout(btn_row)

        # ── Awards panel ──────────────────────────────────────────────────
        awards_grp = QGroupBox(self.tr("Awards Progress"))
        awards_l   = QHBoxLayout(awards_grp)

        # DXCC progress
        dxcc_l = QVBoxLayout()
        dxcc_l.addWidget(QLabel("DXCC (340 total)"))
        self._dxcc_bar = QProgressBar()
        self._dxcc_bar.setRange(0, 340)
        self._dxcc_bar.setStyleSheet(
            "QProgressBar{background:#111;border:1px solid #333;"
            "border-radius:3px;}"
            "QProgressBar::chunk{background:#3fbe6f;}")
        dxcc_l.addWidget(self._dxcc_bar)
        awards_l.addLayout(dxcc_l)

        # WAS progress
        was_l = QVBoxLayout()
        was_l.addWidget(QLabel("WAS (50 states)"))
        self._was_bar = QProgressBar()
        self._was_bar.setRange(0, 50)
        self._was_bar.setStyleSheet(
            "QProgressBar{background:#111;border:1px solid #333;"
            "border-radius:3px;}"
            "QProgressBar::chunk{background:#44aaff;}")
        was_l.addWidget(self._was_bar)
        awards_l.addLayout(was_l)

        # Grids progress
        grids_l = QVBoxLayout()
        grids_l.addWidget(QLabel("Grid squares worked"))
        self._grids_bar = QProgressBar()
        self._grids_bar.setRange(0, 500)
        self._grids_bar.setStyleSheet(
            "QProgressBar{background:#111;border:1px solid #333;"
            "border-radius:3px;}"
            "QProgressBar::chunk{background:#aa44ff;}")
        grids_l.addWidget(self._grids_bar)
        awards_l.addLayout(grids_l)

        root.addWidget(awards_grp)

    # ── Data loading ──────────────────────────────────────────────────────

    def _load_log(self):
        try:
            self._all_qsos = self.log_db.recent_qsos(limit=5000)
            self._apply_filter()
            self._update_stats()
        except Exception as e:
            log.error(f"Log load failed: {e}")

    def _apply_filter(self):
        call_filter = self._search.text().strip().upper()
        band_filter = self._band_filter.currentText()
        mode_filter = self._mode_filter.currentText()

        filtered = []
        for q in self._all_qsos:
            if call_filter and call_filter not in q.call.upper():
                continue
            if band_filter != self.tr("All bands") and q.band != band_filter:
                continue
            if mode_filter != self.tr("All modes") and q.mode != mode_filter:
                continue
            filtered.append(q)

        self._populate_table(filtered)

    def _populate_table(self, qsos: list[QSO]):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)

        for q in qsos:
            row = self._table.rowCount()
            self._table.insertRow(row)

            # Parse datetime
            try:
                dt = datetime.fromisoformat(
                    q.datetime_on.replace('Z', '+00:00'))
                date_str = dt.strftime("%Y-%m-%d")
                time_str = dt.strftime("%H:%M")
            except Exception:
                date_str = q.datetime_on[:10]
                time_str = q.datetime_on[11:16]

            values = [
                date_str, time_str, q.call,
                q.band, q.mode,
                q.rst_sent, q.rst_rcvd,
                q.grid or "—",
                q.dxcc or q.country or "—",
                STATUS_LABELS.get(q.lotw_status, "—"),
                STATUS_LABELS.get(q.qrz_status, "—"),
                f"{q.dist_km:.0f}" if hasattr(q, 'dist_km') and q.dist_km else "—",
            ]

            for col, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                # Color LoTW/QRZ status cells
                if col == C_LOTW:
                    color = STATUS_COLORS.get(q.lotw_status,
                                              STATUS_COLORS["none"])
                    item.setBackground(QBrush(color))
                elif col == C_QRZ:
                    color = STATUS_COLORS.get(q.qrz_status,
                                              STATUS_COLORS["none"])
                    item.setBackground(QBrush(color))

                self._table.setItem(row, col, item)

        self._table.setSortingEnabled(True)

    def _update_stats(self):
        try:
            stats = self.log_db.stats()
            self._stat_widgets["total"].setText(
                str(stats["total_qsos"]))
            self._stat_widgets["dxcc"].setText(
                str(stats["dxcc_worked"]))
            self._stat_widgets["was"].setText(
                str(stats["was_worked"]))
            self._stat_widgets["grids"].setText(
                str(stats["grids_worked"]))

            # LoTW confirmed count
            confirmed = sum(
                1 for q in self._all_qsos
                if q.lotw_status == "confirmed")
            self._stat_widgets["lotw"].setText(str(confirmed))

            # Awards bars
            self._dxcc_bar.setValue(stats["dxcc_worked"])
            self._was_bar.setValue(stats["was_worked"])
            self._grids_bar.setValue(
                min(stats["grids_worked"], 500))

            # Queue counts
            lotw_q = len(self.log_db.lotw_pending())
            qrz_q  = len(self.log_db.qrz_pending())
            self._queue_label.setText(
                f"LoTW queue: {lotw_q}  |  QRZ queue: {qrz_q}")

        except Exception as e:
            log.error(f"Stats update: {e}")

    # ── Manual entry ──────────────────────────────────────────────────────

    def _manual_entry(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("Manual QSO Entry"))
        dlg.setMinimumWidth(380)
        lay = QFormLayout(dlg)

        fields = {}
        for label, key, placeholder in [
            ("Callsign:",  "call",     "W4XYZ"),
            ("Band:",      "band",     "20m"),
            ("Mode:",      "mode",     "SSB"),
            ("RST Sent:",  "rst_sent", "59"),
            ("RST Rcvd:",  "rst_rcvd", "59"),
            ("Grid:",      "grid",     "FM18"),
            ("Name:",      "name",     ""),
            ("Comment:",   "comment",  ""),
        ]:
            edit = QLineEdit()
            edit.setPlaceholderText(placeholder)
            lay.addRow(label, edit)
            fields[key] = edit

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addRow(btns)

        if dlg.exec():
            call = callsign_soft(fields["call"].text())
            if not call:
                QMessageBox.warning(
                    self, "Invalid",
                    "Please enter a valid callsign.")
                return
            try:
                qso = QSO(
                    call      = call,
                    band      = fields["band"].text().strip(),
                    mode      = fields["mode"].text().strip().upper(),
                    rst_sent  = fields["rst_sent"].text().strip() or "59",
                    rst_rcvd  = fields["rst_rcvd"].text().strip() or "59",
                    grid      = grid_square_soft(
                        fields["grid"].text()),
                    name      = fields["name"].text().strip()[:50],
                    comment   = fields["comment"].text().strip()[:200],
                    my_call   = self.cfg.callsign,
                    my_grid   = self.cfg.grid,
                    source    = "manual",
                )
                self.log_db.log_qso(qso)
                self._load_log()
                QMessageBox.information(
                    self, self.tr("QSO Logged"),
                    f"QSO with {call} logged successfully.")
            except Exception as e:
                QMessageBox.warning(
                    self, "Error", f"Could not log QSO: {e}")

    # ── ADIF export ───────────────────────────────────────────────────────

    def _export_adif(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Export ADIF"),
            f"squelch_log_{datetime.now().strftime('%Y%m%d')}.adi",
            "ADIF Files (*.adi *.adif)")
        if not path:
            return
        try:
            count = self.log_db.export_adif(Path(path))
            QMessageBox.information(
                self, self.tr("Export Complete"),
                f"Exported {count} QSOs to {path}")
        except Exception as e:
            QMessageBox.warning(
                self, "Export Failed", str(e))

    # ── ADIF import ───────────────────────────────────────────────────────

    def _import_adif(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Import ADIF"),
            "", "ADIF Files (*.adi *.adif *.ADI *.ADIF)")
        if not path:
            return
        try:
            import adif_io
            with open(path, 'r', encoding='utf-8',
                      errors='replace') as f:
                qsos, _ = adif_io.read_from_string(f.read())

            count = 0
            for record in qsos:
                try:
                    call = callsign_soft(
                        record.get('CALL', ''))
                    if not call:
                        continue
                    qso = QSO(
                        call      = call,
                        band      = record.get('BAND', '').lower(),
                        mode      = record.get('MODE', '').upper(),
                        rst_sent  = record.get('RST_SENT', '59'),
                        rst_rcvd  = record.get('RST_RCVD', '59'),
                        grid      = grid_square_soft(
                            record.get('GRIDSQUARE', '')),
                        name      = record.get('NAME', '')[:50],
                        comment   = record.get('COMMENT', '')[:200],
                        my_call   = self.cfg.callsign,
                        my_grid   = self.cfg.grid,
                        source    = "adif_import",
                    )
                    self.log_db.log_qso(qso)
                    count += 1
                except Exception:
                    pass

            self._load_log()
            QMessageBox.information(
                self, self.tr("Import Complete"),
                f"Imported {count} QSOs from {path}")
        except Exception as e:
            QMessageBox.warning(
                self, "Import Failed", str(e))

    # ── LoTW / QRZ queue ─────────────────────────────────────────────────

    def _show_lotw_queue(self):
        pending = self.log_db.lotw_pending()
        QMessageBox.information(
            self, self.tr("LoTW Upload Queue"),
            f"{len(pending)} QSOs pending LoTW upload.\n\n"
            "LoTW upload via TQSL will be available in Chunk 10.\n"
            "Export ADIF and upload manually via TQSL for now.")

    def _show_qrz_queue(self):
        pending = self.log_db.qrz_pending()
        QMessageBox.information(
            self, self.tr("QRZ Upload Queue"),
            f"{len(pending)} QSOs pending QRZ upload.\n\n"
            "QRZ logbook sync will be available in Chunk 10.")

    # ── Public ────────────────────────────────────────────────────────────

    def refresh(self):
        """Called externally when a new QSO is logged."""
        self._load_log()
