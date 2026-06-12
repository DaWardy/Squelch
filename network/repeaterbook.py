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
from core.constants import APP_VERSION
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

RB_BASE   = "https://www.repeaterbook.com/api"
RB_EXPORT = f"{RB_BASE}/export.php"        # North America
RB_ROW    = f"{RB_BASE}/exportROW.php"     # rest of world
# User-Agent must identify the app + contact (RepeaterBook policy, 2026-03).
RB_UA     = (f"Squelch/{APP_VERSION} "
             "(+https://github.com/dawardy/squelch; squelch@example.org)")
RB_APPLY_URL = "https://www.repeaterbook.com/api/token_request.php"

REQUEST_TIMEOUT = 10
RATE_LIMIT_S    = 2.0   # RepeaterBook asks for 2s between requests
_last_request   = 0.0

# US state / territory name -> FIPS state_id (RepeaterBook export.php key).
_US_FIPS = {
    "alabama":"1","alaska":"2","arizona":"4","arkansas":"5","california":"6",
    "colorado":"8","connecticut":"9","delaware":"10","district of columbia":"11",
    "florida":"12","georgia":"13","hawaii":"15","idaho":"16","illinois":"17",
    "indiana":"18","iowa":"19","kansas":"20","kentucky":"21","louisiana":"22",
    "maine":"23","maryland":"24","massachusetts":"25","michigan":"26",
    "minnesota":"27","mississippi":"28","missouri":"29","montana":"30",
    "nebraska":"31","nevada":"32","new hampshire":"33","new jersey":"34",
    "new mexico":"35","new york":"36","north carolina":"37","north dakota":"38",
    "ohio":"39","oklahoma":"40","oregon":"41","pennsylvania":"42",
    "rhode island":"44","south carolina":"45","south dakota":"46",
    "tennessee":"47","texas":"48","utah":"49","vermont":"50","virginia":"51",
    "washington":"53","west virginia":"54","wisconsin":"55","wyoming":"56",
}


class RepeaterBookError(Exception):
    """Carries a user-facing reason so the UI can guide the operator."""
    def __init__(self, message: str, needs_token: bool = False):
        super().__init__(message)
        self.message = message
        self.needs_token = needs_token


def _rb_token() -> str:
    """The user's approved RepeaterBook API token, from the OS keyring (S4).
    Empty string if not configured."""
    try:
        from core.credentials import CredentialStore
        return CredentialStore().retrieve("repeaterbook_token") or ""
    except Exception:
        return ""


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


def _rb_check_response(resp) -> None:
    """Raise RepeaterBookError for non-200 or oversized RepeaterBook responses."""
    if resp.status_code in (401, 403):
        raise RepeaterBookError(
            "RepeaterBook denied the request (token invalid, inactive, "
            "or not approved). Check your token in Settings, or re-apply "
            "at repeaterbook.com/api/token_request.php.",
            needs_token=True)
    if resp.status_code == 429:
        raise RepeaterBookError(
            "RepeaterBook rate limit hit. Wait a bit and try again.")
    if resp.status_code != 200:
        raise RepeaterBookError(
            f"RepeaterBook returned HTTP {resp.status_code}.")
    if len(resp.content) > 2_000_000:
        raise RepeaterBookError("RepeaterBook response too large.")


def _rb_parse_repeater(r: dict, my_lat: float, my_lon: float) -> "Repeater | None":
    """Parse one RepeaterBook result dict into a Repeater. Returns None on error."""
    try:
        out  = float(r.get("Frequency", 0))
        inp  = float(r.get("Input Freq", out))
        rlat = float(r.get("Lat", 0) or 0)
        rlon = float(r.get("Long", 0) or 0)
        return Repeater(
            callsign     = str(r.get("Callsign", ""))[:12],
            output_mhz   = out,
            input_mhz    = inp,
            offset_mhz   = round(inp - out, 4),
            tone         = str(r.get("PL", ""))[:10],
            tone_type    = str(r.get("Use", "CTCSS"))[:10],
            mode         = str(r.get("Digital Code", "FM"))[:15],
            state        = str(r.get("State ID", ""))[:30],
            county       = str(r.get("County", ""))[:50],
            city         = str(r.get("Nearest City", ""))[:50],
            lat          = rlat,
            lon          = rlon,
            distance_km  = _haversine(my_lat, my_lon, rlat, rlon),
            status       = str(r.get("Operational Status", ""))[:20],
            use_code     = str(r.get("Use", ""))[:20],
            notes        = str(r.get("Notes", ""))[:200],
            last_updated = str(r.get("Last Update", ""))[:20],
        )
    except Exception as e:
        log.debug(f"Repeater parse: {e}")
        return None


