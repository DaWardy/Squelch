"""
Squelch -- network/aprs_anomaly.py
APRS anomaly detector for C-19 RF Security Analyst persona.

Watches the real-time APRS packet stream and flags:

  A1  Rapid beaconing — same callsign sending > N packets in a short window
      (possible tracker runaway, deliberate flooding)

  A2  Impossible speed — position delta implies ground speed > 900 km/h
      (possible replay attack or spoofed position)

  A3  Path abuse — packets routed via WIDE7-7 or similar extreme paths
      (floods the network; sometimes used for coverage mapping attacks)

  A4  Symbol mismatch — callsign registered as one type but transmitting
      a different symbol type than previously observed
      (could indicate SSID hijack or spoofed position)

  A5  Duplicate sequence — identical raw packet seen from same call within
      60 s (relay duplicate is normal; exact-same content suggests replay)

Usage:
    detector = APRSAnomalyDetector()
    for packet in stream:
        alerts = detector.feed(packet)
        for alert in alerts:
            print(alert)           # alert is an APRSAlert namedtuple
"""
from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any


# -------------------------------------------------------------------------
# Public types
# -------------------------------------------------------------------------

@dataclass
class APRSAlert:
    rule: str        # e.g. "A1", "A2"
    callsign: str
    description: str
    packet: Any      # original packet dict for caller to inspect
    timestamp: float = field(default_factory=time.monotonic)

    def __str__(self) -> str:
        return f"[{self.rule}] {self.callsign}: {self.description}"


# -------------------------------------------------------------------------
# Tunable constants
# -------------------------------------------------------------------------

_RAPID_BEACON_WINDOW_S   = 60     # look-back window for rate check
_RAPID_BEACON_THRESHOLD  = 8      # packets per window before flagging
_MAX_SPEED_KMH           = 900    # flag if implied speed > this
_MIN_SPEED_CHECK_S       = 10     # ignore position pairs < 10s apart (avoids
                                  # false positives from rapid network ingest
                                  # or digipeater echoes arriving in burst)
_DUPLICATE_WINDOW_S      = 60     # window for exact-duplicate check
_EXTREME_PATHS           = {"WIDE7", "WIDE6"}  # path fragments to flag


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


# -------------------------------------------------------------------------
# Detector
# -------------------------------------------------------------------------

class APRSAnomalyDetector:
    """Stateful APRS anomaly detector. Not thread-safe — call from one thread."""

    def __init__(self):
        # callsign → deque of monotonic timestamps (for rate check)
        self._timestamps: defaultdict[str, deque] = defaultdict(
            lambda: deque(maxlen=_RAPID_BEACON_THRESHOLD + 5))

        # callsign → (lat, lon, monotonic_time) of last position
        self._last_pos: dict[str, tuple[float, float, float]] = {}

        # callsign → first-seen symbol
        self._symbols: dict[str, str] = {}

        # callsign → deque of raw-content hashes (for duplicate check)
        self._raw_hashes: defaultdict[str, deque] = defaultdict(
            lambda: deque(maxlen=20))

        # callsign → deque of (hash, time) for duplicate expiry
        self._hash_times: defaultdict[str, deque] = defaultdict(
            lambda: deque(maxlen=20))

    def feed(self, packet: dict) -> list[APRSAlert]:
        """Process one packet dict. Returns list of alerts (may be empty)."""
        alerts: list[APRSAlert] = []
        call = (packet.get("from") or packet.get("callsign") or "").upper()
        if not call:
            return alerts

        now = time.monotonic()

        alerts += self._check_rapid_beacon(call, now, packet)
        alerts += self._check_speed(call, packet, now)
        alerts += self._check_path_abuse(call, packet)
        alerts += self._check_symbol_mismatch(call, packet)
        alerts += self._check_duplicate(call, packet, now)

        # Update state
        self._timestamps[call].append(now)
        lat = packet.get("latitude")
        lon = packet.get("longitude")
        if lat is not None and lon is not None:
            try:
                self._last_pos[call] = (float(lat), float(lon), now)
            except (TypeError, ValueError):
                pass

        return alerts

    def recent_alerts_summary(self, window_s: float = 300) -> list[str]:
        """Not stateful — callers should collect alerts from feed() themselves."""
        return []

    # ------------------------------------------------------------------
    # Per-rule checks
    # ------------------------------------------------------------------

    def _check_rapid_beacon(self, call: str, now: float, packet: dict) -> list[APRSAlert]:
        ts = self._timestamps[call]
        cutoff = now - _RAPID_BEACON_WINDOW_S
        recent = sum(1 for t in ts if t >= cutoff)
        if recent >= _RAPID_BEACON_THRESHOLD:
            return [APRSAlert(
                "A1", call,
                f"{recent} packets in {_RAPID_BEACON_WINDOW_S}s "
                f"(threshold {_RAPID_BEACON_THRESHOLD}) — possible beacon flood",
                packet,
            )]
        return []

    def _check_speed(self, call: str, packet: dict, now: float) -> list[APRSAlert]:
        lat = packet.get("latitude")
        lon = packet.get("longitude")
        if lat is None or lon is None:
            return []
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            return []
        prev = self._last_pos.get(call)
        if prev is None:
            return []
        prev_lat, prev_lon, prev_time = prev
        dt_s = now - prev_time
        # Skip pairs too close in time — burst ingest / digipeater echoes
        if dt_s < _MIN_SPEED_CHECK_S:
            return []
        dt_h = dt_s / 3600.0
        dist_km = _haversine_km(prev_lat, prev_lon, lat, lon)
        speed = dist_km / dt_h
        if speed > _MAX_SPEED_KMH:
            return [APRSAlert(
                "A2", call,
                f"Implied speed {speed:.0f} km/h exceeds {_MAX_SPEED_KMH} km/h "
                f"— possible position replay or spoof",
                packet,
            )]
        return []

    def _check_path_abuse(self, call: str, packet: dict) -> list[APRSAlert]:
        path = str(packet.get("path") or "").upper()
        for extreme in _EXTREME_PATHS:
            if extreme in path:
                return [APRSAlert(
                    "A3", call,
                    f"Extreme APRS path '{path}' — network flood risk",
                    packet,
                )]
        return []

    def _check_symbol_mismatch(self, call: str, packet: dict) -> list[APRSAlert]:
        sym = packet.get("symbol") or packet.get("symbol_table", "")
        if not sym:
            return []
        sym = str(sym)
        prev = self._symbols.get(call)
        if prev is None:
            self._symbols[call] = sym
            return []
        if sym != prev:
            return [APRSAlert(
                "A4", call,
                f"Symbol changed from '{prev}' to '{sym}' — possible SSID hijack",
                packet,
            )]
        return []

    def _check_duplicate(self, call: str, packet: dict, now: float) -> list[APRSAlert]:
        raw = packet.get("raw") or str(packet)
        h = hash(raw)
        times = self._hash_times[call]
        # expire old entries
        while times and (now - times[0][1]) > _DUPLICATE_WINDOW_S:
            times.popleft()
        seen_hashes = {entry[0] for entry in times}
        if h in seen_hashes:
            return [APRSAlert(
                "A5", call,
                f"Exact duplicate packet within {_DUPLICATE_WINDOW_S}s "
                f"— possible replay",
                packet,
            )]
        times.append((h, now))
        return []
