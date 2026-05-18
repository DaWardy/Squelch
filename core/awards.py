from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- core/awards.py
Amateur radio award tracking.
DXCC, WAS (Worked All States), WAZ (Worked All Zones),
WAS-CW, DXCC-CW, VUCC grid squares.
Computed from the QSO log database.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)

# US States for WAS
US_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
    "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
    "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
    "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY",
}

# CQ Zones 1-40
CQ_ZONES = set(range(1, 41))

# ITU Zones 1-90
ITU_ZONES = set(range(1, 91))


@dataclass
class AwardProgress:
    """Progress toward a specific award."""
    name:        str
    description: str
    needed:      int          # total entities needed
    worked:      int   = 0    # unique entities worked
    confirmed:   int   = 0    # LoTW/card confirmed
    entities:    set   = field(default_factory=set)
    confirmed_entities: set = field(default_factory=set)

    @property
    def pct_worked(self) -> float:
        return self.worked / self.needed * 100 if self.needed else 0

    @property
    def pct_confirmed(self) -> float:
        return self.confirmed / self.needed * 100 if self.needed else 0

    @property
    def is_complete(self) -> bool:
        return self.worked >= self.needed

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed >= self.needed

    @property
    def summary(self) -> str:
        return (f"{self.worked}/{self.needed} worked "
                f"({self.pct_worked:.0f}%), "
                f"{self.confirmed} confirmed")


class AwardTracker:
    """
    Computes award progress from the QSO log.
    All computations are done from log data in memory —
    no external API calls required.
    """

    def __init__(self, log_db):
        self._db = log_db

    def compute_all(self) -> dict[str, AwardProgress]:
        """Compute progress for all tracked awards."""
        qsos = self._db.recent_qsos(limit=99999)
        return {
            "DXCC":     self._dxcc(qsos),
            "WAS":      self._was(qsos),
            "WAZ":      self._waz(qsos),
            "VUCC":     self._vucc(qsos),
            "DXCC-CW":  self._dxcc_mode(qsos, "CW"),
            "DXCC-FT8": self._dxcc_mode(qsos, "FT8"),
            "DXCC-Phone":self._dxcc_mode(qsos,
                                          "SSB", "USB", "LSB", "AM", "FM"),
            "WAS-CW":   self._was_mode(qsos, "CW"),
            "WAS-FT8":  self._was_mode(qsos, "FT8"),
        }

    def compute_dxcc(self) -> AwardProgress:
        qsos = self._db.recent_qsos(limit=99999)
        return self._dxcc(qsos)

    def compute_was(self) -> AwardProgress:
        qsos = self._db.recent_qsos(limit=99999)
        return self._was(qsos)

    def _dxcc(self, qsos) -> AwardProgress:
        entities = set()
        confirmed = set()
        for q in qsos:
            dxcc = (getattr(q, "dxcc", "") or
                    self._prefix_to_dxcc(q.call))
            if dxcc:
                entities.add(dxcc)
                if getattr(q, "lotw_status", "") == "confirmed":
                    confirmed.add(dxcc)
        return AwardProgress(
            name        = "DXCC",
            description = "DX Century Club — 100 entities",
            needed      = 100,
            worked      = len(entities),
            confirmed   = len(confirmed),
            entities    = entities,
            confirmed_entities = confirmed)

    def _dxcc_mode(self, qsos,
                   *modes: str) -> AwardProgress:
        modes_upper = {m.upper() for m in modes}
        filtered = [q for q in qsos
                    if q.mode.upper() in modes_upper]
        result   = self._dxcc(filtered)
        mode_str = "/".join(modes[:2])
        result.name        = f"DXCC-{mode_str}"
        result.description = (
            f"DXCC on {mode_str}")
        return result

    def _was(self, qsos) -> AwardProgress:
        states = set()
        confirmed = set()
        for q in qsos:
            st = (getattr(q, "state", "") or "").upper()
            if st in US_STATES:
                states.add(st)
                if getattr(q, "lotw_status", "") == "confirmed":
                    confirmed.add(st)
        return AwardProgress(
            name        = "WAS",
            description = "Worked All States (50 states)",
            needed      = 50,
            worked      = len(states),
            confirmed   = len(confirmed),
            entities    = states,
            confirmed_entities = confirmed)

    def _was_mode(self, qsos,
                  *modes: str) -> AwardProgress:
        modes_upper = {m.upper() for m in modes}
        filtered = [q for q in qsos
                    if q.mode.upper() in modes_upper]
        result   = self._was(filtered)
        mode_str = "/".join(modes)
        result.name        = f"WAS-{mode_str}"
        result.description = f"WAS on {mode_str}"
        return result

    def _waz(self, qsos) -> AwardProgress:
        zones = set()
        for q in qsos:
            cqz = getattr(q, "cqz", 0)
            if cqz and cqz in CQ_ZONES:
                zones.add(cqz)
        return AwardProgress(
            name        = "WAZ",
            description = "Worked All Zones (40 CQ zones)",
            needed      = 40,
            worked      = len(zones),
            confirmed   = 0,
            entities    = zones)

    def _vucc(self, qsos) -> AwardProgress:
        """VUCC: Worked different 2-degree grid squares (VHF+)."""
        grids = set()
        vhf_bands = {"6m","2m","1.25m","70cm","33cm","23cm"}
        for q in qsos:
            if q.band in vhf_bands and q.grid:
                grids.add(q.grid[:4].upper())
        return AwardProgress(
            name        = "VUCC",
            description = "VHF/UHF Century Club (100 grids)",
            needed      = 100,
            worked      = len(grids),
            confirmed   = 0,
            entities    = grids)

    @staticmethod
    def _prefix_to_dxcc(callsign: str) -> str:
        """
        Very rough DXCC prefix extraction.
        Full implementation uses CTY.dat (see network/cty_data.py).
        """
        if not callsign:
            return ""
        cs = callsign.upper().split("/")[0]
        # Common prefixes
        if cs.startswith(("W","K","N","AA"-"AK"
                          if False else "W")):
            if cs[0] in "WKNA":
                return "K"   # USA
        if cs.startswith("VE") or cs.startswith("VA"):
            return "VE"  # Canada
        if cs.startswith("G") or cs.startswith("M"):
            return "G"   # England
        if cs.startswith("DL") or cs.startswith("DA"):
            return "DL"  # Germany
        if cs.startswith("F"):
            return "F"   # France
        if cs.startswith("JA"):
            return "JA"  # Japan
        # Return first 1-2 chars as rough prefix
        return cs[:2] if len(cs) >= 2 else cs
