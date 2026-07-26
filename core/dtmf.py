# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/dtmf.py

DTMF (touch-tone) decoder — recover the dialled digits from demodulated audio.
Each key is a pair of one low-group tone and one high-group tone:

        1209  1336  1477  1633 Hz
   697    1     2     3     A
   770    4     5     6     B
   852    7     8     9     C
   941    *     0     #     D

Block-by-block tone detection (short windowed FFT at the eight DTMF frequencies);
a digit is emitted on each low+high pair that dominates its group, and repeated
blocks of the same key collapse into one press. Pure numpy, never raises —
returns "" when there's nothing to decode. Feeds the decode workbench for
AM/FM/NBFM signals carrying touch-tones.
"""

import logging

import numpy as np

log = logging.getLogger(__name__)

LOW_FREQS  = (697.0, 770.0, 852.0, 941.0)
HIGH_FREQS = (1209.0, 1336.0, 1477.0, 1633.0)
_KEYS = (("1", "2", "3", "A"),
         ("4", "5", "6", "B"),
         ("7", "8", "9", "C"),
         ("*", "0", "#", "D"))


def _tone_powers(block, freqs, sample_rate):
    w = np.hanning(len(block))
    spec = np.abs(np.fft.rfft(block * w))
    fbins = np.fft.rfftfreq(len(block), 1.0 / sample_rate)
    return np.array([spec[int(np.argmin(np.abs(fbins - f)))] for f in freqs])


def decode_dtmf(audio, sample_rate: float, *, block_ms: float = 40.0,
                dominance: float = 4.0) -> str:
    """Decode a DTMF digit sequence from `audio`. Never raises.

    `dominance` is how strongly the winning tone in each group must exceed the
    others for a digit to count (rejects noise / speech)."""
    try:
        a = np.asarray(audio, dtype=float)
        if a.size < 64 or sample_rate <= 0:
            return ""
        bs = max(64, int(sample_rate * block_ms / 1000.0))
        step = max(1, bs // 2)                       # 50% overlap
        floor = 1e-9
        digits: list = []
        last = None
        for i in range(0, len(a) - bs + 1, step):
            block = a[i:i + bs]
            low = _tone_powers(block, LOW_FREQS, sample_rate)
            high = _tone_powers(block, HIGH_FREQS, sample_rate)
            li, hi = int(np.argmax(low)), int(np.argmax(high))
            low_others = (low.sum() - low[li]) / 3.0 + floor
            high_others = (high.sum() - high[hi]) / 3.0 + floor
            energy = float(np.mean(block ** 2))
            present = (low[li] > dominance * low_others and
                       high[hi] > dominance * high_others and
                       energy > 1e-6)
            key = _KEYS[li][hi] if present else None
            if key != last:
                if key is not None:
                    digits.append(key)
                last = key
        return "".join(digits)
    except Exception as exc:                         # pragma: no cover
        log.debug("decode_dtmf failed: %s", exc)
        return ""
