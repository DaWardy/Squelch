# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/measure.py

Signal measurement — turn a spectrum frame or an IQ chunk into the numbers that
characterise a detection: SNR, occupied bandwidth, how far its energy sits off
the band centre, and (for IQ) peak-to-average power ratio and RMS level. These
enrich every Signal record so the browser / survey can say "−18 dB SNR, 12.5 kHz
wide, +3 kHz off centre, 1 dB PAPR" instead of just "occupied", and they feed
the modulation heuristics.

`measure_spectrum(powers_db, start_hz, bin_hz)` works on the same power-in-dB
FFT frame the survey/SDR produce; `measure_iq(iq, fs)` computes the spectrum
first and adds the time-domain PAPR/RMS. Pure numpy, never raises.
"""

import logging
from dataclasses import dataclass

import numpy as np

log = logging.getLogger(__name__)


@dataclass
class SignalMeasurement:
    snr_db:           float = 0.0
    noise_floor_db:   float = 0.0
    peak_db:          float = 0.0
    occupied_bw_hz:   int   = 0
    center_offset_hz: float = 0.0      # energy centroid − band centre
    papr_db:          float = 0.0      # peak/avg power (IQ only)
    rms_dbfs:         float = 0.0      # RMS level rel. full scale (IQ only)


def _noise_floor_db(powers, percentile: float = 25.0) -> float:
    vals = np.sort(np.asarray(powers, dtype=np.float64))
    if vals.size == 0:
        return 0.0
    idx = int(round(np.clip(percentile, 0, 100) / 100.0 * (vals.size - 1)))
    return float(vals[idx])


def measure_spectrum(powers_db, start_hz: int, bin_hz: float, *,
                     floor_percentile: float = 25.0,
                     occ_frac: float = 0.99) -> SignalMeasurement:
    """Measure a power spectrum (dB per bin). `powers_db[i]` is centred at
    `start_hz + i*bin_hz`."""
    p = np.asarray(powers_db, dtype=np.float64)
    if p.size == 0 or bin_hz <= 0:
        return SignalMeasurement()
    floor = _noise_floor_db(p, floor_percentile)
    peak = float(p.max())
    m = SignalMeasurement(snr_db=round(peak - floor, 2),
                          noise_floor_db=round(floor, 2),
                          peak_db=round(peak, 2))

    # Signal power above the noise floor, per bin (linear).
    lin = 10.0 ** (p / 10.0)
    sig = np.maximum(lin - 10.0 ** (floor / 10.0), 0.0)
    total = float(sig.sum())
    n = p.size
    band_centre = start_hz + (n - 1) / 2.0 * bin_hz
    if total <= 0:
        return m

    cum = np.cumsum(sig) / total
    tail = (1.0 - occ_frac) / 2.0
    lo = int(np.searchsorted(cum, tail))
    hi = int(np.searchsorted(cum, 1.0 - tail))
    m.occupied_bw_hz = int(max(0, hi - lo) * bin_hz)

    centroid_bin = float(np.sum(np.arange(n) * sig) / total)
    centroid_hz = start_hz + centroid_bin * bin_hz
    m.center_offset_hz = round(centroid_hz - band_centre, 1)
    return m


def measure_iq(iq, fs: float, *, n_fft: int = 4096,
               occ_frac: float = 0.99) -> SignalMeasurement:
    """Measure an IQ chunk: spectrum-derived SNR / occupied BW / carrier offset,
    plus time-domain PAPR and RMS level."""
    x = np.asarray(iq, dtype=np.complex64)
    if x.size < 4 or fs <= 0:
        return SignalMeasurement()

    # Spectrum (Hann-windowed), centred at DC → offset is relative to the tune.
    win = np.hanning(min(x.size, n_fft))
    seg = x[:win.size] * win
    spec = np.fft.fftshift(np.abs(np.fft.fft(seg, n_fft)))
    powers_db = 20.0 * np.log10(spec / n_fft + 1e-12)
    bin_hz = fs / n_fft
    start_hz = int(-fs // 2)
    m = measure_spectrum(powers_db, start_hz, bin_hz, occ_frac=occ_frac)

    # Time-domain power metrics.
    p_inst = (np.abs(x) ** 2).astype(np.float64)
    avg = float(p_inst.mean())
    if avg > 0:
        m.papr_db = round(10.0 * np.log10(float(p_inst.max()) / avg), 2)
        m.rms_dbfs = round(10.0 * np.log10(avg), 2)
    return m
