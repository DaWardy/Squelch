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
"""Squelch -- core/safety.py
Safety systems: app state machine, PTT watchdog,
TX timeout, exception handler, hardware protection alerts.
"""

import sys
import time
import logging
import threading
import atexit
from enum import Enum
from typing import Optional, Callable

log = logging.getLogger(__name__)


class AppState(Enum):
    IDLE        = "Idle"
    RX          = "Receiving"
    TX_MANUAL   = "TX (manual PTT)"
    TX_AUTO_SEQ = "TX (auto-sequence)"
    TX_VARA     = "TX (VARA)"
    TX_WSPR     = "TX (WSPR)"
    TX_CW       = "TX (CW)"
    CONNECTING  = "Connecting"
    SCANNING    = "Scanning"
    TUNING      = "Tuning ATU"
    ERROR       = "Error"


# Controls locked per state
STATE_LOCKS: dict[AppState, set] = {
    AppState.TX_MANUAL:   {"freq","mode","band","connect","scan_start","tune","cq"},
    AppState.TX_AUTO_SEQ: {"freq","mode","band","connect","scan_start","tune","cq","ptt"},
    AppState.TX_VARA:     {"freq","mode","band","connect","scan_start","tune","cq","ptt"},
    AppState.TX_WSPR:     {"freq","mode","band","connect","scan_start","tune"},
    AppState.CONNECTING:  {"connect","freq","mode","ptt"},
    AppState.TUNING:      {"freq","mode","band","ptt","cq","scan_start","tune"},
    AppState.SCANNING:    {"scan_start"},
}

TX_TIMEOUT: dict[str, float] = {
    "FT8": 15.5, "FT4": 8.0, "WSPR": 115.0, "JS8": 30.0,
    "PSK31": 180.0, "RTTY": 180.0, "CW": 300.0,
    "SSB": 180.0, "FM": 180.0, "AM": 180.0,
    "VARA": 600.0, "DEFAULT": 180.0,
}

DUTY_CYCLE: dict[str, float] = {
    "FT8": 1.00, "FT4": 1.00, "WSPR": 1.00,
    "RTTY": 1.00, "PSK31": 1.00, "CW": 0.50,
    "SSB": 0.30, "FM": 1.00, "AM": 1.00, "JS8": 0.50,
}


