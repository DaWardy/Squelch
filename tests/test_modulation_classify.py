# Squelch — RF / SDR signal platform
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/modulation_classify.py — heuristic IQ modulation classifier.

Deterministic synthetic signals (seeded, numpy-only — no scipy) exercise each
modulation. Clean signals must classify to the correct label; noisy variants
and edge cases must not crash and must return a valid label.
"""

import numpy as np
import pytest

from core.modulation_classify import (
    classify_modulation, extract_features,
    NONE, CW, AM, SSB, FM, OOK, FSK, PSK, OFDM,
)

FS = 48000.0
N = 8192
_ALL = {NONE, CW, AM, SSB, FM, OOK, FSK, PSK, OFDM}


def _t():
    return np.arange(N) / FS


def _noise(rng, p=0.02):
    return (rng.standard_normal(N) + 1j * rng.standard_normal(N)) * p / np.sqrt(2)


def _audio(t, fm=300.0):
    return 0.8 * np.cos(2 * np.pi * fm * t) + 0.2 * np.cos(2 * np.pi * 3 * fm * t)


def _analytic(x):
    """FFT-based analytic (Hilbert) signal — numpy-only, no scipy."""
    n = x.size
    X = np.fft.fft(x)
    h = np.zeros(n)
    h[0] = 1
    h[1:n // 2] = 2
    h[n // 2] = 1
    return np.fft.ifft(X * h)


def _gen(kind, rng, npow=0.02):
    t = _t()
    if kind == "noise":
        return _noise(rng, 1.0)
    if kind == "cw":
        return np.exp(2j * np.pi * 2000 * t) + _noise(rng, npow)
    if kind == "cw_keyed":
        keys = (np.arange(N) % 1024 < 512).astype(float)   # deterministic 50%
        return keys * np.exp(2j * np.pi * 2000 * t) + _noise(rng, npow)
    if kind == "am":
        return (1 + 0.7 * _audio(t)) * np.exp(2j * np.pi * 1000 * t) + _noise(rng, npow)
    if kind == "ssb":
        a = _audio(t, 500) + 0.5 * _audio(t, 1200)
        return _analytic(a) * np.exp(2j * np.pi * 800 * t) + _noise(rng, npow)
    if kind == "fm":
        ph = 2 * np.pi * np.cumsum(1000 + 3000 * _audio(t)) / FS
        return np.exp(1j * ph) + _noise(rng, npow)
    if kind == "ook":
        bits = (np.arange(N) % 256 < 128).astype(float)     # deterministic, faster
        return bits * np.exp(2j * np.pi * 1500 * t) + _noise(rng, npow)
    if kind == "fsk":
        bits = np.repeat(rng.integers(0, 2, N // 256), 256)[:N]
        ph = 2 * np.pi * np.cumsum(np.where(bits == 0, -1500.0, 1500.0)) / FS
        return np.exp(1j * ph) + _noise(rng, npow)
    if kind == "psk":
        bits = np.repeat(rng.integers(0, 2, N // 256), 256)[:N]
        return np.where(bits == 0, 1.0, -1.0) * np.exp(2j * np.pi * 1000 * t) + _noise(rng, npow)
    if kind == "ofdm":
        nsub, sym = 52, 128
        out = np.zeros(N, dtype=complex)
        k = np.arange(-nsub // 2, nsub // 2)
        for s in range(0, N, sym):
            data = (rng.integers(0, 2, nsub) * 2 - 1) + 1j * (rng.integers(0, 2, nsub) * 2 - 1)
            seg = np.zeros(min(sym, N - s), dtype=complex)
            tt = np.arange(seg.size) / FS
            for ki, d in zip(k, data):
                seg += d * np.exp(2j * np.pi * (ki * 250) * tt)
            out[s:s + seg.size] = seg
        return out / np.sqrt(nsub) + _noise(rng, 0.05)
    raise ValueError(kind)


# The 8 clearly-separable classes are asserted exactly. CW-keyed vs OOK/ASK is
# the same on/off-keyed family (keying-rate distinction only) — asserted as
# membership below.
_EXPECT = [
    ("noise", NONE), ("cw", CW), ("am", AM), ("ssb", SSB),
    ("fm", FM), ("fsk", FSK), ("psk", PSK), ("ofdm", OFDM),
]
_ALL_KINDS = _EXPECT + [("cw_keyed", CW), ("ook", OOK)]


class TestCleanSignals:
    @pytest.mark.parametrize("kind,expected", _EXPECT)
    def test_classifies_correctly(self, kind, expected):
        rng = np.random.default_rng(1)
        r = classify_modulation(_gen(kind, rng), FS)
        assert r.modulation == expected, (
            f"{kind}: got {r.modulation} ({r.note}); "
            f"features={r.features}")

    @pytest.mark.parametrize("kind", ["cw_keyed", "ook"])
    def test_on_off_keyed_family(self, kind):
        # Same underlying modulation; either label is acceptable.
        rng = np.random.default_rng(1)
        r = classify_modulation(_gen(kind, rng), FS)
        assert r.modulation in {CW, OOK}, f"{kind} -> {r.modulation}"

    @pytest.mark.parametrize("kind,expected", _ALL_KINDS)
    def test_confidence_in_range(self, kind, expected):
        rng = np.random.default_rng(7)
        r = classify_modulation(_gen(kind, rng), FS)
        assert 0.0 <= r.confidence <= 1.0

    def test_deterministic_for_same_seed(self):
        a = classify_modulation(_gen("fsk", np.random.default_rng(3)), FS)
        b = classify_modulation(_gen("fsk", np.random.default_rng(3)), FS)
        assert a.modulation == b.modulation


class TestRobustness:
    @pytest.mark.parametrize("kind", ["cw", "am", "fm", "fsk", "ook"])
    def test_noisy_does_not_crash_and_returns_valid_label(self, kind):
        rng = np.random.default_rng(5)
        # heavy noise — result may be wrong but must be a valid label, no crash
        r = classify_modulation(_gen(kind, rng, npow=0.5), FS)
        assert r.modulation in _ALL

    def test_empty_returns_none(self):
        assert classify_modulation(np.array([], dtype=complex), FS).modulation == NONE

    def test_too_short_returns_none(self):
        assert classify_modulation(np.ones(16, dtype=complex), FS).modulation == NONE

    def test_all_zero_returns_none(self):
        assert classify_modulation(np.zeros(N, dtype=complex), FS).modulation == NONE

    def test_zero_fs_returns_none(self):
        rng = np.random.default_rng(1)
        assert classify_modulation(_gen("cw", rng), 0.0).modulation == NONE

    def test_nan_input_does_not_crash(self):
        x = np.full(N, np.nan, dtype=complex)
        assert classify_modulation(x, FS).modulation in _ALL


class TestFeatures:
    def test_extract_returns_features(self):
        rng = np.random.default_rng(1)
        f = extract_features(_gen("fm", rng), FS)
        assert f.amp_cv < 0.2          # FM is constant-envelope
        assert 0.0 <= f.occ_bw <= 1.0
        assert 0.0 <= f.spectral_flatness <= 1.0

    def test_fsk_is_bimodal_high_duty(self):
        rng = np.random.default_rng(1)
        f = extract_features(_gen("fsk", rng), FS)
        assert f.freq_bimodality > 0.55 and f.freq_duty > 0.55

    def test_psk_is_low_duty(self):
        rng = np.random.default_rng(1)
        f = extract_features(_gen("psk", rng), FS)
        assert f.freq_duty < 0.35      # spikes at transitions, not held
