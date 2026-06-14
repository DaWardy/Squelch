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
Squelch -- digital/op25_bridge.py
OP25 integration for Linux (Osmocom OP25 project).
OP25 is a GNU Radio-based P25 decoder.
On Windows, DSD+ is used instead.
GitHub: github.com/osmocom/op25

OP25 HTTP API runs on localhost:8080 when active.
We poll it for decoded talkgroup/call info.
"""

import sys
import time
import logging
from core.constants import PORT_DUMP1090_HTTP
import threading
from typing import Callable
from dataclasses import dataclass

log = logging.getLogger(__name__)

IS_LINUX = sys.platform.startswith("linux")


@dataclass
class OP25Status:
    """Current OP25 decode status."""
    running:      bool   = False
    talkgroup:    str    = ""
    source_id:    str    = ""
    freq_hz:      int    = 0
    system_name:  str    = ""
    encrypted:    bool   = False
    error_rate:   float  = 0.0
    last_updated: float  = 0.0


class OP25Bridge:
    """
    Bridge to OP25 P25 decoder on Linux.
    OP25 runs as a separate process; we poll its HTTP API.
    On Windows, DSD+ is used instead — see dsdplus.py.
    """

    OP25_API = f"http://localhost:{PORT_DUMP1090_HTTP}"

    def __init__(self, config):
        self.cfg      = config
        self._status  = OP25Status()
        self._running = False
        self._thread: threading.Thread = None
        self._on_status: Callable = None
        self._on_decode: Callable = None

    def available(self) -> bool:
        """Check if OP25 HTTP API is responding."""
        if not IS_LINUX:
            return False
        try:
            import urllib.request
            urllib.request.urlopen(  # nosec B310
                f"{self.OP25_API}/status",
                timeout=1)
            return True
        except Exception:
            return False

    def start_polling(self):
        """Poll OP25 API for current decode status."""
        self._running = True
        self._thread  = threading.Thread(
            target=self._poll_loop,
            daemon=True, name="OP25Poll")
        self._thread.start()

    def stop_polling(self):
        self._running = False

    def _poll_loop(self):
        while self._running:
            try:
                self._fetch_status()
            except Exception as e:
                log.debug(f"OP25 poll: {e}")
            time.sleep(2)

    def _fetch_status(self):
        try:
            import urllib.request
            import json
            with urllib.request.urlopen(  # nosec B310
                    f"{self.OP25_API}/status",
                    timeout=2) as resp:
                raw = resp.read(100_001)
                if len(raw) > 100_000:
                    return
                data = json.loads(raw)
                self._status.running      = True
                self._status.talkgroup    = str(
                    data.get("talkgroup", ""))
                self._status.source_id    = str(
                    data.get("source", ""))
                self._status.freq_hz      = int(
                    data.get("frequency", 0))
                self._status.system_name  = str(
                    data.get("system", ""))
                self._status.encrypted    = bool(
                    data.get("encrypted", False))
                self._status.error_rate   = float(
                    data.get("ber", 0.0))
                self._status.last_updated = time.time()
                if self._on_status:
                    self._on_status(self._status)
        except Exception:
            self._status.running = False

    @property
    def status(self) -> OP25Status:
        return self._status

    def on_status(self, cb: Callable):
        self._on_status = cb

    def on_decode(self, cb: Callable):
        self._on_decode = cb