class SafetyManager:
    def __init__(self):
        self._state        = AppState.IDLE
        self._rig          = None
        self._tx_start:    float | None = None
        self._tx_mode:     str = "SSB"
        self._ptt_active:  bool = False
        self._running:     bool = False
        self._lock         = threading.Lock()
        self._state_cbs:   list[Callable] = []
        self._alert_cbs:   list[Callable] = []
        self._watchdog_th: threading.Thread | None = None

        atexit.register(self._emergency_ptt_release)
        sys.excepthook = self._exception_hook

    def set_rig(self, rig):
        self._rig = rig

    # ── State ─────────────────────────────────────────────────────────────

    @property
    def state(self) -> AppState:
        return self._state

    def set_state(self, new_state: AppState):
        with self._lock:
            self._state = new_state

        tx_states = {AppState.TX_MANUAL, AppState.TX_AUTO_SEQ,
                     AppState.TX_VARA, AppState.TX_WSPR, AppState.TX_CW}
        if new_state in tx_states:
            self._tx_start   = time.time()
            self._ptt_active = True
        elif new_state in (AppState.IDLE, AppState.RX):
            self._tx_start   = None
            self._ptt_active = False

        for cb in self._state_cbs:
            try: cb(new_state)
            except Exception as e: log.debug(f"State cb: {e}")

    def is_locked(self, control: str) -> bool:
        return control in STATE_LOCKS.get(self._state, set())

    def can_transmit(self) -> bool:
        return self._state in (AppState.IDLE, AppState.RX)

    def is_transmitting(self) -> bool:
        return self._state in (
            AppState.TX_MANUAL, AppState.TX_AUTO_SEQ,
            AppState.TX_VARA, AppState.TX_WSPR, AppState.TX_CW)

    def set_tx_mode(self, mode: str):
        self._tx_mode = mode

    def tx_elapsed(self) -> float:
        return time.time() - self._tx_start if self._tx_start else 0.0

    # ── Duty cycle ────────────────────────────────────────────────────────

    def safe_power_watts(self, mode: str, rated_w: float) -> float:
        duty   = DUTY_CYCLE.get(mode, 0.50)
        factor = {1.00: 0.50, 0.50: 0.85, 0.30: 1.00}.get(duty, 1.0)
        return round(rated_w * factor / 5) * 5

    def duty_cycle_warning(self, mode: str,
                            power_w: float,
                            rated_w: float) -> str | None:
        safe = self.safe_power_watts(mode, rated_w)
        if power_w > safe:
            pct = int(DUTY_CYCLE.get(mode, 0.5) * 100)
            return (f"{mode} is {pct}% duty cycle.\n"
                    f"Max safe power: {safe:.0f}W\n"
                    f"Current: {power_w:.0f}W — risk of overheating finals.")
        return None

    # ── Watchdog ──────────────────────────────────────────────────────────

    def start_watchdog(self):
        self._running = True
        self._watchdog_th = threading.Thread(
            target=self._watchdog_loop, daemon=True, name="PTTWatchdog")
        self._watchdog_th.start()
        log.info("PTT watchdog started")

    def stop_watchdog(self):
        self._running = False

    def _watchdog_loop(self):
        while self._running:
            try:
                if self._ptt_active and self._tx_start:
                    elapsed = time.time() - self._tx_start
                    timeout = TX_TIMEOUT.get(
                        self._tx_mode, TX_TIMEOUT["DEFAULT"])
                    if elapsed > timeout:
                        log.warning(f"TX timeout on {self._tx_mode}")
                        self._emergency_ptt_release()
                        self._alert("TX Timeout",
                            f"{self._tx_mode} transmission exceeded "
                            f"{timeout:.0f}s limit.\n"
                            "PTT released automatically.", "warning")

                if (self._rig and self._rig.is_connected
                        and self._ptt_active):
                    try:
                        self._rig.get_freq()
                    except Exception:
                        log.error("Rig lost during TX — releasing PTT")
                        self._emergency_ptt_release()
                        self._alert("Rig Connection Lost",
                            "Rig disconnected during transmission.\n"
                            "PTT released. Check USB cable.", "error")
            except Exception as e:
                log.debug(f"Watchdog: {e}")
            time.sleep(2.0)

    def _emergency_ptt_release(self):
        if not self._ptt_active:
            return
        log.warning("Emergency PTT release")
        self._ptt_active = False
        if self._rig:
            try:
                self._rig.set_ptt(False)
                log.info("PTT released via CAT")
                return
            except Exception as e:
                log.error(f"CAT PTT release failed: {e}")
        # Direct socket fallback
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect(("127.0.0.1", 4532))
            s.sendall(b"T 0\n")
            s.close()
            log.info("PTT released via direct socket")
        except Exception as e2:
            log.critical(
                f"ALL PTT RELEASE METHODS FAILED: {e2}\n"
                "MANUALLY UNKEY THE RADIO IMMEDIATELY")
        self.set_state(AppState.IDLE)

    # ── Hardware alerts ───────────────────────────────────────────────────

    def check_alc(self, alc: float) -> str | None:
        if alc > 0.6:
            return ("ALC active — overdriving detected.\n"
                    "Reduce TX audio level or power.\n"
                    "ALC must be minimal for clean digital modes.")
        if alc > 0.3:
            return "ALC detected — consider reducing audio level."
        return None

    def check_swr(self, swr: float) -> str | None:
        if swr >= 3.0:
            return (f"HIGH SWR {swr:.1f}:1 — finals at risk!\n"
                    "Check antenna. Reduce power or run ATU.")
        if swr >= 2.0:
            return f"Elevated SWR {swr:.1f}:1 — consider running ATU."
        return None

    def check_clipping(self, clip_pct: float) -> str | None:
        if clip_pct > 0.05:
            return (f"Audio clipping {clip_pct*100:.0f}%.\n"
                    "Reduce audio level. Clipping causes splatter.")
        return None

    # ── Exception handler ─────────────────────────────────────────────────

    def _exception_hook(self, exc_type, exc_value, exc_tb):
        self._emergency_ptt_release()
        log.critical("Unhandled exception",
                     exc_info=(exc_type, exc_value, exc_tb))
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance():
                msg = QMessageBox()
                msg.setWindowTitle("Squelch — Unexpected Error")
                msg.setIcon(QMessageBox.Icon.Critical)
                msg.setText(
                    f"Unexpected error: {exc_type.__name__}: {exc_value}\n\n"
                    "PTT has been released.\n"
                    "See logs/squelch.log for details.\n\n"
                    "Report at: github.com/dawardy/squelch/issues")
                msg.exec()
        except Exception:
            print(f"\nFATAL: {exc_type.__name__}: {exc_value}",  # intentional: stderr before logger
                  file=sys.stderr)
        sys.exit(1)

    # ── Callbacks ─────────────────────────────────────────────────────────

    def on_state_change(self, cb: Callable):
        self._state_cbs.append(cb)

    def on_alert(self, cb: Callable):
        self._alert_cbs.append(cb)

    def _alert(self, title: str, msg: str, severity: str = "warning"):
        for cb in self._alert_cbs:
            try: cb(title, msg, severity)
            except Exception as e: log.debug(f"Alert cb: {e}")


_safety: SafetyManager | None = None

def get_safety() -> SafetyManager:
    global _safety
    if _safety is None:
        _safety = SafetyManager()
    return _safety
