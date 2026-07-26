# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/rtty.py

RTTY (radioteletype) decoder — recover text from a 5-bit Baudot / ITA2 FSK
signal (the classic HF teletype mode). FSK-demodulate the IQ to a mark/space
stream, frame each character (1 start bit = space, 5 data bits LSB-first, ≥1
stop bit = mark) at the given baud, and translate via the ITA2 table with
LTRS/FIGS shift handling.

`decode_rtty(iq, fs, baud=45.45, shift…)` — auto-tries normal and reversed
mark/space polarity and keeps whichever yields more printable text, so you don't
have to know the sideband. Pure numpy, never raises — "" when nothing frames.
"""

import logging

import numpy as np

log = logging.getLogger(__name__)

BAUD_45 = 45.45          # standard amateur HF RTTY

# ITA2 (transmission order b1..b5, b1 sent first / LSB) → letters / figures
_LTRS = {
    "00000": "", "00100": " ", "00010": "\r", "01000": "\n",
    "11000": "A", "10011": "B", "01110": "C", "10010": "D", "10000": "E",
    "10110": "F", "01011": "G", "00101": "H", "01100": "I", "11010": "J",
    "11110": "K", "01001": "L", "00111": "M", "00110": "N", "00011": "O",
    "01101": "P", "11101": "Q", "01010": "R", "10100": "S", "00001": "T",
    "11100": "U", "01111": "V", "11001": "W", "10111": "X", "10101": "Y",
    "10001": "Z", "11111": "", "11011": "",
}
_FIGS = {
    "00000": "", "00100": " ", "00010": "\r", "01000": "\n",
    "11000": "-", "10011": "?", "01110": ":", "10010": "$", "10000": "3",
    "10110": "!", "01011": "&", "00101": "#", "01100": "8", "11010": "'",
    "11110": "(", "01001": ")", "00111": ".", "00110": ",", "00011": "9",
    "01101": "0", "11101": "1", "01010": "4", "10100": "'", "00001": "5",
    "11100": "7", "01111": "=", "11001": "2", "10111": "/", "10101": "6",
    "10001": "+", "11111": "", "11011": "",
}


def decode_rtty(iq, fs: float, *, baud: float = BAUD_45) -> str:
    """Decode RTTY text from FSK IQ. Tries both polarities. Never raises."""
    try:
        x = np.asarray(iq)
        if x.size < 32 or fs <= 0 or baud <= 0:
            return ""
        inst = np.angle(x[1:] * np.conj(x[:-1]))     # >0 = higher (mark) tone
        k = max(1, int(fs / baud / 8))
        if k > 1 and k < len(inst):
            inst = np.convolve(inst, np.ones(k) / k, mode="same")
        mark = (inst > np.median(inst)).astype(np.int8)
        best = ""
        for bits in (mark, 1 - mark):
            txt = _frame(bits, fs / baud)
            if _printable(txt) > _printable(best):
                best = txt
        return best
    except Exception as exc:                         # pragma: no cover
        log.debug("decode_rtty failed: %s", exc)
        return ""


def _bit(bits, start: float, spb: float) -> int:
    """Majority vote over the middle half of the bit at [start, start+spb) —
    robust to edge jitter from the FSK-demod smoothing."""
    lo = int(start + 0.25 * spb)
    hi = max(lo + 1, int(start + 0.75 * spb))
    seg = bits[lo:hi]
    return 1 if seg.size and seg.mean() >= 0.5 else 0


def _frame(bits, spb: float) -> str:
    """Frame a mark(1)/space(0) stream into ITA2 characters."""
    n = len(bits)
    need = int(7.5 * spb)
    out, shift = [], "LTRS"
    i = 0
    while i < n - need:
        # start bit = a mark→space edge, confirmed as a real (held) space
        if bits[i] == 1 and bits[i + 1] == 0:
            s = i + 1
            if _bit(bits, s, spb) != 0:              # not a genuine start bit
                i += 1
                continue
            code = "".join(str(_bit(bits, s + (1 + b) * spb, spb))
                           for b in range(5))
            if _bit(bits, s + 6.0 * spb, spb) == 1:  # stop bit is mark
                ch, shift = _decode(code, shift)
                out.append(ch)
                i = int(s + 6.5 * spb)
                continue
        i += 1
    return "".join(out)


def _decode(code: str, shift: str):
    if code == "11111":
        return "", "LTRS"
    if code == "11011":
        return "", "FIGS"
    table = _FIGS if shift == "FIGS" else _LTRS
    return table.get(code, ""), shift


def _printable(txt: str) -> int:
    return sum(1 for c in txt if c.isalnum() or c in " .,?/-")
