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
"""Squelch -- network/dx_cluster.py
DX cluster and alerting API integrations:
  - PSKReporter (spot feed)
  - DX Watch / DX Summit (cluster spots)
  - HamAlert (push alerts)
  - RBN (Reverse Beacon Network - CW/RTTY)
  - ClubLog (log sync)
"""

import logging
import threading
import time
import requests
from dataclasses import dataclass, field
from typing import Optional, Callable
from datetime import datetime, timezone

from core.validator import (
    callsign_soft, api_callsign, api_string,
    api_int, api_float)

log = logging.getLogger(__name__)

# API endpoints
PSKREPORTER_URL  = "https://retrieve.pskreporter.info/query"
DXWATCH_URL      = "https://dxwatch.com/dxsd1/s.php"
DXSUMMIT_URL     = "https://www.dxsummit.fi/api/v1/spots"
HAMALERT_URL     = "https://hamalert.org/api"
RBN_URL          = "https://www.reversebeacon.net/api/spots/dx"
CLUBLOG_URL      = "https://clublog.org/realtime.php"

# Rate limits
PSKREPORTER_INTERVAL = 120   # 2 min minimum
DXWATCH_INTERVAL     = 60
HAMALERT_INTERVAL    = 30
RBN_INTERVAL         = 60


@dataclass
class DXSpot:
    """A single DX cluster or beacon spot."""
    callsign:    str
    freq_hz:     int
    spotter:     str       = ""
    mode:        str       = ""
    snr:         int       = 0
    comment:     str       = ""
    dxcc:        str       = ""
    country:     str       = ""
    band:        str       = ""
    source:      str       = ""   # pskreporter/dxwatch/rbn/hamalert
    timestamp:   float     = field(default_factory=time.time)
    distance_km: float     = 0.0
    bearing_deg: float     = 0.0
    is_new_dxcc: bool      = False
    is_wanted:   bool      = False

    @property
    def age_minutes(self) -> float:
        return (time.time() - self.timestamp) / 60

    @property
    def display_freq(self) -> str:
        return f"{self.freq_hz/1e6:.4f}"

    @property
    def display_time(self) -> str:
        return datetime.fromtimestamp(
            self.timestamp, tz=timezone.utc
        ).strftime("%H:%M")


