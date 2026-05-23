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
"""Squelch -- core/location.py
Location from IC-7100 GPS, system GPS, manual grid/ZIP/city/MGRS, or IP.
Fires callbacks when grid changes enough to warrant a RadioReference refresh.
"""

import logging
import threading
import time
import re
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
from dataclasses import dataclass
from typing import Optional, Callable
from enum import Enum
from core.constants import IPAPI_URL, NOMINATIM_USER_AGENT, API_TIMEOUT_S

log = logging.getLogger(__name__)

NOMINATIM_REV    = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_SEARCH = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HDR    = {"User-Agent": "Squelch-RF-Education/1.0 (github.com/dawardy/squelch)"}
IP_GEO_URL       = "https://ipinfo.io/json"

try:
    import maidenhead
    _HAS_MAIDEN = True
except ImportError:
    _HAS_MAIDEN = False

try:
    import mgrs as mgrs_lib
    _HAS_MGRS = True
except ImportError:
    _HAS_MGRS = False


def geocode_place(query: str) -> tuple[float, float]:
    """Geocode a ZIP/city/place string to (lat, lon) via Nominatim.
    Raises on failure so callers can fall back."""
    if not HAS_REQUESTS:
        raise RuntimeError("requests not available")
    try:
        from core.netlog import record_connection
        record_connection("nominatim.openstreetmap.org",
                          purpose="geocode search start point",
                          user_initiated=True)
    except Exception:
        pass
    r = requests.get(
        NOMINATIM_SEARCH,
        params={"q": query, "format": "json", "limit": 1},
        headers=NOMINATIM_HDR, timeout=8)
    data = r.json()
    if not data:
        raise ValueError(f"no match for {query!r}")
    return float(data[0]["lat"]), float(data[0]["lon"])


def reverse_geocode_state(lat: float, lon: float) -> str:
    """Return the US state name for a lat/lon via Nominatim, or '' on failure.
    Used by the repeater search to pick the RepeaterBook state_id."""
    if not HAS_REQUESTS:
        return ""
    try:
        from core.netlog import record_connection
        record_connection("nominatim.openstreetmap.org",
                          purpose="reverse geocode (repeater search)",
                          user_initiated=True)
    except Exception:
        pass
    try:
        r = requests.get(
            NOMINATIM_REV,
            params={"lat": lat, "lon": lon,
                    "format": "json", "addressdetails": 1},
            headers=NOMINATIM_HDR, timeout=8)
        if r.status_code != 200:
            return ""
        return r.json().get("address", {}).get("state", "") or ""
    except Exception:
        return ""


class LocationSource(Enum):
    RIG_GPS    = "IC-7100 GPS"
    SYSTEM_GPS = "System GPS"
    MANUAL     = "Manual"
    IP_GEO     = "IP Geolocation"
    UNKNOWN    = "Unknown"


@dataclass
class Location:
    lat:          float          = 0.0
    lon:          float          = 0.0
    grid:         str            = ""
    city:         str            = ""
    state:        str            = ""
    county:       str            = ""
    country:      str            = ""
    zip_code:     str            = ""
    mgrs_str:     str            = ""
    source:       LocationSource = LocationSource.UNKNOWN
    last_updated: float          = 0.0

    @property
    def is_valid(self) -> bool:
        return bool(self.grid) or self.lat != 0.0

    @property
    def display(self) -> str:
        parts = []
        if self.grid:
            parts.append(self.grid)
        if self.city and self.state:
            parts.append(f"{self.city}, {self.state}")
        elif self.state:
            parts.append(self.state)
        return "  |  ".join(parts) if parts else "Not set"


