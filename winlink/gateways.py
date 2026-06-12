from __future__ import annotations
"""Winlink RMS gateway lookup via Winlink CMS public API.

No authentication required for gateway status queries.
"""
import logging
import math
from dataclasses import dataclass, field
from typing import Callable

log = logging.getLogger(__name__)

# Public Winlink CMS endpoint — no auth required
_CMS_URL   = "https://cms.winlink.org/json/reply/GatewayStatusSearch"
_TIMEOUT   = 10
_MAX_GW    = 50

# Mode bitmask → human-readable label
_MODE_BITS: list[tuple[int, str]] = [
    (256, "VARA FM"),
    (128, "VARA HF"),
    (64,  "ARDOP"),
    (8,   "Robust Pkt"),
    (4,   "WINMOR"),
    (2,   "Pactor"),
    (1,   "Packet"),
]


@dataclass
class GatewayEntry:
    callsign:    str
    grid:        str   = ""
    lat:         float = 0.0
    lon:         float = 0.0
    freq_hz:     int   = 0
    mode_mask:   int   = 0
    last_heard:  str   = ""
    comments:    str   = ""
    distance_km: float = 0.0

    @property
    def frequency(self) -> str:
        if self.freq_hz <= 0:
            return "—"
        return f"{self.freq_hz / 1_000_000:.3f} MHz"

    @property
    def mode(self) -> str:
        labels = [lbl for bit, lbl in _MODE_BITS if self.mode_mask & bit]
        return "/".join(labels) if labels else f"Mode {self.mode_mask}"


def _latlon_from_grid(grid: str) -> tuple[float, float]:
    try:
        from core.location import _grid_to_latlon
        return _grid_to_latlon(grid)
    except Exception:
        return 0.0, 0.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _latlon_to_grid4(lat: float, lon: float) -> str:
    """Approximate 4-character Maidenhead from lat/lon."""
    lon += 180
    lat += 90
    field_lon = int(lon / 20)
    field_lat = int(lat / 10)
    sq_lon = int((lon % 20) / 2)
    sq_lat = int(lat % 10)
    return (chr(ord('A') + field_lon) + chr(ord('A') + field_lat)
            + str(sq_lon) + str(sq_lat))


def _parse_gw(raw: dict, my_lat: float, my_lon: float) -> GatewayEntry | None:
    callsign = (raw.get("Callsign") or "").strip().upper()
    if not callsign:
        return None
    grid = (raw.get("GridSquare") or "").strip().upper()
    lat, lon = _latlon_from_grid(grid) if grid else (0.0, 0.0)
    dist = (_haversine_km(my_lat, my_lon, lat, lon)
            if (my_lat or my_lon) and (lat or lon) else 0.0)
    ts = raw.get("Timestamp") or ""
    if ts and "T" in ts:
        ts = ts[:16].replace("T", " ")
    return GatewayEntry(
        callsign    = callsign,
        grid        = grid,
        lat         = lat,
        lon         = lon,
        freq_hz     = int(raw.get("BaseFrequency") or 0),
        mode_mask   = int(raw.get("Mode") or 0),
        last_heard  = ts,
        comments    = (raw.get("Comments") or "")[:80],
        distance_km = dist,
    )


def fetch_rms_gateways(lat: float, lon: float,
                        radius_km: float = 150.0) -> list[dict]:
    """Fetch nearby RMS gateways from Winlink CMS.

    Returns list of dicts compatible with WinlinkTab._populate_gateways.
    Each dict also contains 'lat', 'lon', 'grid' for map rendering.
    """
    try:
        import requests
    except ImportError:
        log.warning("requests not installed — cannot fetch gateways")
        return []

    grid4 = _latlon_to_grid4(lat, lon) if (lat or lon) else ""
    try:
        resp = requests.get(_CMS_URL, timeout=_TIMEOUT, params={
            "GridSquare": grid4,
            "DistanceKm": int(radius_km),
            "Mode":       0,
            "Accessible": "true",
            "MaxResults": _MAX_GW,
        })
        try:
            from core.netlog import record_connection
            record_connection("cms.winlink.org",
                              purpose="RMS gateway list",
                              user_initiated=True)
        except Exception:
            pass
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning(f"Gateway fetch: {e}")
        return []

    entries = []
    for raw in data.get("GatewayList") or []:
        gw = _parse_gw(raw, lat, lon)
        if gw is None:
            continue
        entries.append({
            "callsign":   gw.callsign,
            "frequency":  gw.frequency,
            "mode":       gw.mode,
            "distance":   f"{gw.distance_km:.0f} km" if gw.distance_km else "—",
            "last_heard": gw.last_heard,
            "lat":        gw.lat,
            "lon":        gw.lon,
            "grid":       gw.grid,
            "freq_hz":    gw.freq_hz,
            "mode_mask":  gw.mode_mask,
        })
    entries.sort(key=lambda g: float(g["distance"].replace(" km", "") or 9999))
    return entries


def fetch_rms_gateways_async(lat: float, lon: float,
                              callback: Callable,
                              radius_km: float = 150.0) -> None:
    """Non-blocking gateway fetch; calls callback(list) on completion."""
    import threading
    def _run():
        result = fetch_rms_gateways(lat, lon, radius_km)
        callback(result)
    threading.Thread(target=_run, daemon=True, name="GWFetch").start()
