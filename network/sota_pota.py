from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
from core.constants import APP_VERSION
Squelch -- network/sota_pota.py
SOTA (Summits on the Air) and POTA (Parks on the Air)
spot alerts for portable operation.

SOTA API: api2.sota.org.uk/api/spots/latest
POTA API: api.pota.app/spot/activator

Shows active summits/parks on the Modes tab so you can
tune to hear them or work them for award credits.
"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable

log = logging.getLogger(__name__)

SOTA_SPOTS_URL = "https://api2.sota.org.uk/api/spots/latest/9"
POTA_SPOTS_URL = "https://api.pota.app/spot/activator"
REFRESH_S      = 300   # 5 minutes

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


@dataclass
class SOTASpot:
    """A SOTA activator spot."""
    callsign:   str
    summit:     str    # summit reference e.g. W6/NS-001
    summit_name:str
    freq_mhz:   float
    mode:       str
    comment:    str    = ""
    spotter:    str    = ""
    time_utc:   str    = ""
    points:     int    = 0

    @property
    def display(self) -> str:
        return (f"{self.callsign:<10} "
                f"{self.freq_mhz:>9.4f}  "
                f"{self.mode:<5} "
                f"{self.summit:<12} "
                f"{self.summit_name[:25]}")


@dataclass
class POTASpot:
    """A POTA activator spot."""
    callsign:   str
    park:       str    # park reference e.g. K-0001
    park_name:  str
    freq_mhz:   float
    mode:       str
    comment:    str    = ""
    spotter:    str    = ""
    time_utc:   str    = ""

    @property
    def display(self) -> str:
        return (f"{self.callsign:<10} "
                f"{self.freq_mhz:>9.4f}  "
                f"{self.mode:<5} "
                f"{self.park:<10} "
                f"{self.park_name[:25]}")


class SOTAClient:
    """Fetches SOTA activator spots."""

    def __init__(self):
        self._spots:   list[SOTASpot] = []
        self._running  = False
        self._thread   = None
        self._on_spots: Callable = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(
            target=self._poll_loop,
            daemon=True, name="SOTASpots")
        self._thread.start()

    def stop(self):
        self._running = False

    @property
    def spots(self) -> list[SOTASpot]:
        return list(self._spots)

    def _poll_loop(self):
        while self._running:
            try:
                self._fetch()
            except Exception as e:
                log.debug(f"SOTA fetch: {e}")
            time.sleep(REFRESH_S)

    def _fetch(self):
        if not HAS_REQUESTS:
            return
        resp = requests.get(
            SOTA_SPOTS_URL,
            timeout=10,
            headers={"User-Agent":
                     "Squelch/0.9.0"})
        if resp.status_code != 200:
            return
        if len(resp.content) > 100_000:
            return

        raw = resp.json()
        spots = []
        for r in raw[:50]:
            try:
                freq = float(r.get("frequency", 0) or 0)
                spot = SOTASpot(
                    callsign   = str(r.get("activatorCallsign",""))[:12],
                    summit     = str(r.get("associationCode",""))
                                 + "/" + str(r.get("summitCode","")),
                    summit_name= str(r.get("summitName",""))[:40],
                    freq_mhz   = freq,
                    mode       = str(r.get("mode",""))[:10],
                    comment    = str(r.get("comments",""))[:60],
                    spotter    = str(r.get("callsign",""))[:12],
                    time_utc   = str(r.get("timeStamp",""))[:16],
                    points     = int(r.get("points", 0) or 0),
                )
                if freq > 0:
                    spots.append(spot)
            except Exception:
                pass

        self._spots = spots
        if self._on_spots:
            try:
                self._on_spots(spots)
            except Exception:
                pass

    def on_spots(self, cb: Callable):
        self._on_spots = cb


class POTAClient:
    """Fetches POTA activator spots."""

    def __init__(self):
        self._spots:   list[POTASpot] = []
        self._running  = False
        self._thread   = None
        self._on_spots: Callable = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(
            target=self._poll_loop,
            daemon=True, name="POTASpots")
        self._thread.start()

    def stop(self):
        self._running = False

    @property
    def spots(self) -> list[POTASpot]:
        return list(self._spots)

    def _poll_loop(self):
        while self._running:
            try:
                self._fetch()
            except Exception as e:
                log.debug(f"POTA fetch: {e}")
            time.sleep(REFRESH_S)

    def _fetch(self):
        if not HAS_REQUESTS:
            return
        resp = requests.get(
            POTA_SPOTS_URL,
            timeout=10,
            headers={"User-Agent":
                     "Squelch/0.9.0"})
        if resp.status_code != 200:
            return
        if len(resp.content) > 200_000:
            return

        raw = resp.json()
        spots = []
        for r in raw[:100]:
            try:
                freq = float(r.get("frequency", 0) or 0)
                spot = POTASpot(
                    callsign  = str(r.get("activator",""))[:12],
                    park      = str(r.get("reference",""))[:10],
                    park_name = str(r.get("name",""))[:40],
                    freq_mhz  = freq / 1000
                                if freq > 1000 else freq,
                    mode      = str(r.get("mode",""))[:10],
                    comment   = str(r.get("comments",""))[:60],
                    spotter   = str(r.get("spotter",""))[:12],
                    time_utc  = str(r.get("spotTime",""))[:16],
                )
                if spot.freq_mhz > 0:
                    spots.append(spot)
            except Exception:
                pass

        self._spots = spots
        if self._on_spots:
            try:
                self._on_spots(spots)
            except Exception:
                pass

    def on_spots(self, cb: Callable):
        self._on_spots = cb
