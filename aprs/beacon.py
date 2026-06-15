from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- aprs/beacon.py
APRS position beacon via APRS-IS and optionally RF.
"""

import threading
import logging
import time
from typing import Callable

log = logging.getLogger(__name__)

BEACON_INTERVAL_S = 600  # 10 minutes
MIN_INTERVAL_S    = 120  # 2 minutes minimum

SYMBOLS = {
    "house":     ("/", "&"),
    "car":       ("/", ">"),
    "portable":  ("/", "-"),
    "walker":    ("/", "["),
    "bicycle":   ("/", "b"),
    "emergency": ("/", "E"),
}


def _latlon_to_aprs(lat: float, lon: float) -> tuple[str, str]:
    lat_abs = abs(lat)
    lat_deg = int(lat_abs)
    lat_min = (lat_abs - lat_deg) * 60
    lat_str = f"{lat_deg:02d}{lat_min:05.2f}"
    lat_hem = "N" if lat >= 0 else "S"
    lon_abs = abs(lon)
    lon_deg = int(lon_abs)
    lon_min = (lon_abs - lon_deg) * 60
    lon_str = f"{lon_deg:03d}{lon_min:05.2f}"
    lon_hem = "E" if lon >= 0 else "W"
    return f"{lat_str}{lat_hem}", f"{lon_str}{lon_hem}"


def build_position_packet(callsign: str, lat: float, lon: float,
                           comment: str = "", symbol: str = "house",
                           altitude_m: float = 0.0) -> str:
    lat_str, lon_str = _latlon_to_aprs(lat, lon)
    sym_table, sym_code = SYMBOLS.get(symbol, SYMBOLS["house"])
    packet = f"!{lat_str}{sym_table}{lon_str}{sym_code}"
    if altitude_m > 0:
        packet += f"/A={int(altitude_m * 3.28084):06d}"
    if comment:
        packet += f" {comment[:43]}"
    return packet


class APRSBeacon:
    def __init__(self, config, aprs_client=None):
        self.cfg         = config
        self._client     = aprs_client
        self._running    = False
        self._thread     = None
        self._interval   = BEACON_INTERVAL_S
        self._last_tx    = 0.0
        self._on_beacon: Callable = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def seconds_until_next(self) -> int:
        return max(0, int(self._interval - (time.time() - self._last_tx)))

    def start(self, interval_s: int = BEACON_INTERVAL_S):
        """Begin periodic beaconing on configured interval."""
        if self._running:
            return
        self._interval = max(MIN_INTERVAL_S, interval_s)
        self._running  = True
        self._thread   = threading.Thread(
            target=self._loop, daemon=True, name="APRSBeacon")
        self._thread.start()
        log.info(f"APRS beacon started (interval={self._interval}s)")

    def stop(self):
        """Stop beaconing — current TX completes first."""
        self._running = False

    def send_now(self) -> bool:
        return self._send()

    def _loop(self):
        time.sleep(5)
        while self._running:
            self._send()
            elapsed = 0
            while self._running and elapsed < self._interval:
                time.sleep(10)
                elapsed += 10

    def _send(self) -> bool:
        from core.guest_op import operating_callsign
        cs  = operating_callsign(self.cfg)
        lat = self.cfg.get("location.lat", 0.0) or 0.0
        lon = self.cfg.get("location.lon", 0.0) or 0.0
        if not cs or not (lat or lon):
            return False
        comment = self.cfg.get("aprs.beacon_comment",
                               f"Squelch {self.cfg.grid or ''}").strip()
        symbol  = self.cfg.get("aprs.symbol", "house")
        packet  = build_position_packet(cs, lat, lon, comment, symbol)
        path    = self.cfg.get("aprs.path", "WIDE1-1,WIDE2-1")
        full    = f"{cs}>APZS09,{path}:{packet}"
        success = False
        if self._client and self._client.is_connected:
            try:
                sock = self._client._sock
                if sock:
                    sock.sendall((full + "\r\n").encode())
                    success = True
                    log.info(f"APRS beacon: {full}")
            except Exception as e:
                log.warning(f"APRS beacon send: {e}")
        self._last_tx = time.time()
        if self._on_beacon:
            try:
                self._on_beacon(full, success)
            except Exception:
                pass
        return success

    def on_beacon(self, cb: Callable):
        self._on_beacon = cb