class PSKReporterClient:
    """
    PSKReporter API client.
    Fetches spots for your callsign — who hears you and who you hear.
    """

    def __init__(self, config):
        self.cfg = config
        self._last_fetch = 0.0
        self._spots_rx: list[DXSpot] = []  # who hears you
        self._spots_tx: list[DXSpot] = []  # who you hear
        self._on_update: Callable | None = None

    def fetch(self, callsign: str, band: str = "",
              mode: str = "") -> bool:
        """
        Fetch recent spots for callsign.
        Returns True if new data received.
        Rate-limited to once per 2 minutes.
        """
        now = time.time()
        if now - self._last_fetch < PSKREPORTER_INTERVAL:
            return False

        try:
            cs = callsign_soft(callsign)
            params = {
                "senderCallsign": cs,
                "rrOnly":         1,
                "flowStartSeconds": -900,  # last 15 min
                "noactive":       1,
                "noplot":         1,
            }
            if band:
                params["frange"] = self._band_to_freq_range(band)

            resp = requests.get(
                PSKREPORTER_URL,
                params=params,
                timeout=10,
                headers={"User-Agent": "APEX/1.0 github.com/dawardy/squelch"})
            if len(resp.content) > 100_000:
                return None  # response too large
            if resp.status_code == 200:
                self._parse_pskreporter(resp.json(), cs)
                self._last_fetch = now
                if self._on_update:
                    self._on_update(self._spots_rx, self._spots_tx)
                return True

        except requests.exceptions.Timeout:
            log.warning("PSKReporter timeout")
        except Exception as e:
            log.warning(f"PSKReporter fetch failed: {e}")
        return False

    def fetch_async(self, callsign: str, band: str = "",
                    mode: str = ""):
        """Non-blocking version of fetch()."""
        threading.Thread(
            target=self.fetch,
            args=(callsign, band, mode),
            daemon=True).start()

    def _parse_pskreporter(self, data: dict, my_call: str):
        """Parse PSKReporter JSON response."""
        try:
            receptions = data.get("receptionReport", [])
            self._spots_rx = []
            self._spots_tx = []

            for r in receptions:
                try:
                    spot = DXSpot(
                        callsign  = api_callsign(
                            r.get("senderCallsign", "")),
                        freq_hz   = api_int(
                            r.get("frequency", 0),
                            min_val=0, max_val=450_000_000),
                        spotter   = api_callsign(
                            r.get("receiverCallsign", "")),
                        mode      = api_string(
                            r.get("mode", ""), max_length=20),
                        snr       = api_int(
                            r.get("sNR", 0),
                            min_val=-40, max_val=40),
                        source    = "pskreporter",
                        timestamp = self._parse_timestamp(
                            r.get("flowStartSeconds", 0)),
                    )
                    if not spot.callsign:
                        continue

                    if spot.spotter.upper() == my_call.upper():
                        self._spots_tx.append(spot)
                    else:
                        self._spots_rx.append(spot)
                except Exception:
                    continue

        except Exception as e:
            log.warning(f"PSKReporter parse error: {e}")

    @staticmethod
    def _parse_timestamp(val) -> float:
        try:
            return float(val)
        except Exception:
            return time.time()

    @staticmethod
    def _band_to_freq_range(band: str) -> str:
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
        return ranges.get(band, "")

    @property
    def spots_rx(self) -> list[DXSpot]:
        return list(self._spots_rx)

    @property
    def spots_tx(self) -> list[DXSpot]:
        return list(self._spots_tx)

    def on_update(self, cb: Callable):
        self._on_update = cb


class DXClusterClient:
    """
    DX Watch and DX Summit cluster spot feed.
    Shows who is on the air on what band right now.
    """

    def __init__(self, config):
        self.cfg = config
        self._spots: list[DXSpot] = []
        self._last_fetch = 0.0
        self._on_spot: Callable | None = None

    def fetch(self, band: str = "", mode: str = "",
              limit: int = 50) -> list[DXSpot]:
        now = time.time()
        if now - self._last_fetch < DXWATCH_INTERVAL:
            return self._spots

        try:
            # Try DX Summit first (more reliable API)
            params = {"limit": limit}
            if band:
                params["band"] = band.replace("m", "")
            if mode:
                params["mode"] = mode

            resp = requests.get(
                DXSUMMIT_URL,
                params=params,
                timeout=8,
                headers={"User-Agent": "Squelch/1.0"})
            if len(resp.content) > 100_000:
                return None  # response too large
            if resp.status_code == 200:
                spots = self._parse_dxsummit(resp.json())
                self._spots = spots
                self._last_fetch = now
                return spots

        except Exception as e:
            log.debug(f"DX Summit fetch: {e}")

        return self._spots

    def fetch_async(self, band: str = "", mode: str = ""):
        threading.Thread(
            target=self.fetch,
            args=(band, mode),
            daemon=True).start()

    def _parse_dxsummit(self, data) -> list[DXSpot]:
        spots = []
        if not isinstance(data, list):
            return spots
        for item in data[:100]:  # cap at 100
            try:
                spot = DXSpot(
                    callsign = api_callsign(
                        item.get("dx", "")),
                    freq_hz  = int(float(
                        item.get("frequency", 0)) * 1000),
                    spotter  = api_callsign(
                        item.get("spotter", "")),
                    mode     = api_string(
                        item.get("mode", ""), max_length=10),
                    comment  = api_string(
                        item.get("comment", ""), max_length=60),
                    source   = "dxsummit",
                )
                if spot.callsign and spot.freq_hz > 0:
                    spots.append(spot)
            except Exception:
                continue
        return spots

    def on_spot(self, cb: Callable):
        self._on_spot = cb


    def start(self, band: str = "", mode: str = ""):
        """Start periodic DX spot polling (mirrors HamAlertClient API)."""
        import threading
        self._poll_band = band
        self._poll_mode = mode
        self._running   = True
        self._thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="DXClusterPoll")
        self._thread.start()
        log.info("DX Cluster polling started")

    def stop(self):
        """Stop periodic polling."""
        self._running = False

    def _poll_loop(self):
        import time
        while self._running:
            try:
                self.fetch_async(
                    band=self._poll_band,
                    mode=self._poll_mode)
            except Exception as e:
                log.debug(f"DX Cluster poll: {e}")
            time.sleep(120)   # poll every 2 minutes


