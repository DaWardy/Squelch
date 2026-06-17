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

from __future__ import annotations
"""Squelch -- ui/tabs/log_tab.py
QSO logbook tab. Sortable table, awards tracking,
ADIF import/export, LoTW/QRZ queue, manual entry,
callsign lookup integration.
"""
from core.constants import APP_VERSION
from core.sanitize import csv_safe
from core.guest_op import operating_callsign

import logging
from pathlib import Path
from datetime import datetime, timezone
from ui.panel import SquelchPanel
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QLineEdit,
    QComboBox, QSplitter, QFrame, QMessageBox,
    QFileDialog, QDialog, QFormLayout, QDialogButtonBox,
    QProgressBar, QSpinBox, QProgressDialog, QDateEdit,
    QDateTimeEdit
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QDate, QDateTime
from PyQt6.QtGui import QColor, QBrush, QFont

from core.log_db import LogDB, QSO, get_log_db
from core.validator import callsign_soft, grid_square_soft

log = logging.getLogger(__name__)


def _adif_to_iso(date_str: str, time_str: str) -> str:
    """Convert ADIF QSO_DATE (YYYYMMDD) + TIME_ON (HHMM[SS]) to ISO UTC."""
    if not date_str or len(date_str) < 8:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        y = int(date_str[:4])
        m = int(date_str[4:6])
        d = int(date_str[6:8])
        h  = int(time_str[:2]) if len(time_str) >= 2 else 0
        mn = int(time_str[2:4]) if len(time_str) >= 4 else 0
        sc = int(time_str[4:6]) if len(time_str) >= 6 else 0
        return f"{y:04d}-{m:02d}-{d:02d}T{h:02d}:{mn:02d}:{sc:02d}Z"
    except (ValueError, TypeError):
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")



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
C_NAME  = 12

