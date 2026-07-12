# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/framing.py

Protocol framing inspector (ROADMAP Phase 4, DEC-FRAMING). The back half of
"decode arbitrary protocol": take the raw symbol stream from the bit-slicer
(core/bitslicer.slice_bits) and pick out the classic frame structure —

    ┌───────────┬────────────┬──────────────────┬───────┐
    │ preamble  │  sync word │      payload      │  CRC  │
    └───────────┴────────────┴──────────────────┴───────┘

  * preamble — a long alternating 0101… run used for clock/AGC settling.
  * sync word — a known bit pattern that marks the start of data.
  * payload — the bits between the sync and the trailing check.
  * CRC — a trailing checksum; `identify_crc()` tries the common polynomials
    and tells you which one validates the payload (Inspectrum-style).

Pure Python (no numpy, no Qt) — line-oriented list-of-bits in, structured
`FrameReport` out. Never raises on sparse/garbage input. This makes no line-
coding assumptions (Manchester/NRZI decode is the caller's job); it inspects
the bits it is given.
"""

import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


# ── bit helpers ───────────────────────────────────────────────────────────────

def bits_to_int(bits) -> int:
    """MSB-first list of 0/1 → integer."""
    v = 0
    for b in bits:
        v = (v << 1) | (1 if b else 0)
    return v


def _bits_hex(bits) -> str:
    """MSB-first bits → hex string (reuses the slicer's byte packing)."""
    from core.bitslicer import bits_to_bytes
    packed = bits_to_bytes(bits)
    if packed:
        return packed.hex()
    return f"{bits_to_int(bits):x}" if bits else ""


def _normalize_pattern(pattern) -> list:
    """Accept a sync word as bits (list[int]), bytes, or a hex string."""
    if isinstance(pattern, str):
        pattern = bytes.fromhex(pattern.replace(" ", ""))
    if isinstance(pattern, (bytes, bytearray)):
        out = []
        for byte in pattern:
            out.extend((byte >> i) & 1 for i in range(7, -1, -1))
        return out
    return [1 if b else 0 for b in pattern]


# ── frame model ───────────────────────────────────────────────────────────────

@dataclass
class FrameField:
    name:   str
    start:  int          # bit offset in the frame
    length: int          # bits
    bits:   list = field(default_factory=list)
    hex:    str  = ""


@dataclass
class FrameReport:
    total_bits:  int = 0
    preamble:    FrameField | None = None
    sync:        FrameField | None = None
    payload:     FrameField | None = None
    crc:         FrameField | None = None
    crc_matches: list = field(default_factory=list)   # CRC names that validate
    crc_ok:      bool = False
    notes:       list = field(default_factory=list)


def _field(name: str, bits, start: int, length: int) -> FrameField:
    seg = list(bits[start:start + length])
    return FrameField(name, start, length, seg, _bits_hex(seg))


# ── preamble / sync detection ─────────────────────────────────────────────────

def longest_alternating_run(bits):
    """(start, length) of the longest maximal 0101…/1010… run."""
    if not bits:
        return (0, 0)
    best_start = best_len = 0
    cur_start, cur_len = 0, 1
    for i in range(1, len(bits)):
        if bits[i] != bits[i - 1]:
            cur_len += 1
        else:
            if cur_len > best_len:
                best_len, best_start = cur_len, cur_start
            cur_start, cur_len = i, 1
    if cur_len > best_len:
        best_len, best_start = cur_len, cur_start
    return (best_start, best_len)


def find_preamble(bits, min_len: int = 8, max_start: int = 8):
    """Longest alternating run near the start, or None if too short/late."""
    start, length = longest_alternating_run(bits)
    if length >= min_len and start <= max_start:
        return (start, length)
    return None


def find_sync(bits, pattern) -> list:
    """All bit offsets where `pattern` (bits/bytes/hex) occurs in `bits`."""
    pat = _normalize_pattern(pattern)
    n, m = len(bits), len(pat)
    if m == 0 or n < m:
        return []
    bits = [1 if b else 0 for b in bits]
    return [i for i in range(n - m + 1) if bits[i:i + m] == pat]


# ── CRC ───────────────────────────────────────────────────────────────────────

# name → (poly, width, init, refin, refout, xorout)
CRC_ALGOS = {
    "CRC-8":              (0x07,       8,  0x00,       False, False, 0x00),
    "CRC-16/CCITT-FALSE": (0x1021,     16, 0xFFFF,     False, False, 0x0000),
    "CRC-16/XMODEM":      (0x1021,     16, 0x0000,     False, False, 0x0000),
    "CRC-16/ARC":         (0x8005,     16, 0x0000,     True,  True,  0x0000),
    "CRC-32":             (0x04C11DB7, 32, 0xFFFFFFFF, True,  True,  0xFFFFFFFF),
}


def _reflect(value: int, width: int) -> int:
    r = 0
    for i in range(width):
        if value & (1 << i):
            r |= 1 << (width - 1 - i)
    return r


def crc_compute(data: bytes, poly: int, width: int, init: int,
                refin: bool, refout: bool, xorout: int) -> int:
    """Generic bit-wise CRC over `data` bytes."""
    topbit = 1 << (width - 1)
    mask = (1 << width) - 1
    crc = init
    for byte in data:
        if refin:
            byte = _reflect(byte, 8)
        crc ^= (byte << (width - 8)) & mask
        for _ in range(8):
            crc = ((crc << 1) ^ poly) & mask if (crc & topbit) \
                else (crc << 1) & mask
    if refout:
        crc = _reflect(crc, width)
    return crc ^ xorout


def compute_crc(data: bytes, name: str) -> int:
    """CRC of `data` under a named algorithm (see CRC_ALGOS)."""
    return crc_compute(data, *CRC_ALGOS[name])


def check_crc(data_bits, crc_bits, name: str) -> bool:
    """Does `crc_bits` match the named CRC over `data_bits`?"""
    from core.bitslicer import bits_to_bytes
    return compute_crc(bits_to_bytes(data_bits), name) == bits_to_int(crc_bits)


def identify_crc(data_bits, crc_bits) -> list:
    """Return the names of every known CRC whose width matches `crc_bits` and
    that validates `data_bits`. Empty ⇒ no known CRC matched."""
    from core.bitslicer import bits_to_bytes
    data = bits_to_bytes(data_bits)
    want = bits_to_int(crc_bits)
    width = len(crc_bits)
    out = []
    for name, params in CRC_ALGOS.items():
        if params[1] == width and crc_compute(data, *params) == want:
            out.append(name)
    return out


# ── top-level inspector ───────────────────────────────────────────────────────

def _preamble_end(bits, report, preamble_min: int) -> int:
    """Set report.preamble to the leading alternating run and return where it
    ends (0 if none)."""
    pre = find_preamble(bits, min_len=preamble_min)
    if pre:
        s, length = pre
        report.preamble = _field("preamble", bits, s, length)
        return s + length
    return 0


def _apply_payload(report, bits, pos: int, crc_bits: int) -> None:
    """Split bits[pos:] into payload (+ trailing CRC) on `report`."""
    rest = bits[pos:]
    if crc_bits and len(rest) > crc_bits:
        payload_bits = rest[:-crc_bits]
        report.payload = _field("payload", bits, pos, len(payload_bits))
        report.crc = _field("crc", bits, pos + len(payload_bits), crc_bits)
        report.crc_matches = identify_crc(payload_bits, report.crc.bits)
        report.crc_ok = bool(report.crc_matches)
        if not report.crc_ok:
            report.notes.append("no known CRC matched")
    else:
        report.payload = _field("payload", bits, pos, len(rest))


def inspect_frame(bits, *, sync_word=None, crc_bits: int = 0,
                  preamble_min: int = 8) -> FrameReport:
    """Parse a bit stream into preamble / sync / payload / CRC.

    sync_word    — known sync as bits/bytes/hex.
    crc_bits     — width of a trailing CRC to split off and identify.
    preamble_min — minimum alternating run to count as a preamble.

    When a sync word is given it is the reliable anchor — located anywhere in
    the stream — and the preamble is simply whatever precedes it; this avoids
    the alternating-run detector bleeding across the preamble/sync boundary when
    the sync word's first bit continues the alternation. With no sync word and a
    CRC, if stripping a leading alternating run breaks the CRC but keeping it
    validates (e.g. a preamble-less frame whose payload starts 0x55), the
    validating interpretation is kept.
    """
    bits = [1 if b else 0 for b in bits]
    report = FrameReport(total_bits=len(bits))
    sync_pat = _normalize_pattern(sync_word) if sync_word is not None else None

    if sync_pat is not None:
        offs = find_sync(bits, sync_pat)          # sync is the anchor
        if offs:
            s = offs[0]
            if s > 0:
                report.preamble = _field("preamble", bits, 0, s)
            report.sync = _field("sync", bits, s, len(sync_pat))
            pos = s + len(sync_pat)
        else:
            report.notes.append("sync word not found")
            pos = _preamble_end(bits, report, preamble_min)
    else:
        pos = _preamble_end(bits, report, preamble_min)

    _apply_payload(report, bits, pos, crc_bits)

    # No sync anchor + CRC still failing: the stripped "preamble" may be real
    # payload data. Retry without stripping and keep it if the CRC validates.
    if (crc_bits and not report.crc_ok and sync_pat is None
            and report.preamble is not None):
        retry = FrameReport(total_bits=len(bits))
        _apply_payload(retry, bits, 0, crc_bits)
        if retry.crc_ok:
            report.preamble = None
            report.payload, report.crc = retry.payload, retry.crc
            report.crc_matches, report.crc_ok = retry.crc_matches, True
            report.notes = [n for n in report.notes if "CRC" not in n]
    return report
