from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- network/satellites.py
Satellite position tracking via sgp4 + Celestrak TLE data.
Fetches current TLEs from Celestrak and computes lat/lon for
ham radio satellites (AO-7, AO-91, AO-92, ISS, etc.).
"""

import logging
import math
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger(__name__)

try:
    from sgp4.api import Satrec, jday
    HAS_SGP4 = True
except ImportError:
    HAS_SGP4 = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# Celestrak URLs for amateur radio satellite TLEs
CELESTRAK_URLS = {
    "amateur":  "https://celestrak.org/SOCRATES/query.php?CATNR=25544&TYPE=SAT&LIMIT=1",
    "amsaturl":  "https://celestrak.org/SOCRATES/query.php?CATNR=25544&TYPE=SAT",
    # Use the direct group file
    "amateur_group": "https://celestrak.org/SOCRATES/query.php",
    # Working Celestrak endpoints
    "amsat":    "https://celestrak.org/pub/TLE/catalog.tle",
    "iss":      "https://celestrak.org/SOCRATES/query.php?CATNR=25544",
    # Best working endpoint for ham sats
    "ham_sats": "https://celestrak.org/pub/TLE/Amateur.tle",
}

# Popular ham radio satellites to track by default
DEFAULT_SATS = {
    "ISS (ZARYA)":   "ISS",
    "AO-07":         "AO-7",
    "AO-91":         "AO-91",
    "AO-92":         "AO-92",
    "AO-73":         "AO-73",
    "SO-50":         "SO-50",
    "RS-44":         "RS-44",
    "CAS-4A":        "CAS-4A",
    "CAS-4B":        "CAS-4B",
    "TEVEL-1":       "TEVEL-1",
    "FUNCUBE-1":     "AO-73",
    "NOAA 15":       "NOAA 15",
    "NOAA 18":       "NOAA 18",
    "NOAA 19":       "NOAA 19",
}

# Local TLE cache
_TLE_CACHE_PATH = (Path.home() / "AppData" / "Roaming" /
                   "Squelch" / "tle_cache.tle")


@dataclass
class SatPass:
    """A satellite pass over a ground location."""
    sat_name:    str
    aos_utc:     datetime      # acquisition of signal
    los_utc:     datetime      # loss of signal
    max_el_deg:  float         # maximum elevation
    max_el_utc:  datetime      # time of maximum elevation
    aos_az_deg:  float         # azimuth at AOS
    los_az_deg:  float         # azimuth at LOS

    @property
    def duration_min(self) -> float:
        return (self.los_utc - self.aos_utc
                ).total_seconds() / 60


@dataclass
class SatPosition:
    """Current position of a satellite."""
    name:        str
    lat:         float
    lon:         float
    alt_km:      float
    vel_kms:     float   = 0.0
    el_deg:      float   = 0.0   # elevation from observer
    az_deg:      float   = 0.0   # azimuth from observer
    range_km:    float   = 0.0   # slant range
    doppler_hz:  float   = 0.0   # Doppler shift at 145 MHz
    is_sunlit:   bool    = False
    next_pass:   Optional[SatPass] = None
    timestamp:   float   = 0.0

    @property
    def is_visible(self) -> bool:
        return self.el_deg > 0


class SatTracker:
    """
    Tracks ham radio satellites in real time.
    Uses sgp4 for orbital mechanics, Celestrak for TLEs.
    """

    def __init__(self, config=None):
        self.cfg        = config
        self._sats:     dict[str, Satrec] = {}
        self._positions: dict[str, SatPosition] = {}
        self._running   = False
        self._thread    = None
        self._lock      = threading.Lock()
        self._on_update: Callable = None
        self._update_interval = 5.0   # seconds
        self._tle_loaded = False
        # Next-pass cache: name → SatPass (recomputed when pass elapses)
        self._pass_cache: dict[str, "Optional[SatPass]"] = {}

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self):
        """Start tracking. Loads TLEs and begins polling."""
        if self._running:
            return
        if not HAS_SGP4:
            log.warning(
                "sgp4 not installed — satellite tracking disabled. "
                "pip install sgp4")
            return
        self._running = True
        self._thread  = threading.Thread(
            target=self._track_loop,
            daemon=True, name="SatTracker")
        self._thread.start()
        log.info("Satellite tracker started")

    def stop(self):
        self._running = False

    def load_tles(self, tle_text: str) -> int:
        """Parse TLE text and load satellites."""
        if not HAS_SGP4:
            return 0
        lines   = [l.strip() for l in tle_text.splitlines()
                   if l.strip()]
        loaded  = 0
        i       = 0
        while i < len(lines) - 2:
            if (lines[i+1].startswith("1 ") and
                    lines[i+2].startswith("2 ")):
                name = lines[i].strip()
                try:
                    sat = Satrec.twoline2rv(
                        lines[i+1], lines[i+2])
                    with self._lock:
                        self._sats[name] = sat
                    loaded += 1
                    i += 3
                except Exception as e:
                    log.debug(f"TLE parse {name}: {e}")
                    i += 1
            else:
                i += 1
        log.info(f"Loaded {loaded} TLEs")
        return loaded

    def fetch_tles(self) -> bool:
        """Fetch current TLEs from Celestrak."""
        if not HAS_REQUESTS:
            return self._load_cached_tles()

        for url_key, url in [
            ("ham_sats",
             "https://celestrak.org/pub/TLE/Amateur.tle"),
            ("active",
             "https://celestrak.org/pub/TLE/active.tle"),
        ]:
            try:
                from core.netlog import record_connection
                record_connection("celestrak.org", purpose="satellite TLEs", user_initiated=False)
                resp = requests.get(url, timeout=15)
                if resp.status_code == 200 and resp.text:
                    count = self.load_tles(resp.text)
                    if count > 0:
                        # Cache locally
                        try:
                            _TLE_CACHE_PATH.parent.mkdir(
                                parents=True, exist_ok=True)
                            _TLE_CACHE_PATH.write_text(
                                resp.text)
                        except Exception:
                            pass
                        log.info(
                            f"TLEs fetched from Celestrak: "
                            f"{count} satellites")
                        return True
            except Exception as e:
                log.debug(f"TLE fetch {url_key}: {e}")

        return self._load_cached_tles()

    def _load_cached_tles(self) -> bool:
        """Load TLEs from local cache file."""
        cache = _TLE_CACHE_PATH
        if cache.exists():
            age = time.time() - cache.stat().st_mtime
            if age < 86400 * 3:   # 3 days
                count = self.load_tles(
                    cache.read_text())
                if count > 0:
                    log.info(
                        f"TLEs from cache: {count} sats")
                    return True
        return False

    def add_builtin_tles(self):
        """Add hardcoded TLEs for key satellites as fallback."""
        # ISS TLE (approximate — refresh from Celestrak)
        tle_text = """\