def nearest_repeaters(lat: float, lon: float,
                       radius_km: float = 50.0,
                       mode: str = "") -> list[Repeater]:
    """Fetch nearest repeaters from RepeaterBook (token required).
    Rate limited per RepeaterBook API terms.
    """
    if not HAS_REQUESTS:
        log.warning("requests not installed")
        return []
    _rate_limit()

    token = _rb_token()
    if not token:
        m = (mode or "").lower().replace("-", "").replace(" ", "")
        if m and m in _DIGITAL_MODES:
            log.info(f"No RB token; using RadioID.net for {m.upper()}")
            return _radioid_nearest(lat, lon, radius_km, mode)
        raise RepeaterBookError(
            "No working free repeater source for analog. RepeaterBook "
            "needs an approved API token (free for non-commercial use): "
            "repeaterbook.com/api/token_request.php. Alternatively, "
            "import a CHIRP CSV (Local RF tab → Import CHIRP CSV) for "
            "fully offline data with no token required.",
            needs_token=True)

    state_id = _state_id_for(lat, lon)
    params = {"country": "United States"}
    if state_id:
        params["state_id"] = state_id
    if mode and mode.upper() not in ("", "ALL"):
        params["mode"] = {
            "fm": "analog", "dmr": "DMR", "p25": "P25",
            "nxdn": "NXDN", "ysf": "analog", "dstar": "analog",
        }.get(mode.lower(), "analog")

    return _rb_fetch_and_parse(lat, lon, token, params, radius_km)


def _rb_fetch_and_parse(lat: float, lon: float,
                         token: str, params: dict,
                         radius_km: float) -> list:
    try:
        resp = requests.get(RB_EXPORT, params=params, timeout=REQUEST_TIMEOUT,
                            headers={"User-Agent": RB_UA, "X-RB-App-Token": token})
        try:
            from core.netlog import record_connection
            record_connection("www.repeaterbook.com",
                              purpose="repeater search", user_initiated=True)
        except Exception:
            pass
        _rb_check_response(resp)
        results = resp.json().get("results", [])
        if not isinstance(results, list):
            return []
        repeaters = [r for r in
                     (_rb_parse_repeater(raw, lat, lon) for raw in results[:100])
                     if r is not None and r.distance_km <= radius_km]
        repeaters.sort(key=lambda r: r.distance_km)
        return repeaters
    except RepeaterBookError:
        raise
    except Exception as e:
        log.warning(f"RepeaterBook fetch: {e}")
        return []


