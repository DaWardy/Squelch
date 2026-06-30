from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/tabs/rig_scanner_mixin.py

Frequency scanner (sweep / band / channel-list / memory scan with dwell +
squelch advance) for the Rig tab, extracted from rig_tab.py (HOUSE-CS
complexity split).

`_RigScannerMixin` is mixed into `RigTab`. It relies on host-class state set up
by RigTab.__init__ / build:
  * self.rig           — RigController
  * self.cfg           — Config (theme accent for the status colour)
  * self._rig_root     — the rig tab's root QVBoxLayout
  * self._memories     — {slot: (hz, mode, label)} (Memory-scan source)
  * self._set_freq     — host method to tune the displayed/connected frequency
  * self._step_hz      — default step fallback
  * self._scan_running — bool flag (init False in RigTab.__init__)
  * self._scan_timer   — QTimer whose timeout connects to self._scan_step

Note: the step-size widget is `self._scan_step_combo` so it does not shadow the
`self._scan_step` scan-advance method that the timer fires.
"""

from PyQt6.QtWidgets import (
    QWidget, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit, QMessageBox,
)


class _RigScannerMixin:
    """Scanner collapsible section + sweep/band/channel-list/memory scan loop."""

    def _build_scanner_section(self, inner):
        from ui.tabs.rig_tab import _collapse_btn
        self._scan_toggle = _collapse_btn("Scanner")
        self._scan_toggle.toggled.connect(
            lambda c: self._scan_body.setVisible(c))
        self._rig_root.addWidget(self._scan_toggle)
        self._scan_body = self._build_scanner_body()
        self._rig_root.addWidget(self._scan_body)

    def _build_scanner_body(self) -> QWidget:
        body = QWidget()
        body.setVisible(False)
        scan_layout = QGridLayout(body)
        scan_layout.setContentsMargins(8, 4, 8, 4)
        scan_layout.setSpacing(6)
        self._build_scan_params_grid(scan_layout)
        self._build_scan_btn_row(scan_layout)
        return body

    def _build_scan_params_grid(self, scan_layout) -> None:
        scan_layout.addWidget(QLabel("Mode:"), 0, 0)
        self._scan_mode = QComboBox()
        self._scan_mode.addItems(["Sweep", "Band", "Channel list", "Memory"])
        self._scan_mode.setFixedWidth(120)
        scan_layout.addWidget(self._scan_mode, 0, 1)
        scan_layout.addWidget(QLabel("Dwell (s):"), 0, 2)
        self._scan_dwell = QDoubleSpinBox()
        self._scan_dwell.setRange(0.1, 60.0)
        self._scan_dwell.setValue(2.0)
        self._scan_dwell.setSingleStep(0.5)
        self._scan_dwell.setFixedWidth(70)
        scan_layout.addWidget(self._scan_dwell, 0, 3)
        scan_layout.addWidget(QLabel("Squelch:"), 0, 4)
        self._scan_sql = QSpinBox()
        self._scan_sql.setRange(-120, 0)
        self._scan_sql.setValue(-80)
        self._scan_sql.setSuffix(" dBm")
        self._scan_sql.setFixedWidth(80)
        scan_layout.addWidget(self._scan_sql, 0, 5)
        scan_layout.addWidget(QLabel("From:"), 1, 0)
        self._scan_from = QLineEdit("14.000")
        self._scan_from.setFixedWidth(90)
        scan_layout.addWidget(self._scan_from, 1, 1)
        scan_layout.addWidget(QLabel("To:"), 1, 2)
        self._scan_to = QLineEdit("14.350")
        self._scan_to.setFixedWidth(90)
        scan_layout.addWidget(self._scan_to, 1, 3)
        scan_layout.addWidget(QLabel("Step:"), 1, 4)
        self._scan_step_combo = QComboBox()
        self._scan_step_combo.addItems([
            "100 Hz", "500 Hz", "1 kHz", "2.5 kHz",
            "5 kHz", "6.25 kHz", "10 kHz", "12.5 kHz",
            "25 kHz", "50 kHz", "100 kHz"])
        self._scan_step_combo.setCurrentText("5 kHz")
        self._scan_step_combo.setToolTip(
            "Frequency step between scan stops.\n"
            "Match to channel spacing:\n"
            "  FM voice: 12.5 or 25 kHz\n"
            "  HF: 1-5 kHz\n"
            "  AM broadcast: 10 kHz")
        self._scan_step_combo.setFixedWidth(90)
        scan_layout.addWidget(self._scan_step_combo, 1, 5)

    def _build_scan_btn_row(self, scan_layout) -> None:
        scan_btn_row = QHBoxLayout()
        self._scan_start = QPushButton("▶  Start Scan")
        self._scan_start.setFixedHeight(28)
        self._scan_start.setStyleSheet(
            "background:#1a3a1a;color:#3fbe6f;border:1px solid #3fbe6f;"
            "border-radius:4px;")
        self._scan_start.clicked.connect(self._start_scan)
        self._scan_stop = QPushButton("■  Stop")
        self._scan_stop.setFixedHeight(28)
        self._scan_stop.setEnabled(False)
        self._scan_stop.clicked.connect(self._stop_scan)
        self._scan_lock = QPushButton("⊘  Lock current")
        self._scan_lock.setFixedHeight(28)
        self._scan_lock.setToolTip("Add current frequency to lockout list")
        self._scan_status = QLabel("Idle")
        self._scan_status.setStyleSheet(" ")
        scan_btn_row.addWidget(self._scan_start)
        scan_btn_row.addWidget(self._scan_stop)
        scan_btn_row.addWidget(self._scan_lock)
        scan_btn_row.addWidget(self._scan_status)
        scan_btn_row.addStretch()
        scan_layout.addLayout(scan_btn_row, 2, 0, 1, 6)

    def _start_scan(self):
        if not self.rig.is_connected:
            QMessageBox.warning(self, "Scanner",
                                "Connect the rig before scanning.")
            return
        mode = self._scan_mode.currentText()

        if mode == "Memory":
            channels = sorted(self._memories.items())   # [(slot, (hz,mode,label))]
            if not channels:
                QMessageBox.warning(self, "Scanner",
                                    "No memory channels stored.\n"
                                    "Use the Memory Channels section to add some.")
                return
            self._scan_channel_list = [(hz, m, lbl)
                                       for _, (hz, m, lbl) in channels]
            self._scan_channel_idx  = 0
            self._scan_list_mode    = True

        elif mode == "Channel list":
            raw = self._scan_from.text().strip()
            freqs = []
            for tok in raw.replace(";", ",").split(","):
                tok = tok.strip()
                if not tok:
                    continue
                try:
                    freqs.append((int(float(tok) * 1_000_000), "", tok))
                except ValueError:
                    pass
            if not freqs:
                QMessageBox.warning(self, "Scanner",
                                    "Enter comma-separated frequencies in MHz in the 'From' field.")
                return
            self._scan_channel_list = freqs
            self._scan_channel_idx  = 0
            self._scan_list_mode    = True

        else:  # Sweep / Band
            try:
                lo = int(float(self._scan_from.text()) * 1_000_000)
                hi = int(float(self._scan_to.text()) * 1_000_000)
            except ValueError:
                QMessageBox.warning(self, "Scanner", "Invalid frequency range.")
                return
            self._scan_lo  = lo
            self._scan_hi  = hi
            self._scan_cur = lo
            self._scan_list_mode = False
            try:
                step_txt = self._scan_step_combo.currentText()
                if "kHz" in step_txt:
                    step_hz = int(float(step_txt.replace(" kHz", "")) * 1_000)
                elif "Hz" in step_txt:
                    step_hz = int(step_txt.replace(" Hz", ""))
                else:
                    step_hz = 5_000
            except Exception:
                step_hz = 5_000
            self._scan_step_hz = step_hz

        self._scan_running = True
        interval = int(self._scan_dwell.value() * 1000)
        self._scan_timer.setInterval(interval)
        self._scan_timer.start()
        self._scan_start.setEnabled(False)
        self._scan_stop.setEnabled(True)
        self._scan_status.setText("Scanning…")
        from ui.tabs.rig_tab import _get_rig_theme
        self._scan_status.setStyleSheet(
            f"color:{_get_rig_theme(self.cfg.get('ui.theme', 'Dark')).accent}; ")

    def _stop_scan(self):
        self._scan_running = False
        self._scan_timer.stop()
        self._scan_start.setEnabled(True)
        self._scan_stop.setEnabled(False)
        self._scan_status.setText("Idle")
        self._scan_status.setStyleSheet(" ")

    def _scan_squelch_open(self) -> bool:
        """Return True when the rig signal exceeds the scan SQL threshold."""
        try:
            sql_dbm = self._scan_sql.value()       # dBm threshold (e.g. -80)
            s_level = self.rig.state.s_meter       # 0-13
            # Convert S-level to approximate dBm using the standard scale
            from ui.widgets.smeter import _DBM
            level_dbm = _DBM[max(0, min(13, s_level))]
            return level_dbm >= sql_dbm
        except Exception:
            return False   # can't read → don't block scanning

    def _scan_step(self):
        if not self._scan_running:
            return
        # Squelch gate: if signal is above threshold, hold on this channel
        if self.rig.is_connected and self._scan_squelch_open():
            self._scan_status.setText(
                self._scan_status.text() + "  🔴 SIGNAL")
            return  # stay on current frequency

        if getattr(self, "_scan_list_mode", False):
            # Memory / Channel-list mode: advance through channel list
            channels = self._scan_channel_list
            if not channels:
                self._stop_scan()
                return
            idx = getattr(self, "_scan_channel_idx", 0) % len(channels)
            self._scan_channel_idx = (idx + 1) % len(channels)
            hz, mode_str, label = channels[idx]
            self._set_freq(hz)
            if mode_str and self.rig.is_connected:
                from core.spot_tune import infer_rig_mode
                try:
                    self.rig.set_mode(infer_rig_mode(mode_str, hz))
                except Exception:
                    pass
            self._scan_status.setText(
                f"Ch {idx+1}/{len(channels)}  {hz/1e6:.4f} MHz"
                + (f"  {label}" if label and label != str(hz/1e6) else ""))
        else:
            step = getattr(self, "_scan_step_hz", self._step_hz)
            self._scan_cur += step
            if self._scan_cur > self._scan_hi:
                self._scan_cur = self._scan_lo
            self._set_freq(self._scan_cur)
            self._scan_status.setText(
                f"Scanning  {self._scan_cur/1e6:.4f} MHz")
