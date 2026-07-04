# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/rf_baseline.py — RF Baseline & Compare (the "hound" core)."""
import pytest

from core.rf_baseline import (
    Baseline, SignalDelta, BaselineDiff,
    baseline_from_spectrum, compare_baselines, anomalies_to_signals,
)
from core.occupancy import OccupancySegment

START = 100_000_000          # 100 MHz
BIN = 10_000.0               # 10 kHz/bin


def _spectrum(peaks_bins, floor=-100.0, peak=-40.0, n=200):
    """Flat noise floor with strong peaks at the given bin indices."""
    p = [floor] * n
    for b in peaks_bins:
        p[b] = peak
    return p


def _seg(center_hz, peak_db=-40.0, bw=10_000):
    return OccupancySegment(center_hz=center_hz, bandwidth_hz=bw,
                            peak_db=peak_db, floor_db=-100.0, snr_db=60.0,
                            bin_lo=0, bin_hi=0)


# ── snapshot construction ─────────────────────────────────────────────────────

class TestBaselineFromSpectrum:
    def test_detects_floor_and_segments(self):
        b = baseline_from_spectrum(_spectrum([50, 120]), START, BIN,
                                   label="lab")
        assert b.label == "lab"
        assert b.floor_db == pytest.approx(-100.0, abs=1.0)
        assert len(b.segments) == 2
        assert b.freq_lo_hz == START

    def test_freq_range(self):
        b = baseline_from_spectrum(_spectrum([10], n=100), START, BIN)
        assert b.freq_hi_hz == START + 99 * BIN

    def test_created_stamp(self):
        assert baseline_from_spectrum(_spectrum([]), START, BIN).created.endswith("Z")

    def test_empty_spectrum(self):
        b = baseline_from_spectrum([], START, BIN)
        assert b.segments == []


# ── compare: the core capability ──────────────────────────────────────────────

class TestCompare:
    def test_new_signal_is_anomaly(self):
        ref = baseline_from_spectrum(_spectrum([50]), START, BIN, label="empty")
        cur = baseline_from_spectrum(_spectrum([50, 130]), START, BIN,
                                     label="bugged")
        diff = compare_baselines(ref, cur)
        assert len(diff.new) == 1
        assert diff.new[0].kind == "new"
        # the new peak is at bin 130 → 100 MHz + 130*10kHz
        assert diff.new[0].center_hz == pytest.approx(START + 130 * BIN, abs=BIN)
        assert diff.anomaly_count == 1

    def test_missing_signal(self):
        ref = baseline_from_spectrum(_spectrum([50, 130]), START, BIN)
        cur = baseline_from_spectrum(_spectrum([50]), START, BIN)
        diff = compare_baselines(ref, cur)
        assert len(diff.missing) == 1
        assert diff.missing[0].kind == "missing"

    def test_unchanged_environment_no_anomalies(self):
        ref = baseline_from_spectrum(_spectrum([50, 130]), START, BIN)
        cur = baseline_from_spectrum(_spectrum([50, 130]), START, BIN)
        diff = compare_baselines(ref, cur)
        assert diff.anomaly_count == 0
        assert diff.new == [] and diff.missing == []

    def test_power_change_flagged(self):
        ref = baseline_from_spectrum(_spectrum([50], peak=-60.0), START, BIN)
        cur = baseline_from_spectrum(_spectrum([50], peak=-30.0), START, BIN)
        diff = compare_baselines(ref, cur, power_tol_db=6.0)
        assert len(diff.changed) == 1
        assert diff.changed[0].delta_db == pytest.approx(30.0, abs=2.0)

    def test_small_power_change_ignored(self):
        ref = baseline_from_spectrum(_spectrum([50], peak=-60.0), START, BIN)
        cur = baseline_from_spectrum(_spectrum([50], peak=-58.0), START, BIN)
        diff = compare_baselines(ref, cur, power_tol_db=6.0)
        assert diff.changed == []

    def test_floor_delta(self):
        ref = baseline_from_spectrum(_spectrum([], floor=-100.0), START, BIN)
        cur = baseline_from_spectrum(_spectrum([], floor=-90.0), START, BIN)
        diff = compare_baselines(ref, cur)
        assert diff.floor_delta_db == pytest.approx(10.0, abs=1.0)

    def test_snoi_ignore_range_suppresses_anomaly(self):
        ref = baseline_from_spectrum(_spectrum([50]), START, BIN)
        cur = baseline_from_spectrum(_spectrum([50, 130]), START, BIN)
        # ignore a band covering bin 130
        band = (START + 125 * BIN, START + 135 * BIN)
        diff = compare_baselines(ref, cur, ignore_ranges=[band])
        assert diff.new == []

    def test_freq_tolerance_matches_near_signals(self):
        ref = Baseline(segments=[_seg(146_520_000, peak_db=-40)])
        cur = Baseline(segments=[_seg(146_521_000, peak_db=-40)])   # 1 kHz off
        diff = compare_baselines(ref, cur, freq_tol_hz=5000)
        assert diff.new == [] and diff.missing == []               # matched


