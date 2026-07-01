from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/tabs/log_panels_mixin.py

Auxiliary collapsible side panels for the Log tab, extracted from log_tab.py
(HOUSE-CS complexity split): live contest score, SOTA/POTA activation tracker,
contest operating timer, and the session-notes scratch pad.

`_LogPanelsMixin` is mixed into `LogTab`. It relies on host-class state:
  * self.cfg        — Config (session-notes persistence, SOTAwatch key)
  * self.log_db     — LogDB (contest_score)
  * self._all_qsos  — full QSO list (activation progress counting)
  * self.window()   — MainWindow (._tab_map → rig freq/mode for self-spot)

The `_build_*_panel` methods are invoked by LogTab._build; the two update
hooks (_update_contest_score / _update_act_progress) are called from LogTab's
refresh path. Both resolve into this mixin via `self`.
"""

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QHeaderView, QTableWidgetItem,
    QAbstractItemView,
)


class _LogPanelsMixin:
    """Contest score / SOTA-POTA activation / contest timer / session notes."""

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