class HamAlertClient:
    """
    HamAlert push alert client.
    Monitors DX cluster, PSKReporter, SOTA, POTA for
    user-defined targets and fires notifications.
    Requires free HamAlert account and API key.
    """

    def __init__(self, config):
        self.cfg       = config
        self._alerts:  list[dict] = []
        self._last_id: int        = 0
        self._running: bool       = False
        self._thread:  threading.Thread | None = None
        self._on_alert: Callable | None        = None
        self._wantlist: list[str]                  = []

    def start(self):
        key = self.cfg.get("apis.hamalert_key", "")
        if not key:
            log.info("HamAlert: no API key configured")
            return
        self._running = True
        self._thread  = threading.Thread(
            target=self._poll_loop,
            daemon=True, name="HamAlertPoll")
        self._thread.start()
        log.info("HamAlert polling started")

    def stop(self):
        self._running = False

    def set_wantlist(self, entities: list[str]):
        """Set DXCC entities to watch for."""
        self._wantlist = [e.upper().strip() for e in entities]

    def _poll_loop(self):
        while self._running:
            try:
                self._fetch_alerts()
            except Exception as e:
                log.debug(f"HamAlert poll: {e}")
            time.sleep(HAMALERT_INTERVAL)

    def _fetch_alerts(self):
        key = self.cfg.get("apis.hamalert_key", "")
        if not key:
            return

        try:
            resp = requests.get(
                f"{HAMALERT_URL}/spots",
                headers={
                    "Authorization": f"Bearer {key}",
                    "User-Agent": "Squelch/1.0",
                },
                params={"since_id": self._last_id},
                timeout=8)
            if len(resp.content) > 100_000:
                return None  # response too large
            if resp.status_code == 200:
                data = resp.json()
                alerts = data if isinstance(data, list) else \
                         data.get("spots", [])

                for alert in alerts:
                    try:
                        self._process_alert(alert)
                    except Exception:
                        continue

            elif resp.status_code == 401:
                log.warning(
                    "HamAlert: invalid API key")
                self._running = False

        except requests.exceptions.Timeout:
            log.debug("HamAlert timeout")
        except Exception as e:
            log.debug(f"HamAlert fetch: {e}")

    def _process_alert(self, alert: dict):
        spot = DXSpot(
            callsign = api_callsign(
                alert.get("callsign", "")),
            freq_hz  = api_int(
                float(alert.get("frequency", 0)) * 1000,
                min_val=0, max_val=450_000_000),
            mode     = api_string(
                alert.get("mode", ""), max_length=10),
            comment  = api_string(
                alert.get("comment", ""), max_length=100),
            dxcc     = api_string(
                alert.get("dxcc", ""), max_length=50),
            country  = api_string(
                alert.get("entity", ""), max_length=60),
            source   = "hamalert",
        )
        if not spot.callsign:
            return

        spot.is_wanted = (
            spot.dxcc.upper() in self._wantlist or
            spot.country.upper() in self._wantlist)

        alert_id = api_int(
            alert.get("id", 0), min_val=0)
        if alert_id > self._last_id:
            self._last_id = alert_id

        self._alerts.append(alert.__class__.__new__(
            alert.__class__))
        # Keep last 100 alerts
        self._alerts = self._alerts[-100:]

        if self._on_alert:
            self._on_alert(spot)

    def on_alert(self, cb: Callable):
        self._on_alert = cb

    @property
    def has_key(self) -> bool:
        return bool(self.cfg.get("apis.hamalert_key", ""))


