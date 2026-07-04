# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch

from __future__ import annotations
"""Squelch -- core/linecoding.py

Line-coding decode/encode (ROADMAP Phase 4, between DEC-GENERIC and
DEC-FRAMING). The bit-slicer (core/bitslicer.slice_bits) recovers the raw
channel symbols; many real ISM / RFID / telemetry protocols carry their data
*line-coded* on top of those symbols, so the raw stream must be un-coded before
the framing inspector can find preamble/sync/CRC. This module handles the
common schemes:

  * Manchester   — each data bit is two chips (a guaranteed mid-bit
                   transition). Two conventions: IEEE 802.3 (low→high = 1) and
                   G.E. Thomas (the inverse). Chip alignment (phase) is
                   auto-detected.
  * NRZI         — a level *transition* encodes one bit value, no transition
                   the other (used by USB, HDLC, many RF remotes).
  * Differential — each bit is XORed against the previous *coded* symbol
                   (removes absolute-polarity ambiguity, e.g. after DBPSK).

Every decoder has a matching encoder, so encode∘decode is the identity — the
round-trips are the tests. Pure Python (lists of 0/1 in and out); never raises.
"""

import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

MANCHESTER_IEEE   = "ieee"      # 802.3: bit 1 = chips [0,1] (rising)
MANCHESTER_THOMAS = "thomas"    # G.E. Thomas: bit 1 = chips [1,0] (falling)


def _clean(bits) -> list:
    return [1 if b else 0 for b in bits]


def _chip_pairs(convention: str):
    """(chips-for-1, chips-for-0) under the given convention."""
    if convention == MANCHESTER_THOMAS:
        return [1, 0], [0, 1]
    return [0, 1], [1, 0]           # IEEE default


# ── Manchester ────────────────────────────────────────────────────────────────

@dataclass
class ManchesterResult:
    bits:   list = field(default_factory=list)
    offset: int  = 0        # chip alignment used (0 or 1)
    errors: int  = 0        # chip pairs with no transition (00 / 11)


def encode_manchester(bits, convention: str = MANCHESTER_IEEE) -> list:
    one, zero = _chip_pairs(convention)
    out: list = []
    for b in _clean(bits):
        out += one if b else zero
    return out


def _decode_manchester_aligned(chips, convention: str) -> tuple:
    one, _zero = _chip_pairs(convention)
    bits, errors = [], 0
    for i in range(0, len(chips) - 1, 2):
        a, b = chips[i], chips[i + 1]
        if a == b:                              # no transition → invalid chip pair
            errors += 1
            bits.append(0)
        else:
            bits.append(1 if [a, b] == one else 0)
    return bits, errors


def decode_manchester(chips, convention: str = MANCHESTER_IEEE,
                      offset=None) -> ManchesterResult:
    """Decode Manchester chips → data bits.

    When `offset` is None the chip alignment is auto-detected (the alignment
    with fewer invalid — non-transitioning — pairs wins).
    """
    chips = _clean(chips)
    if offset is not None:
        bits, errs = _decode_manchester_aligned(chips[offset:], convention)
        return ManchesterResult(bits, offset, errs)
    best = None
    for off in (0, 1):
        bits, errs = _decode_manchester_aligned(chips[off:], convention)
        if best is None or errs < best.errors:
            best = ManchesterResult(bits, off, errs)
        if errs == 0:
            break
    return best or ManchesterResult()


# ── NRZI ──────────────────────────────────────────────────────────────────────

def encode_nrzi(bits, transition_bit: int = 1, init: int = 0) -> list:
    """Bits → levels. A `transition_bit` flips the level; the other holds it."""
    level = init & 1
    out: list = []
    for b in _clean(bits):
        if b == transition_bit:
            level ^= 1
        out.append(level)
    return out


def decode_nrzi(levels, transition_bit: int = 1, init: int = 0) -> list:
    """Levels → bits. A change from the previous level = `transition_bit`."""
    levels = _clean(levels)
    prev = init & 1
    other = transition_bit ^ 1
    out: list = []
    for lv in levels:
        out.append(transition_bit if lv != prev else other)
        prev = lv
    return out


# ── differential ──────────────────────────────────────────────────────────────

def encode_differential(bits, init: int = 0) -> list:
    """Coded[i] = coded[i-1] XOR bit[i]."""
    prev = init & 1
    out: list = []
    for b in _clean(bits):
        prev ^= b
        out.append(prev)
    return out


def decode_differential(symbols, init: int = 0) -> list:
    """bit[i] = symbol[i] XOR symbol[i-1]."""
    symbols = _clean(symbols)
    prev = init & 1
    out: list = []
    for s in symbols:
        out.append(s ^ prev)
        prev = s
    return out