def nearest_async(lat: float, lon: float,
                   callback: Callable,
                   radius_km: float = 50.0,
                   mode: str = "",
                   error_callback: Callable | None = None):
    """Fetch repeaters in background thread.

    On success calls callback(list[Repeater]). On a RepeaterBookError
    (e.g. missing/invalid token) calls error_callback(message, needs_token)
    if provided, so the UI can guide the operator instead of just showing
    an empty table."""
    def _do():
        try:
            results = nearest_repeaters(lat, lon, radius_km, mode)
        except RepeaterBookError as e:
            if error_callback:
                try:
                    error_callback(e.message, e.needs_token)
                except Exception:
                    pass
            else:
                try:
                    callback([])
                except Exception:
                    pass
            return
        except Exception as e:
            log.debug(f"RepeaterBook fetch: {e}")
            if error_callback:
                try:
                    error_callback(str(e), False)
                except Exception:
                    pass
            else:
                callback([])
            return
        try:
            callback(results)
        except Exception as e:
            log.debug(f"RepeaterBook callback: {e}")
    threading.Thread(target=_do, daemon=True,
                     name="RBFetch").start()


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two lat/lon points."""
    import math
    if not (lat2 or lon2):
        return 9999.0
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp/2)**2
         + math.cos(p1) * math.cos(p2) * math.sin(dl/2)**2)
    return r * 2 * math.asin(min(1.0, math.sqrt(a)))


def _state_id_for(lat: float, lon: float) -> str:
    """Reverse-geocode a lat/lon to a US FIPS state_id for the RepeaterBook
    query. Uses the existing Nominatim helper; returns '' if unknown (the
    query then covers the whole country and we filter locally)."""
    try:
        from core.location import reverse_geocode_state
        name = (reverse_geocode_state(lat, lon) or "").strip().lower()
        return _US_FIPS.get(name, "")
    except Exception:
        return ""
# hearham.com: HTTP 403 since early 2026 — function removed.
# Free fallbacks: RadioID.net (digital, no token) and RepeaterBook (token required).




# ── RadioID.net digital repeater fallback ─────────────────────────────────
# radioid.net: free API for DMR/P25/NXDN/D-STAR (no token required as of 2026).
# "Be gentle. Excessive requests may be blocked." — we apply the same rate limit.
# API: https://radioid.net/api/dmr/repeater/?lat=X&lon=Y&range=Z&distance=km
RADIOID_DMR  = "https://radioid.net/api/dmr/repeater/"
RADIOID_P25  = "https://radioid.net/api/p25/tg/"
RADIOID_UA   = f"Squelch/{APP_VERSION} (+https://github.com/dawardy/squelch)"
_DIGITAL_MODES = frozenset({"dmr", "p25", "nxdn", "dstar", "d-star", "fusion", "ysf"})


def _radioid_build_repeater(r: dict, m: str, dist: float) -> "Repeater":
    """Construct a Repeater from a RadioID response dict."""
    return Repeater(
        callsign    = str(r.get("callsign", "")).upper()[:12],
        output_mhz  = float(r.get("frequency") or r.get("output") or 0),
        offset_mhz  = float(r.get("offset") or 0),
        tone        = str(r.get("color_code") or r.get("tone") or "")[:12],
        mode        = m.upper()[:12],
        city        = str(r.get("city") or r.get("location") or "")[:40],
        state       = str(r.get("state") or r.get("country") or "")[:20],
        distance_km = dist,
        status      = "Operational",
        use_code    = "OPEN",
        notes       = f"CC:{r.get('color_code','')} TG:{r.get('id','')}".strip()[:200],
        last_updated= "",
    )


def _radioid_parse_repeater(
        r: dict, my_lat: float, my_lon: float,
        radius_km: float, m: str) -> "Repeater | None":
    """Parse one RadioID result dict into a Repeater, or None if out-of-range."""
    try:
        rlat = float(r.get("lat") or r.get("latitude") or 0)
        rlon = float(r.get("lon") or r.get("longitude") or 0)
        if not rlat and not rlon:
            return None
        dist = _haversine(my_lat, my_lon, rlat, rlon)
        if dist > radius_km:
            return None
        freq = float(r.get("frequency") or r.get("output") or 0)
        if not freq:
            return None
        return _radioid_build_repeater(r, m, dist)
    except Exception:
        return None


def _radioid_nearest(lat: float, lon: float,
                     radius_km: float = 50.0,
                     mode: str = "dmr") -> list["Repeater"]:
    """Fetch digital repeaters from radioid.net (free, no token).
    Covers DMR, P25, NXDN, D-STAR.  Returns Repeater list sorted by distance."""
    try:
        import requests
    except ImportError:
        return []

    _rate_limit()
    try:
        from core.netlog import record_connection
        record_connection("radioid.net",
                          purpose=f"digital repeater search ({mode})",
                          user_initiated=True)
    except Exception:
        pass

    m = mode.lower().replace("-", "").replace(" ", "")
    url = RADIOID_DMR if m in ("dmr", "mototrbo") else (
          RADIOID_P25 if m in ("p25", "apco25") else RADIOID_DMR)

    try:
        resp = requests.get(
            url,
            params={"lat": round(lat, 4), "lon": round(lon, 4),
                    "range": min(int(radius_km), 200), "distance": "km"},
            headers={"User-Agent": RADIOID_UA},
            timeout=15)
        if resp.status_code != 200:
            log.debug(f"RadioID returned HTTP {resp.status_code}")
            return []
        data = resp.json()
    except Exception as e:
        log.debug(f"RadioID fetch: {e}")
        return []

    rows = data if isinstance(data, list) else data.get("results", data.get("repeaters", []))
    results = [r for r in
               (_radioid_parse_repeater(row, lat, lon, radius_km, m) for row in rows)
               if r is not None]
    results.sort(key=lambda r: r.distance_km)
    log.info(f"RadioID: {len(results)} {m.upper()} repeaters within {radius_km:.0f} km")
    return results