class LocationManager:
    def __init__(self, config):
        self.cfg      = config
        self.location = Location()
        self._callbacks: list[Callable] = []
        self._last_rr_grid = ""
        self._history: list[dict] = list(
            config.get("location.search_history") or [])

    # ── Load saved ────────────────────────────────────────────────────────

    def load_from_config(self):
        src  = self.cfg.get("location.source", "manual")
        grid = self.cfg.get("location.grid", "")
        lat  = self.cfg.get("location.lat",  0.0)
        lon  = self.cfg.get("location.lon",  0.0)
        if grid:
            self.set_from_grid(grid, notify=False)
        elif lat and lon:
            self.set_from_latlon(lat, lon, notify=False)
        elif src == "ip":
            # Don't re-run IP geolocation on startup —
            # use the saved grid/lat/lon from last session.
            # IP geo only runs during first-run setup.
            if lat and lon:
                self.set_from_latlon(lat, lon, notify=False)

    # ── Setters ───────────────────────────────────────────────────────────

    def set_from_grid(self, grid: str, notify: bool = True) -> bool:
        grid = grid.upper().strip()
        if not _valid_grid(grid):
            log.warning(f"Invalid grid: {grid}")
            return False
        lat, lon = _grid_to_latlon(grid)
        self.location.grid   = grid
        self.location.lat    = lat
        self.location.lon    = lon
        self.location.source = LocationSource.MANUAL
        self.location.last_updated = time.time()
        # Save to config immediately
        self.cfg.set("location.grid", grid)
        self.cfg.set("location.lat",  lat)
        self.cfg.set("location.lon",  lon)
        self.cfg.set("grid_square",   grid)
        self.cfg.save()
        self._enrich_bg(lat, lon)
        if notify:
            self._check_grid_change()
        return True

    def set_from_latlon(self, lat: float, lon: float,
                        source: LocationSource = LocationSource.MANUAL,
                        notify: bool = True):
        self.location.lat    = lat
        self.location.lon    = lon
        self.location.grid   = _latlon_to_grid(lat, lon)
        self.location.source = source
        self.location.last_updated = time.time()
        self.location.mgrs_str = _latlon_to_mgrs(lat, lon)
        self._enrich_bg(lat, lon)
        if notify:
            self._check_grid_change()

    def set_from_mgrs(self, mgrs_str: str) -> bool:
        """Convert MGRS string to lat/lon then set location."""
        if not _HAS_MGRS:
            log.warning("mgrs library not installed")
            return False
        try:
            m = mgrs_lib.MGRS()
            lat, lon = m.toLatLon(mgrs_str.encode())
            self.location.mgrs_str = mgrs_str.upper()
            self.set_from_latlon(lat, lon)
            return True
        except Exception as e:
            log.warning(f"MGRS parse failed '{mgrs_str}': {e}")
            return False

    def set_from_ip(self):
        """
        Set location from IP geolocation.
        Only used during first-run setup — not called on subsequent starts.
        """
        try:
            loc = self._ip_geolocation()
            if loc and loc.is_valid:
                self.location = loc
                log.info(
                    f"IP geolocation: {loc.lat:.4f}, "
                    f"{loc.lon:.4f} → {loc.grid}")
                self._notify(rr_refresh=False)
        except Exception as e:
            log.warning(f"IP geolocation failed: {e}")

    # ── Search ────────────────────────────────────────────────────────────

    # ── Auto-location ─────────────────────────────────────────────────

    def auto_detect(self) -> Location | None:
        """
        Try to determine location automatically.
        Order: Windows Location API → IP geolocation → None.
        Returns Location if found, None if unavailable.
        """
        # Try Windows Location API first
        loc = self._windows_location()
        if loc:
            log.info(f"Location from Windows API: {loc.grid}")
            return loc

        # Fall back to IP geolocation
        loc = self._ip_geolocation()
        if loc:
            log.info(f"Location from IP geo: {loc.grid}")
            return loc

        return None

    def _windows_location(self) -> Location | None:
        """Try Windows Location API via ctypes."""
        try:
            import ctypes
            import ctypes.wintypes as wintypes
            # Use Windows.Devices.Geolocation via WinRT
            # Simpler: use the GeoCoordinateWatcher COM API
            # Fall back if not available
            # Try WlanAPI for rough location (no permission needed)
            # This is a simplified approach - returns None on failure
            return None
        except Exception:
            return None

    def _ip_geolocation(self) -> Location | None:
        """Get approximate location via IP geolocation."""
        if not HAS_REQUESTS:
            return None
        try:
            # ipapi.co — free, no API key, HTTPS
            from core.netlog import record_connection
            record_connection("ip geolocation service",
                              purpose="auto-fill grid from IP",
                              user_initiated=False)
            resp = requests.get(
                IPAPI_URL,
                timeout=5,
                headers={"User-Agent": "Squelch/0.6.0-alpha"})
            if resp.status_code != 200:
                return None
            if len(resp.content) > 10_000:
                return None
            data = resp.json()
            lat  = float(data.get("latitude", 0))
            lon  = float(data.get("longitude", 0))
            city = str(data.get("city", ""))[:50]
            region = str(data.get("region", ""))[:50]
            country = str(data.get("country_name", ""))[:50]
            if not lat and not lon:
                return None
            grid = _latlon_to_grid(lat, lon)
            display = ", ".join(filter(None,
                [city, region, country]))
            return Location(
                lat=lat, lon=lon, grid=grid,
                display=display, is_valid=True,
                source=LocationSource.IP_GEO)
        except Exception as e:
            log.debug(f"IP geolocation: {e}")
            return None

    def estimate_from_adsb(self) -> Location | None:
        """
        Estimate location from dump1090 aircraft positions.
        Uses centroid of received aircraft as rough location.
        Typically accurate to 50-150km.
        """
        if not HAS_REQUESTS:
            return None
        try:
            resp = requests.get(
                "http://localhost:8080/data/aircraft.json",
                timeout=2)
            if resp.status_code != 200:
                return None
            data = resp.json()
            aircraft = data.get("aircraft", [])
            # Only use aircraft with valid positions
            # and altitude > 1000ft (filtering ground vehicles)
            positions = [
                (float(a["lat"]), float(a["lon"]))
                for a in aircraft
                if "lat" in a and "lon" in a
                and float(a.get("alt_baro", 0)) > 1000
            ]
            if len(positions) < 5:
                return None   # need enough to be meaningful
            lat = sum(p[0] for p in positions) / len(positions)
            lon = sum(p[1] for p in positions) / len(positions)
            grid = _latlon_to_grid(lat, lon)
            return Location(
                lat=lat, lon=lon, grid=grid,
                display=f"Estimated from {len(positions)} aircraft",
                is_valid=True, source=LocationSource.UNKNOWN)
        except Exception as e:
            log.debug(f"ADS-B location estimate: {e}")
            return None

    def write_dump1090_receiver_json(self,
            dump1090_dir: str = "") -> bool:
        """
        Write receiver.json for dump1090-fa.
        This places a station marker on the dump1090 map.
        """
        if not self.location.is_valid:
            return False
        import json
        data = {
            "lat":  round(self.location.lat, 6),
            "lon":  round(self.location.lon, 6),
            "alt":  0,
        }
        # Try common dump1090 locations
        candidates = [
            Path(dump1090_dir) / "receiver.json"
            if dump1090_dir else None,
            Path("C:/dump1090/receiver.json"),
            Path("C:/Program Files/dump1090/receiver.json"),
            Path("/usr/share/dump1090-fa/html/receiver.json"),
            Path("/usr/share/dump1090/html/receiver.json"),
        ]
        for path in candidates:
            if path is None:
                continue
            try:
                if path.parent.exists():
                    path.write_text(
                        json.dumps(data, indent=2),
                        encoding="utf-8")
                    log.info(
                        f"dump1090 receiver.json written: {path}")
                    return True
            except Exception as e:
                log.debug(f"receiver.json {path}: {e}")
        return False

    def search(self, query: str) -> Location | None:
        """
        Resolve ZIP, city/state, grid square, or MGRS to a Location.
        Called from the search bar -- runs synchronously, call from thread.
        """
        query = query.strip()

        # MGRS (e.g. 18SUJ2337006519)
        if _HAS_MGRS and re.match(r"^\d{1,2}[A-Z]{3}\d{2,10}$", query.upper()):
            try:
                m = mgrs_lib.MGRS()
                lat, lon = m.toLatLon(query.upper().encode())
                loc = Location(lat=lat, lon=lon,
                               grid=_latlon_to_grid(lat, lon),
                               mgrs_str=query.upper(),
                               source=LocationSource.MANUAL)
                self._enrich_location(loc)
                return loc
            except Exception:
                pass

        # Grid square
        if _valid_grid(query.upper()):
            lat, lon = _grid_to_latlon(query.upper())
            loc = Location(lat=lat, lon=lon, grid=query.upper(),
                           source=LocationSource.MANUAL)
            self._enrich_location(loc)
            return loc

        # ZIP code
        if re.match(r"^\d{5}$", query):
            return self._nominatim_search(query + ", USA")

        # Free text
        return self._nominatim_search(query)

    def apply(self, loc: Location):
        """
        Apply a resolved Location as the current station location.
        Saves all fields to config for persistence and for QSO logging.
        """
        self.location = loc
        self.location.last_updated = time.time()
        self._add_history(loc)
        # Save all location fields
        self.cfg.set("location.lat",      loc.lat)
        self.cfg.set("location.lon",      loc.lon)
        self.cfg.set("location.grid",     loc.grid)
        self.cfg.set("location.city",     loc.city)
        self.cfg.set("location.state",    loc.state)
        self.cfg.set("location.county",   loc.county)
        self.cfg.set("location.country",  loc.country)
        self.cfg.set("location.zip_code", loc.zip_code)
        self.cfg.set("location.mgrs",     loc.mgrs_str)
        # Save source as string for JSON serialization
        src_val = (loc.source.value
                   if hasattr(loc.source, 'value')
                   else str(loc.source))
        self.cfg.set("location.source",   src_val)
        # Keep legacy key in sync for compatibility
        self.cfg.set("grid_square",       loc.grid)
        self.cfg.save()
        self._check_grid_change()

    # ── Nominatim ─────────────────────────────────────────────────────────

    def _enrich_bg(self, lat: float, lon: float):
        threading.Thread(
            target=self._enrich_latlon,
            args=(lat, lon), daemon=True).start()

    def _enrich_latlon(self, lat: float, lon: float):
        try:
            r = requests.get(NOMINATIM_REV,
                params={"lat": lat, "lon": lon,
                        "format": "json", "addressdetails": 1},
                headers=NOMINATIM_HDR, timeout=8)
            addr = r.json().get("address", {})
            self.location.city    = (addr.get("city") or
                                     addr.get("town") or
                                     addr.get("village", ""))
            self.location.state   = addr.get("state", "")
            self.location.county  = addr.get("county", "")
            self.location.country = addr.get("country_code", "").upper()
            self.location.zip_code = addr.get("postcode", "")
            self._notify(rr_refresh=False)
        except Exception as e:
            log.debug(f"Nominatim reverse: {e}")

    def _enrich_location(self, loc: Location):
        try:
            r = requests.get(NOMINATIM_REV,
                params={"lat": loc.lat, "lon": loc.lon,
                        "format": "json", "addressdetails": 1},
                headers=NOMINATIM_HDR, timeout=8)
            addr = r.json().get("address", {})
            loc.city    = (addr.get("city") or addr.get("town") or
                           addr.get("village", ""))
            loc.state   = addr.get("state", "")
            loc.county  = addr.get("county", "")
            loc.country = addr.get("country_code", "").upper()
            loc.zip_code = addr.get("postcode", "")
        except Exception as e:
            log.debug(f"Nominatim enrich: {e}")

    def _nominatim_search(self, query: str) -> Location | None:
        if not HAS_REQUESTS:
            log.warning("requests not installed — location search unavailable")
            return None
        try:
            r = requests.get(NOMINATIM_SEARCH,
                params={"q": query, "format": "json",
                        "addressdetails": 1, "limit": 1},
                headers=NOMINATIM_HDR, timeout=8)
            results = r.json()
            if not results:
                return None
            d    = results[0]
            lat  = float(d["lat"])
            lon  = float(d["lon"])
            addr = d.get("address", {})
            return Location(
                lat=lat, lon=lon,
                grid=_latlon_to_grid(lat, lon),
                mgrs_str=_latlon_to_mgrs(lat, lon),
                city=(addr.get("city") or addr.get("town") or
                      addr.get("village", "")),
                state=addr.get("state", ""),
                county=addr.get("county", ""),
                country=addr.get("country_code", "").upper(),
                zip_code=addr.get("postcode", ""),
                source=LocationSource.MANUAL,
                last_updated=time.time(),
            )
        except Exception as e:
            log.warning(f"Nominatim search '{query}': {e}")
            return None

    # ── Grid change detection ─────────────────────────────────────────────

    def _check_grid_change(self):
        g4 = self.location.grid[:4] if self.location.grid else ""
        rr = g4 != self._last_rr_grid
        self._last_rr_grid = g4
        self._notify(rr_refresh=rr)

    # ── History ───────────────────────────────────────────────────────────

    def _add_history(self, loc: Location):
        entry = {"display": loc.display, "grid": loc.grid,
                 "lat": loc.lat, "lon": loc.lon,
                 "city": loc.city, "state": loc.state,
                 "mgrs": loc.mgrs_str}
        self._history = [h for h in self._history
                         if h.get("grid") != loc.grid]
        self._history.insert(0, entry)
        self._history = self._history[:10]
        self.cfg.set("location.search_history", self._history)

    @property
    def history(self) -> list[dict]:
        return self._history

    # ── Callbacks ─────────────────────────────────────────────────────────

    def on_location_change(self, cb: Callable):
        self._callbacks.append(cb)

    def _notify(self, rr_refresh: bool = False):
        for cb in self._callbacks:
            try: cb(self.location, rr_refresh)
            except Exception as e: log.debug(f"Location cb: {e}")