class RBNClient:
    """
    Reverse Beacon Network client.
    Shows CW and RTTY spots — who the skimmer network
    is hearing you at what SNR.
    Active when CW or RTTY mode is selected.
    """

    def __init__(self, config):
        self.cfg       = config
        self._spots:   list[DXSpot] = []
        self._last_fetch = 0.0
        self._on_spot: Callable | None = None

    def fetch(self, callsign: str,
              mode: str = "CW") -> list[DXSpot]:
        now = time.time()
        if now - self._last_fetch < RBN_INTERVAL:
            return self._spots

        try:
            cs = callsign_soft(callsign)
            resp = requests.get(
                RBN_URL,
                params={
                    "dx":   cs,
                    "mode": "CW" if "CW" in mode.upper() else "RTTY",
                    "rows": 20,
                },
                timeout=8,
                headers={"User-Agent": "Squelch/1.0"})

            if resp.status_code == 200:
                self._spots = self._parse_rbn(resp.json())
                self._last_fetch = now

        except Exception as e:
            log.debug(f"RBN fetch: {e}")

        return self._spots

    def _parse_rbn(self, data) -> list[DXSpot]:
        spots = []
        if not isinstance(data, list):
            return spots
        for item in data[:30]:
            try:
                spot = DXSpot(
                    callsign = api_callsign(
                        item.get("dx", "")),
                    freq_hz  = int(float(
                        item.get("freq", 0)) * 1000),
                    spotter  = api_callsign(
                        item.get("callsign", "")),
                    snr      = api_int(
                        item.get("db", 0),
                        min_val=-10, max_val=60),
                    mode     = api_string(
                        item.get("mode", "CW"), max_length=10),
                    source   = "rbn",
                )
                if spot.callsign and spot.freq_hz > 0:
                    spots.append(spot)
            except Exception:
                continue
        return spots

    def fetch_async(self, callsign: str, mode: str = "CW"):
        threading.Thread(
            target=self.fetch,
            args=(callsign, mode),
            daemon=True).start()

    def on_spot(self, cb: Callable):
        self._on_spot = cb


class ClubLogClient:
    """
    ClubLog API client.
    Upload QSOs, check DXCC standings, fetch confirmation status.
    """

    BASE = "https://clublog.org/realtime.php"

    def __init__(self, config):
        self.cfg = config

    def _password(self) -> str:
        try:
            from core.credentials import get_store
            return get_store(
                self.cfg.get("profile.name", "default")
            ).retrieve("clublog_password")
        except Exception:
            return ""

    @property
    def has_credentials(self) -> bool:
        email    = self.cfg.get("apis.clublog_email", "")
        callsign = self.cfg.callsign
        return bool(email and self._password() and callsign)

    def upload_adif(self, adif_content: str) -> bool:
        """Upload an ADIF string to ClubLog."""
        if not self.has_credentials:
            log.warning("ClubLog: no credentials configured")
            return False
        try:
            from core.netlog import record_connection
            record_connection("clublog_upload", self.BASE, "POST")
            resp = requests.post(
                self.BASE,
                data={
                    "email":    self.cfg.get("apis.clublog_email"),
                    "password": self._password(),
                    "callsign": self.cfg.callsign,
                    "adif":     adif_content,
                },
                timeout=30,
                headers={"User-Agent": "Squelch/1.0"})
            ok = resp.status_code == 200 and "OK" in resp.text
            if ok:
                log.info("ClubLog upload: OK")
            else:
                log.warning(
                    f"ClubLog upload failed: {resp.status_code}")
            return ok
        except Exception as e:
            log.warning(f"ClubLog upload error: {e}")
            return False
