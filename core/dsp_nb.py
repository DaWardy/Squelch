# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/dsp_nb.py

Time-domain impulse noise blanker (NB) for IQ samples.

Removes short, high-amplitude impulses (ignition/electrical noise, power-line
arcs) before the FFT/demod by clamping samples whose magnitude greatly exceeds
the running median magnitude — preserving phase so the wanted signal is barely
touched. Pure numpy; unit-tested on arrays (no SDR needed).
"""

import numpy as np


def noise_blank(iq: np.ndarray, strength: float = 0.5) -> np.ndarray:
    """Return a copy of `iq` with impulsive samples magnitude-clamped.

    `strength` 0..1 sets how aggressive the blanker is: the clamp threshold is
    `median(|iq|) * factor`, where factor runs 10× (gentle, strength 0) down to
    2× (aggressive, strength 1). Samples above the threshold are scaled back to
    the threshold magnitude, keeping their phase. Non-impulsive samples are
    untouched. A flat/empty/zero-median input is returned unchanged.
    """
    if iq is None:
        return iq
    arr = np.asarray(iq)
    if arr.size == 0:
        return arr
    mag = np.abs(arr)
    med = float(np.median(mag))
    if med <= 0.0:
        return arr.copy()
    s = min(1.0, max(0.0, float(strength)))
    factor = 10.0 - 8.0 * s            # 10 (gentle) … 2 (aggressive)
    thr = med * factor
    over = mag > thr
    if not bool(over.any()):
        return arr.copy()
    out = arr.copy()
    # Scale impulsive samples back to the threshold magnitude, preserve phase.
    out[over] = arr[over] / mag[over] * thr
    return out


def impulse_count(iq: np.ndarray, strength: float = 0.5) -> int:
    """How many samples the blanker would clamp (for a UI activity indicator)."""
    if iq is None:
        return 0
    arr = np.asarray(iq)
    if arr.size == 0:
        return 0
    mag = np.abs(arr)
    med = float(np.median(mag))
    if med <= 0.0:
        return 0
    s = min(1.0, max(0.0, float(strength)))
    thr = med * (10.0 - 8.0 * s)
    return int(np.count_nonzero(mag > thr))
