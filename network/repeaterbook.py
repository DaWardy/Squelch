from __future__ import annotations
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
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- network/repeaterbook.py
RepeaterBook.com API integration.
Free API, no key required for basic queries.
Returns nearest repeaters by lat/lon or state.
API docs: repeaterbook.com/pages/api.php
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

log = logging.getLogger(__name__)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

RB_BASE = "https://www.repeaterbook.com/api"
RB_NEAR = f"{RB_BASE}/export.php"
RB_UA   = "Squelch/0.7.0-alpha (github.com/dawardy/squelch)"

REQUEST_TIMEOUT = 10
RATE_LIMIT_S    = 2.0   # RepeaterBook asks for 2s between requests
_last_request   = 0.0


@dataclass
class Repeater:
    """A single repeater entry from RepeaterBook."""
    callsign:     str
    output_mhz:   float
    input_mhz:    float
    offset_mhz:   float
    tone:         str        = ""   # CTCSS tone or DCS code
    tone_type:    str        = ""   # "CTCSS" / "DCS" / ""
    mode:         str        = ""   # FM / DMR / P25 / YSF / D-STAR / NXDN
    state:        str        = ""
    county:       str        = ""
    city:         str        = ""
    lat:          float      = 0.0
    lon:          float      = 0.0
    distance_km:  float      = 0.0
    status:       str        = ""   # "Open" / "Closed" / "Private"
    use_code:     str        = ""   # "OPEN" / "ARES" etc
    notes:        str        = ""
    last_updated: str        = ""

    @property
    def output_str(self) -> str:
        return f"{self.output_mhz:.4f}"

    @property
    def offset_str(self) -> str:
        sign = "+" if self.offset_mhz >= 0 else ""
        return f"{sign}{self.offset_mhz:.3f}"

    @property
    def tone_str(self) -> str:
        if not self.tone:
            return ""
        return f"{self.tone_type} {self.tone}".strip()

    @property
    def band(self) -> str:
        mhz = self.output_mhz
        if 28 <= mhz < 30:   return "10m"
        if 50 <= mhz < 54:   return "6m"
        if 144 <= mhz < 148: return "2m"
        if 222 <= mhz < 225: return "1.25m"
        if 420 <= mhz < 450: return "70cm"
        if 902 <= mhz < 928: return "33cm"
        if 1240 <= mhz:      return "23cm"
        return f"{mhz:.0f}MHz"

    @property
    def is_digital(self) -> bool:
        return self.mode.upper() in (
            "DMR", "P25", "YSF", "DSTAR", "D-STAR",
            "NXDN", "FUSION", "C4FM")

    @property
    def display_line(self) -> str:
        parts = [f"{self.output_str} MHz"]
        if self.offset_str:
            parts.append(self.offset_str)
        if self.tone_str:
            parts.append(self.tone_str)
        if self.mode:
            parts.append(self.mode)
        return "  ".join(parts)


def _rate_limit():
    global _last_request
    elapsed = time.time() - _last_request
    if elapsed < RATE_LIMIT_S:
        time.sleep(RATE_LIMIT_S - elapsed)
    _last_request = time.time()


def nearest_repeaters(lat: float, lon: float,
                       radius_km: float = 50.0,
                       mode: str = "") -> list[Repeater]:
    """
    Fetch nearest repeaters from RepeaterBook.
    Rate limited per RepeaterBook API terms.
    """
    if not HAS_REQUESTS:
        log.warning("requests not installed")
        return []

    _rate_limit()

    params = {
        "lat":      round(lat, 6),
        "lon":      round(lon, 6),
        "radius":   min(radius_km, 200),
        "unit":     "km",
        "type":     mode or "FM",  # FM/DMR/P25/YSF/DStar
    }

    try:
        resp = requests.get(
            RB_NEAR,
            params=params,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": RB_UA})

        if resp.status_code != 200:
            log.warning(
                f"RepeaterBook API: {resp.status_code}")
            return []
        if len(resp.content) > 500_000:
            return []

        data = resp.json()
        results = data.get("results", [])
        if not isinstance(results, list):
            return []

        repeaters = []
        for r in results[:100]:
            try:
                out   = float(r.get("Frequency", 0))
                inp   = float(r.get("Input Freq", out))
                offset = round(inp - out, 4)
                rep = Repeater(
                    callsign     = str(r.get("Callsign", ""))[:12],
                    output_mhz   = out,
                    input_mhz    = inp,
                    offset_mhz   = offset,
                    tone         = str(r.get("PL", ""))[:10],
                    tone_type    = str(r.get("Use", "CTCSS"))[:10],
                    mode         = str(r.get("Digital Code", "FM"))[:15],
                    state        = str(r.get("State ID", ""))[:30],
                    county       = str(r.get("County", ""))[:50],
                    city         = str(r.get("Nearest City", ""))[:50],
                    lat          = float(r.get("Lat", 0)),
                    lon          = float(r.get("Long", 0)),
                    distance_km  = float(r.get("distance", 0)),
                    status       = str(r.get("Operational Status", ""))[:20],
                    use_code     = str(r.get("Use", ""))[:20],
                    notes        = str(r.get("Notes", ""))[:200],
                    last_updated = str(r.get("Last Update", ""))[:20],
                )
                repeaters.append(rep)
            except Exception as e:
                log.debug(f"Repeater parse: {e}")

        repeaters.sort(key=lambda r: r.distance_km)
        return repeaters

    except Exception as e:
        log.warning(f"RepeaterBook fetch: {e}")
        return []


def nearest_async(lat: float, lon: float,
                   callback: Callable,
                   radius_km: float = 50.0,
                   mode: str = ""):
    """Fetch repeaters in background thread."""
    def _do():
        results = nearest_repeaters(lat, lon, radius_km, mode)
        try:
            callback(results)
        except Exception as e:
            log.debug(f"RepeaterBook callback: {e}")
    threading.Thread(target=_do, daemon=True,
                     name="RBFetch").start()
