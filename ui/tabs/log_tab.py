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
    QDateTimeEdit, QCheckBox, QAbstractItemView
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QDate, QDateTime
from PyQt6.QtGui import QColor, QBrush, QFont

from core.freq_format import (format_freq_cfg, freq_label, freq_placeholder,
                               parse_freq_input)
from core.log_db import (LogDB, QSO, get_log_db,
                         first_contact_keys, first_contact_band_keys)
from ui.tabs.log_upload_mixin import _LogUploadMixin
from ui.tabs.log_io_mixin import _LogIOMixin
from ui.tabs.log_entry_mixin import _LogEntryMixin

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

NEW_DXCC_COLOR = QColor("#5a4800")  # first contact with a DXCC entity
NEW_BAND_COLOR = QColor("#003d5a")  # first QSO with this DXCC entity on this band

QRZ_BASE_URL = "https://www.qrz.com/db/"


def _qrz_url(call: str) -> str:
    """Return the QRZ.com lookup URL for *call*."""
    return QRZ_BASE_URL + call.upper().strip()


STATUS_LABELS = {
    "none":      "—",
    "pending":   "⏳",
    "queued":    "📤",
    "uploaded":  "✓",
    "confirmed": "✅",
    "error":     "❌",
}


class LogTab(_LogUploadMixin, _LogIOMixin, _LogEntryMixin, SquelchPanel, QWidget):
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
        self._current_filtered: list[QSO] = []
        self._session_start = datetime.now(timezone.utc)
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
        self._build_contest_score_panel(root)
        self._build_activator_panel(root)
        self._build_contest_timer_panel(root)
        self._build_session_notes_panel(root)

    def _build_stats_bar(self, root):
        """Top row of QSO count / award stat counters."""
        stats = QHBoxLayout()
        self._stat_widgets = {}
        for key, label in [
            ("total",  "Total QSOs"),
            ("today",  "Today"),
            ("dxcc",   "DXCC"),
            ("was",    "WAS"),
            ("waz",    "WAZ"),
            ("bands",  "Bands"),
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
            self.tr("Search callsign, name, grid, DXCC, country, state, comment…"))
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

        self._firsts_filter = QCheckBox(self.tr("🏆 Firsts"))
        self._firsts_filter.setToolTip(
            "Show only first-contact QSOs\n"
            "(new DXCC entity or new band slot for a DXCC entity)")
        self._firsts_filter.stateChanged.connect(self._apply_filter)
        filter_row.addWidget(self._firsts_filter)

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
        adif_exp.setToolTip("Export log as ADIF\nHonours active filter")
        adif_exp.clicked.connect(self._export_adif)
        btn_row.addWidget(adif_exp)

        csv_exp = QPushButton(self.tr("Export CSV"))
        csv_exp.setToolTip("Export log as CSV spreadsheet\nHonours active filter")
        csv_exp.clicked.connect(self._export_csv)
        btn_row.addWidget(csv_exp)

        adif_imp = QPushButton(self.tr("Import ADIF"))
        adif_imp.clicked.connect(self._import_adif)
        btn_row.addWidget(adif_imp)

        stats_btn = QPushButton(self.tr("📊 Analytics…"))
        stats_btn.setToolTip("Band, mode, year and entity breakdown")
        stats_btn.clicked.connect(self._show_analytics)
        btn_row.addWidget(stats_btn)

        sess_btn = QPushButton(self.tr("📋 Session…"))
        sess_btn.setToolTip(
            "Summary for this operating session\n"
            "(QSOs, bands, new DXCC, best DX distance)")
        sess_btn.clicked.connect(self._show_session_summary)
        btn_row.addWidget(sess_btn)

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

    def _build_contest_score_panel(self, root) -> None:
        """Collapsible live contest score breakdown."""
        from PyQt6.QtWidgets import QToolButton as _TB
        from PyQt6.QtWidgets import QTableWidget as _TW, QTableWidgetItem as _TWI

        toggle = _TB(); toggle.setText("▶ Contest Score (live)")
        toggle.setCheckable(True)
        toggle.setChecked(False)
        toggle.setToolTip(
            "Expand for live QSO/multiplier/score breakdown.\n"
            "Scoring: CW/FT8/digital = 2 pts, SSB/AM/FM = 1 pt.\n"
            "Multipliers = unique DXCC entities worked.")
        toggle.setStyleSheet(
            "QToolButton{background:transparent;border:none;"
            "font-weight:bold;text-align:left;padding:4px 8px;}")
        root.addWidget(toggle)

        self._cs_body = QWidget()
        self._cs_body.setVisible(False)
        toggle.toggled.connect(self._cs_body.setVisible)
        cs_lay = QVBoxLayout(self._cs_body)
        cs_lay.setContentsMargins(8, 2, 8, 4)
        cs_lay.setSpacing(2)

        self._cs_table = _TW(0, 3)
        self._cs_table.setHorizontalHeaderLabels(["Band", "QSOs", "Points"])
        self._cs_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self._cs_table.setMaximumHeight(150)
        self._cs_table.setStyleSheet(
            "QTableWidget{background:#0a0a0a;gridline-color:#1a1a1a;}"
            "QHeaderView::section{background:#141414;}")
        self._cs_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        cs_lay.addWidget(self._cs_table)

        self._cs_summary = QLabel("")
        self._cs_summary.setStyleSheet(
            "color:#3fbe6f;font-family:'Courier New';font-size:12px;"
            "font-weight:bold;padding:4px;")
        cs_lay.addWidget(self._cs_summary)
        root.addWidget(self._cs_body)

    def _update_contest_score(self) -> None:
        """Refresh the contest score panel from LogDB."""
        if not hasattr(self, "_cs_body") or not self._cs_body.isVisible():
            return
        try:
            cs = self.log_db.contest_score()
            BAND_ORDER = ["160m","80m","60m","40m","30m","20m",
                          "17m","15m","12m","10m","6m","2m","?"]
            self._cs_table.setRowCount(0)
            by_band = cs["by_band"]
            for band in BAND_ORDER:
                if band not in by_band:
                    continue
                qsos = by_band[band]
                r = self._cs_table.rowCount()
                self._cs_table.insertRow(r)
                for col, txt in [(0, band), (1, str(qsos)),
                                  (2, str(qsos * 2))]:
                    self._cs_table.setItem(r, col, QTableWidgetItem(txt))
            self._cs_summary.setText(
                f"QSOs {cs['total_qsos']}  ×  "
                f"Pts {cs['points']}  ×  "
                f"Mults {cs['mults']} (DXCC)  "
                f"= Score {cs['score']:,}")
        except Exception:
            pass

    def _build_activator_panel(self, root) -> None:
        """SOTA/POTA activator mode — track QSOs toward activation minimum."""
        from PyQt6.QtWidgets import QToolButton as _TB, QComboBox as _CB
        from datetime import datetime, timezone

        toggle = _TB(); toggle.setText("▶ SOTA/POTA Activation")
        toggle.setCheckable(True)
        toggle.setChecked(False)
        toggle.setStyleSheet(
            "QToolButton{background:transparent;border:none;"
            "font-weight:bold;text-align:left;padding:4px 8px;}")
        root.addWidget(toggle)

        self._act_body = QWidget()
        self._act_body.setVisible(False)
        toggle.toggled.connect(self._act_body.setVisible)
        al = QVBoxLayout(self._act_body)
        al.setContentsMargins(8, 2, 8, 4)
        al.setSpacing(4)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Program:"))
        self._act_type = _CB()
        self._act_type.addItems(["SOTA", "POTA"])
        self._act_type.setFixedWidth(70)
        row1.addWidget(self._act_type)
        row1.addWidget(QLabel("Ref:"))
        self._act_ref = QLineEdit()
        self._act_ref.setPlaceholderText("e.g. W7O/NC-001 or K-0001")
        self._act_ref.setMaxLength(20)
        row1.addWidget(self._act_ref, 1)
        al.addLayout(row1)

        row2 = QHBoxLayout()
        self._act_start_btn = QPushButton("Start")
        self._act_start_btn.setFixedHeight(24)
        self._act_start_btn.setFixedWidth(60)
        self._act_start_btn.clicked.connect(self._act_start)
        row2.addWidget(self._act_start_btn)
        self._act_spot_btn = QPushButton("Post Spot")
        self._act_spot_btn.setFixedHeight(24)
        self._act_spot_btn.setEnabled(False)
        self._act_spot_btn.setToolTip(
            "Post self-spot to SOTAwatch/POTA.\n"
            "Uses current rig frequency and mode.")
        self._act_spot_btn.clicked.connect(self._act_post_spot)
        row2.addWidget(self._act_spot_btn)
        self._act_status = QLabel("Not started")
        self._act_status.setStyleSheet("color:#667788;font-size:10px;")
        row2.addWidget(self._act_status, 1)
        al.addLayout(row2)

        self._act_progress = QLabel("")
        self._act_progress.setStyleSheet(
            "color:#3fbe6f;font-family:'Courier New';font-size:12px;font-weight:bold;")
        al.addWidget(self._act_progress)
        root.addWidget(self._act_body)
        self._act_start_time: "str | None" = None

    def _act_start(self) -> None:
        """Begin an activation session — records start time."""
        from datetime import datetime, timezone
        ref = self._act_ref.text().strip().upper()
        if not ref:
            self._act_status.setText("Enter a summit or park reference first")
            return
        self._act_start_time = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        prog_type = self._act_type.currentText()
        minimum   = 4 if prog_type == "SOTA" else 10
        self._act_minimum  = minimum
        self._act_spot_btn.setEnabled(True)
        self._act_start_btn.setText("Reset")
        self._act_status.setText(f"Active: {ref}  (need {minimum} QSOs)")
        self._update_act_progress()

    def _update_act_progress(self) -> None:
        """Count QSOs logged since activation started."""
        if not self._act_start_time or not self.log_db:
            return
        try:
            qsos = [q for q in self._all_qsos
                    if q.datetime_on and q.datetime_on >= self._act_start_time]
            n = len(qsos)
            minimum = getattr(self, "_act_minimum", 10)
            if n >= minimum:
                self._act_progress.setText(
                    f"✓ {n}/{minimum} QSOs — VALID ACTIVATION!")
                self._act_progress.setStyleSheet(
                    "color:#3fbe6f;font-family:'Courier New';font-size:12px;"
                    "font-weight:bold;")
            else:
                self._act_progress.setText(
                    f"{n}/{minimum} QSOs  ({minimum - n} to go)")
                self._act_progress.setStyleSheet(
                    "color:#ffcc00;font-family:'Courier New';font-size:12px;"
                    "font-weight:bold;")
        except Exception:
            pass

    def _act_post_spot(self) -> None:
        """Post self-spot to SOTAwatch or POTA."""
        from network.sota_pota import post_sota_spot, post_pota_spot
        from core.guest_op import operating_callsign
        ref  = self._act_ref.text().strip().upper()
        call = operating_callsign(self.cfg) or "NOCALL"
        # Try to get frequency from rig_tab
        freq_mhz = 14.0
        mode_str  = "SSB"
        try:
            mw  = self.window()
            rig = getattr(mw, "_tab_map", {}).get("rig")
            if rig and hasattr(rig, "freq_display"):
                freq_mhz = rig.freq_display._freq_hz / 1e6
            if rig and hasattr(rig, "rig"):
                mode_str = rig.rig.state.mode or "SSB"
        except Exception:
            pass
        prog_type = self._act_type.currentText()
        if prog_type == "SOTA":
            api_key = self.cfg.get("apis.sotawatch_key", "") if self.cfg else ""
            ok, msg = post_sota_spot(call, ref, freq_mhz, mode_str,
                                     api_key=api_key)
        else:
            ok, msg = post_pota_spot(call, ref, freq_mhz, mode_str)
        self._act_status.setText(msg)
        self._act_status.setStyleSheet(
            f"color:{'#3fbe6f' if ok else '#cc4444'};font-size:10px;")

    def _build_contest_timer_panel(self, root) -> None:
        """Collapsible contest operating timer — elapsed + countdown."""
        from PyQt6.QtWidgets import QToolButton as _TB
        toggle = _TB(); toggle.setText("▶ Contest Timer")
        toggle.setCheckable(True)
        toggle.setChecked(False)
        toggle.setStyleSheet(
            "QToolButton{background:transparent;border:none;"
            "font-weight:bold;text-align:left;padding:4px 8px;}")
        root.addWidget(toggle)

        self._ctimer_body = QWidget()
        self._ctimer_body.setVisible(False)
        toggle.toggled.connect(self._ctimer_body.setVisible)
        cl = QVBoxLayout(self._ctimer_body)
        cl.setContentsMargins(8, 2, 8, 4)
        cl.setSpacing(4)

        # Duration row
        dur_row = QHBoxLayout()
        dur_row.addWidget(QLabel("Duration:"))
        self._ctimer_dur = QSpinBox()
        self._ctimer_dur.setRange(1, 96)
        self._ctimer_dur.setValue(24)
        self._ctimer_dur.setSuffix(" hr")
        self._ctimer_dur.setFixedWidth(80)
        self._ctimer_dur.setToolTip("Contest duration in hours (e.g. 24 for Field Day)")
        dur_row.addWidget(self._ctimer_dur)
        dur_row.addStretch()
        self._ctimer_start_btn = QPushButton("▶ Start")
        self._ctimer_start_btn.setFixedHeight(24)
        self._ctimer_start_btn.setFixedWidth(60)
        self._ctimer_start_btn.clicked.connect(self._ctimer_start)
        dur_row.addWidget(self._ctimer_start_btn)
        self._ctimer_reset_btn = QPushButton("↺")
        self._ctimer_reset_btn.setFixedHeight(24)
        self._ctimer_reset_btn.setFixedWidth(30)
        self._ctimer_reset_btn.setToolTip("Reset timer")
        self._ctimer_reset_btn.clicked.connect(self._ctimer_reset)
        dur_row.addWidget(self._ctimer_reset_btn)
        cl.addLayout(dur_row)

        # Timer display
        self._ctimer_display = QLabel("00:00:00 elapsed  •  — remaining")
        self._ctimer_display.setStyleSheet(
            "color:#3fbe6f;font-family:'Courier New';font-size:13px;"
            "font-weight:bold;")
        cl.addWidget(self._ctimer_display)
        root.addWidget(self._ctimer_body)

        # Internal timer state
        self._ctimer_running  = False
        self._ctimer_start_ts: "float | None" = None
        self._ctimer_qt = QTimer(self)
        self._ctimer_qt.setInterval(1000)
        self._ctimer_qt.timeout.connect(self._ctimer_tick)

    def _ctimer_start(self) -> None:
        import time
        if self._ctimer_running:
            self._ctimer_running = False
            self._ctimer_qt.stop()
            self._ctimer_start_btn.setText("▶ Start")
        else:
            if self._ctimer_start_ts is None:
                self._ctimer_start_ts = time.time()
            self._ctimer_running = True
            self._ctimer_qt.start()
            self._ctimer_start_btn.setText("⏸ Pause")

    def _ctimer_reset(self) -> None:
        self._ctimer_running  = False
        self._ctimer_start_ts = None
        self._ctimer_qt.stop()
        self._ctimer_start_btn.setText("▶ Start")
        self._ctimer_display.setText("00:00:00 elapsed  •  — remaining")

    def _ctimer_tick(self) -> None:
        import time
        if not self._ctimer_start_ts:
            return
        elapsed_s  = int(time.time() - self._ctimer_start_ts)
        dur_s      = self._ctimer_dur.value() * 3600
        remaining_s = max(0, dur_s - elapsed_s)
        def _fmt(s):
            h, rem = divmod(s, 3600)
            m, sec = divmod(rem, 60)
            return f"{h:02d}:{m:02d}:{sec:02d}"
        elapsed_str   = _fmt(elapsed_s)
        remaining_str = _fmt(remaining_s) if remaining_s > 0 else "00:00:00  FINISHED"
        self._ctimer_display.setText(
            f"{elapsed_str} elapsed  •  {remaining_str} remaining")
        if remaining_s == 0:
            self._ctimer_running = False
            self._ctimer_qt.stop()
            self._ctimer_start_btn.setText("▶ Start")
            self._ctimer_display.setStyleSheet(
                "color:#cc4444;font-family:'Courier New';font-size:13px;"
                "font-weight:bold;")

    def _build_session_notes_panel(self, root) -> None:
        """Collapsible scratch pad for session notes, callsigns, exchanges."""
        from PyQt6.QtWidgets import QToolButton as _TB, QTextEdit as _TE
        toggle = _TB(); toggle.setText("▶ Session Notes")
        toggle.setCheckable(True)
        toggle.setChecked(False)
        toggle.setStyleSheet(
            "QToolButton{background:transparent;border:none;"
            "font-weight:bold;text-align:left;padding:4px 8px;}")
        root.addWidget(toggle)

        self._notes_body = QWidget()
        self._notes_body.setVisible(False)
        toggle.toggled.connect(self._notes_body.setVisible)
        nl = QVBoxLayout(self._notes_body)
        nl.setContentsMargins(8, 2, 8, 4)
        nl.setSpacing(2)

        self._session_notes = _TE()
        self._session_notes.setMaximumHeight(120)
        self._session_notes.setPlaceholderText(
            "Quick notes — exchanges, callsigns, contest info, conditions…\n"
            "Saved automatically between sessions.")
        self._session_notes.setStyleSheet(
            "background:#0a0a0a;color:#cccccc;"
            "font-family:'Courier New';font-size:10px;border:none;")
        # Restore saved notes
        if self.cfg:
            saved = self.cfg.get("log.session_notes", "") or ""
            if saved:
                self._session_notes.setPlainText(saved)
        self._session_notes.textChanged.connect(self._save_session_notes)
        nl.addWidget(self._session_notes)
        root.addWidget(self._notes_body)

    def _save_session_notes(self) -> None:
        if self.cfg and hasattr(self, "_session_notes"):
            self.cfg.set("log.session_notes",
                         self._session_notes.toPlainText()[:4000])

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
                if not any(
                    term in (v or "").upper()
                    for v in (q.call, q.name, q.grid,
                              q.dxcc, q.country, q.state, q.comment)
                ):
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

        # "Firsts only" gate — reduce to first-contact / first-band-slot QSOs
        firsts_cb = getattr(self, "_firsts_filter", None)
        if firsts_cb and firsts_cb.isChecked():
            dxcc_keys = first_contact_keys(self._all_qsos)
            band_keys = frozenset(
                (dt, c)
                for dt, c, _b in first_contact_band_keys(self._all_qsos))
            first_keys = dxcc_keys | band_keys
            filtered = [q for q in filtered
                        if (q.datetime_on, q.call) in first_keys]

        self._current_filtered = filtered
        self._populate_table(filtered)

    def _populate_table(self, qsos: list[QSO]):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        _all = getattr(self, "_all_qsos", [])
        new_dxcc = first_contact_keys(_all)
        new_band = first_contact_band_keys(_all)

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
                elif col == C_BAND:
                    if (q.datetime_on, q.call, q.band) in new_band:
                        item.setBackground(QBrush(NEW_BAND_COLOR))
                        item.setToolTip(
                            "New band slot for this DXCC entity")
                elif col == C_DXCC:
                    if (q.datetime_on, q.call) in new_dxcc:
                        item.setBackground(QBrush(NEW_DXCC_COLOR))
                        item.setToolTip("First contact with this DXCC entity")

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
            self._stat_widgets["waz"].setText(
                str(stats["waz_worked"]))
            self._stat_widgets["bands"].setText(
                str(stats["bands_worked"]))
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

            # QSO rate — rolling 60-minute window via LogDB
            self._stat_widgets["rate"].setText(
                str(stats.get("rate_per_hour", 0)))

            # Today's QSO count + optional daily goal
            today_start = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT00:00:00Z")
            today = sum(
                1 for q in self._all_qsos
                if q.datetime_on and q.datetime_on >= today_start)
            goal = self.cfg.get("log.daily_goal", 0) if self.cfg else 0
            w = self._stat_widgets["today"]
            base_ss = ("font-size:14px;font-weight:bold;"
                       "font-family:'Courier New';")
            if goal:
                pct = today / goal
                if pct >= 1.0:
                    color = "#3fbe6f"   # green — goal met
                elif pct >= 0.5:
                    color = "#ffcc00"   # amber — halfway there
                else:
                    color = "#cc4444"   # red — less than halfway
                w.setText(f"{today}/{goal}")
                w.setStyleSheet(base_ss + f"color:{color};")
            else:
                w.setText(str(today))
                w.setStyleSheet(base_ss)

            # Queue counts
            lotw_q = len(self.log_db.lotw_pending())
            qrz_q  = len(self.log_db.qrz_pending())
            self._queue_label.setText(
                f"LoTW queue: {lotw_q}  |  QRZ queue: {qrz_q}")

        except Exception as e:
            log.error(f"Stats update: {e}")
        self._update_contest_score()
        if getattr(self, "_act_start_time", None):
            self._update_act_progress()

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

    # ── Analytics ─────────────────────────────────────────────────────────

    def _show_analytics(self):
        from ui.dialogs.log_stats_dialog import LogStatsDialog
        dlg = LogStatsDialog(self.log_db, self)
        dlg.exec()

    def _show_session_summary(self) -> None:
        from ui.dialogs.session_summary_dialog import show_session_summary
        show_session_summary(self, self.log_db, self._session_start)

    def _log_context_menu(self, pos):
        """Right-click menu on log table rows."""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QGuiApplication, QDesktopServices
        from PyQt6.QtCore import QUrl
        row = self._table.rowAt(pos.y())
        if row < 0:
            return
        qso = self._get_row_qso(row)
        call = qso.call if qso else ""
        menu = QMenu(self)
        edit_act   = menu.addAction("✏️  Edit QSO")
        copy_act   = menu.addAction("📋  Copy callsign")
        qrz_act    = menu.addAction(f"🔗  Open QRZ page")
        filter_act = menu.addAction(
            f"🔍  Show all QSOs with {call}" if call else "🔍  Show all QSOs with…")
        # Tune rig to QSO frequency
        tune_act = None
        if qso and getattr(qso, "freq_hz", 0):
            freq_label = f"{qso.freq_hz/1e6:.4f} MHz  {qso.mode or ''}"
            tune_act = menu.addAction(f"📻  Tune rig → {freq_label}")
        menu.addSeparator()
        del_act    = menu.addAction("🗑  Delete QSO…")
        action = menu.exec(self._table.mapToGlobal(pos))
        if action == edit_act:
            self._edit_qso_row(row)
        elif action == copy_act:
            if qso:
                QGuiApplication.clipboard().setText(qso.call)
        elif action == qrz_act:
            if qso:
                QDesktopServices.openUrl(QUrl(_qrz_url(qso.call)))
        elif action == filter_act:
            if qso:
                self._search.setText(qso.call)
                self._apply_filter()
        elif tune_act and action == tune_act:
            self._tune_rig_to_qso(qso)
        elif action == del_act:
            self._delete_qso_row(row)

    def _tune_rig_to_qso(self, qso) -> None:
        """Retune the rig to the frequency and mode stored in a log QSO."""
        try:
            mw  = self.window()
            rig = getattr(mw, "_tab_map", {}).get("rig")
            if rig and hasattr(rig, "rig") and rig.rig.is_connected:
                hz   = int(getattr(qso, "freq_hz", 0) or 0)
                mode = (getattr(qso, "mode", "") or "").upper().strip()
                if hz > 0:
                    rig.rig.set_freq(hz)
                if mode:
                    rig.rig.set_mode(mode)
                # Also update the VFO display
                if hz > 0 and hasattr(rig, "_set_freq"):
                    rig._set_freq(hz)
        except Exception:
            pass

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

        _fu3 = (self.cfg.get("display.freq_units", "MHz")
                if self.cfg else "MHz")
        hz0 = getattr(qso, "freq_hz", 0) or 0
        if hz0:
            from core.freq_format import format_freq
            freq_val = format_freq(hz0, _fu3).split()[0]  # number only
        else:
            freq_val = ""
        freq = QLineEdit(freq_val)
        freq.setMaxLength(16)
        freq.setPlaceholderText(freq_placeholder(_fu3))
        f.addRow(f"{freq_label(_fu3)}:", freq)

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
            _fu4 = (self.cfg.get("display.freq_units", "MHz")
                    if self.cfg else "MHz")
            qso.freq_hz = parse_freq_input(freq.text(), _fu4)
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

    # ── Public ────────────────────────────────────────────────────────────

    def refresh(self):
        """Called externally when a new QSO is logged."""
        self._load_log()
