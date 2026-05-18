# APEX — Amateur Platform for EXperimentation
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
"""APEX -- network/cty_data.py
CTY.DAT country file parser (AD1C format).
Maps callsign prefixes to DXCC entities, CQ zones, ITU zones.
Bundled copy updated periodically from:
  https://www.country-files.com/cty/cty.dat
"""

import re
import logging
import requests
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

CTY_LOCAL  = Path("assets/cty.dat")
CTY_URL    = "https://www.country-files.com/cty/cty.dat"
CTY_BACKUP = "https://ad1c.us/contest/cty.dat"


@dataclass
class DXCCEntity:
    name:       str
    cq_zone:    int
    itu_zone:   int
    continent:  str
    lat:        float
    lon:        float
    utc_offset: float
    prefix:     str
    deleted:    bool = False


class CTYData:
    """
    Parses CTY.DAT and provides fast DXCC lookups.
    Lookup priority: exact prefix → longest match → best guess
    """

    def __init__(self):
        self._entities:  dict[str, DXCCEntity] = {}
        self._prefixes:  dict[str, str] = {}   # prefix → entity name
        self._loaded     = False

    def load(self) -> bool:
        """Load CTY.DAT from local file or download if missing."""
        if CTY_LOCAL.exists():
            return self._parse(CTY_LOCAL.read_text(encoding="utf-8",
                                                    errors="replace"))
        log.info("CTY.DAT not found locally — downloading")
        return self.update()

    def update(self) -> bool:
        """Download latest CTY.DAT from country-files.com."""
        for url in (CTY_URL, CTY_BACKUP):
            try:
                resp = requests.get(url, timeout=15)
                if len(resp.content) > 2_000_000:
                    return None  # response too large
                if resp.status_code == 200:
                    CTY_LOCAL.parent.mkdir(parents=True, exist_ok=True)
                    CTY_LOCAL.write_text(resp.text, encoding="utf-8")
                    log.info(f"CTY.DAT downloaded from {url}")
                    return self._parse(resp.text)
            except Exception as e:
                log.warning(f"CTY.DAT download from {url} failed: {e}")
        log.error("Could not load CTY.DAT from any source")
        return False

    def _parse(self, content: str) -> bool:
        """Parse CTY.DAT format into lookup tables."""
        self._entities.clear()
        self._prefixes.clear()

        lines = content.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.startswith('#'):
                i += 1
                continue

            # Entity header line ends with ':'
            if line.endswith(':') or (i+1 < len(lines) and
                                       not lines[i].startswith(' ')):
                parts = line.rstrip(':').split(':')
                if len(parts) >= 9:
                    try:
                        entity = DXCCEntity(
                            name      = parts[0].strip(),
                            cq_zone   = int(parts[1].strip()),
                            itu_zone  = int(parts[2].strip()),
                            continent = parts[3].strip(),
                            lat       = float(parts[4].strip()),
                            lon       = float(parts[5].strip()),
                            utc_offset= float(parts[6].strip()),
                            prefix    = parts[7].strip(),
                        )
                        self._entities[entity.name] = entity

                        # Collect prefix aliases from following lines
                        i += 1
                        prefix_str = ""
                        while i < len(lines):
                            pline = lines[i].strip()
                            if not pline:
                                i += 1
                                break
                            if (pline.endswith(':') or
                                    (not lines[i].startswith(' ') and
                                     ':' in pline)):
                                break
                            prefix_str += pline.rstrip(';').rstrip(',')
                            if pline.endswith(';'):
                                i += 1
                                break
                            i += 1

                        # Parse individual prefixes
                        for raw in prefix_str.split(','):
                            raw = raw.strip()
                            if not raw:
                                continue
                            # Strip modifiers like (14) for CQ zone overrides
                            prefix = re.sub(r'[\(\[<][^\)\]>]*[\)\]>]', '',
                                            raw).strip().upper()
                            if prefix.startswith('='):
                                prefix = prefix[1:]  # exact match marker
                            if prefix:
                                self._prefixes[prefix] = entity.name

                        continue
                    except (ValueError, IndexError) as e:
                        log.debug(f"CTY parse error line {i}: {e}")
            i += 1

        self._loaded = len(self._entities) > 0
        log.info(f"CTY.DAT loaded: {len(self._entities)} entities, "
                 f"{len(self._prefixes)} prefixes")
        return self._loaded

    def lookup(self, callsign: str) -> DXCCEntity | None:
        """
        Look up a callsign and return its DXCC entity.
        Uses longest prefix match.
        """
        if not self._loaded:
            return None

        call = callsign.upper().strip()

        # Try progressively shorter prefixes
        for length in range(len(call), 0, -1):
            prefix = call[:length]
            if prefix in self._prefixes:
                entity_name = self._prefixes[prefix]
                return self._entities.get(entity_name)

        return None

    def dxcc_name(self, callsign: str) -> str:
        entity = self.lookup(callsign)
        return entity.name if entity else ""

    def cq_zone(self, callsign: str) -> int:
        entity = self.lookup(callsign)
        return entity.cq_zone if entity else 0

    def itu_zone(self, callsign: str) -> int:
        entity = self.lookup(callsign)
        return entity.itu_zone if entity else 0

    def continent(self, callsign: str) -> str:
        entity = self.lookup(callsign)
        return entity.continent if entity else ""

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def entity_count(self) -> int:
        return len(self._entities)


# Module-level singleton
_cty: CTYData | None = None

def get_cty() -> CTYData:
    global _cty
    if _cty is None:
        _cty = CTYData()
        _cty.load()
    return _cty
