# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/live_analysis.py — the live SDR-frame → analysis pump.

Frames are synthetic power-in-dB spectra shaped exactly like sdr_tab's FFT
output: a flat noise floor with strong peaks, centred on center_hz spanning
sample_rate.
"""
import pytest

from core.live_analysis import SurveyEngine, Detection
from core.signal_model import SignalStore
from core.soi_snoi import WatchList, SOI, SNOI

CENTER = 100_000_000        # 100 MHz
RATE = 2_048_000            # 2.048 Msps
NBINS = 1024                # → bin_hz = 2000 Hz


def _frame(peak_bins, floor=-100.0, peak=-40.0, n=NBINS, width=3):
    """Flat floor with peaks `width` bins wide (real signals span >1 bin)."""
    p = [floor] * n
    half = width // 2
    for b in peak_bins:
        for i in range(b - half, b + half + 1):
            if 0 <= i < n:
                p[i] = peak
    return p


def _bin_freq(b, center=CENTER, rate=RATE, n=NBINS):
    start = center - rate // 2
    return int(start + b * (rate / n))


# ── geometry ──────────────────────────────────────────────────────────────────

class TestGeometry:
    def test_frame_geometry_matches_fft_layout(self):
        start, bin_hz = SurveyEngine.frame_geometry(NBINS, CENTER, RATE)
        assert start == CENTER - RATE // 2
        assert bin_hz == RATE / NBINS

    def test_bin_maps_to_expected_frequency(self):
        # bin 512 (centre) ≈ CENTER
        start, bin_hz = SurveyEngine.frame_geometry(NBINS, CENTER, RATE)
        assert abs((start + 512 * bin_hz) - CENTER) < bin_hz


# ── detection ─────────────────────────────────────────────────────────────────

class TestDetect:
    def test_detects_a_peak(self):
        eng = SurveyEngine(ingest=False)
        dets = eng.offer_frame(_frame([600]), CENTER, RATE)
        assert len(dets) == 1
        assert isinstance(dets[0], Detection)
        # detected near the bin-600 frequency
        assert abs(dets[0].signal.freq_hz - _bin_freq(600)) < 5000

    def test_quiet_frame_no_detections(self):
        eng = SurveyEngine(ingest=False)
        assert eng.offer_frame(_frame([]), CENTER, RATE) == []

    def test_multiple_peaks(self):
        eng = SurveyEngine(ingest=False)
        dets = eng.offer_frame(_frame([300, 700]), CENTER, RATE)
        assert len(dets) == 2

    def test_records_into_store(self):
        store = SignalStore(":memory:")
        eng = SurveyEngine(store=store, ingest=True)
        eng.offer_frame(_frame([600]), CENTER, RATE)
        assert store.count_total() == 1
        assert store.recent()[0].source == "survey"

    def test_frames_seen_and_last_detections(self):
        eng = SurveyEngine(ingest=False)
        eng.offer_frame(_frame([600]), CENTER, RATE)
        eng.offer_frame(_frame([]), CENTER, RATE)
        assert eng.frames_seen == 2
        assert eng.last_detections == []


# ── SOI / SNOI integration ────────────────────────────────────────────────────

class TestWatchList:
    def test_snoi_signal_dropped(self):
        wl = WatchList()
        f = _bin_freq(600)
        wl.add_range(f - 20_000, f + 20_000, SNOI, "ignore me")
        eng = SurveyEngine(ingest=False, watchlist=wl)
        assert eng.offer_frame(_frame([600]), CENTER, RATE) == []

    def test_soi_signal_tagged(self):
        wl = WatchList()
        f = _bin_freq(600)
        wl.add_range(f - 20_000, f + 20_000, SOI, "watch me")
        eng = SurveyEngine(ingest=False, watchlist=wl)
        dets = eng.offer_frame(_frame([600]), CENTER, RATE)
        assert len(dets) == 1
        assert dets[0].interest == SOI

    def test_untagged_signal_is_other(self):
        eng = SurveyEngine(ingest=False, watchlist=WatchList())
        dets = eng.offer_frame(_frame([600]), CENTER, RATE)
        assert dets[0].interest == "other"


# ── baseline accumulation + compare ───────────────────────────────────────────

class TestBaseline:
    def test_accumulates_across_a_sweep(self):
        eng = SurveyEngine(ingest=False)
        # two frames at different tuned centres (a sweep) build one wideband base
        eng.offer_frame(_frame([600]), CENTER, RATE)
        eng.offer_frame(_frame([600]), CENTER + RATE, RATE)
        assert eng.baseline is not None
        assert eng.baseline.n_sweeps == 2
        assert len(eng.baseline.segments) == 2      # a signal in each chunk

    def test_snapshot_returns_labelled_copy(self):
        eng = SurveyEngine(ingest=False)
        eng.offer_frame(_frame([600]), CENTER, RATE)
        snap = eng.snapshot(label="site-A")
        assert snap is not None and snap.label == "site-A"
        # a copy — mutating the engine doesn't change the snapshot
        eng.reset()
        assert len(snap.segments) == 1

    def test_snapshot_none_when_empty(self):
        assert SurveyEngine(ingest=False).snapshot() is None

    def test_compare_to_reference_surfaces_new_signal(self):
        eng = SurveyEngine(ingest=False)
        eng.offer_frame(_frame([300]), CENTER, RATE)     # reference env
        reference = eng.snapshot("ref")
        eng.reset()
        eng.offer_frame(_frame([300, 700]), CENTER, RATE)  # a new emitter at 700
        diff = eng.compare_to(reference)
        assert diff is not None
        assert diff.anomaly_count == 1                    # the bin-700 signal

    def test_compare_honours_snoi(self):
        wl = WatchList()
        f = _bin_freq(700)
        wl.add_range(f - 20_000, f + 20_000, SNOI, "ignore new one")
        eng = SurveyEngine(ingest=False, watchlist=wl)
        eng.offer_frame(_frame([300]), CENTER, RATE)
        reference = eng.snapshot("ref")
        eng.reset()
        eng.offer_frame(_frame([300, 700]), CENTER, RATE)
        diff = eng.compare_to(reference)
        assert diff.new == []                            # SNOI-suppressed

    def test_reset_clears(self):
        eng = SurveyEngine(ingest=False)
        eng.offer_frame(_frame([600]), CENTER, RATE)
        eng.reset()
        assert eng.baseline is None and eng.frames_seen == 0


# ── robustness ────────────────────────────────────────────────────────────────

class TestRobustness:
    def test_bad_frames_are_safe(self):
        eng = SurveyEngine(ingest=False)
        assert eng.offer_frame([], CENTER, RATE) == []
        assert eng.offer_frame([1, 2], CENTER, RATE) == []
        assert eng.offer_frame(_frame([600]), CENTER, 0) == []

    def test_compare_none_when_no_data(self):
        assert SurveyEngine(ingest=False).compare_to(None) is None
