from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- core/memory_channels.py
Radio memory channel management.
Exports to CHIRP CSV format for programming handhelds,
mobile radios, and HTs without manual entry.
Supports import from Squelch repeater searches.
"""

import csv
import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# CHIRP tone modes
TONE_MODES = {
    "":     "",          # None
    "CTCSS":"Tone",      # CTCSS TX only
    "DCS":  "DTCS",      # DCS TX only
    "T/CS": "TSQL",      # CTCSS TX+RX squelch
    "D/CS": "DTCS",      # DCS TX+RX squelch
}

# CHIRP duplex modes
DUPLEX = {
    "split":  "split",
    "+":      "+",
    "-":      "-",
    "":       "",
    "simplex":"",
}


@dataclass
class MemoryChannel:
    """A single radio memory channel."""
    number:     int
    name:       str        = ""
    freq_mhz:   float      = 0.0
    duplex:     str        = ""     # "" / "+" / "-" / "split"
    offset_mhz: float      = 0.0
    tone_mode:  str        = ""     # "" / "Tone" / "TSQL" / "DTCS"
    ctcss_tone: float      = 0.0   # e.g. 100.0 Hz
    dcs_code:   int        = 23
    rx_freq:    float      = 0.0   # for split
    mode:       str        = "FM"  # FM / NFM / AM / DV / DN
    width:      str        = "25K" # 25K / 12.5K
    power:      str        = "High"
    comment:    str        = ""
    skip:       str        = ""    # "" / "S" / "P"
    tuning_step:float      = 5.0   # kHz

    @property
    def rx_mhz(self) -> float:
        if self.rx_freq:
            return self.rx_freq
        if self.duplex == "+":
            return self.freq_mhz + self.offset_mhz
        if self.duplex == "-":
            return self.freq_mhz - self.offset_mhz
        return self.freq_mhz

    @property
    def is_digital(self) -> bool:
        return self.mode in ("DV", "DN", "D-STAR",
                             "DMR", "P25", "YSF", "NXDN")

    @classmethod
    def from_repeater(cls, number: int,
                      repeater) -> "MemoryChannel":
        """Create from a Repeater object (repeaterbook)."""
        # Map tone type
        tone_mode = ""
        ctcss = 0.0
        dcs   = 23
        if repeater.tone:
            try:
                tone_val = float(repeater.tone)
                ctcss    = tone_val
                tone_mode = "Tone"
            except ValueError:
                # DCS code
                try:
                    dcs      = int(repeater.tone)
                    tone_mode = "DTCS"
                except ValueError:
                    pass

        # Map mode
        mode_map = {
            "FM":    "FM",
            "DMR":   "NFM",
            "P25":   "NFM",
            "YSF":   "NFM",
            "NXDN":  "NFM",
            "D-STAR":"DV",
            "DSTAR": "DV",
            "C4FM":  "DN",
        }
        mode = mode_map.get(
            repeater.mode.upper(), "FM")

        # Map offset
        duplex = ""
        if repeater.offset_mhz > 0:
            duplex = "+"
        elif repeater.offset_mhz < 0:
            duplex = "-"

        # Name: use callsign, max 8 chars for most radios
        name = repeater.callsign[:8]

        return cls(
            number     = number,
            name       = name,
            freq_mhz   = repeater.output_mhz,
            duplex     = duplex,
            offset_mhz = abs(repeater.offset_mhz),
            tone_mode  = tone_mode,
            ctcss_tone = ctcss,
            dcs_code   = dcs,
            mode       = mode,
            comment    = (f"{repeater.city} "
                          f"{repeater.mode}".strip()
                          )[:20],
        )


class MemoryBank:
    """
    A collection of memory channels.
    Supports import from repeater searches and
    export to CHIRP CSV format.
    """

    def __init__(self):
        self._channels: dict[int, MemoryChannel] = {}

    def add(self, ch: MemoryChannel):
        self._channels[ch.number] = ch

    def remove(self, number: int):
        self._channels.pop(number, None)

    def get(self, number: int
            ) -> MemoryChannel | None:
        return self._channels.get(number)

    def all_channels(self) -> list[MemoryChannel]:
        return [self._channels[k]
                for k in sorted(self._channels)]

    def next_free(self, start: int = 0) -> int:
        used = set(self._channels.keys())
        n = start
        while n in used:
            n += 1
        return n

    def from_repeaters(self,
                       repeaters: list,
                       start: int = 0):
        """
        Import repeaters from a RepeaterBook search result.
        Numbers channels starting at `start`.
        """
        for i, rep in enumerate(repeaters):
            num = self.next_free(start + i)
            ch  = MemoryChannel.from_repeater(num, rep)
            self.add(ch)
        return len(repeaters)

    def to_chirp_csv(self) -> str:
        """
        Export to CHIRP generic CSV format.
        Compatible with most CHIRP-supported radios.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # CHIRP CSV header
        writer.writerow([
            "Location", "Name", "Frequency",
            "Duplex", "Offset", "Tone", "rToneFreq",
            "cToneFreq", "DtcsCode", "DtcsPolarity",
            "Mode", "TStep", "Skip", "Comment",
            "URCALL", "RPT1CALL", "RPT2CALL",
            "DVCODE",
        ])

        for ch in self.all_channels():
            # CTCSS / DCS tone
            tone_val   = ""
            r_tone     = "88.5"  # default CTCSS RX
            c_tone     = "88.5"  # default CTCSS TX
            dtcs_code  = "023"
            dtcs_pol   = "NN"

            if ch.ctcss_tone:
                tone_val = f"{ch.ctcss_tone:.1f}"
                r_tone   = tone_val
                c_tone   = tone_val
            if ch.dcs_code:
                dtcs_code = f"{ch.dcs_code:03d}"

            writer.writerow([
                ch.number,
                ch.name[:8],
                f"{ch.freq_mhz:.6f}",
                ch.duplex,
                f"{ch.offset_mhz:.6f}",
                ch.tone_mode,
                r_tone,
                c_tone,
                dtcs_code,
                dtcs_pol,
                ch.mode,
                f"{ch.tuning_step:.2f}",
                ch.skip,
                ch.comment[:20],
                "",  # URCALL (D-STAR)
                "",  # RPT1CALL
                "",  # RPT2CALL
                "",  # DVCODE
            ])

        return output.getvalue()

    def save_chirp_csv(self, path: Path) -> int:
        """Write CHIRP CSV to file. Returns channel count."""
        csv_text = self.to_chirp_csv()
        path     = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(csv_text, encoding="utf-8")
        count = len(self._channels)
        log.info(f"Exported {count} channels to {path}")
        return count

    def __len__(self) -> int:
        return len(self._channels)

    def __iter__(self):
        return iter(self.all_channels())
