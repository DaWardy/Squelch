# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/measure.py — signal measurement (SNR / BW / offset / PAPR)."""
import numpy as np
import pytest

from core.measure import (
    measure_spectrum, measure_iq, SignalMeasurement, _noise_floor_db,
)

FS = 1_000_000.0
NFFT = 4096


# ── spectrum measurement ──────────────────────────────────────────────────────

class TestMeasureSpectrum:
    def _spec(self, peak_bins, floor=-100.0, peak=-40.0, n=1000):
        p = np.full(n, floor)
        for b in peak_bins:
            p[b] = peak
        return p

    def test_snr_from_peak_and_floor(self):
        m = measure_spectrum(self._spec([500]), 100_000_000, 1000.0)
        assert abs(m.snr_db - 60.0) < 1.0        # -40 peak over -100 floor
        assert abs(m.noise_floor_db - (-100.0)) < 1.0
        assert abs(m.peak_db - (-40.0)) < 0.1

    def test_center_offset_zero_when_centred(self):
        n = 1001
        m = measure_spectrum(self._spec([500], n=n), 0, 1000.0)
        assert abs(m.center_offset_hz) < 1500     # signal at the centre bin

    def test_center_offset_detects_shift(self):
        n = 1001
        # signal well right of centre (bin 800 vs centre 500) → +300 bins
        m = measure_spectrum(self._spec([800], n=n), 0, 1000.0)
        assert m.center_offset_hz > 250_000

    def test_occupied_bandwidth(self):
        # a 20-bin-wide block at 1 kHz/bin ≈ 20 kHz occupied
        n = 1000
        p = np.full(n, -100.0)
        p[490:510] = -40.0
        m = measure_spectrum(p, 0, 1000.0)
        assert 15_000 <= m.occupied_bw_hz <= 25_000

    def test_flat_spectrum_no_signal(self):
        m = measure_spectrum(np.full(500, -95.0), 0, 1000.0)
        assert m.occupied_bw_hz == 0
        assert abs(m.snr_db) < 1.0

    def test_empty(self):
        m = measure_spectrum([], 0, 1000.0)
        assert m == SignalMeasurement()


# ── IQ measurement ────────────────────────────────────────────────────────────

class TestMeasureIq:
    def _tone(self, offset_hz, n=8192, amp=1.0, noise=0.0):
        t = np.arange(n) / FS
        iq = amp * np.exp(2j * np.pi * offset_hz * t)
        if noise:
            rng = np.random.default_rng(0)
            iq = iq + noise * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
        return iq.astype(np.complex64)

    def test_carrier_offset_detected(self):
        m = measure_iq(self._tone(100_000), FS)      # +100 kHz tone
        assert abs(m.center_offset_hz - 100_000) < 2_000

    def test_cw_tone_low_papr(self):
        # a pure complex tone is constant-envelope → PAPR ≈ 0 dB
        m = measure_iq(self._tone(50_000), FS)
        assert m.papr_db < 1.0

    def test_noise_higher_papr(self):
        rng = np.random.default_rng(1)
        noise = (rng.standard_normal(8192)
                 + 1j * rng.standard_normal(8192)).astype(np.complex64)
        m = measure_iq(noise, FS)
        assert m.papr_db > 5.0                       # Gaussian noise peaks well above avg

    def test_snr_positive_for_tone_in_noise(self):
        m = measure_iq(self._tone(0, amp=1.0, noise=0.05), FS)
        assert m.snr_db > 10.0

    def test_rms_dbfs_reasonable(self):
        m = measure_iq(self._tone(0, amp=1.0), FS)
        assert -1.0 < m.rms_dbfs < 1.0               # unit-amplitude tone ≈ 0 dBFS

    def test_too_short(self):
        assert measure_iq(np.ones(2, np.complex64), FS) == SignalMeasurement()

    def test_zero_fs(self):
        assert measure_iq(self._tone(0), 0.0) == SignalMeasurement()


# ── helper ────────────────────────────────────────────────────────────────────

def test_noise_floor_percentile():
    vals = np.array([-100.0] * 90 + [-40.0] * 10)   # 90% floor, 10% signal
    assert abs(_noise_floor_db(vals, 25.0) - (-100.0)) < 0.1
