from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/tabs/sdr_bottom_bar.py

Bottom-bar group builders for the SDR tab, extracted from sdr_tab.py
(HOUSE-CS complexity split): the IQ Recorder group (transport, status, play
bar, scheduled record, squelch-trigger), the Scanner group, and the Recordings
library group.

`_SDRBottomBarMixin` is mixed into `SDRTab`. Pure widget construction — every
button/timer connects to a handler that stays on the host or an existing mixin
(_SDRRecordingMixin / _SDRScannerMixin), resolved via self:
  * _toggle_record / _toggle_play / _stop_playback / _refresh_recordings /
    _load_recording / _browse_recording        — recording (host/mixin)
  * _arm_scheduled_record / _check_schedule / _check_sqtrig  — recording (host)
  * _start_scan / _stop_scan                    — scanner mixin
The builders create the widgets (self._rec_btn, self._scan_from, self._rec_combo,
…) and initialise the scheduled-record / squelch-trigger runtime state + timers.
"""

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QGridLayout, QGroupBox, QLabel,
    QPushButton, QProgressBar, QSpinBox, QDoubleSpinBox, QCheckBox,
    QComboBox, QLineEdit,
)


class _SDRBottomBarMixin:
    """IQ Recorder / Scanner / Recordings-library group builders."""

    def _build_bottom_bar(self) -> QFrame:
        bar = QFrame()
        # The IQ Recorder group grew to ~6 rows (transport, status, play bar,
        # scheduled record, squelch-trigger); a fixed 90px clipped everything
        # below it.  Let the bar size to its contents with a safe minimum.
        bar.setMinimumHeight(174)
        bar.setStyleSheet(
            "background:#0d0d0d;"
            "border-top:1px solid #1a1a1a;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(12)
        lay.addWidget(self._build_recorder_group())
        lay.addWidget(self._build_scanner_group())
        lay.addWidget(self._build_recordings_group())
        lay.addStretch()
        self._refresh_recordings()
        return bar

    def _build_recorder_group(self) -> QGroupBox:
        rec_grp = QGroupBox(self.tr("IQ Recorder"))
        rl = QVBoxLayout(rec_grp)
        rl.setSpacing(5)
        rec_btn_row = QHBoxLayout()
        self._rec_btn = QPushButton("⏺ Record")
        self._rec_btn.setFixedHeight(26)
        self._rec_btn.setStyleSheet(
            "background:#3a1a1a;color:#cc4444;"
            "border:1px solid #cc4444;border-radius:4px;")
        self._rec_btn.clicked.connect(self._toggle_record)
        self._play_btn = QPushButton("▶ Play")
        self._play_btn.setFixedHeight(26)
        self._play_btn.clicked.connect(self._toggle_play)
        self._stop_btn = QPushButton("■ Stop")
        self._stop_btn.setFixedHeight(26)
        self._stop_btn.clicked.connect(self._stop_playback)
        self._stop_btn.setEnabled(False)
        rec_btn_row.addWidget(self._rec_btn)
        rec_btn_row.addWidget(self._play_btn)
        rec_btn_row.addWidget(self._stop_btn)
        rl.addLayout(rec_btn_row)
        # Transport: reverse toggle + playback speed (fast-forward)
        trans_row = QHBoxLayout()
        self._rev_btn = QPushButton("◀ Rev")
        self._rev_btn.setCheckable(True)
        self._rev_btn.setFixedHeight(24)
        self._rev_btn.setToolTip(self.tr("Play the recording backwards"))
        self._rev_btn.toggled.connect(self._on_playback_reverse)
        self._speed_combo = QComboBox()
        self._speed_combo.addItems(["0.5×", "1×", "2×", "4×", "8×"])
        self._speed_combo.setCurrentText("1×")
        self._speed_combo.setToolTip(self.tr("Playback speed"))
        self._speed_combo.currentTextChanged.connect(self._on_playback_speed)
        trans_row.addWidget(self._rev_btn)
        trans_row.addWidget(QLabel(self.tr("Speed:")))
        trans_row.addWidget(self._speed_combo)
        trans_row.addStretch()
        rl.addLayout(trans_row)
        self._rec_status = QLabel(self.tr("Idle"))
        self._rec_status.setStyleSheet("font-family:'Courier New';")
        rl.addWidget(self._rec_status)
        self._play_bar = QProgressBar()
        self._play_bar.setRange(0, 100)
        self._play_bar.setValue(0)
        self._play_bar.setFixedHeight(6)
        self._play_bar.setTextVisible(False)
        rl.addWidget(self._play_bar)
        # Scheduled recording row
        sched_row = QHBoxLayout()
        from PyQt6.QtWidgets import QTimeEdit
        from PyQt6.QtCore import QTime
        sched_row.addWidget(QLabel("Sched:"))
        self._sched_time = QTimeEdit(QTime(0, 0))
        self._sched_time.setDisplayFormat("HH:mm")
        self._sched_time.setFixedWidth(52)
        self._sched_time.setToolTip("UTC start time for scheduled recording")
        sched_row.addWidget(self._sched_time)
        sched_row.addWidget(QLabel("for"))
        self._sched_dur = QSpinBox()
        self._sched_dur.setRange(1, 1440)
        self._sched_dur.setValue(10)
        self._sched_dur.setSuffix(" min")
        self._sched_dur.setFixedWidth(70)
        sched_row.addWidget(self._sched_dur)
        sched_arm = QPushButton("Arm")
        sched_arm.setFixedWidth(38)
        sched_arm.setFixedHeight(20)
        sched_arm.setToolTip("Arm the scheduled recording")
        sched_arm.clicked.connect(self._arm_scheduled_record)
        sched_row.addWidget(sched_arm)
        rl.addLayout(sched_row)
        self._sched_status = QLabel("")
        self._sched_status.setStyleSheet("font-size:9px;color:#778899;")
        rl.addWidget(self._sched_status)
        # Timer checks schedule every 10 seconds
        self._sched_armed   = False
        self._sched_dur_min = 10
        self._sched_stop_at: "str | None" = None
        self._sched_timer = QTimer(self)
        self._sched_timer.setInterval(10_000)
        self._sched_timer.timeout.connect(self._check_schedule)
        self._sched_timer.start()
        # Squelch-triggered recording row
        sqtrig_row = QHBoxLayout()
        self._sqtrig_cb = QCheckBox(self.tr("Squelch trigger"))
        self._sqtrig_cb.setToolTip(self.tr(
            "Automatically start recording when squelch opens\n"
            "(signal detected) and stop after the tail time when\n"
            "the channel goes quiet. Requires Squelch enabled."))
        sqtrig_row.addWidget(self._sqtrig_cb)
        sqtrig_row.addWidget(QLabel(self.tr("Tail:")))
        self._sqtrig_tail = QSpinBox()
        self._sqtrig_tail.setRange(1, 60)
        self._sqtrig_tail.setValue(5)
        self._sqtrig_tail.setSuffix(self.tr(" s"))
        self._sqtrig_tail.setFixedWidth(58)
        self._sqtrig_tail.setToolTip(
            "Seconds to keep recording after squelch closes.")
        sqtrig_row.addWidget(self._sqtrig_tail)
        sqtrig_row.addStretch()
        rl.addLayout(sqtrig_row)
        # Internal squelch-trigger state
        self._sqtrig_open_ts:  "float | None" = None   # time squelch opened
        self._sqtrig_close_ts: "float | None" = None   # time squelch closed
        self._sqtrig_check_timer = QTimer(self)
        self._sqtrig_check_timer.setInterval(500)
        self._sqtrig_check_timer.timeout.connect(self._check_sqtrig)
        self._sqtrig_check_timer.start()
        return rec_grp

    def _build_scanner_group(self) -> QGroupBox:
        scan_grp = QGroupBox(self.tr("Scanner"))
        scl = QGridLayout(scan_grp)
        scl.setSpacing(3)
        scl.addWidget(QLabel(self.tr("From:")), 0, 0)
        self._scan_from = QLineEdit("100.0")
        self._scan_from.setFixedWidth(70)
        scl.addWidget(self._scan_from, 0, 1)
        scl.addWidget(QLabel("MHz"), 0, 2)
        scl.addWidget(QLabel(self.tr("To:")), 0, 3)
        self._scan_to = QLineEdit("108.0")
        self._scan_to.setFixedWidth(70)
        scl.addWidget(self._scan_to, 0, 4)
        scl.addWidget(QLabel("MHz"), 0, 5)
        scl.addWidget(QLabel(self.tr("Dwell:")), 1, 0)
        self._scan_dwell = QDoubleSpinBox()
        self._scan_dwell.setRange(0.1, 10.0)
        self._scan_dwell.setValue(1.0)
        self._scan_dwell.setSuffix(" s")
        self._scan_dwell.setFixedWidth(70)
        scl.addWidget(self._scan_dwell, 1, 1, 1, 2)
        scan_btns = QHBoxLayout()
        self._scan_start = QPushButton(self.tr("▶ Scan"))
        self._scan_start.setFixedHeight(24)
        self._scan_start.setStyleSheet(
            "background:#1a3a1a;color:#3fbe6f;"
            "border:1px solid #3fbe6f;border-radius:3px;")
        self._scan_start.clicked.connect(self._start_scan)
        self._scan_stop = QPushButton(self.tr("■ Stop"))
        self._scan_stop.setFixedHeight(24)
        self._scan_stop.setEnabled(False)
        self._scan_stop.clicked.connect(self._stop_scan)
        scan_btns.addWidget(self._scan_start)
        scan_btns.addWidget(self._scan_stop)
        scl.addLayout(scan_btns, 1, 3, 1, 3)
        self._scan_squelch_cb = QCheckBox(self.tr("Squelch advance"))
        self._scan_squelch_cb.setToolTip(self.tr(
            "When checked: scanner pauses on channels with active signal\n"
            "(squelch open) and advances when the channel goes quiet.\n"
            "Requires Squelch to be enabled in the Demodulator group."))
        scl.addWidget(self._scan_squelch_cb, 2, 0, 1, 6)
        return scan_grp

    def _build_recordings_group(self) -> QGroupBox:
        """Build the recordings library group (combo + load + browse buttons)."""
        lib_grp = QGroupBox(self.tr("Recordings"))
        ll = QVBoxLayout(lib_grp)
        self._rec_combo = QComboBox()
        self._rec_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._rec_combo.setMinimumWidth(200)
        ll.addWidget(self._rec_combo)
        self._load_rec_btn = QPushButton(self.tr("Load selected"))
        self._load_rec_btn.setFixedHeight(24)
        self._load_rec_btn.setToolTip(
            "Load the selected recording from Squelch's recordings folder")
        self._load_rec_btn.clicked.connect(self._load_recording)
        ll.addWidget(self._load_rec_btn)
        # Browse picks arbitrary .wav/.iq files outside the recordings folder
        self._browse_rec_btn = QPushButton(self.tr("Browse…"))
        self._browse_rec_btn.setFixedHeight(24)
        self._browse_rec_btn.setToolTip(
            "Open a .wav or .iq file from anywhere on disk")
        self._browse_rec_btn.clicked.connect(self._browse_recording)
        ll.addWidget(self._browse_rec_btn)
        return lib_grp
