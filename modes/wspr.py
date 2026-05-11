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
Squelch -- modes/wspr.py
WSPR beacon and decode engine.
Controls WSJT-X WSPR mode and uploads spots to WSPRnet.
"""

import logging
import threading
import time
import requests
from dataclasses import dataclass, field
from typing import Optional, Callable

log = logging.getLogger(__name__)

WSPRNET_URL = "http://wsprnet.org/post"
WSPR_BANDS = {
    "160m": 1_836_600,
    "80m":  3_568_600,
    "60m":  5_287_200,
    "40m":  7_038_600,
    "30m":  10_138_700,
    "20m":  14_095_600,
    "17m":  18_104_600,
    "15m":  21_094_600,
    "12m":  24_924_600,
    "10m":  28_124_600,
    "6m":   50_293_000,
    "2m":   144_489_000,
}


@dataclass
class WSPRSpot:
    """A single decoded WSPR spot."""
    timestamp:    float
    callsign:     str
    grid:         str
    power_dbm:    int
    snr:          int
    dt:           float
    freq_hz:      int
    drift:        int
    distance_km:  float = 0.0
    bearing_deg:  float = 0.0
    band:         str   = ""
    uploaded:     bool  = False

    @property
    def display(self) -> str:
        from datetime import datetime, timezone
        t = datetime.fromtimestamp(
            self.timestamp, tz=timezone.utc).strftime("%H:%M")
        return (f"{t}  {self.callsign:<12}  {self.grid:<6}  "
                f"{self.power_dbm:>3}dBm  {self.snr:>+4}dB  "
                f"{self.distance_km:>7,.0f}km")


class WSPREngine:
    """
    WSPR beacon controller.
    Manages TX duty cycle, band rotation, and WSPRnet uploads.
    Runs as a background daemon alongside other modes.
    """

    def __init__(self, config, rig=None, log_db=None):
        self.cfg    = config
        self.rig    = rig
        self.log_db = log_db

        self._bands:        list[str] = []
        self._tx_pct:       int       = 20
        self._power_dbm:    int       = 27
        self._upload:       bool      = True
        self._running:      bool      = False
        self._spots:        list[WSPRSpot] = []
        self._tx_count:     int       = 0
        self._rx_count:     int       = 0
        self._band_idx:     int       = 0
        self._in_tx:        bool      = False

        self._on_spot:   Optional[Callable] = None
        self._on_tx:     Optional[Callable] = None
        self._on_status: Optional[Callable] = None

        self._thread: Optional[threading.Thread] = None

    # ── Public API ────────────────────────────────────────────────────────

    def start(self, bands: list[str], tx_pct: int = 20,
              power_dbm: int = 27):
        self._bands     = bands or ["20m"]
        self._tx_pct    = max(1, min(100, tx_pct))
        self._power_dbm = power_dbm
        self._upload    = self.cfg.get("wspr.upload_to_wsprnet", True)
        self._running   = True
        self._thread    = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="WSPRThread")
        self._thread.start()
        log.info(
            f"WSPR started — bands={bands} "
            f"tx_pct={tx_pct}% power={power_dbm}dBm")

    def stop(self):
        self._running = False
        log.info("WSPR stopped")

    def add_spot(self, spot: WSPRSpot):
        """Called by FT8 engine or WSJT-X UDP when a WSPR decode arrives."""
        self._spots.append(spot)
        self._rx_count += 1
        if self._on_spot:
            self._on_spot(spot)
        if self._upload:
            threading.Thread(
                target=self._upload_spot,
                args=(spot,), daemon=True).start()

    @property
    def spots(self) -> list[WSPRSpot]:
        return list(self._spots)

    @property
    def tx_count(self) -> int:
        return self._tx_count

    @property
    def rx_count(self) -> int:
        return self._rx_count

    @property
    def is_tx(self) -> bool:
        return self._in_tx

    def on_spot(self, cb: Callable):
        self._on_spot = cb

    def on_tx(self, cb: Callable):
        self._on_tx = cb

    def on_status(self, cb: Callable):
        self._on_status = cb

    # ── WSPR cycle loop ───────────────────────────────────────────────────

    def _run_loop(self):
        """
        WSPR runs on 2-minute cycles.
        TX happens at start of even UTC minutes.
        TX/RX ratio controlled by tx_pct setting.
        """
        while self._running:
            now     = time.time()
            # Align to next 2-minute boundary
            cycle_start = (int(now / 120) + 1) * 120
            wait = cycle_start - now
            if wait > 0:
                time.sleep(wait)
            if not self._running:
                break

            cycle_num = int(time.time() / 120)
            should_tx = self._should_tx_this_cycle(cycle_num)

            if should_tx and self._bands:
                band = self._bands[
                    self._band_idx % len(self._bands)]
                self._band_idx += 1
                self._do_tx(band)
            else:
                self._status("Receiving…")
                time.sleep(110)  # RX for most of the cycle

    def _should_tx_this_cycle(self, cycle_num: int) -> bool:
        """Determine TX/RX based on duty cycle percentage."""
        if self._tx_pct <= 0:
            return False
        if self._tx_pct >= 100:
            return True
        period = max(1, int(100 / self._tx_pct))
        return (cycle_num % period) == 0

    def _do_tx(self, band: str):
        freq = WSPR_BANDS.get(band)
        if not freq:
            return

        # Tune rig if available
        if self.rig and self.rig.is_connected:
            self.rig.set_freq(freq)
            self.rig.set_mode("PKTUSB")

        cs   = self.cfg.callsign
        grid = self.cfg.grid[:4] if self.cfg.grid else "AA00"
        msg  = f"{cs} {grid} {self._power_dbm}"

        self._in_tx = True
        self._tx_count += 1
        self._status(f"TX  {band}  {freq/1e6:.4f} MHz  {msg}")
        log.info(f"WSPR TX: {msg} on {band}")

        if self._on_tx:
            self._on_tx(band, freq, msg)

        # WSPR TX lasts ~110 seconds
        time.sleep(110)
        self._in_tx = False
        self._status("TX complete")

    def _status(self, msg: str):
        if self._on_status:
            self._on_status(msg)

    # ── WSPRnet upload ────────────────────────────────────────────────────

    def _upload_spot(self, spot: WSPRSpot):
        """Upload a decoded spot to WSPRnet."""
        try:
            from datetime import datetime, timezone
            dt_str = datetime.fromtimestamp(
                spot.timestamp, tz=timezone.utc
            ).strftime("%Y-%m-%d %H:%M")

            params = {
                "function":   "wspr",
                "rcall":      self.cfg.callsign,
                "rgrid":      self.cfg.grid[:4],
                "rqrg":       f"{spot.freq_hz/1e6:.6f}",
                "date":       dt_str[:10],
                "time":       dt_str[11:],
                "sig":        str(spot.snr),
                "dt":         f"{spot.dt:.1f}",
                "tqrg":       f"{spot.freq_hz/1e6:.6f}",
                "tcall":      spot.callsign,
                "tgrid":      spot.grid,
                "dbm":        str(spot.power_dbm),
                "version":    "Squelch-1.0",
                "mode":       "2",
            }
            resp = requests.get(
                WSPRNET_URL, params=params, timeout=10)
            if resp.status_code == 200:
                spot.uploaded = True
                log.debug(
                    f"WSPRnet upload OK: {spot.callsign}")
            else:
                log.warning(
                    f"WSPRnet upload failed: {resp.status_code}")
        except Exception as e:
            log.warning(f"WSPRnet upload error: {e}")

    # ── Stats ─────────────────────────────────────────────────────────────

    def session_stats(self) -> dict:
        if not self._spots:
            return {"tx": self._tx_count, "rx": 0,
                    "unique": 0, "max_dist_km": 0,
                    "best_snr": 0, "bands": self._bands}
        distances = [s.distance_km for s in self._spots
                     if s.distance_km > 0]
        snrs = [s.snr for s in self._spots]
        return {
            "tx":          self._tx_count,
            "rx":          self._rx_count,
            "unique":      len(set(s.callsign for s in self._spots)),
            "max_dist_km": max(distances) if distances else 0,
            "best_snr":    max(snrs) if snrs else 0,
            "bands":       self._bands,
        }