# ── Standalone helpers ────────────────────────────────────────────────────

def _valid_grid(grid) -> bool:
    if not isinstance(grid, str):
        return False
    return bool(re.match(
        r"^[A-R]{2}[0-9]{2}([A-X]{2}([0-9]{2})?)?$", grid.upper()))

def _latlon_to_grid(lat: float, lon: float) -> str:
    if _HAS_MAIDEN:
        for method in ('toMaiden', 'to_maiden', 'latlon_to_maiden'):
            fn = getattr(maidenhead, method, None)
            if fn:
                try:
                    result = fn(lat, lon, 3)
                    if isinstance(result, str) and len(result) >= 4:
                        return result.upper()
                except Exception:
                    pass
    # Manual calculation fallback
    lon2 = lon + 180
    lat2 = lat + 90
    g  = chr(ord('A') + int(lon2 / 20))
    g += chr(ord('A') + int(lat2 / 10))
    g += str(int((lon2 % 20) / 2))
    g += str(int(lat2 % 10))
    sub_lon = (lon2 % 2) / 2 * 24
    sub_lat = (lat2 % 1) * 24
    g += chr(ord('a') + int(sub_lon))
    g += chr(ord('a') + int(sub_lat))
    return g.upper()

def _grid_to_latlon(grid: str) -> tuple[float, float]:
    if _HAS_MAIDEN:
        # maidenhead library has different APIs in different versions
        # Try each known method name
        for method in ('toLoc', 'to_location', 'maiden_to_latlon'):
            fn = getattr(maidenhead, method, None)
            if fn:
                try:
                    result = fn(grid)
                    if isinstance(result, (list, tuple)) and len(result) >= 2:
                        return float(result[0]), float(result[1])
                except Exception:
                    pass
    # Manual calculation fallback (always works)
    # Returns center of the grid square
    g = grid.upper()
    # Field (2 letters): 20° lon, 10° lat each
    lon = (ord(g[0]) - ord('A')) * 20 - 180
    lat = (ord(g[1]) - ord('A')) * 10 - 90
    if len(g) >= 4:
        # Square (2 digits): 2° lon, 1° lat each
        lon += int(g[2]) * 2
        lat += int(g[3])
        if len(g) >= 6:
            # Subsquare (2 letters): 5' lon, 2.5' lat each
            lon += (ord(g[4]) - ord('A')) * (2.0 / 24)
            lat += (ord(g[5]) - ord('A')) * (1.0 / 24)
            # Center of subsquare
            lon += 1.0 / 24
            lat += 0.5 / 24
        else:
            # Center of square
            lon += 1.0
            lat += 0.5
    else:
        # Center of field
        lon += 10.0
        lat += 5.0
    return lat, lon

