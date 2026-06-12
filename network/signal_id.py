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

"""
Squelch -- network/signal_id.py
Signal identification via SigID Wiki and Artemis database.
Matches observed signals to known modulation types.
Used by SDR tab right-click → Identify Signal.
"""

import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

ARTEMIS_DB_URL = (
    "https://raw.githubusercontent.com/AresValley/"
    "Artemis/master/db/signals.json")
SIGID_URL = "https://www.sigidwiki.com/api.php"
ARTEMIS_LOCAL = Path("assets/artemis_signals.json")


@dataclass
class SignalMatch:
    """A potential signal identification match."""
    name:           str
    modulation:     str
    bandwidth_hz:   int
    freq_hz:        int         = 0
    description:    str         = ""
    url:            str         = ""
    category:       str         = ""   # Amateur/Military/Aviation/etc
    confidence:     float       = 0.0  # 0.0-1.0
    source:         str         = ""   # "artemis" / "sigidwiki"


class SignalIdentifier:
    """
    Identifies signals by bandwidth and frequency range.
    Uses local Artemis database + optional SigID Wiki API.
    """

    def __init__(self):
        self._db:      list[dict] = []
        self._loaded   = False
        self._lock     = threading.Lock()

    def load_db(self) -> bool:
        """Load Artemis signal database. Downloads if not cached."""
        if ARTEMIS_LOCAL.exists():
            try:
                self._db = json.loads(
                    ARTEMIS_LOCAL.read_text(
                        encoding='utf-8'))
                self._loaded = len(self._db) > 0
                log.info(
                    f"Artemis DB loaded: "
                    f"{len(self._db)} signals")
                return self._loaded
            except Exception as e:
                log.warning(f"Artemis DB load: {e}")

        return self._download_db()

    def _download_db(self) -> bool:
        if not HAS_REQUESTS:
            return False
        try:
            resp = requests.get(
                ARTEMIS_DB_URL, timeout=15)
            if len(resp.content) > 5_000_000:
                return None  # response too large
            if resp.status_code != 200:
                return False
            data = resp.json()
            ARTEMIS_LOCAL.parent.mkdir(
                parents=True, exist_ok=True)
            ARTEMIS_LOCAL.write_text(
                json.dumps(data, indent=2),
                encoding='utf-8')
            self._db    = data if isinstance(data, list) \
                          else data.get('signals', [])
            self._loaded = True
            log.info(
                f"Artemis DB downloaded: "
                f"{len(self._db)} signals")
            return True
        except Exception as e:
            log.warning(f"Artemis DB download: {e}")
            return False

    def _match_candidate(self, sig: dict, bandwidth_hz: int,
                          freq_hz: int, bw_lo: float, bw_hi: float):
        """Return a SignalMatch if sig matches, or None."""
        bw_val = self._parse_hz(str(sig.get('bandwidth', '0')))
        if bw_val <= 0 or not (bw_lo <= bw_val <= bw_hi):
            return None
        if freq_hz > 0:
            freq_lo = self._parse_hz(str(sig.get('frequency_lower', '0')))
            freq_hi = self._parse_hz(
                str(sig.get('frequency_upper', '999999999999')))
            if freq_lo > 0 and freq_hi > 0:
                if not (freq_lo <= freq_hz <= freq_hi):
                    return None
        bw_diff = abs(bw_val - bandwidth_hz) / max(bandwidth_hz, 1)
        confidence = max(0.0, 1.0 - bw_diff * 2)
        return SignalMatch(
            name         = str(sig.get('name', 'Unknown'))[:80],
            modulation   = str(sig.get('modulation', ''))[:40],
            bandwidth_hz = int(bw_val),
            freq_hz      = freq_hz,
            description  = str(sig.get('description', ''))[:200],
            url          = str(sig.get('url', '')),
            category     = str(sig.get('category', ''))[:40],
            confidence   = confidence,
            source       = 'artemis',
        )

    def identify(self,
                  bandwidth_hz: int,
                  freq_hz: int = 0,
                  bw_tolerance: float = 0.3
                  ) -> list[SignalMatch]:
        """
        Find signals matching bandwidth and optional frequency.
        bw_tolerance: fraction above/below to match (0.3 = ±30%)
        """
        if not self._loaded:
            self.load_db()
        bw_lo = bandwidth_hz * (1 - bw_tolerance)
        bw_hi = bandwidth_hz * (1 + bw_tolerance)
        matches = []
        for sig in self._db:
            try:
                m = self._match_candidate(sig, bandwidth_hz, freq_hz,
                                          bw_lo, bw_hi)
                if m is not None:
                    matches.append(m)
            except Exception:
                continue
        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches[:10]

    def identify_async(self,
                        bandwidth_hz: int,
                        freq_hz: int,
                        callback: Callable):
        """Non-blocking identification."""
        def _do():
            results = self.identify(bandwidth_hz, freq_hz)
            try:
                callback(results)
            except Exception as e:
                log.debug(f"Signal ID callback: {e}")
        threading.Thread(target=_do, daemon=True).start()

    def update_db(self, callback: Callable = None):
        """Re-download Artemis database in background."""
        def _do():
            ok = self._download_db()
            if callback:
                try:
                    callback(ok, len(self._db))
                except Exception:
                    pass
        threading.Thread(target=_do, daemon=True).start()

    @staticmethod
    def _parse_hz(value: str) -> float:
        """Parse frequency/bandwidth string to Hz."""
        try:
            v = str(value).strip().upper()
            v = v.replace(',', '').replace(' ', '')
            if v.endswith('GHZ'):
                return float(v[:-3]) * 1e9
            if v.endswith('MHZ'):
                return float(v[:-3]) * 1e6
            if v.endswith('KHZ'):
                return float(v[:-3]) * 1e3
            if v.endswith('HZ'):
                return float(v[:-2])
            return float(v)
        except (ValueError, TypeError):
            return 0.0

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def signal_count(self) -> int:
        return len(self._db)


# Module singleton
_identifier: SignalIdentifier = None

def get_identifier() -> SignalIdentifier:
    global _identifier
    if _identifier is None:
        _identifier = SignalIdentifier()
    return _identifier