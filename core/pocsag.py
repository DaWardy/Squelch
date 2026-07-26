# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/pocsag.py

POCSAG pager decoder — recover pager address + message from a 2-FSK POCSAG
transmission (512 / 1200 / 2400 baud). This is the classic "decode that pager"
capability.

Structure: a long 1010… preamble, then batches. Each batch is one 32-bit sync
codeword (0x7CD215D8) followed by 16 codewords in 8 frames. A codeword's top bit
flags address (0) vs message (1); 21 bits are protected by a BCH(31,21) check +
even parity. An address codeword gives the RIC (= 18 address bits × 8 + the
frame index) and two function bits; the message codewords after it carry the
text — numeric (reversed 4-bit BCD) or alphanumeric (7-bit ASCII, LSB-first,
packed across codewords).

`decode_pocsag(iq, fs)` FSK-demodulates and tries baud rates + polarity;
`decode_pocsag_bits(bits)` works on an NRZ bit stream. Pure Python/numpy, never
raises — returns [] when nothing frames. Includes matching encoders so the
framing + BCH are round-trip verified.
"""

import logging
from dataclasses import dataclass

import numpy as np

log = logging.getLogger(__name__)

SYNC = 0x7CD215D8
IDLE = 0x7A89C197
_BCH_POLY = 0x769            # x^10+x^9+x^8+x^6+x^5+x^3+1  (BCH(31,21))
_NUMERIC = "0123456789*U -)("   # reversed-nibble → digit
BAUDS = (512, 1200, 2400)


@dataclass
class PocsagMessage:
    ric:      int
    function: int
    kind:     str       # 'numeric' | 'alpha'
    text:     str

    def __str__(self):
        return f"RIC {self.ric} F{self.function} [{self.kind}]: {self.text}"


# ── BCH(31,21) + parity codeword ─────────────────────────────────────────────
def _bch(data21: int) -> int:
    reg = (data21 & 0x1FFFFF) << 10
    for i in range(20, -1, -1):
        if reg & (1 << (i + 10)):
            reg ^= _BCH_POLY << i
    return reg & 0x3FF


def encode_codeword(data21: int) -> int:
    cw = ((data21 & 0x1FFFFF) << 11) | (_bch(data21) << 1)
    parity = bin(cw >> 1).count("1") & 1
    return cw | parity


def _valid(cw: int) -> bool:
    return encode_codeword(cw >> 11) == cw


# ── bit helpers ──────────────────────────────────────────────────────────────
def _bits_of(value: int, width: int) -> list:
    return [(value >> (width - 1 - i)) & 1 for i in range(width)]


def _to_int(bits) -> int:
    v = 0
    for b in bits:
        v = (v << 1) | (int(b) & 1)
    return v


# ── encode (for tests / TX-side, unauthenticated synthesis) ──────────────────
def encode_numeric(ric: int, message: str, *, function: int = 0) -> list:
    """Bits for one address+numeric message (no preamble/sync). RIC low 3 bits
    select the frame; the codeword pair is padded with idles to that frame."""
    frame = ric & 0x7
    # data21 (address) = addr18(18) << 2 | function(2); flag bit stays 0
    addr_cw = encode_codeword((((ric >> 3) & 0x3FFFF) << 2) | (function & 0x3))
    rev = {c: i for i, c in enumerate(_NUMERIC)}
    digits = [rev.get(c, 0) for c in message]
    # pack 4-bit reversed nibbles into 20-bit message codewords
    msg_cws = []
    nib = []
    for d in digits:
        nib.append(int(f"{d:04b}"[::-1], 2))
        if len(nib) == 5:
            msg_cws.append(_pack_nibbles(nib)); nib = []
    if nib:
        while len(nib) < 5:
            nib.append(int("1100"[::-1], 2))       # pad with 'space'/idle nibble
        msg_cws.append(_pack_nibbles(nib))
    codewords = [addr_cw] + msg_cws
    return _lay_batch(frame, codewords)


def _pack_nibbles(nibbles) -> int:
    data20 = 0
    for n in nibbles:
        data20 = (data20 << 4) | (n & 0xF)
    return encode_codeword((1 << 20) | data20)      # flag=1 (message)


def _lay_batch(frame: int, codewords) -> list:
    """Sync + 16-slot batches holding the codewords consecutively from `frame`,
    spilling into additional batches (each its own sync) when a batch fills."""
    bits, slots, pos = [], [IDLE] * 16, frame * 2
    for cw in codewords:
        if pos >= 16:
            bits += _bits_of(SYNC, 32)
            for s in slots:
                bits += _bits_of(s, 32)
            slots, pos = [IDLE] * 16, 0
        slots[pos] = cw
        pos += 1
    bits += _bits_of(SYNC, 32)
    for s in slots:
        bits += _bits_of(s, 32)
    return bits


def encode_alpha(ric: int, text: str, *, function: int = 3) -> list:
    """Bits for one address + alphanumeric message (7-bit ASCII, LSB-first)."""
    frame = ric & 0x7
    addr_cw = encode_codeword((((ric >> 3) & 0x3FFFF) << 2) | (function & 0x3))
    stream = []
    for ch in text:
        stream += _bits_of(ord(ch) & 0x7F, 7)[::-1]     # LSB first
    while len(stream) % 20:
        stream.append(0)
    msg_cws = [encode_codeword((1 << 20) | _to_int(stream[k:k + 20]))
               for k in range(0, len(stream), 20)]
    return _lay_batch(frame, [addr_cw] + msg_cws)


def encode_frame(ric: int, message: str, *, function: int = 0,
                 preamble_bits: int = 576, alpha: bool = False) -> list:
    """A complete transmittable POCSAG frame (preamble+sync+batch)."""
    pre = [1, 0] * (preamble_bits // 2)
    body = (encode_alpha(ric, message, function=function) if alpha
            else encode_numeric(ric, message, function=function))
    return pre + body


# ── decode ───────────────────────────────────────────────────────────────────
def decode_pocsag_bits(bits) -> list:
    """Decode an NRZ bit stream → list[PocsagMessage]. Never raises.

    A message runs from its address codeword through all following message
    codewords — across batch (SYNC) boundaries — until the next address or an
    idle codeword, matching real POCSAG."""
    try:
        b = [int(x) & 1 for x in bits]
        n = len(b)
        i = 0
        while i <= n - 32 and _to_int(b[i:i + 32]) != SYNC:
            i += 1                                   # skip preamble to first sync
        out, cur = [], None
        while i <= n - 32:
            if _to_int(b[i:i + 32]) != SYNC:
                i += 1                               # lost alignment → resync
                continue
            i += 32                                  # consume the sync codeword
            for slot in range(16):
                if i + 32 > n:
                    break
                cw = _to_int(b[i:i + 32])
                i += 32
                if cw == IDLE or not _valid(cw):
                    if cw == IDLE:
                        cur = None
                    continue
                if (cw >> 31) == 0:                  # address codeword
                    ric = (((cw >> 13) & 0x3FFFF) << 3) | (slot // 2)
                    cur = PocsagMessage(ric, (cw >> 11) & 0x3, "numeric", "")
                    cur._bits = []
                    out.append(cur)
                elif cur is not None:                # message codeword
                    cur._bits += _bits_of((cw >> 11) & 0xFFFFF, 20)
        _finish(out)
        return out
    except Exception as exc:                         # pragma: no cover
        log.debug("decode_pocsag_bits failed: %s", exc)
        return []


def _finish(out):
    for m in out:
        if getattr(m, "_decoded", False) or not getattr(m, "_bits", None):
            continue
        if m.function == 3:                          # commonly alphanumeric
            m.kind, m.text = "alpha", _alpha_text(m._bits)
        else:
            m.kind, m.text = "numeric", _numeric_text(m._bits)
        m._decoded = True


def _numeric_text(bits) -> str:
    chars = []
    for k in range(0, len(bits) - 3, 4):
        nib = bits[k:k + 4]
        val = _to_int(nib[::-1])                     # nibble is bit-reversed
        chars.append(_NUMERIC[val] if val < len(_NUMERIC) else "?")
    return "".join(chars).rstrip(" ")


def _alpha_text(bits) -> str:
    chars = []
    for k in range(0, len(bits) - 6, 7):
        code = _to_int(bits[k:k + 7][::-1])          # 7-bit ASCII, LSB first
        if code == 0:
            break                                    # NUL / end of message
        if 32 <= code < 127:
            chars.append(chr(code))
    return "".join(chars).rstrip()


def decode_pocsag(iq, fs: float) -> list:
    """FSK-demodulate IQ and decode POCSAG, trying baud rates + polarity."""
    try:
        x = np.asarray(iq)
        if x.size < 64 or fs <= 0:
            return []
        inst = np.angle(x[1:] * np.conj(x[:-1]))
        best = []
        for pol in (inst, -inst):
            level = (pol > np.median(pol)).astype(np.int8)
            for baud in BAUDS:
                spb = fs / baud
                if spb < 2 or spb * 40 > len(level):
                    continue
                bits = level[np.clip(
                    (np.arange(int(len(level) / spb)) * spb + spb / 2).astype(int),
                    0, len(level) - 1)]
                msgs = decode_pocsag_bits(bits)
                if len(msgs) > len(best):
                    best = msgs
        return best
    except Exception as exc:                         # pragma: no cover
        log.debug("decode_pocsag failed: %s", exc)
        return []
