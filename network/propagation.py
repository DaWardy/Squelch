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
    storm_level:  int   = 0       # 0=none 1=G1 2=G2 3=G3 4=G4 5=G5
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

    def _fetch_solar(self):
        """Fetch real-time solar data from NOAA SWPC."""
        if not HAS_REQUESTS:
            return

        # ── Real-time 10.7cm flux (updates every 3h) ──────────────
        try:
            from core.netlog import record_connection
            record_connection("services.swpc.noaa.gov", purpose="solar/band conditions", user_initiated=False)
            resp = requests.get(
                NOAA_SOLAR_RT_URL, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                # Response: {"Flux": "156.8", "TimeStamp": "..."}
                if isinstance(data, dict):
                    raw = (data.get("Flux") or
                           data.get("flux") or
                           data.get("solarflux") or
                           data.get("value"))
                    sfi = api_float(raw, 0.0)
                    if sfi > 50:  # sanity check
                        self._solar.sfi = sfi
                        self._solar.fetched_at = time.time()
                        log.debug(f"Solar RT SFI={sfi}")
        except Exception as e:
            log.debug(f"Solar RT: {e}")

        # ── 45-day solar cycle file for sunspot + trend ───────────
        try:
            resp = requests.get(
                NOAA_SOLAR_URL, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) >= 2:
                    latest = data[-1]
                    prev   = data[-2]
                    # Update SFI only if RT failed
                    if self._solar.sfi <= 0:
                        sfi = api_float(
                            latest.get("flux") or
                            latest.get("f10.7") or
                            latest.get("smoothed_ssn"), 0.0)
                        if sfi > 50:
                            self._solar.sfi = sfi
                    # Sunspot number
                    ssn = api_int(
                        latest.get("ssn") or
                        latest.get("smoothed_ssn"), 0)
                    if ssn >= 0:
                        self._solar.sunspot_num = ssn
                    # Trend
                    prev_sfi = api_float(
                        prev.get("flux") or
                        prev.get("f10.7"), 0.0)
                    if self._solar.sfi > prev_sfi + 2:
                        self._solar.sfi_trend = "rising"
                    elif self._solar.sfi < prev_sfi - 2:
                        self._solar.sfi_trend = "falling"
                    else:
                        self._solar.sfi_trend = "stable"
                    log.debug(
                        f"Solar cycle: SFI={self._solar.sfi} "
                        f"SSN={self._solar.sunspot_num} "
                        f"trend={self._solar.sfi_trend}")
        except Exception as e:
            log.debug(f"Solar cycle: {e}")


    def _fetch_solar_UNUSED(self):
        """Old implementation — kept for reference."""
        if not HAS_REQUESTS:
            return None
        resp = requests.get(
            NOAA_SOLAR_URL, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return
        if len(resp.content) > 200_000:
            return

        data = resp.json()
        if not isinstance(data, list) or not data:
            return

        # Most recent entry
        latest = data[-1]
        prev   = data[-2] if len(data) > 1 else latest

        sfi_now  = api_float(latest.get("smoothed_ssn") or
                             latest.get("f10.7"), 0.0)
        sfi_prev = api_float(prev.get("smoothed_ssn") or
                             prev.get("f10.7"), 0.0)

        if sfi_now > sfi_prev + 2:
            trend = "rising"
        elif sfi_now < sfi_prev - 2:
            trend = "falling"
        else:
            trend = "stable"

        with self._lock:
            self._solar.sfi         = sfi_now
            self._solar.sfi_trend   = trend
            self._solar.sunspot_num = api_int(
                latest.get("ssn"), 0)
            self._solar.fetched_at  = time.time()

    def _fetch_kp(self):
        if not HAS_REQUESTS:
            return None
        try:
            resp = requests.get(
                NOAA_KP_URL, timeout=REQUEST_TIMEOUT)
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

        # Last few readings
        readings = data[-4:]  # last 12 hours
        kp_vals  = []
        for row in readings:
            if isinstance(row, list) and len(row) >= 2:
                try:
                    kp_vals.append(float(row[1]))
                except (ValueError, TypeError):
                    pass

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

        # G-scale storm level
        storm = 0
        if kp_now >= 9:   storm = 5
        elif kp_now >= 8: storm = 4
        elif kp_now >= 7: storm = 3
        elif kp_now >= 6: storm = 2
        elif kp_now >= 5: storm = 1

        with self._lock:
            self._solar.k_index     = kp_now
            self._solar.k_trend     = trend
            self._solar.storm_level = storm
            self._solar.aurora_alert = kp_now >= 5

        if storm >= 2 and self._on_alert:
            msg = (f"Geomagnetic storm G{storm} — "
                   f"Kp={kp_now:.0f}\n"
                   f"HF propagation may be disrupted.\n"
                   f"Aurora possible at lower latitudes.")
            try:
                self._on_alert("Geomagnetic Storm", msg,
                               "warning")
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

    def _update_band_conditions(self):
        """
        Estimate band conditions from solar indices.
        Simplified model — VOACAP integration in future chunk.
        """
        solar = self._solar
        conditions = []

        def _assess(band: str, min_sfi: float,
                     good_sfi: float,
                     kp_sensitive: bool) -> BandCondition:
            if solar.storm_level >= 3 and kp_sensitive:
                cond = "closed"
            elif solar.k_index >= 5 and kp_sensitive:
                cond = "poor"
            elif solar.sfi >= good_sfi:
                cond = "excellent" if solar.sfi >= good_sfi * 1.3 \
                    else "good"
            elif solar.sfi >= min_sfi:
                cond = "fair"
            else:
                cond = "poor"
            return BandCondition(
                band      = band,
                condition = cond,
                color     = CONDITION_COLORS.get(cond, "#555"),
            )

        conditions = [
            _assess("160m",  70,  90, True),
            _assess("80m",   70,  90, True),
            _assess("40m",   70, 100, True),
            _assess("30m",   80, 110, True),
            _assess("20m",   80, 120, True),
            _assess("17m",   90, 130, True),
            _assess("15m",  100, 140, True),
            _assess("12m",  110, 150, True),
            _assess("10m",  120, 160, True),
            _assess("6m",   130, 170, False),
        ]

        with self._lock:
            self._bands = conditions


# Module singleton
_feed: PropagationFeed | None = None

def get_prop_feed() -> PropagationFeed:
    global _feed
    if _feed is None:
        _feed = PropagationFeed()
    return _feed
