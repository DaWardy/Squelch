# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/apex
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
"""Squelch -- network/dx_spots.py
Spot feeds: PSKReporter, RBN, DX Watch, HamAlert.
All responses validated before use — no injection possible.
"""

import time
import logging
import threading
import requests
from dataclasses import dataclass, field
from typing import Optional, Callable
from core.validator import api_string, api_callsign, api_float, api_int

log = logging.getLogger(__name__)

PSKREPORTER_URL = "https://retrieve.pskreporter.info/query"
RBNHOLE_URL     = "https://www.reversebeacon.net/api/spots/15"
DXWATCH_URL     = "https://dxwatch.com/dxsd1/s.php"
HAMALERT_URL    = "https://hamalert.org/api/spots"

REQUEST_TIMEOUT = 10
MAX_RESPONSE_BYTES = 512_000   # 512 KB max response


@dataclass
class Spot:
    """A single DX spot from any source."""
    callsign:    str
    freq_hz:     int
    mode:        str
    snr:         int
    spotter:     str
    grid:        str
    dxcc:        str
    country:     str
    cq_zone:     int
    distance_km: float
    bearing_deg: float
    source:      str       # "pskreporter" / "rbn" / "dxwatch" / "hamalert"
    timestamp:   float     = field(default_factory=time.time)
    band:        str       = ""
    comment:     str       = ""
    is_hearing_me: bool    = False
    i_am_hearing:  bool    = False

    @property
    def age_seconds(self) -> float:
        return time.time() - self.timestamp

    @property
    def display_freq(self) -> str:
        return f"{self.freq_hz/1e6:.4f}"