HEADERS = [
    "Date","Time","Callsign","Band","Mode",
    "RST Sent","RST Rcvd","Grid","DXCC",
    "LoTW","QRZ","Dist km","Name"
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


class LogTab(SquelchPanel, QWidget):
    panel_id    = "log"
    panel_title = "Log"

    def panel_actions(self) -> list:
        """Toolbar actions for workspace-mode title bar."""
        from PyQt6.QtGui import QAction
        a_add = QAction("+ Entry", self)
        a_add.setToolTip("Add QSO manually")
        a_add.triggered.connect(self._manual_entry)

        a_exp = QAction("⬇ ADIF", self)
        a_exp.setToolTip("Export log as ADIF")
        a_exp.triggered.connect(self._export_adif)

        a_ref = QAction("↺", self)
        a_ref.setToolTip("Refresh log from database")
        a_ref.triggered.connect(self._load_log)

        return [a_add, a_exp, a_ref]

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.cfg    = config
        self.log_db = get_log_db()
        self._all_qsos: list[QSO] = []
        self._build()
        self._build_awards_panel()
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
        self._build_stats_bar(root)
        self._build_filter_bar(root)
        self._build_qso_table(root)
        self._build_action_buttons(root)
        self._build_awards_section(root)

    def _build_stats_bar(self, root):
        """Top row of QSO count / award stat counters."""
        stats = QHBoxLayout()
        self._stat_widgets = {}
        for key, label in [
            ("total",  "Total QSOs"),
            ("dxcc",   "DXCC"),
            ("was",    "WAS"),
            ("grids",  "Grids"),
            ("lotw",   "LoTW ✅"),
            ("rate",   "QSOs / hr"),
        ]:
            grp = QGroupBox(label)
            grp.setFixedHeight(56)
            gl = QVBoxLayout(grp)
            val = QLabel("0")
            val.setStyleSheet(
                "color:#3fbe6f;"
                "font-weight:bold;font-family:'Courier New';")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            gl.addWidget(val)
            self._stat_widgets[key] = val
            stats.addWidget(grp)
        root.addLayout(stats)

    def _build_filter_bar(self, root):
        """Search box + band/mode filter dropdowns."""
        filter_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText(
            self.tr("Search callsign, name, grid…"))
        self._search.textChanged.connect(self._apply_filter)
        self._search.setMaxLength(20)
        filter_row.addWidget(self._search, 2)

        self._band_filter = QComboBox()
        self._band_filter.addItems([
            self.tr("All bands"),
            "160m","80m","40m","30m","20m",
            "17m","15m","12m","10m","6m","2m","70cm"
        ])
        self._band_filter.currentTextChanged.connect(self._apply_filter)
        filter_row.addWidget(self._band_filter)

        self._mode_filter = QComboBox()
        self._mode_filter.addItems([
            self.tr("All modes"),
            "FT8","FT4","WSPR","JS8","SSB","CW",
            "PSK31","RTTY","FM","AM","SSTV"
        ])
        self._mode_filter.currentTextChanged.connect(self._apply_filter)
        filter_row.addWidget(self._mode_filter)

        filter_row.addWidget(QLabel(self.tr("From:")))
        self._date_from = QDateEdit()
        self._date_from.setDisplayFormat("yyyy-MM-dd")
        self._date_from.setDate(QDate(2000, 1, 1))
        self._date_from.setCalendarPopup(True)
        self._date_from.setMaximumWidth(105)
        self._date_from.dateChanged.connect(self._apply_filter)
        filter_row.addWidget(self._date_from)

        filter_row.addWidget(QLabel("–"))

        self._date_to = QDateEdit()
        self._date_to.setDisplayFormat("yyyy-MM-dd")
        self._date_to.setDate(QDate(2099, 12, 31))
        self._date_to.setCalendarPopup(True)
        self._date_to.setMaximumWidth(105)
        self._date_to.dateChanged.connect(self._apply_filter)
        filter_row.addWidget(self._date_to)

        refresh_btn = QPushButton(self.tr("↺ Refresh"))
        refresh_btn.setFixedWidth(90)
        refresh_btn.clicked.connect(self._load_log)
        filter_row.addWidget(refresh_btn)
        root.addLayout(filter_row)

    def _build_qso_table(self, root):
        """Main QSO table. setSortingEnabled deferred to showEvent."""
        self._table = QTableWidget(0, len(HEADERS))
        self._table.setHorizontalHeaderLabels(HEADERS)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(C_DXCC, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        # setSortingEnabled(True) deferred to showEvent — blocks in offscreen Qt
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet("""
            QTableWidget{
              background:#0d0d0d;
              gridline-color:#1a1a1a;
              font-family:'Courier New';
              alternate-background-color:#0a1a0a;}
            QTableWidget::item{
              padding:2px 4px;}
            QTableWidget::item:hover{
              background:#1a2a1a;color:#fff;}
            QTableWidget::item:selected{
              background:#1a3a1a;color:#3fbe6f;}
            QHeaderView::section{
              background:#141414;
              border:none;padding:4px;}
        """)
        self._table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        # Restore saved column widths
        from PyQt6.QtCore import QSettings
        _settings = QSettings("Squelch", "squelch")
        for col in range(self._table.columnCount()):
            w = _settings.value(f"log/col_{col}_width")
            if w:
                self._table.setColumnWidth(col, int(w))
        self._table.horizontalHeader().sectionResized.connect(
            self._save_column_width)
        self._table.customContextMenuRequested.connect(
            self._log_context_menu)
        self._table.doubleClicked.connect(
            lambda idx: self._edit_qso_row(idx.row()))
        root.addWidget(self._table, 4)

    def _save_column_width(self, col: int, _old: int, new_w: int):
        """Persist column width to QSettings."""
        from PyQt6.QtCore import QSettings
        QSettings("Squelch", "squelch").setValue(
            f"log/col_{col}_width", new_w)

    def showEvent(self, event):
        """Defer setSortingEnabled — blocks in offscreen Qt during init."""
        super().showEvent(event)
        if not getattr(self, "_sorting_enabled", False):
            self._sorting_enabled = True
            self._table.setSortingEnabled(True)

    def _build_action_buttons(self, root):
        """Row of export/import/upload action buttons."""
        btn_row = QHBoxLayout()

        add_btn = QPushButton(self.tr("+ Manual Entry"))
        add_btn.setToolTip("Add a QSO manually\nOpens entry form with dropdowns")
        add_btn.clicked.connect(self._manual_entry)
        btn_row.addWidget(add_btn)

        adif_exp = QPushButton(self.tr("Export ADIF"))
        adif_exp.clicked.connect(self._export_adif)
        btn_row.addWidget(adif_exp)

        adif_imp = QPushButton(self.tr("Import ADIF"))
        adif_imp.clicked.connect(self._import_adif)
        btn_row.addWidget(adif_imp)

        stats_btn = QPushButton(self.tr("📊 Analytics…"))
        stats_btn.setToolTip("Band, mode, year and entity breakdown")
        stats_btn.clicked.connect(self._show_analytics)
        btn_row.addWidget(stats_btn)

        lotw_btn = QPushButton(self.tr("Upload LoTW queue"))
        lotw_btn.setToolTip(
            "Upload pending QSOs to ARRL LoTW\n"
            "Requires TQSL and LoTW credentials in Settings → APIs")
        lotw_btn.clicked.connect(self._show_lotw_queue)
        btn_row.addWidget(lotw_btn)

        qrz_btn = QPushButton(self.tr("Upload QRZ queue"))
        qrz_btn.setToolTip(
            "Sync log with QRZ logbook\n"
            "Requires QRZ Logbook API key in Settings → APIs")
        qrz_btn.clicked.connect(self._show_qrz_queue)
        btn_row.addWidget(qrz_btn)

        clublog_btn = QPushButton(self.tr("Upload ClubLog"))
        clublog_btn.setToolTip(
            "Upload pending QSOs to ClubLog\n"
            "Requires ClubLog email and password in Settings → APIs")
        clublog_btn.clicked.connect(self._show_clublog_upload)
        btn_row.addWidget(clublog_btn)

        eqsl_btn = QPushButton(self.tr("Upload eQSL"))
        eqsl_btn.setToolTip(
            "Upload log to eQSL.cc\n"
            "Requires eQSL username and password in Settings → APIs")
        eqsl_btn.clicked.connect(self._show_eqsl_upload)
        btn_row.addWidget(eqsl_btn)

        hrdlog_btn = QPushButton(self.tr("Upload HRDLog"))
        hrdlog_btn.setToolTip(
            "Upload log to HRDLog.net\n"
            "Requires callsign and API key in Settings → APIs")
        hrdlog_btn.clicked.connect(self._show_hrdlog_upload)
        btn_row.addWidget(hrdlog_btn)

        btn_row.addStretch()
        self._queue_label = QLabel("")
        self._queue_label.setStyleSheet(" ")
        btn_row.addWidget(self._queue_label)
        root.addLayout(btn_row)

    def _build_awards_section(self, root):
        """Simple inline DXCC/WAS/Grids progress bars above the awards panel."""
        awards_grp = QGroupBox(self.tr("Awards Progress"))
        awards_l   = QHBoxLayout(awards_grp)

        dxcc_l = QVBoxLayout()
        dxcc_l.addWidget(QLabel("DXCC (340 total)"))
        self._dxcc_bar = QProgressBar()
        self._dxcc_bar.setRange(0, 340)
        self._dxcc_bar.setStyleSheet(
            "QProgressBar::chunk{background:#3fbe6f;border-radius:2px;}")
        dxcc_l.addWidget(self._dxcc_bar)
        awards_l.addLayout(dxcc_l)

        was_l = QVBoxLayout()
        was_l.addWidget(QLabel("WAS (50 states)"))
        self._was_bar = QProgressBar()
        self._was_bar.setRange(0, 50)
        self._was_bar.setStyleSheet(
            "QProgressBar::chunk{background:#44aaff;border-radius:2px;}")
        was_l.addWidget(self._was_bar)
        awards_l.addLayout(was_l)

        grids_l = QVBoxLayout()
        grids_l.addWidget(QLabel("Grid squares worked"))
        self._grids_bar = QProgressBar()
        self._grids_bar.setRange(0, 500)
        self._grids_bar.setStyleSheet(
            "QProgressBar::chunk{background:#aa44ff;border-radius:2px;}")
        grids_l.addWidget(self._grids_bar)
        awards_l.addLayout(grids_l)

        dxcc_btn = QPushButton(self.tr("DX Needed…"))
        dxcc_btn.setFixedWidth(90)
        dxcc_btn.setToolTip(
            self.tr("Show full list of worked / needed DXCC entities"))
        dxcc_btn.clicked.connect(self._show_dxcc_needed)
        awards_l.addWidget(dxcc_btn, 0, Qt.AlignmentFlag.AlignBottom)

        root.addWidget(awards_grp)

    def _show_dxcc_needed(self):
        """Open the DXCC entity status dialog."""
        from core.awards import AwardTracker
        from ui.dialogs.dxcc_needed_dialog import DXCCNeededDialog
        tracker = AwardTracker(self.log_db)
        progress = tracker.compute_dxcc()
        dlg = DXCCNeededDialog(
            worked=progress.entities,
            confirmed=progress.confirmed_entities,
            parent=self)
        dlg.exec()

    # ── Data loading ──────────────────────────────────────────────────────

    def _build_awards_panel(self):
        """Add collapsible awards progress panel."""
        from PyQt6.QtWidgets import (
            QGroupBox, QProgressBar, QGridLayout)

        awards_grp = QGroupBox("Award Progress")
        awards_grp.setCheckable(True)
        awards_grp.setChecked(False)
        awards_grp.setToolTip(
            "Award progress computed from your log\n"
            "Click to expand/collapse")
        ag = QGridLayout(awards_grp)
        ag.setSpacing(4)

        self._award_bars = {}
        awards_display = [
            ("DXCC",  "DXCC (100 entities)"),
            ("WAS",   "WAS (50 states)"),
            ("WAZ",   "WAZ (40 CQ zones)"),
            ("VUCC",  "VUCC VHF (100 grids)"),
            ("DXCC-FT8", "DXCC-FT8"),
            ("DXCC-CW",  "DXCC-CW"),
        ]
        for row, (key, label) in enumerate(awards_display):
            ag.addWidget(QLabel(label), row, 0)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setFixedHeight(16)
            bar.setFormat("%v/%m")
            bar.setTextVisible(True)
            bar.setStyleSheet(
                "QProgressBar{border-radius:3px;text-align:center;}"
                "QProgressBar::chunk{"
                "background:#3fbe6f;border-radius:2px;}")
            self._award_bars[key] = bar
            ag.addWidget(bar, row, 1)
            lbl = QLabel("0/100")
            lbl.setStyleSheet("")
            lbl.setFixedWidth(60)
            ag.addWidget(lbl, row, 2)
            self._award_bars[key + "_lbl"] = lbl

        # Add to root layout
        self.layout().addWidget(awards_grp)
        self._awards_grp = awards_grp
        QTimer.singleShot(1500, self._update_awards)

    def _update_awards(self):
        """Compute and display award progress."""
        try:
            from core.awards import AwardTracker
            tracker = AwardTracker(self.log_db)
            awards  = tracker.compute_all()

            for key, progress in awards.items():
                bar = self._award_bars.get(key)
                lbl = self._award_bars.get(key + "_lbl")
                if bar:
                    bar.setMaximum(progress.needed)
                    bar.setValue(min(
                        progress.worked, progress.needed))
                    if progress.is_complete:
                        bar.setStyleSheet(
                            "QProgressBar::chunk{"
                            "background:#44aaff;"
                            "border-radius:2px;}")
                if lbl:
                    lbl.setText(
                        f"{progress.worked}/{progress.needed}")
        except Exception as e:
            log.debug(f"Awards update: {e}")

    def _load_log(self):
        try:
            self._all_qsos = self.log_db.recent_qsos(limit=5000)
            self._apply_filter()
            self._update_stats()
            QTimer.singleShot(100, self._update_awards)
        except Exception as e:
            log.error(f"Log load failed: {e}")

    def _apply_filter(self):
        call_filter = self._search.text().strip().upper()
        band_filter = self._band_filter.currentText()
        mode_filter = self._mode_filter.currentText()
        date_from_str = self._date_from.date().toString("yyyy-MM-dd")
        date_to_str   = self._date_to.date().toString("yyyy-MM-dd")
        filter_dates  = (date_from_str != "2000-01-01"
                         or date_to_str != "2099-12-31")

        filtered = []
        for q in self._all_qsos:
            if call_filter:
                term = call_filter
                if (term not in q.call.upper()
                        and term not in q.name.upper()
                        and term not in (q.grid or "").upper()):
                    continue
            if band_filter != self.tr("All bands") and q.band != band_filter:
                continue
            if mode_filter != self.tr("All modes") and q.mode != mode_filter:
                continue
            if filter_dates:
                qdate = q.datetime_on[:10] if q.datetime_on else ""
                if qdate < date_from_str or qdate > date_to_str:
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
                f"{q.dist_km:.0f}" if q.dist_km else "—",
                q.name or "—",
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

                # Store QSO id on column 0 for right-click/edit lookup
                if col == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        getattr(q, 'id', None))
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

            # QSO rate — count QSOs in the last 60 minutes
            cutoff = datetime.now(timezone.utc).replace(
                minute=0, second=0, microsecond=0)
            hour_ago = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
            rate = sum(
                1 for q in self._all_qsos
                if q.datetime_on and q.datetime_on >= hour_ago)
            self._stat_widgets["rate"].setText(str(rate))

            # Queue counts
            lotw_q = len(self.log_db.lotw_pending())
            qrz_q  = len(self.log_db.qrz_pending())
            self._queue_label.setText(
                f"LoTW queue: {lotw_q}  |  QRZ queue: {qrz_q}")

        except Exception as e:
            log.error(f"Stats update: {e}")

    # ── Manual entry ──────────────────────────────────────────────────────

    # ── Manual QSO entry ──────────────────────────────────────────────────

    _BANDS = [
        "160m","80m","60m","40m","30m","20m",
        "17m","15m","12m","10m","6m","2m",
        "1.25m","70cm","33cm","23cm",
    ]
    _MODES = [
        "SSB","USB","LSB","AM","FM","CW",
        "FT8","FT4","WSPR","JS8","PSK31",
        "RTTY","SSTV","D-STAR","DMR","P25",
        "YSF","NXDN","Olivia","MFSK","Other",
    ]
    _RST_DEFAULTS = {
        "SSB":"59","USB":"59","LSB":"59","AM":"59","FM":"59",
        "CW":"599","FT8":"-10","FT4":"-10","WSPR":"-10",
    }

    def _build_manual_entry_fields(self, lay: "QFormLayout") -> "dict":
        """Populate *lay* with QSO entry widgets; return fields dict."""
        from PyQt6.QtWidgets import QComboBox
        cs_edit = QLineEdit()
        cs_edit.setPlaceholderText("e.g. W4XYZ")
        cs_edit.setMaxLength(15)
        lay.addRow("Callsign:", cs_edit)

        dupe_label = QLabel("")
        dupe_label.setStyleSheet("font-size:10px;font-style:italic;")
        lay.addRow("", dupe_label)

        freq_edit = QLineEdit()
        freq_edit.setPlaceholderText("MHz, e.g. 14.074")
        freq_edit.setMaxLength(12)
        freq_edit.setToolTip(
            "Frequency in MHz — auto-fills Band when recognised")
        lay.addRow("Freq (MHz):", freq_edit)

        band_combo = QComboBox()
        band_combo.addItems(self._BANDS)
        band_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        band_combo.setCurrentText("20m")
        lay.addRow("Band:", band_combo)

        def _freq_to_band():
            from core.band_plan import band_at_freq
            text = freq_edit.text().strip().replace(",", ".")
            try:
                hz = int(float(text) * 1_000_000)
                b = band_at_freq(hz)
                if b:
                    band_combo.setCurrentText(b.name)
            except (ValueError, TypeError):
                pass
        freq_edit.editingFinished.connect(_freq_to_band)

        now_utc = QDateTime.currentDateTimeUtc()
        dt_edit = QDateTimeEdit(now_utc)
        dt_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        dt_edit.setTimeSpec(Qt.TimeSpec.UTC)
        dt_edit.setToolTip("QSO date/time in UTC")
        lay.addRow("DateTime (UTC):", dt_edit)

        mode_combo = QComboBox()
        mode_combo.addItems(self._MODES)
        mode_combo.setEditable(True)
        mode_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        mode_combo.setCurrentText("SSB")
        lay.addRow("Mode:", mode_combo)

        rst_sent = QLineEdit("59")
        rst_sent.setMaxLength(6)
        rst_rcvd = QLineEdit("59")
        rst_rcvd.setMaxLength(6)
        mode_combo.currentTextChanged.connect(
            lambda m: (rst_sent.setText(self._RST_DEFAULTS.get(m, "59")),
                       rst_rcvd.setText(self._RST_DEFAULTS.get(m, "59"))))
        lay.addRow("RST Sent:", rst_sent)
        lay.addRow("RST Rcvd:", rst_rcvd)

        grid_edit = QLineEdit()
        grid_edit.setPlaceholderText("e.g. DM79rr")
        grid_edit.setMaxLength(8)
        lay.addRow("Their Grid:", grid_edit)

        name_edit = QLineEdit()
        name_edit.setMaxLength(50)
        lay.addRow("Name:", name_edit)

        lkp_status = QLabel("")
        lkp_status.setStyleSheet("color:#888;font-style:italic;font-size:10px;")
        lay.addRow("", lkp_status)

        bearing_label = QLabel("")
        bearing_label.setStyleSheet("color:#aaa;font-size:10px;")
        lay.addRow("Path:", bearing_label)

        comment_edit = QLineEdit()
        comment_edit.setMaxLength(200)
        lay.addRow("Comment:", comment_edit)

        return {
            "cs_edit": cs_edit, "freq_edit": freq_edit,
            "band_combo": band_combo, "dt_edit": dt_edit,
            "mode_combo": mode_combo, "rst_sent": rst_sent,
            "rst_rcvd": rst_rcvd, "grid_edit": grid_edit,
            "name_edit": name_edit, "lkp_status": lkp_status,
            "bearing_label": bearing_label,
            "comment_edit": comment_edit,
            "dupe_label": dupe_label,
        }

    def _build_manual_entry_dialog(self):
        """Build and return (dialog, fields_dict) for manual QSO entry."""
        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("Manual QSO Entry"))
        dlg.setMinimumWidth(420)
        lay = QFormLayout(dlg)
        lay.setSpacing(8)
        fields = self._build_manual_entry_fields(lay)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addRow(btns)
        return dlg, fields

    def _wire_callsign_lookup(self, dlg, f: dict) -> None:
        """Async callsign lookup: on cs_edit editingFinished, auto-fill name+grid."""
        from PyQt6.QtCore import QObject, pyqtSignal

        class _Bridge(QObject):
            found = pyqtSignal(object)

        bridge = _Bridge(dlg)

        def _update_bearing():
            grid = f["grid_edit"].text().strip().upper()
            my_lat = self.cfg.get("location.lat", 0.0)
            my_lon = self.cfg.get("location.lon", 0.0)
            if not grid or not (my_lat or my_lon):
                f["bearing_label"].setText("")
                return
            try:
                from core.location import _grid_to_latlon
                from core.log_db import QSO as _QSO
                q = _QSO(call="X", grid=grid, my_lat=my_lat, my_lon=my_lon)
                if q.dist_km:
                    f["bearing_label"].setText(
                        f"{q.dist_km:.0f} km  ·  {q.bearing_deg:.0f}°")
            except Exception:
                f["bearing_label"].setText("")

        def _on_cs_finished():
            call = f["cs_edit"].text().strip().upper()
            if len(call) < 3:
                return
            f["lkp_status"].setText(self.tr("Looking up…"))
            from network.qrz_lookup import get_lookup
            get_lookup(self.cfg).lookup_async(call, bridge.found.emit)

        def _on_result(info):
            f["lkp_status"].setText("")
            if not info:
                return
            if info.name and not f["name_edit"].text().strip():
                f["name_edit"].setText(info.name)
            if info.grid and not f["grid_edit"].text().strip():
                f["grid_edit"].setText(info.grid[:6])
            _update_bearing()

        bridge.found.connect(_on_result)
        f["cs_edit"].editingFinished.connect(_on_cs_finished)
        f["grid_edit"].editingFinished.connect(_update_bearing)

    def _wire_dupe_check(self, f: dict) -> None:
        """Show inline dupe warning as callsign/band/mode change."""
        dupe_lbl = f.get("dupe_label")
        if dupe_lbl is None:
            return

        def _check():
            call = f["cs_edit"].text().strip().upper()
            band = f["band_combo"].currentText()
            mode = f["mode_combo"].currentText().upper()
            if not call:
                dupe_lbl.setText("")
                return
            try:
                if self.log_db.is_duplicate(call, band, mode):
                    dupe_lbl.setStyleSheet(
                        "color:#e06c00;font-size:10px;font-style:italic;")
                    dupe_lbl.setText(
                        f"⚠ Worked {call} on {band}/{mode} in last 24h")
                elif self.log_db.worked_before(call):
                    dupe_lbl.setStyleSheet(
                        "color:#888;font-size:10px;font-style:italic;")
                    dupe_lbl.setText(
                        f"ℹ Worked {call} before (different band/mode)")
                else:
                    dupe_lbl.setText("")
            except Exception:
                dupe_lbl.setText("")

        f["cs_edit"].editingFinished.connect(_check)
        f["band_combo"].currentTextChanged.connect(lambda _: _check())
        f["mode_combo"].currentTextChanged.connect(lambda _: _check())

    def _manual_entry(self):
        """Open the manual QSO entry dialog and log on accept."""
        dlg, f = self._build_manual_entry_dialog()
        self._wire_callsign_lookup(dlg, f)
        self._wire_dupe_check(f)
        if not dlg.exec():
            return
        call = callsign_soft(f["cs_edit"].text())
        if not call:
            QMessageBox.warning(self, "Invalid Callsign",
                                "Please enter a valid callsign.")
            return
        band = f["band_combo"].currentText()
        mode = f["mode_combo"].currentText().upper()
        try:
            if self.cfg.get("log.warn_dupes", True):
                if self.log_db.is_duplicate(call, band, mode):
                    reply = QMessageBox.question(
                        self, "Duplicate QSO",
                        f"{call} already logged on {band} {mode}.\n\n"
                        "Log anyway?",
                        QMessageBox.StandardButton.Yes |
                        QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.No:
                        return
            try:
                freq_hz = int(
                    float(f["freq_edit"].text().strip()
                          .replace(",", ".")) * 1_000_000)
            except (ValueError, TypeError):
                freq_hz = 0
            dt_str = (f["dt_edit"].dateTime()
                      .toUTC().toString("yyyy-MM-ddTHH:mm:ssZ"))
            qso = QSO(
                call         = call,
                datetime_on  = dt_str,
                band         = band,
                freq_hz      = freq_hz,
                mode         = mode,
                rst_sent     = f["rst_sent"].text().strip() or "59",
                rst_rcvd     = f["rst_rcvd"].text().strip() or "59",
                grid         = grid_square_soft(f["grid_edit"].text()),
                name         = f["name_edit"].text().strip()[:50],
                comment      = f["comment_edit"].text().strip()[:200],
                my_call      = operating_callsign(self.cfg),
                my_grid      = self.cfg.grid,
                my_lat       = self.cfg.get("location.lat", 0.0),
                my_lon       = self.cfg.get("location.lon", 0.0),
                source       = "manual",
            )
            self.log_db.log_qso(qso)
            self._load_log()
            QMessageBox.information(
                self, self.tr("QSO Logged"),
                f"QSO with {call} on {band} {mode} logged.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not log QSO: {e}")

    # ── Analytics ─────────────────────────────────────────────────────────

    def _show_analytics(self):
        from ui.dialogs.log_stats_dialog import LogStatsDialog
        dlg = LogStatsDialog(self.log_db, self)
        dlg.exec()

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

    def _export_cabrillo(self):
        """Export log in Cabrillo format for contest submission."""
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Cabrillo",
            f"{self.cfg.callsign or 'log'}.cbr",
            "Cabrillo (*.cbr *.log);All Files (*)")
        if not path:
            return
        try:
            qsos    = self.log_db.recent_qsos(limit=9999)
            from core.guest_op import operating_callsign
            cs      = operating_callsign(self.cfg) or "NOCALL"
            grid    = self.cfg.grid or ""
            lines   = [
                "START-OF-LOG: 3.0",
                f"CALLSIGN: {cs}",
                f"GRID-LOCATOR: {grid}",
                "CONTEST: ",
                f"OPERATORS: {cs}",
                f"CREATED-BY: Squelch v{APP_VERSION}",
                "",
            ]
            for q in qsos:
                # Cabrillo QSO line format:
                # QSO: freq mode date time my-call rst-sent exch
                #      dx-call rst-rcvd exch
                freq_khz = int(q.freq_hz / 1000)                            if hasattr(q, "freq_hz") and q.freq_hz                            else 14074
                dt = q.datetime_on[:16].replace("T", " ")                      if "T" in q.datetime_on                      else q.datetime_on[:16]
                lines.append(
                    f"QSO: {freq_khz:>5} "
                    f"{q.mode:<2} "
                    f"{dt} "
                    f"{cs:<13} "
                    f"{q.rst_sent:<3} "
                    f"{'':>6}  "
                    f"{q.call:<13} "
                    f"{q.rst_rcvd:<3} "
                    f"{'':>6}")
            lines.append("END-OF-LOG:")
            Path(path).write_text(
                "\n".join(lines), encoding="utf-8")
            QMessageBox.information(
                self, "Cabrillo Exported",
                f"Exported {len(qsos)} QSOs to:\n{path}\n\n"
                "Fill in CONTEST: and exchange fields\n"
                "before submitting to contest robot.")
        except Exception as e:
            QMessageBox.warning(
                self, "Export Failed", str(e))

    def _export_csv(self):
        """Export log as CSV spreadsheet."""
        import csv
        import io
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV",
            f"{self.cfg.callsign or 'log'}_qsos.csv",
            "CSV (*.csv);All Files (*)")
        if not path:
            return
        try:
            qsos = self.log_db.recent_qsos(limit=9999)
            output = io.StringIO()
            writer = csv.writer(output)
            # Header
            writer.writerow([
                "Date", "Time UTC", "Callsign",
                "Band", "Mode", "Freq MHz",
                "RST Sent", "RST Rcvd",
                "Their Grid", "Name", "Country",
                "My Callsign", "My Grid",
                "LoTW Status", "Comment"])
            for q in qsos:
                dt  = q.datetime_on
                date = dt[:10] if len(dt) >= 10 else dt
                time = dt[11:16] if len(dt) >= 16 else ""
                freq = f"{q.freq_hz/1e6:.6f}"                        if hasattr(q, "freq_hz") and q.freq_hz                        else ""
                writer.writerow([csv_safe(x) for x in (
                    date, time, q.call,
                    q.band, q.mode, freq,
                    q.rst_sent, q.rst_rcvd,
                    q.grid, q.name,
                    getattr(q, "country", ""),
                    q.my_call, q.my_grid,
                    q.lotw_status, q.comment)])
            Path(path).write_text(
                output.getvalue(), encoding="utf-8")
            QMessageBox.information(
                self, "CSV Exported",
                f"Exported {len(qsos)} QSOs to:\n{path}")
        except Exception as e:
            QMessageBox.warning(
                self, "Export Failed", str(e))

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
                records, _ = adif_io.read_from_string(f.read())

            imported = skipped = errors = 0
            my_call = operating_callsign(self.cfg)
            for record in records:
                try:
                    call = callsign_soft(record.get('CALL', ''))
                    if not call:
                        continue
                    dt_on = _adif_to_iso(
                        record.get('QSO_DATE', ''),
                        record.get('TIME_ON', ''))
                    if self.log_db.has_qso_at(call, dt_on):
                        skipped += 1
                        continue
                    try:
                        freq_hz = int(float(
                            record.get('FREQ', 0) or 0) * 1e6)
                    except (ValueError, TypeError):
                        freq_hz = 0
                    try:
                        tx_pwr = float(record.get('TX_PWR', 0) or 0)
                    except (ValueError, TypeError):
                        tx_pwr = 0.0
                    try:
                        cqz = int(record.get('CQZ', 0) or 0)
                    except (ValueError, TypeError):
                        cqz = 0
                    try:
                        ituz = int(record.get('ITUZ', 0) or 0)
                    except (ValueError, TypeError):
                        ituz = 0
                    dt_off = _adif_to_iso(
                        record.get('QSO_DATE_OFF',
                                   record.get('QSO_DATE', '')),
                        record.get('TIME_OFF', ''))
                    qso = QSO(
                        call         = call,
                        datetime_on  = dt_on,
                        datetime_off = dt_off,
                        band         = record.get('BAND', '').lower(),
                        freq_hz      = freq_hz,
                        mode         = record.get('MODE', '').upper(),
                        submode      = record.get('SUBMODE', '').upper(),
                        rst_sent     = record.get('RST_SENT', '59'),
                        rst_rcvd     = record.get('RST_RCVD', '59'),
                        grid         = grid_square_soft(
                            record.get('GRIDSQUARE', '')),
                        name         = record.get('NAME', '')[:50],
                        comment      = (record.get('COMMENT', '')
                                        or record.get('NOTES', ''))[:200],
                        dxcc         = record.get('DXCC', ''),
                        country      = record.get('COUNTRY', '')[:60],
                        state        = record.get('STATE', '')[:10],
                        cqz          = cqz,
                        ituz         = ituz,
                        tx_pwr_w     = tx_pwr,
                        my_call      = my_call,
                        my_grid      = self.cfg.grid,
                        source       = "adif_import",
                    )
                    self.log_db.log_qso(qso)
                    imported += 1
                except Exception:
                    errors += 1

            self._load_log()
            msg = f"Imported {imported} QSOs."
            if skipped:
                msg += f"\nSkipped {skipped} duplicates."
            if errors:
                msg += f"\n{errors} records had errors and were skipped."
            QMessageBox.information(
                self, self.tr("Import Complete"), msg)
        except Exception as e:
            QMessageBox.warning(
                self, "Import Failed", str(e))

    # ── LoTW / QRZ queue ─────────────────────────────────────────────────

    def _log_context_menu(self, pos):
        """Right-click menu on log table rows."""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QGuiApplication
        row = self._table.rowAt(pos.y())
        if row < 0:
            return
        menu = QMenu(self)
        edit_act = menu.addAction("✏️  Edit QSO")
        copy_act = menu.addAction("📋  Copy callsign")
        menu.addSeparator()
        del_act  = menu.addAction("🗑  Delete QSO…")
        action   = menu.exec(
            self._table.mapToGlobal(pos))
        if action == edit_act:
            self._edit_qso_row(row)
        elif action == copy_act:
            qso = self._get_row_qso(row)
            if qso:
                QGuiApplication.clipboard().setText(qso.call)
        elif action == del_act:
            self._delete_qso_row(row)

    def _get_row_qso(self, row: int):
        """Get QSO object for a table row via stored QSO id."""
        try:
            item = self._table.item(row, 0)
            if item is None:
                return None
            qso_id = item.data(Qt.ItemDataRole.UserRole)
            # Find QSO by id
            if qso_id is not None:
                for q in self._all_qsos:
                    if getattr(q, 'id', None) == qso_id:
                        return q
            # Fallback: match by callsign + date from row
            call_col = 2  # callsign column
            call_item = self._table.item(row, call_col)
            if call_item:
                call = call_item.text()
                for q in self._all_qsos:
                    if q.call == call:
                        return q
        except Exception:
            pass
        return None

    def _edit_qso_row(self, row: int):
        """Open edit dialog for the QSO at this row."""
        qso = self._get_row_qso(row)
        if not qso:
            QMessageBox.warning(
                self, "Edit QSO",
                "Could not find QSO data for this row.")
            return
        self._show_edit_dialog(qso)

    def _build_edit_qso_form(self, dlg: "QDialog", qso) -> "tuple":
        """Build the edit form; return field widgets as a tuple."""
        from PyQt6.QtWidgets import (
            QFormLayout, QLineEdit, QComboBox, QDialogButtonBox)
        f = QFormLayout(dlg)
        f.setSpacing(8)
        f.setContentsMargins(12, 12, 12, 12)

        call = QLineEdit(qso.call)
        call.setMaxLength(12)
        f.addRow("Callsign:", call)

        freq_mhz = (qso.freq_hz / 1_000_000
                    if getattr(qso, "freq_hz", 0) else 0.0)
        freq = QLineEdit(f"{freq_mhz:.6g}" if freq_mhz else "")
        freq.setMaxLength(12)
        freq.setPlaceholderText("MHz, e.g. 14.074")
        f.addRow("Freq (MHz):", freq)

        band = QComboBox()
        bands = ["160m","80m","60m","40m","30m","20m",
                 "17m","15m","12m","10m","6m","2m","70cm"]
        band.addItems(bands)
        if qso.band in bands:
            band.setCurrentText(qso.band)
        f.addRow("Band:", band)

        dt_val = QDateTime.fromString(
            qso.datetime_on or "", "yyyy-MM-ddTHH:mm:ssZ")
        if not dt_val.isValid():
            dt_val = QDateTime.currentDateTimeUtc()
        dt_edit = QDateTimeEdit(dt_val)
        dt_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        dt_edit.setTimeSpec(Qt.TimeSpec.UTC)
        dt_edit.setToolTip("QSO date/time in UTC")
        f.addRow("DateTime (UTC):", dt_edit)

        mode = QComboBox()
        modes = ["FT8","FT4","CW","SSB","USB","LSB",
                 "FM","AM","WSPR","JS8","RTTY","PSK31"]
        mode.addItems(modes)
        if qso.mode in modes:
            mode.setCurrentText(qso.mode)
        f.addRow("Mode:", mode)

        rst_s = QLineEdit(qso.rst_sent)
        rst_s.setMaxLength(3)
        f.addRow("RST Sent:", rst_s)

        rst_r = QLineEdit(qso.rst_rcvd)
        rst_r.setMaxLength(3)
        f.addRow("RST Rcvd:", rst_r)

        grid = QLineEdit(qso.grid or "")
        grid.setMaxLength(8)
        f.addRow("Their Grid:", grid)

        name    = QLineEdit(qso.name or "")
        comment = QLineEdit(qso.comment or "")
        f.addRow("Name:", name)
        f.addRow("Comment:", comment)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        f.addRow(btns)
        return call, freq, band, dt_edit, mode, rst_s, rst_r, grid, name, comment

    def _apply_qso_edit(self, qso, call, freq, band, dt_edit,
                        mode, rst_s, rst_r, grid, name, comment):
        try:
            qso.call        = call.text().strip().upper()
            qso.band        = band.currentText()
            qso.mode        = mode.currentText()
            qso.rst_sent    = rst_s.text().strip()
            qso.rst_rcvd    = rst_r.text().strip()
            qso.grid        = grid.text().strip().upper()
            qso.name        = name.text().strip()
            qso.comment     = comment.text().strip()
            qso.datetime_on = (dt_edit.dateTime().toUTC()
                               .toString("yyyy-MM-ddTHH:mm:ssZ"))
            try:
                qso.freq_hz = int(
                    float(freq.text().strip()
                          .replace(",", ".")) * 1_000_000)
            except (ValueError, TypeError):
                qso.freq_hz = 0
            self.log_db.update_qso(qso)
            self._load_log()
            log.info(f"QSO edited: {qso.call}")
        except Exception as e:
            QMessageBox.warning(
                self, "Save Failed",
                f"Could not save changes:\n{e}")

    def _show_edit_dialog(self, qso):
        """Open a pre-filled QSO entry dialog for editing."""
        from PyQt6.QtWidgets import QDialog
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Edit QSO — {qso.call}")
        dlg.setMinimumWidth(360)
        fields = self._build_edit_qso_form(dlg, qso)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._apply_qso_edit(qso, *fields)

    def _delete_qso_row(self, row: int):
        """Delete QSO at row with confirmation."""
        qso = self._get_row_qso(row)
        if not qso:
            return

        reply = QMessageBox.question(
            self,
            "Delete QSO",
            f"Delete this QSO?\n\n"
            f"  {qso.call}  {qso.band}  {qso.mode}\n"
            f"  {qso.datetime_on[:16]}\n\n"
            f"This cannot be undone.",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.log_db.delete_qso(qso)
            self._load_log()
            log.info(f"QSO deleted: {qso.call}")
        except Exception as e:
            QMessageBox.warning(
                self, "Delete Failed",
                f"Could not delete QSO:\n{e}")

    def _edit_qso(self, index):
        """Handle double-click on log row."""
        self._edit_qso_row(index.row())

    def _show_lotw_queue(self):
        from network.lotw_sync import LoTWSync
        from PyQt6.QtWidgets import QProgressDialog
        pending = self.log_db.lotw_pending()
        if not pending:
            QMessageBox.information(
                self, "LoTW Queue",
                "No QSOs pending LoTW upload.\n\n"
                "All logged QSOs have been uploaded.")
            return

        reply = QMessageBox.question(
            self, "Upload to LoTW",
            f"{len(pending)} QSOs pending upload.\n\n"
            "Upload to LoTW now via TQSL?\n\n"
            "Requires:\n"
            "• TQSL installed (tqsl.arrl.org)\n"
            "• LoTW credentials in Settings → APIs",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Show progress
        prog = QProgressDialog(
            "Uploading to LoTW…", "Cancel",
            0, 100, self)
        prog.setWindowTitle("LoTW Upload")
        prog.setWindowModality(
            Qt.WindowModality.WindowModal)
        prog.show()

        sync = LoTWSync(self.cfg)

        def _on_progress(msg: str, pct: int):
            QTimer.singleShot(0, lambda:
                (prog.setLabelText(msg),
                 prog.setValue(pct)))

        def _on_complete(result):
            QTimer.singleShot(0, lambda r=result:
                self._lotw_done(r, prog))

        sync.on_progress(_on_progress)
        sync.on_complete(_on_complete)
        sync.upload_async(self.log_db, pending)

    def _lotw_done(self, result, prog):
        prog.close()
        if result.success:
            QMessageBox.information(
                self, "LoTW Upload Complete",
                f"{result.message}\n\n"
                "LoTW confirmations typically arrive "
                "within 24-48 hours.")
            # Mark as uploaded
            for q in self.log_db.lotw_pending():
                self.log_db.mark_lotw_uploaded(q.id)
            self._load_log()
        else:
            QMessageBox.warning(
                self, "LoTW Upload Failed",
                f"Upload failed:\n{result.error}\n\n"
                "Check Settings → APIs for credentials\n"
                "and Settings → Paths for TQSL location.")

    def _show_qrz_queue(self):
        from network.qrz_sync import QRZSync
        pending = self.log_db.qrz_pending()
        if not pending:
            QMessageBox.information(
                self, "QRZ Queue",
                "No QSOs pending QRZ sync.\n\n"
                "All logged QSOs have been uploaded.")
            return

        reply = QMessageBox.question(
            self, "Upload to QRZ Logbook",
            f"{len(pending)} QSOs pending upload.\n\n"
            "Upload to QRZ.com logbook now?\n\n"
            "Requires:\n"
            "• QRZ Logbook API key in Settings → APIs\n"
            "  (get it free at qrz.com → Logbook → Settings)",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        prog = QProgressDialog(
            "Uploading to QRZ Logbook…", "Cancel",
            0, 100, self)
        prog.setWindowTitle("QRZ Logbook Upload")
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.show()

        sync = QRZSync(self.cfg)

        def _on_progress(msg: str, pct: int):
            QTimer.singleShot(0, lambda: (
                prog.setLabelText(msg),
                prog.setValue(pct)))

        def _on_complete(result):
            QTimer.singleShot(0,
                lambda r=result: self._qrz_done(r, prog))

        sync.on_progress(_on_progress)
        sync.on_complete(_on_complete)
        sync.upload_async(self.log_db, pending)

    def _qrz_done(self, result, prog):
        prog.close()
        if result.success:
            QMessageBox.information(
                self, "QRZ Upload Complete",
                f"{result.message}\n\n"
                "QSOs are now visible in your QRZ logbook.")
            self._load_log()
        else:
            QMessageBox.warning(
                self, "QRZ Upload Failed",
                f"Upload failed:\n{result.error}\n\n"
                "Check Settings → APIs for your QRZ Logbook API key.\n"
                "Get the key free at qrz.com → Logbook → Settings.")

    def _show_clublog_upload(self):
        from network.dx_cluster import ClubLogClient
        client = ClubLogClient(self.cfg)
        if not client.has_credentials:
            QMessageBox.warning(
                self, "ClubLog Credentials Missing",
                "No ClubLog credentials found.\n\n"
                "Add your email and password in Settings → APIs → ClubLog.\n"
                "Register free at clublog.org.")
            return

        total = self.log_db.total_qsos()
        if not total:
            QMessageBox.information(
                self, "ClubLog",
                "No QSOs in log to upload.")
            return

        reply = QMessageBox.question(
            self, "Upload to ClubLog",
            f"Upload all {total} QSOs to ClubLog now?\n\n"
            "ClubLog will merge duplicates automatically.",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        prog = QProgressDialog(
            "Building ADIF for ClubLog…", "Cancel",
            0, 0, self)
        prog.setWindowTitle("ClubLog Upload")
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.show()

        import threading, tempfile
        from pathlib import Path as _P
        def _worker():
            try:
                fd, tmp = tempfile.mkstemp(suffix=".adif")
                import os; os.close(fd)
                tmp_path = _P(tmp)
                self.log_db.export_adif(tmp_path)
                adif = tmp_path.read_text(encoding="utf-8")
                tmp_path.unlink(missing_ok=True)
                ok = client.upload_adif(adif)
                QTimer.singleShot(0, lambda: self._clublog_done(ok, prog))
            except Exception as exc:
                QTimer.singleShot(0, lambda e=exc:
                    self._clublog_done(False, prog, str(e)))
        threading.Thread(target=_worker, daemon=True,
                         name="ClubLogUpload").start()

    def _clublog_done(self, ok: bool, prog, error: str = "") -> None:
        prog.close()
        if ok:
            QMessageBox.information(
                self, "ClubLog Upload Complete",
                "Log uploaded to ClubLog successfully.\n\n"
                "ClubLog processes uploads within a few minutes.")
        else:
            QMessageBox.warning(
                self, "ClubLog Upload Failed",
                f"Upload failed.\n{error}\n\n"
                "Check Settings → APIs for your ClubLog credentials.")

    def _show_eqsl_upload(self):
        from network.eqsl_sync import EQSLSync
        total = self.log_db.total_qsos()
        if not total:
            QMessageBox.information(
                self, "eQSL", "No QSOs in log to upload.")
            return

        reply = QMessageBox.question(
            self, "Upload to eQSL.cc",
            f"Upload all {total} QSOs to eQSL.cc now?\n\n"
            "Requires eQSL username and password in Settings → APIs.",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        prog = QProgressDialog(
            "Uploading to eQSL.cc…", "Cancel",
            0, 100, self)
        prog.setWindowTitle("eQSL Upload")
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.show()

        sync = EQSLSync(self.cfg)

        def _on_progress(msg: str, pct: int):
            QTimer.singleShot(0, lambda: (
                prog.setLabelText(msg),
                prog.setValue(pct)))

        def _on_complete(result):
            QTimer.singleShot(0,
                lambda r=result: self._eqsl_done(r, prog))

        sync.on_progress(_on_progress)
        sync.on_complete(_on_complete)
        sync.upload_async(self.log_db)

    def _eqsl_done(self, result, prog) -> None:
        prog.close()
        if result.success:
            QMessageBox.information(
                self, "eQSL Upload Complete",
                f"{result.message}")
        else:
            QMessageBox.warning(
                self, "eQSL Upload Failed",
                f"Upload failed:\n{result.error}\n\n"
                "Check Settings → APIs for your eQSL credentials.")

    def _show_hrdlog_upload(self):
        from network.hrdlog_sync import HRDLogSync
        total = self.log_db.total_qsos()
        if not total:
            QMessageBox.information(
                self, "HRDLog", "No QSOs in log to upload.")
            return

        reply = QMessageBox.question(
            self, "Upload to HRDLog.net",
            f"Upload all {total} QSOs to HRDLog.net now?\n\n"
            "Requires callsign and API key in Settings → APIs.",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        prog = QProgressDialog(
            "Uploading to HRDLog.net…", "Cancel",
            0, 100, self)
        prog.setWindowTitle("HRDLog Upload")
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.show()

        sync = HRDLogSync(self.cfg)

        def _on_progress(msg: str, pct: int):
            QTimer.singleShot(0, lambda: (
                prog.setLabelText(msg),
                prog.setValue(pct)))

        def _on_complete(result):
            QTimer.singleShot(0,
                lambda r=result: self._hrdlog_done(r, prog))

        sync.on_progress(_on_progress)
        sync.on_complete(_on_complete)
        sync.upload_async(self.log_db)

    def _hrdlog_done(self, result, prog) -> None:
        prog.close()
        if result.success:
            QMessageBox.information(
                self, "HRDLog Upload Complete",
                f"{result.message}")
        else:
            QMessageBox.warning(
                self, "HRDLog Upload Failed",
                f"Upload failed:\n{result.error}\n\n"
                "Check Settings → APIs for your HRDLog credentials.")

    # ── Public ────────────────────────────────────────────────────────────

    def refresh(self):
        """Called externally when a new QSO is logged."""
        self._load_log()
