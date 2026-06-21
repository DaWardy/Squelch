# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/occupancy.py

Spectrum occupancy detection (ROADMAP Phase 1, SIG-SURVEY).

The hard, hardware-independent part of a wideband survey: turn a power
spectrum (one FFT frame, or an averaged/peak-held frame) into a list of
occupied-frequency *segments*. A live survey loop (tuning an SDR across a
range and accumulating frames) feeds frames in; each detected segment becomes
a `Signal` (source="survey") via core.signal_ingest.signal_from_occupancy.

Pure Python, no numpy — small, import-light, fully unit-tested.

Power values are in dB (dBFS or dBm — only relative levels matter here).
"""

import math
from dataclasses import dataclass


@dataclass
class OccupancySegment:
    """A contiguous run of spectrum bins above the detection threshold."""
    center_hz:    int
    bandwidth_hz: int
    peak_db:      float
    floor_db:     float
    snr_db:       float
    bin_lo:       int      # first bin index (inclusive)
    bin_hi:       int      # last bin index (inclusive)


def estimate_noise_floor(powers_db, percentile: float = 25.0) -> float:
    """Robust noise floor = the given percentile of the power values.

    A low percentile (default 25th) tracks the quiet baseline and ignores the
    occupied bins, which is more robust than mean/median on busy spectra.
    """
    vals = [float(p) for p in powers_db]
    if not vals:
        return 0.0
    vals.sort()
    pct = max(0.0, min(100.0, percentile))
    idx = int(round((pct / 100.0) * (len(vals) - 1)))
    return vals[idx]


def detect_segments(powers_db, start_hz: int, bin_hz: float, *,
                    threshold_db: float = 6.0,
                    min_width_bins: int = 1,
                    floor_db: float | None = None) -> list[OccupancySegment]:
    """Detect occupied segments in one power spectrum.

    `powers_db[i]` is the power of the bin centred at `start_hz + i*bin_hz`.
    A bin is "occupied" when it exceeds `floor + threshold_db` (floor is
    auto-estimated when not supplied). Contiguous occupied bins are merged;
    runs narrower than `min_width_bins` are dropped.
    """
    powers = [float(p) for p in powers_db]
    if not powers or bin_hz <= 0:
        return []
    floor = estimate_noise_floor(powers) if floor_db is None else float(floor_db)
    thresh = floor + threshold_db

    segments: list[OccupancySegment] = []
    run_start = None
    for i, p in enumerate(powers):
        if p >= thresh:
            if run_start is None:
                run_start = i
        elif run_start is not None:
            segments.append(_make_segment(
                powers, run_start, i - 1, start_hz, bin_hz, floor))
            run_start = None
    if run_start is not None:
        segments.append(_make_segment(
            powers, run_start, len(powers) - 1, start_hz, bin_hz, floor))

    return [s for s in segments
            if (s.bin_hi - s.bin_lo + 1) >= max(1, min_width_bins)]


def _make_segment(powers, lo: int, hi: int, start_hz: int,
                  bin_hz: float, floor: float) -> OccupancySegment:
    peak = max(powers[lo:hi + 1])
    width_bins = hi - lo + 1
    # Centre frequency = midpoint of the run's bin span.
    center = start_hz + (lo + hi) / 2.0 * bin_hz
    return OccupancySegment(
        center_hz=int(round(center)),
        bandwidth_hz=int(round(width_bins * bin_hz)),
        peak_db=round(peak, 2),
        floor_db=round(floor, 2),
        snr_db=round(peak - floor, 2),
        bin_lo=lo,
        bin_hi=hi,
    )


def occupancy_fraction(powers_db, *, threshold_db: float = 6.0,
                       floor_db: float | None = None) -> float:
    """Fraction of bins (0..1) that are occupied — a quick band-busy metric."""
    powers = [float(p) for p in powers_db]
    if not powers:
        return 0.0
    floor = estimate_noise_floor(powers) if floor_db is None else float(floor_db)
    thresh = floor + threshold_db
    return sum(1 for p in powers if p >= thresh) / len(powers)
