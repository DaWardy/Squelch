# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/cw_decode.py

Morse (CW) decoder — turn an on/off-keyed carrier into text. Works from the raw
IQ envelope (|iq|) of a keyed carrier, or from a keyed audio tone. This is the
"decode that beeping" complement to the workbench's OOK/CW branch.

Pipeline: envelope → smooth → adaptive on/off threshold → run-length the keying →
estimate the dot unit (dots/element-gaps are the shortest runs) → classify each
on-run as dot/dash and each off-run as element / letter / word gap → look up the
Morse table. Self-timing (no WPM needed). Pure numpy, never raises — returns ""
when there's nothing decodable.
"""

import logging

import numpy as np

log = logging.getLogger(__name__)

# Morse → character (international + digits + common punctuation/prosigns)
_MORSE = {
    ".-": "A", "-...": "B", "-.-.": "C", "-..": "D", ".": "E", "..-.": "F",
    "--.": "G", "....": "H", "..": "I", ".---": "J", "-.-": "K", ".-..": "L",
    "--": "M", "-.": "N", "---": "O", ".--.": "P", "--.-": "Q", ".-.": "R",
    "...": "S", "-": "T", "..-": "U", "...-": "V", ".--": "W", "-..-": "X",
    "-.--": "Y", "--..": "Z",
    "-----": "0", ".----": "1", "..---": "2", "...--": "3", "....-": "4",
    ".....": "5", "-....": "6", "--...": "7", "---..": "8", "----.": "9",
    ".-.-.-": ".", "--..--": ",", "..--..": "?", "-..-.": "/", "-...-": "=",
    ".----.": "'", "-.-.--": "!", "---...": ":", ".-.-.": "+", "-....-": "-",
    ".--.-.": "@", "...-.-": "<SK>", "-.-.-": "<CT>",
}


def decode_cw(signal, sample_rate: float, *, is_envelope: bool = False) -> str:
    """Decode Morse from a keyed IQ carrier (or audio). Never raises."""
    try:
        x = np.asarray(signal)
        if x.size < 16 or sample_rate <= 0:
            return ""
        env = np.abs(x).astype(float) if not is_envelope \
            else np.asarray(signal, dtype=float)
        env = _smooth(env, sample_rate)
        on = env > _threshold(env)
        runs = _runs(on)
        if len(runs) < 2:
            return ""
        unit = _estimate_unit(runs)
        if unit <= 0:
            return ""
        return _runs_to_text(runs, unit)
    except Exception as exc:                         # pragma: no cover
        log.debug("decode_cw failed: %s", exc)
        return ""


# ── helpers ──────────────────────────────────────────────────────────────────
def _smooth(env, sample_rate):
    # ~2 ms moving average tames the carrier ripple without blurring keying
    k = max(1, int(sample_rate * 0.002))
    if k > 1 and k < len(env):
        env = np.convolve(env, np.ones(k) / k, mode="same")
    return env


def _threshold(env):
    hi = float(np.percentile(env, 90))
    lo = float(np.percentile(env, 10))
    return lo + 0.5 * (hi - lo)


def _runs(mask):
    """[(is_on, length), …] run-length encoding of a boolean array."""
    out = []
    if len(mask) == 0:
        return out
    cur = bool(mask[0])
    n = 1
    for v in mask[1:]:
        if bool(v) == cur:
            n += 1
        else:
            out.append((cur, n))
            cur, n = bool(v), 1
    out.append((cur, n))
    return out


def _estimate_unit(runs):
    """Dot length in samples: the low cluster of run lengths (dots + element
    gaps are 1 unit; dashes/letter-gaps 3; word gaps 7)."""
    lengths = sorted(r[1] for r in runs)
    if not lengths:
        return 0.0
    # the shortest ~third of runs are ~1 unit; use their median for robustness
    short = lengths[:max(1, len(lengths) // 3)]
    return float(np.median(short))


def _runs_to_text(runs, unit):
    out, cur = [], ""
    for is_on, length in runs:
        u = length / unit
        if is_on:
            cur += "." if u < 2.0 else "-"
        else:
            if u < 2.0:
                continue                     # gap within a letter
            if cur:
                out.append(_MORSE.get(cur, "?"))
                cur = ""
            if u >= 5.0:
                out.append(" ")              # word gap
    if cur:
        out.append(_MORSE.get(cur, "?"))
    return "".join(out).strip()
