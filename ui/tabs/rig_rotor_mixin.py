from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/tabs/rig_rotor_mixin.py

Rotor / antenna-rotator control + satellite auto-tracking for the Rig tab,
extracted from rig_tab.py (HOUSE-CS complexity split).

`_RigRotorMixin` is mixed into `RigTab`. It relies on host-class state set in
`RigTab.__init__` / `_build`:
  * self._rig_root  — the rig tab's root QVBoxLayout
  * self._rotor     — RotorController | None (initialised in __init__)
  * self.rig        — RigController (for Doppler correction)

Public API used by main_window's satellite feed:
  * update_from_sat_position(positions)
  * set_sat_track_cb_enabled()
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QCheckBox,
)


class _RigRotorMixin:
    """Rotor control + satellite auto-tracking (collapsible section)."""

    def _build_rotor_section(self, inner):
        """Collapsible rotor/antenna controller panel."""
        from PyQt6.QtWidgets import (QDoubleSpinBox as _DSB, QLineEdit as _LE,
                                      QSpinBox as _SB)
        from ui.widgets.rotor_compass import RotorCompass
        from ui.tabs.rig_tab import _collapse_btn

        self._rotor_toggle = _collapse_btn("Rotor Control")
        self._rotor_toggle.toggled.connect(
            lambda c: self._rotor_body.setVisible(c))
        self._rig_root.addWidget(self._rotor_toggle)

        self._rotor_body = QWidget()
        self._rotor_body.setVisible(False)
        rl = QVBoxLayout(self._rotor_body)
        rl.setContentsMargins(8, 4, 8, 4)
        rl.setSpacing(4)

        # Host:Port + status
        conn_row = QHBoxLayout()
        self._rotor_host = _LE("localhost")
        self._rotor_host.setFixedWidth(110)
        self._rotor_host.setPlaceholderText("host")
        self._rotor_port_spin = _SB()
        self._rotor_port_spin.setRange(1, 65535)
        self._rotor_port_spin.setValue(4533)
        self._rotor_port_spin.setFixedWidth(65)
        self._rotor_conn_btn = QPushButton("Connect")
        self._rotor_conn_btn.setFixedHeight(24)
        self._rotor_conn_btn.setFixedWidth(76)
        self._rotor_conn_btn.clicked.connect(self._rotor_toggle_connect)
        self._rotor_status = QLabel("● Disconnected")
        self._rotor_status.setStyleSheet("color:#777;font-size:10px;")
        conn_row.addWidget(QLabel("Host:"))
        conn_row.addWidget(self._rotor_host)
        conn_row.addWidget(QLabel(":"))
        conn_row.addWidget(self._rotor_port_spin)
        conn_row.addWidget(self._rotor_conn_btn)
        conn_row.addWidget(self._rotor_status, 1)
        rl.addLayout(conn_row)

        # Compass rose + az/el controls side by side
        ctrl_row = QHBoxLayout()
        self._rotor_compass = RotorCompass()
        self._rotor_compass.setFixedSize(140, 140)
        ctrl_row.addWidget(self._rotor_compass)

        az_el_col = QVBoxLayout()
        az_el_col.setSpacing(4)
        az_row = QHBoxLayout()
        az_row.addWidget(QLabel("Az:"))
        self._rotor_az = _DSB()
        self._rotor_az.setRange(0.0, 360.0)
        self._rotor_az.setDecimals(1)
        self._rotor_az.setSuffix("°")
        self._rotor_az.setFixedWidth(80)
        az_row.addWidget(self._rotor_az)
        az_el_col.addLayout(az_row)

        el_row = QHBoxLayout()
        el_row.addWidget(QLabel("El:"))
        self._rotor_el = _DSB()
        self._rotor_el.setRange(0.0, 90.0)
        self._rotor_el.setDecimals(1)
        self._rotor_el.setSuffix("°")
        self._rotor_el.setFixedWidth(80)
        el_row.addWidget(self._rotor_el)
        az_el_col.addLayout(el_row)

        btn_col = QVBoxLayout()
        set_btn  = QPushButton("Set →")
        set_btn.setFixedHeight(26)
        set_btn.setToolTip("Send azimuth/elevation to rotator")
        set_btn.clicked.connect(self._rotor_set_position)
        park_btn = QPushButton("Park")
        park_btn.setFixedHeight(26)
        park_btn.setToolTip("Send the rotator to its park position")
        park_btn.clicked.connect(self._rotor_park)
        for b in (set_btn, park_btn):
            b.setStyleSheet("background:#1a1a1a;border:1px solid #333;"
                            "border-radius:3px;")
        btn_col.addWidget(set_btn)
        btn_col.addWidget(park_btn)

        az_el_col.addLayout(btn_col)
        az_el_col.addStretch()
        ctrl_row.addLayout(az_el_col)
        rl.addLayout(ctrl_row)

        self._build_rotor_tracking(rl)

        self._rig_root.addWidget(self._rotor_body)

    def _build_rotor_tracking(self, rl) -> None:
        """Satellite auto-track, Doppler correction, and next-pass display."""
        # Satellite auto-track row
        sat_row = QHBoxLayout()
        sat_row.addWidget(QLabel("Track:"))
        self._rotor_sat_combo = QComboBox()
        self._rotor_sat_combo.setFixedWidth(130)
        self._rotor_sat_combo.setToolTip(
            "Satellite to track.\n"
            "Enable Auto-track to send position updates to rotctld.")
        for name in ("— off —", "ISS (ZARYA)", "AO-91", "AO-92", "AO-73",
                     "SO-50", "RS-44", "CAS-4A", "CAS-4B"):
            self._rotor_sat_combo.addItem(name)
        sat_row.addWidget(self._rotor_sat_combo)
        self._rotor_auto_btn = QPushButton("Auto-track")
        self._rotor_auto_btn.setCheckable(True)
        self._rotor_auto_btn.setFixedHeight(24)
        self._rotor_auto_btn.setFixedWidth(84)
        self._rotor_auto_btn.setToolTip(
            "When checked, rotor follows the selected satellite\n"
            "using live az/el data from the satellite tracker.\n"
            "Requires rotctld connection and satellite tracking.")
        self._rotor_auto_btn.toggled.connect(self._rotor_auto_toggled)
        sat_row.addWidget(self._rotor_auto_btn)
        self._rotor_sat_status = QLabel("")
        self._rotor_sat_status.setStyleSheet("color:#777;font-size:9px;")
        sat_row.addWidget(self._rotor_sat_status, 1)
        rl.addLayout(sat_row)

        # Doppler correction row
        doppler_row = QHBoxLayout()
        self._doppler_cb = QCheckBox("Doppler correct")
        self._doppler_cb.setToolTip(
            "Auto-apply Doppler shift to the rig's VFO A frequency\n"
            "during satellite tracking. Enter the satellite's nominal\n"
            "downlink frequency. Requires rig connection.")
        doppler_row.addWidget(self._doppler_cb)
        doppler_row.addWidget(QLabel("Nom. freq:"))
        from PyQt6.QtWidgets import QDoubleSpinBox as _DSB2
        self._doppler_nom_freq = _DSB2()
        self._doppler_nom_freq.setRange(0.001, 6000.0)
        self._doppler_nom_freq.setDecimals(4)
        self._doppler_nom_freq.setSuffix(" MHz")
        self._doppler_nom_freq.setValue(145.2000)
        self._doppler_nom_freq.setFixedWidth(100)
        self._doppler_nom_freq.setToolTip(
            "Nominal (unshifted) satellite downlink frequency in MHz.")
        doppler_row.addWidget(self._doppler_nom_freq)
        self._doppler_status = QLabel("")
        self._doppler_status.setStyleSheet("color:#aaa;font-size:9px;")
        doppler_row.addWidget(self._doppler_status, 1)
        rl.addLayout(doppler_row)

        # Next-pass countdown display
        self._pass_lbl = QLabel("Next pass: —")
        self._pass_lbl.setStyleSheet(
            "color:#3fbe6f;font-family:'Courier New';font-size:10px;")
        self._pass_lbl.setWordWrap(True)
        rl.addWidget(self._pass_lbl)
        self._pass_progress = QLabel("")
        self._pass_progress.setStyleSheet(
            "color:#ffcc00;font-family:'Courier New';font-size:11px;"
            "font-weight:bold;")
        rl.addWidget(self._pass_progress)

    # ── Rotor callbacks ───────────────────────────────────────────────────

    def _rotor_toggle_connect(self):
        from core.rotor import RotorController
        from PyQt6.QtCore import QTimer as _QT
        if self._rotor and self._rotor.is_connected:
            self._rotor.disconnect()
            self._rotor = None
            self._rotor_conn_btn.setText("Connect")
            self._rotor_status.setText("● Disconnected")
            self._rotor_status.setStyleSheet("color:#777;font-size:10px;")
            return
        host = self._rotor_host.text().strip() or "localhost"
        port = self._rotor_port_spin.value()
        self._rotor = RotorController(host, port)
        self._rotor.on_position(self._on_rotor_position)
        if self._rotor.connect():
            self._rotor_conn_btn.setText("Disconnect")
            self._rotor_status.setText("● Connected")
            self._rotor_status.setStyleSheet("color:#3fbe6f;font-size:10px;")
        else:
            self._rotor = None
            self._rotor_status.setText("● Connection failed")
            self._rotor_status.setStyleSheet("color:#cc4444;font-size:10px;")

    def _on_rotor_position(self, az: float, el: float):
        """Called from rotor poll thread — marshal to UI thread."""
        from PyQt6.QtCore import QTimer as _QT
        _QT.singleShot(0, lambda: self._apply_rotor_position(az, el))

    def _apply_rotor_position(self, az: float, el: float):
        if hasattr(self, "_rotor_compass"):
            self._rotor_compass.set_current(az, el)
        if hasattr(self, "_rotor_az"):
            self._rotor_az.setValue(az)
        if hasattr(self, "_rotor_el"):
            self._rotor_el.setValue(el)

    def _rotor_set_position(self):
        if self._rotor and self._rotor.is_connected:
            az = self._rotor_az.value()
            el = self._rotor_el.value()
            self._rotor.set_position(az, el)
            self._rotor_compass.set_target(az)

    def _rotor_park(self):
        if self._rotor and self._rotor.is_connected:
            self._rotor.park()

    # ── Satellite auto-tracking ───────────────────────────────────────────

    def _rotor_auto_toggled(self, checked: bool) -> None:
        """Enable/disable satellite auto-tracking via the rotor."""
        if checked:
            sat_name = self._rotor_sat_combo.currentText()
            if sat_name == "— off —":
                self._rotor_auto_btn.setChecked(False)
                return
            self._rotor_auto_btn.setStyleSheet("color:#3fbe6f;")
            self._rotor_sat_status.setText(f"Tracking {sat_name}")
        else:
            self._rotor_auto_btn.setStyleSheet("")
            self._rotor_sat_status.setText("")
            self._rotor_compass.set_target(None)

    def set_sat_track_cb_enabled(self) -> bool:
        """Return True when satellite auto-tracking is active."""
        return (hasattr(self, "_rotor_auto_btn") and
                self._rotor_auto_btn.isChecked())

    def update_from_sat_position(self, positions: list) -> None:
        """Called with SatTracker positions; auto-tracks and shows pass info."""
        target_name = self._rotor_sat_combo.currentText()
        # Update pass countdown for the selected satellite (regardless of tracking state)
        self._update_pass_countdown(positions, target_name)
        if not self.set_sat_track_cb_enabled():
            return
        for pos in positions:
            if not isinstance(pos, dict):
                continue
            if pos.get("name", "").upper() != target_name.upper():
                continue
            az = pos.get("az_deg", pos.get("az", 0.0))
            el = pos.get("el_deg", pos.get("el", 0.0))
            if el < 0:
                self._rotor_sat_status.setText(
                    f"{target_name} below horizon  El {el:.1f}°")
                return
            # Only move rotor when satellite is above horizon
            if self._rotor and self._rotor.is_connected:
                self._rotor.set_position(az, el)
            self._rotor_compass.set_target(az)
            self._rotor_sat_status.setText(
                f"Az {az:.1f}°  El {el:.1f}°")

            # Doppler correction: scale shift from 145 MHz reference
            doppler_ref = pos.get("doppler_hz", 0.0)
            if (doppler_ref and
                    hasattr(self, "_doppler_cb") and
                    self._doppler_cb.isChecked()):
                nom_hz  = self._doppler_nom_freq.value() * 1_000_000
                scaled  = doppler_ref * (nom_hz / 145_000_000)
                corrected_hz = int(nom_hz + scaled)
                if self.rig and self.rig.is_connected:
                    try:
                        self.rig.set_freq(corrected_hz)
                    except Exception:
                        pass
                shift_khz = scaled / 1000
                self._doppler_status.setText(
                    f"Shift {shift_khz:+.2f} kHz → {corrected_hz/1e6:.4f} MHz")
            break

    def _update_pass_countdown(self, positions: list, target_name: str) -> None:
        """Update the next-pass info panel for the selected satellite."""
        if not hasattr(self, "_pass_lbl"):
            return
        if target_name == "— off —":
            self._pass_lbl.setText("Next pass: select a satellite above")
            self._pass_progress.setText("")
            return
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        for pos in positions:
            if not isinstance(pos, dict):
                continue
            if pos.get("name", "").upper() != target_name.upper():
                continue
            np = pos.get("next_pass")
            el = pos.get("el_deg", -99.0)
            if el >= 0:
                # Currently in a pass
                self._pass_progress.setText(
                    f"▲ PASS IN PROGRESS  El {el:.1f}°  "
                    f"Az {pos.get('az_deg', 0.0):.0f}°")
                self._pass_lbl.setText(target_name)
                return
            self._pass_progress.setText("")
            if not np:
                self._pass_lbl.setText(f"{target_name}: no pass predicted in 24h")
                return
            try:
                aos_str = np.get("aos", "?")
                los_str = np.get("los", "?")
                max_el  = np.get("max_el", 0.0)
                aos_az  = np.get("aos_az", 0.0)
                # Compute countdown from AOS string (HH:MM UTC)
                self._pass_lbl.setText(
                    f"{target_name}  AOS {aos_str}  "
                    f"Max El {max_el:.0f}°  Az {aos_az:.0f}°  "
                    f"LOS {los_str}")
            except Exception:
                self._pass_lbl.setText(f"{target_name}: pass data unavailable")
            break
