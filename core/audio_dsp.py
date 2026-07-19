# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/audio_dsp.py

Audio-domain DSP for the demodulator output (ROADMAP §14.5, SDR-Console DSP
parity). Sits after `core/demod.demodulate`:

  * `notch(audio, sr, freq_hz, width_hz)` — **manual notch**: remove a narrow
    band around a chosen frequency (kill one steady tone / carrier).
  * `auto_notch(audio, sr, …)` — **auto-notch**: find the strong, narrow
    heterodyne tones that stick up out of the audio (the classic "tuning
    whistle") and notch each, leaving broadband speech untouched. Returns the
    cleaned audio and the frequencies it removed.

FFT-domain (rfft → zero the band → irfft): vectorised, no scipy, no new deps,
and easy to reason about. Pure numpy, float32 in/out, never raises — an audio
filter must not kill the receiver. Ready to drop into the audio path when it
lands; independently testable now with synthetic tones.
"""

import logging

import numpy as np

log = logging.getLogger(__name__)

DEFAULT_WIDTH_HZ = 120.0
# A real het whistle stands 25-50 dB above the noise; the max bin of a large
# noise FFT is only ~10-14 dB above its local mean, so 20 dB cleanly separates
# tones from noise without a Welch average.
DEFAULT_PROMINENCE_DB = 20.0


# ── manual notch ─────────────────────────────────────────────────────────────
def notch(audio, sample_rate: float, freq_hz: float,
          width_hz: float = DEFAULT_WIDTH_HZ) -> np.ndarray:
    """Remove a narrow band (±width/2) around `freq_hz`. Never raises."""
    try:
        a = np.asarray(audio, dtype=float)
        n = a.size
        if n < 8 or freq_hz <= 0 or sample_rate <= 0:
            return a.astype(np.float32)
        spec = np.fft.rfft(a)
        freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)
        spec[np.abs(freqs - freq_hz) <= width_hz / 2.0] = 0.0
        return np.fft.irfft(spec, n).astype(np.float32)
    except Exception as exc:                        # pragma: no cover
        log.debug("notch failed: %s", exc)
        return np.asarray(audio, dtype=np.float32)


# ── auto-notch ───────────────────────────────────────────────────────────────
def auto_notch(audio, sample_rate: float, *, max_notches: int = 3,
               prominence_db: float = DEFAULT_PROMINENCE_DB,
               width_hz: float = DEFAULT_WIDTH_HZ,
               min_hz: float = 200.0, max_hz: float = 0.0) -> tuple:
    """Detect and remove strong narrowband tones. Returns (audio, [freqs_hz]).

    A "tone" is a bin whose magnitude stands `prominence_db` above the locally
    smoothed spectrum — steady het whistles do, broadband speech does not."""
    try:
        a = np.asarray(audio, dtype=float)
        n = a.size
        if n < 16 or sample_rate <= 0:
            return a.astype(np.float32), []
        freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)
        mag_db = 20.0 * np.log10(np.abs(np.fft.rfft(a)) + 1e-12)
        prominence = mag_db - _smooth(mag_db, freqs, span_hz=400.0)
        hi = max_hz if max_hz and max_hz > 0 else sample_rate / 2.0
        removed = _pick_tones(freqs, prominence, prominence_db,
                              max_notches, width_hz, min_hz, hi)
        out = a.astype(np.float32)
        for f in removed:
            out = notch(out, sample_rate, f, width_hz)
        return out, removed
    except Exception as exc:                        # pragma: no cover
        log.debug("auto_notch failed: %s", exc)
        return np.asarray(audio, dtype=np.float32), []


def _pick_tones(freqs, prominence, prominence_db, max_n, width_hz,
                min_hz, max_hz) -> list:
    removed: list = []
    for idx in np.argsort(prominence)[::-1]:
        if prominence[idx] < prominence_db:
            break                              # sorted desc → nothing left
        f = float(freqs[idx])
        if f < min_hz or f > max_hz:
            continue
        if any(abs(f - rf) < width_hz for rf in removed):
            continue                           # already covered by a notch
        removed.append(f)
        if len(removed) >= max_n:
            break
    return removed


def _smooth(x, freqs, span_hz: float) -> np.ndarray:
    """Moving-average baseline over ~`span_hz` — the local spectral floor.

    Edge-corrected: divide by the true number of contributing taps at the
    spectrum ends, or the baseline dips at 0/Nyquist and fakes a tone there."""
    if len(freqs) < 2:
        return x
    bin_hz = float(freqs[1] - freqs[0]) or 1.0
    k = max(3, int(span_hz / bin_hz) | 1)          # odd window
    if k >= len(x):
        return np.full_like(x, float(np.mean(x)))
    ker = np.ones(k)
    num = np.convolve(x, ker, mode="same")
    den = np.convolve(np.ones_like(x), ker, mode="same")
    return num / den
