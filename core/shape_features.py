# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/shape_features.py

Signal shape / timing features (ROADMAP §13.4 foundation). Identification today
keys on frequency + bandwidth + modulation, but a huge amount of what makes a
signal recognisable — the way SigIDWiki/Artemis humans do it — is its *behaviour*
over time: is it a continuous carrier, or bursty? What's the duty cycle? How many
bursts, how long? This extracts those time-domain shape features from an IQ slice
so the workbench can say "bursty, ~40% duty, 6 bursts" alongside the modulation —
a strong extra discriminator (e.g. paging vs a data link vs a voice repeater).

Pure numpy, never raises (returns a neutral ShapeFeatures on bad input). Envelope
based: threshold the amplitude between its noise floor and peak, then measure the
on/off structure. Hopping across frequency is a separate concern handled over a
whole sweep by `core/fhss_detect`.
"""

import logging
from dataclasses import dataclass

import numpy as np

log = logging.getLogger(__name__)


@dataclass
class ShapeFeatures:
    duty_cycle:    float = 0.0     # fraction of time the signal is "on"
    is_continuous: bool  = False   # steady carrier (low amplitude variation)
    is_bursty:     bool  = False   # on/off keyed / packetised
    burst_count:   int   = 0       # number of on-intervals in the slice
    mean_burst_ms: float = 0.0     # average on-interval length
    contrast:      float = 0.0     # (peak-floor)/peak amplitude contrast

    def label(self) -> str:
        if self.is_continuous:
            return "continuous"
        if self.is_bursty:
            return f"bursty ~{self.duty_cycle * 100:.0f}% ({self.burst_count} bursts)"
        return ""


def analyze_shape(iq, fs: float, *, contrast_floor: float = 0.25) -> ShapeFeatures:
    """Time-domain shape of an IQ slice → ShapeFeatures. Never raises.

    `contrast_floor`: below this amplitude contrast the signal is treated as a
    continuous carrier (duty 1.0) rather than threshold-sliced into bursts."""
    f = ShapeFeatures()
    try:
        env = np.abs(np.asarray(iq, dtype=np.complex64))
        if env.size < 8 or fs <= 0:
            return f
        # Smooth the envelope (~0.5 ms) so random noise micro-crossings don't
        # read as bursts; real on/off bursts (ms+) survive.
        win = int(max(8, min(env.size // 4, fs * 0.0005)))
        if win > 1:
            env = np.convolve(env, np.ones(win) / win, mode="same")
        peak = float(np.percentile(env, 95))
        floor = float(np.percentile(env, 20))
        if peak <= 1e-12:
            return f                                # silence
        f.contrast = round((peak - floor) / peak, 3)
        if f.contrast < contrast_floor:
            # steady amplitude → continuous carrier
            f.duty_cycle = 1.0
            f.is_continuous = True
            f.burst_count = 1
            f.mean_burst_ms = round(len(env) / fs * 1000.0, 2)
            return f
        thr = floor + 0.5 * (peak - floor)
        on = env > thr
        f.duty_cycle = round(float(np.mean(on)), 3)
        onb = on.astype(np.int8)
        rising = int(np.sum((onb[1:] == 1) & (onb[:-1] == 0)))
        if onb[0] == 1:
            rising += 1
        f.burst_count = rising
        on_samples = int(np.sum(onb))
        if rising > 0:
            f.mean_burst_ms = round(on_samples / rising / fs * 1000.0, 3)
        f.is_continuous = f.duty_cycle > 0.95
        f.is_bursty = (rising >= 2) and (0.02 < f.duty_cycle < 0.95)
        return f
    except Exception as exc:                        # pragma: no cover
        log.debug("analyze_shape failed: %s", exc)
        return f
