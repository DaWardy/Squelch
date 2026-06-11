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
"""Squelch -- network/propagation.py
Solar and propagation data.
NOAA SWPC solar indices, aurora alerts, WSPRnet band conditions.
All responses validated before use.
"""

import time
import logging
import threading
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
from dataclasses import dataclass, field
from typing import Optional, Callable
from core.validator import api_float, api_int, api_string

log = logging.getLogger(__name__)

from core.constants import (
    NOAA_SOLAR_URL, NOAA_SOLAR_RT_URL,
    NOAA_KP_URL, NOAA_KP_RT_URL,
    NOAA_ALERTS_URL)

# NOAA SWPC endpoints
NOAA_XRAY_URL  = (
    "https://services.swpc.noaa.gov/json/goes/primary/"
    "xrays-1-day.json")
WSPRNET_URL    = "https://www.wsprnet.org/drupal/wsprnet/spotquery"

REQUEST_TIMEOUT = 10
POLL_INTERVAL   = 300    # 5 minutes - respect rate limits


@dataclass
class SolarData:
    """Current solar conditions."""
    sfi:          float = 0.0     # Solar Flux Index 10.7cm
    sfi_trend:    str   = ""      # "rising" / "falling" / "stable"
    sunspot_num:  int   = 0
    a_index:      float = 0.0     # planetary A-index (daily)
    k_index:      float = 0.0     # planetary K-index (3-hourly)
    k_trend:      str   = ""
    xray_class:   str   = "A"     # X-ray flare class A/B/C/M/X
    xray_flux:    float = 0.0
    aurora_alert: bool  = False
    storm_level:     int   = 0       # 0=none 1=G1 2=G2 3=G3 4=G4 5=G5
    muf_estimate_mhz: float = 0.0    # estimated MUF for ~3000km F2 path
    fetched_at:   float = field(default_factory=time.time)

    @property
    def age_minutes(self) -> float:
        return (time.time() - self.fetched_at) / 60

    @property
    def conditions_summary(self) -> str:
        """One-line summary of band conditions."""
        if self.storm_level >= 3:
            return f"⚠ Geomagnetic storm G{self.storm_level} — HF degraded"
        if self.storm_level >= 1:
            return f"⚠ Geomagnetic activity G{self.storm_level}"
        if self.k_index >= 4:
            return f"⚠ K={self.k_index:.0f} — elevated activity"
        if self.sfi >= 200:
            return f"★ Excellent — SFI={self.sfi:.0f} K={self.k_index:.0f}"
        if self.sfi >= 150:
            return f"✓ Good — SFI={self.sfi:.0f} K={self.k_index:.0f}"
        if self.sfi >= 100:
            return f"~ Fair — SFI={self.sfi:.0f} K={self.k_index:.0f}"
        return f"Poor — SFI={self.sfi:.0f} K={self.k_index:.0f}"

    @property
    def band_recommendations(self) -> list[str]:
        """Suggest best bands based on current conditions."""
        recs = []
        if self.storm_level >= 2:
            recs.append("160m/80m — low bands less affected by storms")
            recs.append("VHF/UHF local — avoid HF during storm")
            return recs

        if self.sfi >= 150:
            recs.append("10m — excellent high-band conditions")
            recs.append("12m/15m — great DX opportunity")
            recs.append("17m/20m — reliable long path")
        elif self.sfi >= 100:
            recs.append("20m — reliable day/night DX")
            recs.append("17m — good afternoon conditions")
            recs.append("40m — good evening/night")
        else:
            recs.append("40m — most reliable in low solar flux")
            recs.append("80m — evening regional")
            recs.append("20m — short skip only")

        if self.k_index <= 1:
            recs.append("All bands — quiet geomagnetic conditions")

        return recs[:4]


@dataclass
class BandCondition:
    """Condition assessment for a specific band."""
    band:       str
    condition:  str    # "excellent" / "good" / "fair" / "poor" / "closed"
    muf_hz:     int    = 0
    notes:      str    = ""
    color:      str    = "#555555"


CONDITION_COLORS = {
    "excellent": "#00aa44",
    "good":      "#3fbe6f",
    "fair":      "#aaaa22",
    "poor":      "#cc8822",
    "closed":    "#cc4444",
}


