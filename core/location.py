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
Squelch -- core/location.py
Location from IC-7100 GPS, system GPS, manual grid/ZIP/city/MGRS, or IP.
Fires callbacks when grid changes enough to warrant a RadioReference refresh.
"""

import logging
import threading
import time
import re
import requests
from dataclasses import dataclass
from typing import Optional, Callable
from enum import Enum

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
            threading.Thread(target=self.set_from_ip,
                             daemon=True).start()

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
        try:
            r = requests.get(IP_GEO_URL, timeout=5)
            data = r.json()
            if "loc" in data:
                lat, lon = (float(x) for x in data["loc"].split(","))
                self.set_from_latlon(lat, lon, LocationSource.IP_GEO)
                log.info(f"IP geolocation: {lat:.4f}, {lon:.4f}")
        except Exception as e:
            log.warning(f"IP geolocation failed: {e}")

    # ── Search ────────────────────────────────────────────────────────────

    def search(self, query: str) -> Optional[Location]:
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
        self.location = loc
        self.location.last_updated = time.time()
        self._add_history(loc)
        self.cfg.set("location.lat", loc.lat)
        self.cfg.set("location.lon", loc.lon)
        self.cfg.set("location.grid", loc.grid)
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

    def _nominatim_search(self, query: str) -> Optional[Location]:
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

def _valid_grid(grid: str) -> bool:
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
    return g

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
    g = grid.upper()
    lon = (ord(g[0]) - ord('A')) * 20 - 180
    lat = (ord(g[1]) - ord('A')) * 10 - 90
    if len(g) >= 4:
        lon += int(g[2]) * 2
        lat += int(g[3])
    if len(g) >= 6:
        lon += (ord(g[4]) - ord('A')) * 2 / 24
        lat += (ord(g[5]) - ord('A')) / 24
    return lat + 0.5, lon + 1.0

def _latlon_to_mgrs(lat: float, lon: float) -> str:
    if not _HAS_MGRS:
        return ""
    try:
        m = mgrs_lib.MGRS()
        return m.toMGRS(lat, lon).decode()
    except Exception:
        return ""
