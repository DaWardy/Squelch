from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- network/pskreporter.py
PSKReporter.info spot submission.
Submits FT8/FT4/WSPR reception reports to the
PSKReporter network for propagation tracking.

PSKReporter API:
  https://pskreporter.info/pskdev.html
  UDP port 14739 or HTTPS POST
"""
from core.constants import APP_VERSION

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

log = logging.getLogger(__name__)

PSKREPORTER_HOST = "report.pskreporter.info"
PSKREPORTER_PORT = 14739
PSKREPORTER_HTTP = "https://www.pskreporter.info/cgi-bin/pskrepsubmit.cgi"

# Send no more often than every 5 minutes
SUBMIT_INTERVAL_S = 300
MAX_SPOTS_PER_REPORT = 200


@dataclass
class ReceptionReport:
    """A single station heard — for PSKReporter."""
    dx_call:    str           # who was heard
    freq_hz:    int           # frequency in Hz
    mode:       str           # FT8 / FT4 / WSPR / JS8
    snr_db:     int   = -99   # signal/noise ratio dB
    dt_s:       float = 0.0   # time offset seconds
    grid:       str   = ""    # DX station grid square
    timestamp:  float = 0.0   # when heard (epoch UTC)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


class PSKReporter:
    """
    Submits FT8/FT4/WSPR reception reports to PSKReporter.
    Reports are batched and submitted every 5 minutes.
    This builds propagation maps showing where your signal
    is heard worldwide.
    """

    def __init__(self, config):
        self.cfg         = config
        self._pending:   list[ReceptionReport] = []
        self._lock       = threading.Lock()
        self._timer      = None
        self._running    = False
        self._last_submit= 0.0
        self._on_submit: Callable = None

    def start(self):
        """Start the periodic submission loop."""
        if self._running:
            return
        self._running = True
        self._schedule_next()
        log.info("PSKReporter submission started")

    def stop(self):
        self._running = False
        if self._timer:
            self._timer.cancel()

    def add_spot(self, report: ReceptionReport):
        """Add a reception report to the pending queue."""
        if not self.cfg.get(
                "spotting.pskreporter_enabled", True):
            return
        with self._lock:
            # Deduplicate: keep only latest per dx_call/mode
            self._pending = [
                r for r in self._pending
                if not (r.dx_call == report.dx_call and
                        r.mode   == report.mode)]
            self._pending.append(report)
            if len(self._pending) > MAX_SPOTS_PER_REPORT:
                self._pending = self._pending[
                    -MAX_SPOTS_PER_REPORT:]

    def add_from_wsjt_decode(self, decode):
        """
        Add a reception report from a WSJT-X decode.
        decode should have: callsign, freq_hz, mode,
        snr, dt, grid attributes.
        """
        try:
            report = ReceptionReport(
                dx_call   = decode.callsign.upper(),
                freq_hz   = int(decode.freq_hz),
                mode      = decode.mode or "FT8",
                snr_db    = int(decode.snr),
                dt_s      = float(decode.dt),
                grid      = decode.grid or "",
                timestamp = time.time(),
            )
            self.add_spot(report)
        except Exception as e:
            log.debug(f"PSKReporter add: {e}")

    def submit_now(self) -> bool:
        """Submit all pending spots immediately."""
        with self._lock:
            if not self._pending:
                return True
            spots = list(self._pending)

        success = self._submit_http(spots)
        if success:
            with self._lock:
                # Remove submitted spots
                submitted_calls = {s.dx_call for s in spots}
                self._pending = [
                    r for r in self._pending
                    if r.dx_call not in submitted_calls]
            self._last_submit = time.time()

        if self._on_submit:
            try:
                self._on_submit(
                    len(spots), success)
            except Exception:
                pass

        return success

    def _schedule_next(self):
        """Schedule next submission."""
        if not self._running:
            return
        elapsed  = time.time() - self._last_submit
        wait     = max(5, SUBMIT_INTERVAL_S - elapsed)
        self._timer = threading.Timer(
            wait, self._timed_submit)
        self._timer.daemon = True
        self._timer.start()

    def _timed_submit(self):
        self.submit_now()
        self._schedule_next()

    def _submit_http(self,
                     spots: list[ReceptionReport]
                     ) -> bool:
        """Submit via HTTPS POST (more reliable than UDP)."""
        try:
            import requests
            payload = self._build_xml_payload(spots)
            resp    = requests.post(
                PSKREPORTER_HTTP,
                data    = payload,
                headers = {
                    "Content-Type": "text/xml",
                    "User-Agent":   "Squelch/0.9.0"},
                timeout = 15)

            if resp.status_code in (200, 204):
                log.info(
                    f"PSKReporter: {len(spots)} spots "
                    f"submitted")
                return True
            else:
                log.warning(
                    f"PSKReporter HTTP {resp.status_code}")
                return False

        except Exception as e:
            log.warning(f"PSKReporter submit: {e}")
            return False

    def _build_xml_payload(self,
                           spots: list[ReceptionReport]
                           ) -> str:
        """Build PSKReporter XML submission payload."""
        cs   = self.cfg.callsign or "NOCALL"
        grid = self.cfg.grid or ""
        now  = int(time.time())

        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<receptionReport '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xsi:noNamespaceSchemaLocation='
            '"http://www.pskreporter.info/schema/pskr_schema.xsd"'
            '>',
            f'  <receiverInfo '
            f'callsign="{_xml_escape(cs)}" '
            f'locator="{_xml_escape(grid[:6])}" '
            f'programId="Squelch" '
            f'version="{APP_VERSION.split("-")[0]}"/>',
        ]

        for spot in spots:
            freq   = max(0, spot.freq_hz)
            ts_str = _utc_str(spot.timestamp)
            lines.append(
                f'  <receptionReport '
                f'callsign="{_xml_escape(spot.dx_call)}" '
                f'locator="{_xml_escape(spot.grid[:6])}" '
                f'frequency="{freq}" '
                f'mode="{_xml_escape(spot.mode)}" '
                f'sNR="{spot.snr_db}" '
                f'iMSec="0" '
                f'receiverCallsign="{_xml_escape(cs)}" '
                f'receiverLocator="{_xml_escape(grid[:6])}" '
                f'flowStartSeconds="{int(spot.timestamp)}" '
                f'/>')

        lines.append('</receptionReport>')
        return "\n".join(lines)

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    def on_submit(self, cb: Callable):
        self._on_submit = cb


def _xml_escape(s: str) -> str:
    """Escape special XML characters."""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&apos;"))


def _utc_str(timestamp: float) -> str:
    """Format epoch timestamp as UTC string."""
    import datetime
    dt = datetime.datetime.fromtimestamp(
        timestamp,
        tz=datetime.timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Inbound query — who is hearing my transmissions ───────────────────────

def fetch_hearing_me(callsign: str,
                     seconds: int = 900) -> list[dict]:
    """Query PSKReporter for stations that recently received our signal.

    Returns a list of dicts with keys: callsign, grid, freq_hz, mode, snr, ts
    Source: retrieve.pskreporter.info (public, no key, ~15-min resolution)

    Typical use: called from the Map tab on a 5-minute timer to pin
    spots on the "heard stations" layer as ORANGE triangles (distinct
    from green "stations we heard" dots).
    """
    import xml.etree.ElementTree as ET
    import requests
    import logging
    log = logging.getLogger(__name__)
    url = "https://retrieve.pskreporter.info/query"
    params = {
        "senderCallsign":  callsign.upper(),
        "flowStartSeconds": str(-abs(seconds)),
        "fCallsign":        "1",
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            log.debug(f"PSKReporter query HTTP {r.status_code}")
            return []
        root = ET.fromstring(r.text)
        ns = {"p": "http://pskreporter.info/pskr"}
        spots = []
        for rx in root.findall(".//p:receptionReport", ns):
            try:
                spots.append({
                    "callsign": rx.get("receiverCallsign", ""),
                    "grid":     rx.get("receiverLocator",  ""),
                    "freq_hz":  int(rx.get("frequency", 0)),
                    "mode":     rx.get("mode", ""),
                    "snr":      float(rx.get("sNR", 0)),
                    "ts":       int(rx.get("flowStartSeconds", 0)),
                })
            except Exception:
                continue
        log.info(f"PSKReporter: {len(spots)} stations heard {callsign}")
        return spots
    except Exception as e:
        log.debug(f"PSKReporter fetch_hearing_me: {e}")
        return []