class PropagationFeed:
    """
    Polls NOAA SWPC and WSPRnet for propagation data.
    Fires callbacks when data updates.
    """

    def __init__(self):
        self._solar:    SolarData = SolarData()
        self._path_km:  float     = 0.0   # 0 = use default 3000km
        self._bands:    list[BandCondition] = []
        self._alerts:   list[str] = []
        self._running   = False
        self._thread:   threading.Thread | None = None
        self._lock      = threading.Lock()

        self._on_solar:  Callable | None = None
        self._on_alert:  Callable | None = None

    # ── Public API ────────────────────────────────────────────────────────

    def start(self):
        self._running = True
        self._thread  = threading.Thread(
            target=self._run, daemon=True,
            name="PropFeed")
        self._thread.start()

    def stop(self):
        self._running = False

    @property
    def solar(self) -> SolarData:
        with self._lock:
            return self._solar

    @property
    def band_conditions(self) -> list[BandCondition]:
        with self._lock:
            return list(self._bands)

    @property
    def alerts(self) -> list[str]:
        with self._lock:
            return list(self._alerts)

    def on_solar_update(self, cb: Callable):
        self._on_solar = cb

    def set_path_km(self, km: float):
        """Set path distance for MUF calculation. 0 = use default 3000 km."""
        self._path_km = max(0.0, float(km))
        self._update_band_conditions()

    def on_alert(self, cb: Callable):
        self._on_alert = cb

    # ── Poll loop ─────────────────────────────────────────────────────────

    def _run(self):
        # Fetch immediately then poll
        self._fetch_all()
        while self._running:
            for _ in range(POLL_INTERVAL):
                if not self._running:
                    return
                time.sleep(1)
            self._fetch_all()

    def _fetch_all(self):
        try:
            self._fetch_solar()
        except Exception as e:
            log.debug(f"Solar fetch: {e}")
        try:
            self._fetch_kp()
        except Exception as e:
            log.debug(f"KP fetch: {e}")
        try:
            self._fetch_alerts()
        except Exception as e:
            log.debug(f"Alerts fetch: {e}")
        self._update_band_conditions()
        if self._on_solar:
            try:
                self._on_solar(self._solar)
            except Exception:
                pass

    def _fetch_solar_rt_flux(self) -> None:
        """Update self._solar.sfi from the NOAA real-time 10.7cm flux endpoint."""
        try:
            from core.netlog import record_connection
            record_connection("services.swpc.noaa.gov",
                              purpose="solar/band conditions",
                              user_initiated=False)
            resp = requests.get(NOAA_SOLAR_RT_URL, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                return
            data = resp.json()
            if not isinstance(data, dict):
                return
            raw = (data.get("Flux") or data.get("flux") or
                   data.get("solarflux") or data.get("value"))
            sfi = api_float(raw, 0.0)
            if sfi > 50:
                self._solar.sfi = sfi
                self._solar.fetched_at = time.time()
                log.debug(f"Solar RT SFI={sfi}")
        except Exception as e:
            log.debug(f"Solar RT: {e}")

    def _fetch_solar_cycle_data(self) -> None:
        """Update sunspot number and SFI trend from the NOAA 45-day cycle file."""
        try:
            resp = requests.get(NOAA_SOLAR_URL, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                return
            data = resp.json()
            if not (isinstance(data, list) and len(data) >= 2):
                return
            latest, prev = data[-1], data[-2]
            if self._solar.sfi <= 0:
                sfi = api_float(
                    latest.get("flux") or latest.get("f10.7") or
                    latest.get("smoothed_ssn"), 0.0)
                if sfi > 50:
                    self._solar.sfi = sfi
            ssn = api_int(latest.get("ssn") or latest.get("smoothed_ssn"), 0)
            if ssn >= 0:
                self._solar.sunspot_num = ssn
            prev_sfi = api_float(prev.get("flux") or prev.get("f10.7"), 0.0)
            if self._solar.sfi > prev_sfi + 2:
                self._solar.sfi_trend = "rising"
            elif self._solar.sfi < prev_sfi - 2:
                self._solar.sfi_trend = "falling"
            else:
                self._solar.sfi_trend = "stable"
            log.debug(f"Solar cycle: SFI={self._solar.sfi} "
                      f"SSN={self._solar.sunspot_num} trend={self._solar.sfi_trend}")
        except Exception as e:
            log.debug(f"Solar cycle: {e}")

    def _fetch_solar(self):
        """Fetch real-time solar data from NOAA SWPC."""
        if not HAS_REQUESTS:
            return
        self._fetch_solar_rt_flux()
        self._fetch_solar_cycle_data()

    @staticmethod
    def _kp_to_storm_level(kp: float) -> int:
        """Return NOAA G-scale storm level (0–5) for a Kp value."""
        if kp >= 9: return 5
        if kp >= 8: return 4
        if kp >= 7: return 3
        if kp >= 6: return 2
        if kp >= 5: return 1
        return 0

    @staticmethod
    def _parse_kp_readings(data: list) -> list[float]:
        """Extract float Kp values from the last 4 NOAA API rows."""
        vals = []
        for row in data[-4:]:
            if isinstance(row, list) and len(row) >= 2:
                try:
                    vals.append(float(row[1]))
                except (ValueError, TypeError):
                    pass
        return vals

    def _fetch_kp(self):
        if not HAS_REQUESTS:
            return None
        try:
            resp = requests.get(NOAA_KP_URL, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                return
            if len(resp.content) > 50_000:
                return
            data = resp.json()
        except Exception as e:
            log.debug(f"K-index fetch failed: {e}")
            return None
        if not isinstance(data, list) or len(data) < 2:
            return

        kp_vals = self._parse_kp_readings(data)
        if not kp_vals:
            return

        kp_now  = kp_vals[-1]
        kp_prev = kp_vals[-2] if len(kp_vals) > 1 else kp_now

        if kp_now > kp_prev + 0.5:
            trend = "rising"
        elif kp_now < kp_prev - 0.5:
            trend = "falling"
        else:
            trend = "stable"

        storm = self._kp_to_storm_level(kp_now)

        with self._lock:
            self._solar.k_index      = kp_now
            self._solar.k_trend      = trend
            self._solar.storm_level  = storm
            self._solar.aurora_alert = kp_now >= 5

        if storm >= 2 and self._on_alert:
            msg = (f"Geomagnetic storm G{storm} — "
                   f"Kp={kp_now:.0f}\n"
                   f"HF propagation may be disrupted.\n"
                   f"Aurora possible at lower latitudes.")
            try:
                self._on_alert("Geomagnetic Storm", msg, "warning")
            except Exception:
                pass

    def _fetch_alerts(self):
        if not HAS_REQUESTS:
            return None
        resp = requests.get(
            NOAA_ALERTS_URL, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return
        if len(resp.content) > 100_000:
            return

        data = resp.json()
        if not isinstance(data, list):
            return

        alerts = []
        for entry in data[:10]:
            if isinstance(entry, dict):
                msg = api_string(entry.get("message", ""), 200)
                if msg:
                    alerts.append(msg)

        with self._lock:
            self._alerts = alerts

    @staticmethod
    def _compute_muf_factors(sfi: float, k: float,
                             path_km: float) -> "tuple[float, float]":
        """Return (muf_1hop_mhz, muf_short_mhz) using ARRL/CCIR foF2 model.

        Validated: ~8 MHz at SFI=100, ~11 at SFI=200, ~6.5 at SFI=70.
        """
        import math
        import time as _time
        sfi         = max(70.0, sfi)
        fof2_day    = math.sqrt(sfi / 25.0) * 4.0
        fof2_night  = fof2_day * 0.55
        utc_h       = _time.gmtime().tm_hour + _time.gmtime().tm_min / 60
        day_frac    = 0.5 + 0.5 * math.sin(math.radians((utc_h - 6) * 15))
        fof2        = fof2_night + (fof2_day - fof2_night) * day_frac
        geo_factor  = max(0.3, 1.0 - 0.08 * k)          # K5→−40%, K9→−72%
        path_km     = path_km if path_km > 100 else 3000.0
        path_factor = max(1.5, min(4.5, path_km / 1000.0 + 1.2))
        return fof2 * geo_factor * path_factor, fof2 * geo_factor * 1.5

    @staticmethod
    def _assess_band_condition(band: str, low_mhz: float, high_mhz: float,
                               needs_f2: bool, muf_1hop: float,
                               muf_short: float, storm_level: int,
                               k: float) -> "BandCondition":
        """Return a BandCondition for one band given current propagation state."""
        centre = (low_mhz + high_mhz) / 2
        muf    = muf_1hop if needs_f2 else muf_short
        if storm_level >= 4:
            cond, note = "closed", "Severe storm"
        elif storm_level >= 3 and needs_f2:
            cond, note = "poor", "G3 storm"
        elif muf >= high_mhz * 1.15:
            cond, note = "excellent", ""
        elif muf >= centre:
            cond, note = "good", ""
        elif muf >= low_mhz * 0.8:
            cond, note = "fair", ""
        else:
            cond, note = "poor", ""
        if k >= 4 and low_mhz < 14:
            if cond in ("excellent", "good"):
                cond = "fair"
            note = f"K={k:.0f} absorption"
        return BandCondition(
            band=band, condition=cond,
            muf_hz=int(muf * 1_000_000),
            notes=note,
            color=CONDITION_COLORS.get(cond, "#555"),
        )

    def _update_band_conditions(self):
        """Estimate band conditions using foF2-based MUF model (offline)."""
        solar = self._solar
        k = float(solar.k_index or 0)
        muf_1hop, muf_short = self._compute_muf_factors(
            float(solar.sfi or 70), k, self._path_km)
        sl = solar.storm_level

        def _a(band, lo, hi, f2=True):
            return self._assess_band_condition(
                band, lo, hi, f2, muf_1hop, muf_short, sl, k)

        conditions = [
            _a("160m",  1.8,  2.0,  False),
            _a("80m",   3.5,  4.0,  False),
            _a("40m",   7.0,  7.3),
            _a("30m",  10.1, 10.15),
            _a("20m",  14.0, 14.35),
            _a("17m",  18.0, 18.17),
            _a("15m",  21.0, 21.45),
            _a("12m",  24.8, 24.99),
            _a("10m",  28.0, 29.7),
            _a("6m",   50.0, 54.0,  False),
        ]
        solar.muf_estimate_mhz = round(muf_1hop, 1)
        with self._lock:
            self._bands = conditions


# Module singleton
_feed: PropagationFeed | None = None

def get_prop_feed() -> PropagationFeed:
    global _feed
    if _feed is None:
        _feed = PropagationFeed()
    return _feed