class SpotFeed:
    """
    Aggregates spots from multiple sources.
    Fires callbacks when new spots arrive.
    Filters by band/mode automatically.
    """

    def __init__(self, config):
        self.cfg      = config
        self._spots:  list[Spot] = []
        self._lock    = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

        self._band:   str = "20m"
        self._mode:   str = "FT8"
        self._my_call: str = ""

        self._on_spot:  Callable | None = None
        self._on_alert: Callable | None = None

        # HamAlert wantlist
        self._wantlist: set[str] = set()

    # ── Public API ────────────────────────────────────────────────────────

    def start(self, band: str, mode: str):
        self._band    = band
        self._mode    = mode
        self._my_call = self.cfg.callsign.upper()
        self._running = True
        self._thread  = threading.Thread(
            target=self._run, daemon=True, name="SpotFeed")
        self._thread.start()

    def stop(self):
        self._running = False

    def set_filter(self, band: str, mode: str):
        self._band = band
        self._mode = mode

    def set_wantlist(self, dxcc_list: list[str]):
        self._wantlist = {d.upper() for d in dxcc_list}

    @property
    def spots(self) -> list[Spot]:
        with self._lock:
            # Return spots less than 15 minutes old
            cutoff = time.time() - 900
            return [s for s in self._spots if s.timestamp > cutoff]

    def hearing_me(self) -> list[Spot]:
        return [s for s in self.spots if s.is_hearing_me]

    def i_am_hearing(self) -> list[Spot]:
        return [s for s in self.spots if s.i_am_hearing]

    def on_spot(self, cb: Callable):
        self._on_spot = cb

    def on_alert(self, cb: Callable):
        self._on_alert = cb

    # ── Poll loop ─────────────────────────────────────────────────────────

    def _run(self):
        while self._running:
            try:
                self._poll_pskreporter()
            except Exception as e:
                log.debug(f"PSKReporter poll: {e}")
            try:
                if self._mode in ("CW", "RTTY"):
                    self._poll_rbn()
            except Exception as e:
                log.debug(f"RBN poll: {e}")
            try:
                self._poll_dxwatch()
            except Exception as e:
                log.debug(f"DXWatch poll: {e}")
            try:
                if self.cfg.get("apis.hamalert_key"):
                    self._poll_hamalert()
            except Exception as e:
                log.debug(f"HamAlert poll: {e}")

            # PSKReporter rate limit — poll every 2 minutes
            for _ in range(120):
                if not self._running:
                    return
                time.sleep(1)

    # ── PSKReporter ───────────────────────────────────────────────────────

    def _poll_pskreporter(self):
        if not self._my_call:
            return

        params = {
            "senderCallsign": self._my_call,
            "mode":           self._mode,
            "lastNMinutes":   15,
            "frange":         self._band_to_frange(self._band),
            "rronly":         1,
        }
        resp = self._get(PSKREPORTER_URL, params)
        if not resp:
            return

        data = self._safe_json(resp)
        if not data:
            return

        new_spots = []
        for rx in data.get("receptionReport", []):
            try:
                spot = Spot(
                    callsign    = api_callsign(rx.get("senderCallsign")),
                    freq_hz     = api_int(rx.get("frequency"), 0),
                    mode        = api_string(rx.get("mode"), 10),
                    snr         = api_int(rx.get("sNR"), 0, -30, 30),
                    spotter     = api_callsign(rx.get("receiverCallsign")),
                    grid        = api_string(rx.get("senderLocator"), 8),
                    dxcc        = api_string(rx.get("DXCC"), 50),
                    country     = api_string(rx.get("country"), 50),
                    cq_zone     = api_int(rx.get("cqZone"), 0),
                    distance_km = api_float(rx.get("distance"), 0),
                    bearing_deg = api_float(rx.get("azimuth"), 0),
                    source      = "pskreporter",
                    band        = self._band,
                )
                if not spot.callsign:
                    continue
                # Flag direction
                spot.is_hearing_me = (
                    spot.callsign == self._my_call)
                spot.i_am_hearing  = (
                    spot.spotter == self._my_call)
                new_spots.append(spot)
            except Exception as e:
                log.debug(f"PSKReporter spot parse: {e}")

        self._add_spots(new_spots)

        # Also query who we're hearing
        params2 = dict(params)
        params2["receiverCallsign"] = self._my_call
        del params2["senderCallsign"]
        resp2 = self._get(PSKREPORTER_URL, params2)
        if resp2:
            data2 = self._safe_json(resp2)
            if data2:
                for rx in data2.get("receptionReport", []):
                    try:
                        spot = Spot(
                            callsign    = api_callsign(
                                rx.get("senderCallsign")),
                            freq_hz     = api_int(
                                rx.get("frequency"), 0),
                            mode        = api_string(
                                rx.get("mode"), 10),
                            snr         = api_int(
                                rx.get("sNR"), 0, -30, 30),
                            spotter     = self._my_call,
                            grid        = api_string(
                                rx.get("senderLocator"), 8),
                            dxcc        = api_string(
                                rx.get("DXCC"), 50),
                            country     = api_string(
                                rx.get("country"), 50),
                            cq_zone     = 0,
                            distance_km = 0.0,
                            bearing_deg = 0.0,
                            source      = "pskreporter",
                            band        = self._band,
                            i_am_hearing = True,
                        )
                        if spot.callsign:
                            new_spots.append(spot)
                    except Exception:
                        pass
                self._add_spots(new_spots)

    # ── RBN ───────────────────────────────────────────────────────────────

    def _poll_rbn(self):
        if not self._my_call:
            return
        params = {"de": self._my_call, "rows": 25}
        resp = self._get(RBNHOLE_URL, params)
        if not resp:
            return
        data = self._safe_json(resp)
        if not isinstance(data, list):
            return
        new_spots = []
        for entry in data[:50]:
            try:
                spot = Spot(
                    callsign    = api_callsign(entry.get("dx")),
                    freq_hz     = int(api_float(
                        entry.get("freq"), 0) * 1000),
                    mode        = api_string(entry.get("mode"), 10),
                    snr         = api_int(entry.get("db"), 0),
                    spotter     = api_callsign(entry.get("de")),
                    grid        = "",
                    dxcc        = "",
                    country     = api_string(entry.get("country"), 50),
                    cq_zone     = 0,
                    distance_km = 0.0,
                    bearing_deg = 0.0,
                    source      = "rbn",
                    band        = self._band,
                    comment     = api_string(entry.get("comment"), 50),
                    is_hearing_me = (
                        api_callsign(entry.get("dx")) == self._my_call),
                )
                if spot.callsign:
                    new_spots.append(spot)
            except Exception as e:
                log.debug(f"RBN spot parse: {e}")
        self._add_spots(new_spots)

    # ── DX Watch ──────────────────────────────────────────────────────────

    def _poll_dxwatch(self):
        try:
            resp = self._get(DXWATCH_URL,
                             {"s": 1, "r": 25, "b": self._band})
            if not resp:
                return
            data = self._safe_json(resp)
            if not data:
                return
            new_spots = []
            for entry in (data.get("s", []) or [])[:50]:
                try:
                    spot = Spot(
                        callsign    = api_callsign(entry.get("dx")),
                        freq_hz     = int(api_float(
                            entry.get("f"), 0) * 1000),
                        mode        = api_string(entry.get("m"), 10),
                        snr         = 0,
                        spotter     = api_callsign(entry.get("de")),
                        grid        = "",
                        dxcc        = "",
                        country     = api_string(
                            entry.get("c"), 50),
                        cq_zone     = 0,
                        distance_km = 0.0,
                        bearing_deg = 0.0,
                        source      = "dxwatch",
                        band        = self._band,
                        comment     = api_string(
                            entry.get("t"), 80),
                    )
                    if spot.callsign:
                        new_spots.append(spot)
                        # Check wantlist
                        if spot.country.upper() in self._wantlist:
                            self._fire_alert(spot)
                except Exception:
                    pass
            self._add_spots(new_spots)
        except Exception as e:
            log.debug(f"DXWatch: {e}")

    # ── HamAlert ──────────────────────────────────────────────────────────

    def _poll_hamalert(self):
        key = self.cfg.get("apis.hamalert_key", "")
        if not key:
            return
        try:
            headers = {"X-API-Key": key[:200]}
            resp = requests.get(
                HAMALERT_URL,
                headers=headers,
                timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                return
            data = self._safe_json(resp)
            if not isinstance(data, list):
                return
            for entry in data[:20]:
                try:
                    spot = Spot(
                        callsign    = api_callsign(
                            entry.get("callsign")),
                        freq_hz     = api_int(
                            entry.get("frequency"), 0),
                        mode        = api_string(
                            entry.get("mode"), 10),
                        snr         = api_int(
                            entry.get("snr"), 0),
                        spotter     = api_callsign(
                            entry.get("spotter")),
                        grid        = api_string(
                            entry.get("grid"), 8),
                        dxcc        = api_string(
                            entry.get("dxcc"), 50),
                        country     = api_string(
                            entry.get("country"), 50),
                        cq_zone     = api_int(
                            entry.get("cqZone"), 0),
                        distance_km = 0.0,
                        bearing_deg = 0.0,
                        source      = "hamalert",
                        band        = api_string(
                            entry.get("band"), 6),
                        comment     = api_string(
                            entry.get("comment"), 100),
                    )
                    if spot.callsign:
                        self._add_spots([spot])
                        self._fire_alert(spot)
                except Exception:
                    pass
        except Exception as e:
            log.debug(f"HamAlert: {e}")

    # ── Helpers ───────────────────────────────────────────────────────────

    def _get(self, url: str, params: dict) -> requests.Response | None:
        try:
            resp = requests.get(
                url, params=params,
                timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                return None
            if len(resp.content) > MAX_RESPONSE_BYTES:
                log.warning(f"Response too large from {url}")
                return None
            return resp
        except Exception as e:
            log.debug(f"HTTP GET {url}: {e}")
            return None

    def _safe_json(self, resp: requests.Response):
        try:
            return resp.json()
        except Exception as e:
            log.debug(f"JSON parse failed: {e}")
            return None

    def _add_spots(self, new_spots: list[Spot]):
        if not new_spots:
            return
        with self._lock:
            cutoff = time.time() - 900
            self._spots = [s for s in self._spots
                           if s.timestamp > cutoff]
            self._spots.extend(new_spots)
            self._spots = self._spots[-500:]  # cap at 500

        for spot in new_spots:
            if self._on_spot:
                try:
                    self._on_spot(spot)
                except Exception as e:
                    log.debug(f"Spot callback: {e}")

    def _fire_alert(self, spot: Spot):
        if self._on_alert:
            try:
                self._on_alert(spot)
            except Exception as e:
                log.debug(f"Alert callback: {e}")

    @staticmethod
    def _band_to_frange(band: str) -> str:
        ranges = {
            "160m": "1800000-2000000",
            "80m":  "3500000-4000000",
            "40m":  "7000000-7300000",
            "30m":  "10100000-10150000",
            "20m":  "14000000-14350000",
            "17m":  "18068000-18168000",
            "15m":  "21000000-21450000",
            "12m":  "24890000-24990000",
            "10m":  "28000000-29700000",
            "6m":   "50000000-54000000",
        }
        return ranges.get(band, "14000000-14350000")
