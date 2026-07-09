# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/fhss_detect.py — frequency-hopping emitter detection."""
import pytest

from core.fhss_detect import (
    detect_hopping, observations_from, HopSet, _channelise,
)

# 5 channels ~1 MHz apart
CHANNELS = [433_000_000, 434_000_000, 435_000_000, 436_000_000, 437_000_000]


def _hopper(n_hops=40, dwell=0.05):
    """One emitter hopping through CHANNELS, one obs per dwell slot."""
    obs = []
    for i in range(n_hops):
        obs.append((i * dwell, CHANNELS[i % len(CHANNELS)]))
    return obs


def _static_multi(n_frames=40, dwell=0.05):
    """All 5 channels present in every frame (static signals)."""
    obs = []
    for i in range(n_frames):
        for ch in CHANNELS:
            obs.append((i * dwell, ch))
    return obs


# ── the core discriminator ────────────────────────────────────────────────────

class TestHopperVsStatic:
    def test_detects_a_hopper(self):
        hs = detect_hopping(_hopper())
        assert hs is not None
        assert hs.n_channels == 5
        assert set(hs.channels) == set(CHANNELS)
        assert hs.hop_count >= 6

    def test_rejects_static_multi_signal(self):
        # all 5 channels active every frame → high simultaneity → not hopping
        assert detect_hopping(_static_multi()) is None

    def test_hop_rate_and_dwell(self):
        hs = detect_hopping(_hopper(n_hops=40, dwell=0.05))
        # ~20 hops/s at 50 ms dwell
        assert 15 < hs.hop_rate < 25
        assert 0.03 < hs.dwell_s < 0.07

    def test_freq_range(self):
        hs = detect_hopping(_hopper())
        assert hs.freq_lo == 433_000_000
        assert hs.freq_hi == 437_000_000


# ── thresholds ────────────────────────────────────────────────────────────────

class TestThresholds:
    def test_too_few_channels(self):
        # only 2 channels → below min_channels
        obs = [(i * 0.05, CHANNELS[i % 2]) for i in range(20)]
        assert detect_hopping(obs) is None

    def test_too_few_hops(self):
        obs = [(i * 0.05, CHANNELS[i % 5]) for i in range(5)]  # < min_hops
        assert detect_hopping(obs, min_hops=6) is None

    def test_single_static_signal(self):
        obs = [(i * 0.05, 433_000_000) for i in range(40)]
        assert detect_hopping(obs) is None

    def test_custom_min_channels(self):
        obs = [(i * 0.05, CHANNELS[i % 3]) for i in range(30)]
        assert detect_hopping(obs, min_channels=3) is not None
        assert detect_hopping(obs, min_channels=5) is None

    def test_channel_tolerance_merges_near_freqs(self):
        # jitter within tolerance should collapse to one channel
        obs = [(i * 0.05, CHANNELS[i % 5] + (i % 3) * 1000) for i in range(40)]
        hs = detect_hopping(obs, freq_tol_hz=25_000)
        assert hs.n_channels == 5           # jitter didn't split channels


# ── bridge + extraction ───────────────────────────────────────────────────────

class TestBridge:
    def test_to_signal(self):
        hs = detect_hopping(_hopper())
        sig = hs.to_signal()
        assert sig.source == "fhss"
        assert sig.classification == "frequency-hopping"
        assert 433_000_000 <= sig.freq_hz <= 437_000_000
        assert "fhss" in sig.tags

    def test_observations_from_dicts(self):
        items = [{"t": 0.0, "freq_hz": 433_000_000},
                 {"t": 0.05, "freq_hz": 434_000_000},
                 {"t": 0.1, "freq_hz": 0}]           # no freq → skipped
        obs = observations_from(items)
        assert obs == [(0.0, 433_000_000), (0.05, 434_000_000)]

    def test_observations_from_objects(self):
        class S:
            def __init__(self, t, f):
                self.t = t
                self.freq_hz = f
        obs = observations_from([S(1.0, 435_000_000)])
        assert obs == [(1.0, 435_000_000)]


# ── channelisation + robustness ───────────────────────────────────────────────

class TestHelpersRobustness:
    def test_channelise_clusters(self):
        m = _channelise([433_000_000, 433_010_000, 435_000_000], 25_000)
        assert m[433_000_000] == m[433_010_000]      # within tol → same channel
        assert m[435_000_000] != m[433_000_000]

    def test_empty_and_none_safe(self):
        assert detect_hopping([]) is None
        assert detect_hopping(None) is None
        assert observations_from(None) == []

    def test_zero_freqs_skipped(self):
        assert detect_hopping([(i * 0.05, 0) for i in range(40)]) is None
