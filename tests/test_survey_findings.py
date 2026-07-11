# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for SurveyEngine findings — running FHSS + emitter correlation over the
whole sweep (pipeline composition)."""
import pytest

from core.live_analysis import SurveyEngine
from core.signal_model import SignalStore

CENTER = 433_500_000
RATE = 2_048_000
NBINS = 1024


def _frame(peak_bins, floor=-100.0, peak=-40.0, n=NBINS, width=3):
    p = [floor] * n
    half = width // 2
    for b in peak_bins:
        for i in range(b - half, b + half + 1):
            if 0 <= i < n:
                p[i] = peak
    return p


def _bin_freq(b, center=CENTER, rate=RATE, n=NBINS):
    return int((center - rate // 2) + b * (rate / n))


# ── frequency-hopper across a sweep ───────────────────────────────────────────

class TestHopperFindings:
    def test_detects_a_hopper_across_frames(self):
        eng = SurveyEngine(ingest=False)
        hop_bins = [200, 350, 500, 650, 800]      # 5 well-separated channels
        # each frame at a new time shows the hopper on one channel
        for i in range(40):
            eng.offer_frame(_frame([hop_bins[i % 5]]), CENTER, RATE,
                            t=i * 0.05)
        hs = eng.detect_hoppers()
        assert hs is not None
        assert hs.n_channels == 5

    def test_no_hopper_for_static_signals(self):
        eng = SurveyEngine(ingest=False)
        for i in range(40):
            # 5 static signals present every frame → not hopping
            eng.offer_frame(_frame([200, 350, 500, 650, 800]), CENTER, RATE,
                            t=i * 0.05)
        assert eng.detect_hoppers() is None

    def test_observations_cleared_on_reset(self):
        eng = SurveyEngine(ingest=False)
        eng.offer_frame(_frame([500]), CENTER, RATE, t=0.0)
        eng.reset()
        assert eng.detect_hoppers() is None       # no observations left


# ── emitter correlation over the sweep ────────────────────────────────────────

class TestEmitterFindings:
    def test_correlates_from_store(self):
        store = SignalStore(":memory:")
        eng = SurveyEngine(store=store, ingest=True)
        # a repeated signal on one channel merges → one emitter
        for i in range(5):
            eng.offer_frame(_frame([500]), CENTER, RATE, t=i * 0.1)
        emitters = eng.correlate_emitters()
        assert len(emitters) == 1
        assert emitters[0].n_observations >= 5

    def test_correlates_without_store(self):
        eng = SurveyEngine(ingest=False)           # no store → uses signal log
        for i in range(4):
            eng.offer_frame(_frame([300]), CENTER, RATE, t=i * 0.1)
        emitters = eng.correlate_emitters()
        assert len(emitters) >= 1

    def test_default_time_is_frame_index(self):
        # without an explicit t, the frame index is used as the timestamp
        eng = SurveyEngine(ingest=False)
        hop_bins = [200, 350, 500, 650, 800]
        for i in range(40):
            eng.offer_frame(_frame([hop_bins[i % 5]]), CENTER, RATE)  # no t
        hs = eng.detect_hoppers()
        assert hs is not None and hs.n_channels == 5