ISS (ZARYA)
1 25544U 98067A   24001.50000000  .00021899  00000+0  39751-3 0  9994
2 25544  51.6413  96.6289 0001200 185.0000 175.0000 15.50000000000000
NOAA 19
1 33591U 09005A   24001.50000000  .00000087  00000+0  69347-4 0  9994
2 33591  99.0884 130.4270 0013966 248.6019 111.3656 14.12413400000000
"""
        count = self.load_tles(tle_text)
        log.info(f"Builtin TLEs loaded: {count}")

    def get_position(self, name: str,
                     observer_lat: float = 0.0,
                     observer_lon: float = 0.0
                     ) -> Optional[SatPosition]:
        """Get current position of a named satellite."""
        if not HAS_SGP4:
            return None
        with self._lock:
            sat = self._sats.get(name)
        if sat is None:
            return None
        return self._compute_position(
            name, sat, observer_lat, observer_lon)

    def all_positions(self,
                      observer_lat: float = 0.0,
                      observer_lon: float = 0.0
                      ) -> list[SatPosition]:
        """Get positions of all tracked satellites."""
        if not HAS_SGP4:
            return []
        result = []
        with self._lock:
            sats = dict(self._sats)
        for name, sat in sats.items():
            pos = self._compute_position(
                name, sat, observer_lat, observer_lon)
            if pos:
                result.append(pos)
        return result

    @staticmethod
    def _eci_to_geodetic(
            r: "tuple", jd: float, fr: float
    ) -> "tuple[float, float, float]":
        """Convert ECI position vector to (lat_deg, lon_deg, alt_km)."""
        rx, ry, rz = r
        a  = 6378.137       # Earth semi-major axis km
        f  = 1 / 298.257    # flattening
        e2 = 2 * f - f * f

        t   = (jd + fr - 2451545.0) / 36525
        gst = (280.46061837 + 360.98564736629 *
               (jd + fr - 2451545.0) +
               0.000387933 * t * t) % 360
        gst = math.radians(gst)

        lon = math.degrees(math.atan2(ry, rx) - gst)
        lon = ((lon + 180) % 360) - 180
        p   = math.sqrt(rx**2 + ry**2)
        lat = math.degrees(math.atan2(rz, p * (1 - e2)))

        for _ in range(5):
            s_lat = math.sin(math.radians(lat))
            N     = a / math.sqrt(1 - e2 * s_lat**2)
            lat   = math.degrees(math.atan2(rz + e2 * N * s_lat, p))

        alt = (p / math.cos(math.radians(lat)) -
               a / math.sqrt(1 - e2 * math.sin(math.radians(lat))**2))
        return lat, lon, alt

    def _compute_next_pass(
            self, name: str, sat,
            obs_lat: float, obs_lon: float,
            hours_ahead: int = 24
    ) -> "Optional[SatPass]":
        """Predict the next pass of a satellite for a ground observer.

        Steps forward at 60-second intervals for up to ``hours_ahead`` hours.
        Returns the first positive-elevation window found as a SatPass,
        or None if no pass is predicted in the look-ahead window.

        Runs in the tracking thread — safe to call from _compute_position.
        """
        if not HAS_SGP4 or (obs_lat == 0.0 and obs_lon == 0.0):
            return None
        from datetime import timedelta
        now        = datetime.now(timezone.utc)
        step_s     = 60
        max_steps  = hours_ahead * 3600 // step_s
        in_pass    = False
        aos_time   = now
        aos_az     = 0.0
        max_el     = -1.0
        max_el_time = now
        try:
            for i in range(max_steps):
                t = now + timedelta(seconds=i * step_s)
                jd, fr = jday(t.year, t.month, t.day,
                              t.hour, t.minute,
                              t.second + t.microsecond / 1e6)
                e, r, _ = sat.sgp4(jd, fr)
                if e != 0:
                    continue
                sat_lat, sat_lon, sat_alt = self._eci_to_geodetic(r, jd, fr)
                el, az, _ = self._azel(
                    obs_lat, obs_lon, 0.0, sat_lat, sat_lon, sat_alt)
                if not in_pass and el > 0:
                    in_pass     = True
                    aos_time    = t
                    aos_az      = az
                    max_el      = el
                    max_el_time = t
                elif in_pass:
                    if el > max_el:
                        max_el      = el
                        max_el_time = t
                    elif el <= 0:
                        return SatPass(
                            sat_name    = name,
                            aos_utc     = aos_time,
                            los_utc     = t,
                            max_el_deg  = round(max_el, 1),
                            max_el_utc  = max_el_time,
                            aos_az_deg  = round(aos_az, 1),
                            los_az_deg  = round(az, 1),
                        )
        except Exception as e:
            log.debug(f"next_pass {name}: {e}")
        return None

    def _compute_position(
            self, name: str, sat,
            obs_lat: float, obs_lon: float
    ) -> Optional[SatPosition]:
        """Compute satellite ECI → geographic position."""
        try:
            now = datetime.now(timezone.utc)
            jd, fr = jday(now.year, now.month, now.day,
                          now.hour, now.minute,
                          now.second + now.microsecond / 1e6)
            e, r, v = sat.sgp4(jd, fr)
            if e != 0:
                return None

            vx, vy, vz = v
            vel = math.sqrt(vx**2 + vy**2 + vz**2)
            lat, lon, alt = self._eci_to_geodetic(r, jd, fr)

            el_deg = az_deg = rng_km = 0.0
            if obs_lat or obs_lon:
                el_deg, az_deg, rng_km = \
                    self._azel(obs_lat, obs_lon, 0, lat, lon, alt)

            # Retrieve or compute next pass (cached; recomputed when elapsed)
            cached = self._pass_cache.get(name)
            now_ts = time.time()
            if (cached is None or
                    cached.los_utc.timestamp() < now_ts):
                cached = self._compute_next_pass(
                    name, sat, obs_lat, obs_lon)
                self._pass_cache[name] = cached

            return SatPosition(
                name       = name,
                lat        = round(lat, 3),
                lon        = round(lon, 3),
                alt_km     = round(alt, 1),
                vel_kms    = round(vel, 2),
                el_deg     = round(el_deg, 1),
                az_deg     = round(az_deg, 1),
                range_km   = round(rng_km, 0),
                doppler_hz = self._doppler(vel, el_deg, 145_000_000),
                is_sunlit  = False,
                next_pass  = cached,
                timestamp  = time.time(),
            )
        except Exception as e:
            log.debug(f"Position {name}: {e}")
            return None

    def _azel(self, obs_lat, obs_lon, obs_alt_km,
               sat_lat, sat_lon, sat_alt_km
               ) -> tuple[float, float, float]:
        """Compute elevation, azimuth, range from observer to satellite."""
        R    = 6371.0   # Earth radius km
        ola  = math.radians(obs_lat)
        olo  = math.radians(obs_lon)
        sla  = math.radians(sat_lat)
        slo  = math.radians(sat_lon)

        # Range vector in ECEF
        def ecef(lat, lon, alt):
            c = math.cos(lat)
            return ((R + alt) * c * math.cos(lon),
                    (R + alt) * c * math.sin(lon),
                    (R + alt) * math.sin(lat))

        ox, oy, oz = ecef(ola, olo, obs_alt_km)
        sx, sy, sz = ecef(sla, slo, sat_alt_km)
        dx, dy, dz = sx-ox, sy-oy, sz-oz
        rng = math.sqrt(dx**2 + dy**2 + dz**2)

        # To topocentric South-East-Z
        cos_la, sin_la = math.cos(ola), math.sin(ola)
        cos_lo, sin_lo = math.cos(olo), math.sin(olo)
        S  = (-sin_la*cos_lo*dx
              - sin_la*sin_lo*dy + cos_la*dz)
        E  = -sin_lo*dx + cos_lo*dy
        Z  = (cos_la*cos_lo*dx
              + cos_la*sin_lo*dy + sin_la*dz)

        el  = math.degrees(math.atan2(Z, math.sqrt(S**2+E**2)))
        az  = math.degrees(math.atan2(E, -S)) % 360
        return el, az, rng

    def _doppler(self, vel_kms: float,
                  el_deg: float, freq_hz: int) -> float:
        """Rough Doppler shift estimate."""
        radial = vel_kms * math.sin(math.radians(el_deg))
        return -radial / 300000 * freq_hz

    def _track_loop(self):
        """Fetch TLEs then poll positions continuously."""
        if not self._tle_loaded:
            self.fetch_tles()
            if not self._sats:
                self.add_builtin_tles()
            self._tle_loaded = True

        while self._running:
            obs_lat = obs_lon = 0.0
            if self.cfg:
                obs_lat = float(
                    self.cfg.get("location.lat", 0) or 0)
                obs_lon = float(
                    self.cfg.get("location.lon", 0) or 0)
            positions = self.all_positions(obs_lat, obs_lon)
            with self._lock:
                self._positions = {
                    p.name: p for p in positions}
            if self._on_update and positions:
                try:
                    self._on_update(positions)
                except Exception:
                    pass
            time.sleep(self._update_interval)

    def on_update(self, cb: Callable):
        self._on_update = cb

    def visible_sats(self) -> list[SatPosition]:
        with self._lock:
            return [p for p in self._positions.values()
                    if p.is_visible]

    def all_map_positions(self) -> list[dict]:
        with self._lock:
            return [
                {"name":   p.name,
                 "lat":    p.lat,
                 "lon":    p.lon,
                 "alt_km": p.alt_km,
                 "el_deg": p.el_deg,
                 "az_deg": p.az_deg,
                 "visible": p.is_visible}
                for p in self._positions.values()]