# ── labels + signal bridge ────────────────────────────────────────────────────

class TestLabelsAndBridge:
    def test_anomaly_carries_classification_label(self):
        # 146.52 MHz = 2m amateur simplex → known allocation label
        ref = Baseline(segments=[])
        cur = Baseline(segments=[_seg(146_520_000)])
        diff = compare_baselines(ref, cur)
        assert len(diff.new) == 1
        # label/category may be filled by the allocation classifier (best-effort)
        assert isinstance(diff.new[0].label, str)

    def test_anomalies_to_signals(self):
        ref = Baseline(segments=[])
        cur = Baseline(segments=[_seg(146_520_000, peak_db=-42)])
        diff = compare_baselines(ref, cur)
        sigs = anomalies_to_signals(diff)
        assert len(sigs) == 1
        assert sigs[0].source == "anomaly"
        assert sigs[0].freq_hz == 146_520_000
        assert sigs[0].rssi_dbm == -42
        assert "baseline-compare" in sigs[0].tags


# ── merge / accumulate ────────────────────────────────────────────────────────

class TestMerge:
    def test_merge_unions_segments(self):
        a = Baseline(floor_db=-100, n_sweeps=1, segments=[_seg(100_000_000)])
        b = Baseline(floor_db=-100, n_sweeps=1, segments=[_seg(200_000_000)])
        a.merge(b)
        assert len(a.segments) == 2
        assert a.n_sweeps == 2

    def test_merge_keeps_stronger_peak(self):
        a = Baseline(n_sweeps=1, segments=[_seg(100_000_000, peak_db=-60)])
        b = Baseline(n_sweeps=1, segments=[_seg(100_000_500, peak_db=-30)])
        a.merge(b, freq_tol_hz=5000)
        assert len(a.segments) == 1
        assert a.segments[0].peak_db == -30

    def test_merge_averages_floor(self):
        a = Baseline(floor_db=-100, n_sweeps=1)
        b = Baseline(floor_db=-80, n_sweeps=1)
        a.merge(b)
        assert a.floor_db == pytest.approx(-90.0)


# ── persistence ───────────────────────────────────────────────────────────────

class TestPersistence:
    def test_round_trip_dict(self):
        b = baseline_from_spectrum(_spectrum([50, 130]), START, BIN,
                                   label="site-A", lat=40.0, lon=-75.0)
        back = Baseline.from_dict(b.to_dict())
        assert back.label == "site-A"
        assert back.lat == 40.0
        assert len(back.segments) == 2
        assert isinstance(back.segments[0], OccupancySegment)

    def test_save_and_load(self, tmp_path):
        b = baseline_from_spectrum(_spectrum([50]), START, BIN, label="site-B")
        p = tmp_path / "sub" / "base.json"
        b.save(p)
        loaded = Baseline.load(p)
        assert loaded.label == "site-B"
        assert len(loaded.segments) == 1
        # still comparable after a round-trip
        cur = baseline_from_spectrum(_spectrum([50, 130]), START, BIN)
        assert compare_baselines(loaded, cur).anomaly_count == 1