def _latlon_to_mgrs(lat: float, lon: float) -> str:
    if not _HAS_MGRS:
        return ""
    try:
        m = mgrs_lib.MGRS()
        return m.toMGRS(lat, lon).decode()
    except Exception:
        return ""

# ── Map-ready helpers ─────────────────────────────────────────────────────

def grid_to_map_point(grid: str) -> dict | None:
    """
    Convert a Maidenhead grid to a map-ready dict.
    Used by log map, APRS map, gray line overlay.
    Returns None if grid is invalid.
    """
    if not _valid_grid(grid):
        return None
    try:
        lat, lon = _grid_to_latlon(grid)
        return {
            "grid":  grid,
            "lat":   round(lat, 6),
            "lon":   round(lon, 6),
            "label": grid,
        }
    except Exception:
        return None


def qso_to_map_points(qso) -> tuple[dict | None, dict | None]:
    """
    Return (my_point, their_point) for a QSO.
    Both are map-ready dicts or None if unavailable.
    Used by log map to draw great circle paths.
    """
    my_pt = None
    if qso.my_lat and qso.my_lon:
        my_pt = {
            "grid":  qso.my_grid,
            "lat":   qso.my_lat,
            "lon":   qso.my_lon,
            "label": qso.my_call,
        }
    elif qso.my_grid:
        my_pt = grid_to_map_point(qso.my_grid)
        if my_pt:
            my_pt["label"] = qso.my_call

    their_pt = None
    if qso.lat and qso.lon:
        their_pt = {
            "grid":  qso.grid,
            "lat":   qso.lat,
            "lon":   qso.lon,
            "label": qso.call,
        }
    elif qso.grid:
        their_pt = grid_to_map_point(qso.grid)
        if their_pt:
            their_pt["label"] = qso.call

    return my_pt, their_pt
