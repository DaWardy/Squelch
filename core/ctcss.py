# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/ctcss.py

CTCSS (Continuous Tone-Coded Squelch System) tone detection from demodulated FM
audio. CTCSS is the sub-audible tone (67.0–250.3 Hz) that FM voice systems and
repeaters transmit to key a specific sub-channel; detecting it tells you which
tone a signal / repeater is using, and lets a monitor separate users sharing a
channel.

`detect_ctcss(audio, fs)` runs a Goertzel filter tuned to each of the 38
standard EIA tones and reports the strongest one when it clearly dominates the
rest. Goertzel (a single-bin DFT) resolves these closely-spaced low tones from a
short audio window far better than a coarse FFT, and is cheap.

Pure numpy, never raises. Feed it the FM-demodulated audio (the same low-rate
audio the SDR/rig produces). A few tenths of a second of audio is needed for a
reliable lock, as with any real CTCSS decoder.
"""

import logging
from dataclasses import dataclass

import numpy as np

log = logging.getLogger(__name__)

# The 38 standard EIA/TIA CTCSS tones (Hz).
CTCSS_TONES = [
    67.0, 71.9, 74.4, 77.0, 79.7, 82.5, 85.4, 88.5, 91.5, 94.8,
    97.4, 100.0, 103.5, 107.2, 110.9, 114.8, 118.8, 123.0, 127.3, 131.8,
    136.5, 141.3, 146.2, 151.4, 156.7, 162.2, 167.9, 173.8, 179.9, 186.2,
    192.8, 203.5, 210.7, 218.1, 225.7, 233.6, 241.8, 250.3,
]

_MIN_SAMPLES = 512          # need a reasonable window for a low-tone lock


@dataclass
class CTCSSResult:
    tone_hz:    float
    index:      int          # position in CTCSS_TONES
    confidence: float        # 0..1 — how much the tone dominates the others


def goertzel_power(samples: np.ndarray, fs: float, freq: float) -> float:
    """Power at `freq` via the Goertzel algorithm (a single-bin DFT)."""
    x = np.asarray(samples, dtype=np.float64)
    n = x.size
    if n == 0 or fs <= 0:
        return 0.0
    w = 2.0 * np.pi * freq / fs
    coeff = 2.0 * np.cos(w)
    s1 = s2 = 0.0
    for v in x:
        s0 = v + coeff * s1 - s2
        s2 = s1
        s1 = s0
    power = s1 * s1 + s2 * s2 - coeff * s1 * s2
    return float(max(0.0, power)) / n


def tone_powers(audio, fs: float) -> np.ndarray:
    """Goertzel power at every standard CTCSS tone."""
    return np.array([goertzel_power(audio, fs, t) for t in CTCSS_TONES])


def detect_ctcss(audio, fs: float, *, min_ratio: float = 10.0):
    """Detect the CTCSS tone in FM audio, or None.

    Returns the strongest standard tone when its Goertzel power exceeds
    `min_ratio` × the median of the others (i.e. it clearly dominates), else
    None. `confidence` reflects that dominance.
    """
    x = np.asarray(audio, dtype=np.float64)
    if x.size < _MIN_SAMPLES or fs <= 0:
        return None
    # Remove DC / very-low drift so the 67 Hz Goertzel isn't biased by offset.
    x = x - float(np.mean(x))
    powers = tone_powers(x, fs)
    idx = int(np.argmax(powers))
    peak = powers[idx]
    if peak <= 0:
        return None
    others = np.delete(powers, idx)
    ref = float(np.median(others)) or 1e-12
    ratio = peak / ref
    if ratio < min_ratio:
        return None
    conf = 1.0 - (ref / peak)        # →1 as the peak dominates
    return CTCSSResult(tone_hz=CTCSS_TONES[idx], index=idx,
                       confidence=round(float(conf), 3))


def nearest_tone(freq_hz: float) -> float:
    """Snap an arbitrary sub-audible frequency to the nearest standard tone."""
    return min(CTCSS_TONES, key=lambda t: abs(t - float(freq_hz)))
