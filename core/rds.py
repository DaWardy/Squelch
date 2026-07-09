# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/rds.py

RDS / RBDS decoder — the digital data carried on the 57 kHz subcarrier of an FM
broadcast: the station's short name (PS), scrolling Radio Text (RT), programme
identification (PI) and programme type (PTY). This is the protocol layer, and
it is pure + fully round-trip tested:

  * `make_block()` / `check_block()` — the 26-bit RDS block (16 info + 10 check
    bits), using the standard CRC-10 generator g(x)=x^10+x^8+x^7+x^5+x^4+x^3+1
    and the A/B/C/C'/D offset words.
  * `bits_to_groups()` — synchronise a raw RDS bitstream to groups by sliding
    for a valid block A then reading B/C/D at their offsets.
  * `decode_group()` — parse a group's four info words (PI, group type/version,
    PTY, TP, payload).
  * `RDSDecoder` — accumulate PS (8 chars) and Radio Text (64 chars) across
    groups and expose the current station state.

The remaining live piece (not here): recover the RDS bitstream from FM IQ —
FM-demod → 57 kHz bandpass → biphase/DBPSK at 1187.5 bps → differential decode —
which needs the audio-rate stream. Feed those bits to `bits_to_groups()`.

Pure Python, never raises on bad input.
"""

import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

# CRC-10 generator (lower 11 bits: x^10+x^8+x^7+x^5+x^4+x^3+1) and offset words.
_POLY = 0x5B9
OFFSETS = {"A": 0x0FC, "B": 0x198, "C": 0x168, "Cp": 0x350, "D": 0x1B4}

GROUP_BITS = 104        # 4 blocks × 26 bits
BLOCK_BITS = 26

# US RBDS programme types (0-31).
PTY_RBDS = [
    "None", "News", "Information", "Sports", "Talk", "Rock", "Classic Rock",
    "Adult Hits", "Soft Rock", "Top 40", "Country", "Oldies", "Soft",
    "Nostalgia", "Jazz", "Classical", "Rhythm and Blues", "Soft R&B",
    "Foreign Language", "Religious Music", "Religious Talk", "Personality",
    "Public", "College", "Spanish Talk", "Spanish Music", "Hip Hop",
    "Unassigned", "Unassigned", "Weather", "Emergency Test", "ALERT! ALERT!",
]


# ── block CRC / checkword ─────────────────────────────────────────────────────

def _calc_check(info16: int) -> int:
    """10-bit CRC of a 16-bit info word (info·x^10 mod g)."""
    reg = 0
    val = (info16 & 0xFFFF) << 10
    for i in range(25, -1, -1):
        reg = (reg << 1) | ((val >> i) & 1)
        if reg & 0x400:
            reg ^= _POLY
    return reg & 0x3FF


def make_block(info16: int, offset: int) -> int:
    """Encode a 26-bit RDS block: info word + (CRC ⊕ offset word)."""
    return ((info16 & 0xFFFF) << 10) | ((_calc_check(info16) ^ offset) & 0x3FF)


def check_block(block26: int, offset: int):
    """Return the 16-bit info word if the block's checkword is valid for
    `offset`, else None."""
    info = (block26 >> 10) & 0xFFFF
    if (_calc_check(info) ^ offset) == (block26 & 0x3FF):
        return info
    return None


# ── group model ───────────────────────────────────────────────────────────────

@dataclass
class RDSGroup:
    pi:         int
    group_type: int          # 0..15
    version:    str          # 'A' | 'B'
    pty:        int
    tp:         int
    info:       tuple        # the 4 info words


def decode_group(info_words) -> "RDSGroup | None":
    """Parse a group from its four 16-bit info words."""
    if not info_words or len(info_words) < 4:
        return None
    b = int(info_words[1]) & 0xFFFF
    return RDSGroup(
        pi=int(info_words[0]) & 0xFFFF,
        group_type=(b >> 12) & 0xF,
        version="B" if (b >> 11) & 1 else "A",
        tp=(b >> 10) & 1,
        pty=(b >> 5) & 0x1F,
        info=tuple(int(w) & 0xFFFF for w in info_words[:4]))


# ── bitstream synchroniser ────────────────────────────────────────────────────

def _window(bits, start: int, length: int) -> int:
    v = 0
    for k in range(length):
        v = (v << 1) | bits[start + k]
    return v


def bits_to_groups(bits) -> list:
    """Synchronise a raw RDS bitstream (list of 0/1) to groups."""
    b = [1 if x else 0 for x in bits]
    n = len(b)
    out = []
    i = 0
    while i + GROUP_BITS <= n:
        info_a = check_block(_window(b, i, BLOCK_BITS), OFFSETS["A"])
        if info_a is None:
            i += 1
            continue
        info_b = check_block(_window(b, i + 26, BLOCK_BITS), OFFSETS["B"])
        if info_b is None:
            i += 1
            continue
        off_c = OFFSETS["Cp"] if (info_b >> 11) & 1 else OFFSETS["C"]
        info_c = check_block(_window(b, i + 52, BLOCK_BITS), off_c)
        info_d = check_block(_window(b, i + 78, BLOCK_BITS), OFFSETS["D"])
        if info_c is None or info_d is None:
            i += 1
            continue
        g = decode_group((info_a, info_b, info_c, info_d))
        if g is not None:
            out.append(g)
        i += GROUP_BITS
    return out


# ── stateful decoder (PS / RadioText accumulation) ────────────────────────────

def _char(code: int) -> str:
    return chr(code) if 32 <= code < 127 else " "


class RDSDecoder:
    """Accumulate station state (PI/PTY/PS/RadioText) across RDS groups."""

    def __init__(self):
        self.pi = 0
        self.pty = 0
        self.tp = 0
        self._ps = [" "] * 8
        self._rt = [" "] * 64
        self._rt_ab = None

    def feed(self, group) -> None:
        if group is None:
            return
        self.pi = group.pi
        self.pty = group.pty
        self.tp = group.tp
        if group.group_type == 0:                 # 0A/0B — Programme Service name
            seg = group.info[1] & 0x3
            d = group.info[3]
            self._ps[seg * 2] = _char((d >> 8) & 0xFF)
            self._ps[seg * 2 + 1] = _char(d & 0xFF)
        elif group.group_type == 2 and group.version == "A":   # 2A — Radio Text
            ab = (group.info[1] >> 4) & 1
            if self._rt_ab is not None and ab != self._rt_ab:
                self._rt = [" "] * 64             # A/B flag toggled → clear
            self._rt_ab = ab
            seg = group.info[1] & 0xF
            c, d = group.info[2], group.info[3]
            base = seg * 4
            for k, code in enumerate(((c >> 8) & 0xFF, c & 0xFF,
                                      (d >> 8) & 0xFF, d & 0xFF)):
                if base + k < 64:
                    self._rt[base + k] = _char(code)

    def feed_bits(self, bits) -> None:
        for g in bits_to_groups(bits):
            self.feed(g)

    @property
    def ps(self) -> str:
        return "".join(self._ps).rstrip()

    @property
    def radiotext(self) -> str:
        return "".join(self._rt).rstrip()

    @property
    def pty_name(self) -> str:
        return PTY_RBDS[self.pty] if 0 <= self.pty < len(PTY_RBDS) else ""

    def state(self) -> dict:
        return {
            "pi": self.pi, "pi_hex": f"{self.pi:04X}",
            "pty": self.pty, "pty_name": self.pty_name,
            "tp": self.tp, "ps": self.ps, "radiotext": self.radiotext,
        }
