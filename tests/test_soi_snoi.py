# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/soi_snoi.py — SOI/SNOI watch/ignore rules."""
import json
import pytest

from core.soi_snoi import (
    WatchRule, WatchList, SOI, SNOI,
)


# ── rule matching ─────────────────────────────────────────────────────────────

class TestWatchRule:
    def test_in_range_matches(self):
        r = WatchRule(144_000_000, 148_000_000, SOI)
        assert r.matches(146_520_000)

    def test_out_of_range_no_match(self):
        r = WatchRule(144_000_000, 148_000_000, SOI)
        assert not r.matches(150_000_000)

    def test_disabled_never_matches(self):
        r = WatchRule(144_000_000, 148_000_000, SOI, enabled=False)
        assert not r.matches(146_520_000)

    def test_modulation_narrows_match(self):
        r = WatchRule(144_000_000, 148_000_000, SOI, modulation="FSK")
        assert r.matches(146_000_000, "AFSK")     # same family
        assert not r.matches(146_000_000, "FM")

    def test_reversed_bounds_tolerated(self):
        r = WatchRule(148_000_000, 144_000_000, SOI)   # hi/lo swapped
        assert r.matches(146_000_000)


# ── classify + precedence ─────────────────────────────────────────────────────

class TestClassify:
    def test_soi_and_snoi(self):
        wl = WatchList()
        wl.add_range(144_000_000, 148_000_000, SOI, "2m")
        wl.add_range(88_000_000, 108_000_000, SNOI, "FM bcast")
        assert wl.classify(146_520_000) == SOI
        assert wl.classify(99_500_000) == SNOI
        assert wl.classify(50_000_000) is None

    def test_soi_wins_on_overlap(self):
        wl = WatchList()
        wl.add_range(100_000_000, 200_000_000, SNOI, "ignore band")
        wl.add_range(146_000_000, 147_000_000, SOI, "watch this")
        # 146.5 is in both → SOI precedence
        assert wl.classify(146_520_000) == SOI

    def test_is_soi_is_snoi(self):
        wl = WatchList()
        wl.add_range(144_000_000, 148_000_000, SOI)
        wl.add_range(88_000_000, 108_000_000, SNOI)
        assert wl.is_soi(146_000_000)
        assert wl.is_snoi(99_000_000)
        assert not wl.is_soi(99_000_000)


# ── ranges for baseline compare ───────────────────────────────────────────────

class TestRanges:
    def test_snoi_ranges(self):
        wl = WatchList()
        wl.add_range(88_000_000, 108_000_000, SNOI)
        wl.add_range(144_000_000, 148_000_000, SOI)      # not SNOI
        assert wl.snoi_ranges() == [(88_000_000, 108_000_000)]

    def test_disabled_excluded_from_ranges(self):
        wl = WatchList()
        wl.add(WatchRule(88_000_000, 108_000_000, SNOI, enabled=False))
        assert wl.snoi_ranges() == []

    def test_feeds_compare_baselines(self):
        """snoi_ranges() plugs straight into rf_baseline.compare_baselines."""
        from core.rf_baseline import Baseline, compare_baselines
        from core.occupancy import OccupancySegment

        def seg(c):
            return OccupancySegment(center_hz=c, bandwidth_hz=10_000,
                                    peak_db=-40, floor_db=-100, snr_db=60,
                                    bin_lo=0, bin_hi=0)
        ref = Baseline(segments=[])
        cur = Baseline(segments=[seg(99_500_000)])       # inside FM broadcast
        wl = WatchList()
        wl.add_range(88_000_000, 108_000_000, SNOI, "FM bcast")
        diff = compare_baselines(ref, cur, ignore_ranges=wl.snoi_ranges())
        assert diff.new == []                            # SNOI suppressed it


# ── partition / filter ────────────────────────────────────────────────────────

class TestPartitionFilter:
    def _items(self):
        return [
            {"freq_hz": 146_520_000, "modulation": "FM"},   # SOI
            {"freq_hz": 99_500_000,  "modulation": "FM"},   # SNOI
            {"freq_hz": 50_000_000,  "modulation": "CW"},   # other
        ]

    def _wl(self):
        wl = WatchList()
        wl.add_range(144_000_000, 148_000_000, SOI)
        wl.add_range(88_000_000, 108_000_000, SNOI)
        return wl

    def test_partition(self):
        p = self._wl().partition(self._items())
        assert len(p[SOI]) == 1 and len(p[SNOI]) == 1 and len(p["other"]) == 1

    def test_filter_out_snoi(self):
        kept = self._wl().filter_out_snoi(self._items())
        freqs = [i["freq_hz"] for i in kept]
        assert 99_500_000 not in freqs           # SNOI dropped
        assert 146_520_000 in freqs and 50_000_000 in freqs

    def test_partition_works_on_objects(self):
        class S:
            def __init__(self, f):
                self.freq_hz = f
                self.modulation = ""
        p = self._wl().partition([S(146_520_000), S(99_500_000)])
        assert len(p[SOI]) == 1 and len(p[SNOI]) == 1


# ── persistence ───────────────────────────────────────────────────────────────

class TestPersistence:
    def test_dict_round_trip(self):
        wl = WatchList()
        wl.add_range(144_000_000, 148_000_000, SOI, "2m", "FM")
        wl.add_range(88_000_000, 108_000_000, SNOI, "FM bcast")
        back = WatchList.from_dicts(wl.to_dicts())
        assert len(back) == 2
        assert back.rules[0].label == "2m"
        assert back.rules[0].modulation == "FM"
        assert back.rules[1].kind == SNOI

    def test_save_load(self, tmp_path):
        wl = WatchList()
        wl.add_range(144_000_000, 148_000_000, SOI, "2m")
        p = tmp_path / "sub" / "watch.json"
        wl.save(p)
        loaded = WatchList.load(p)
        assert loaded.is_soi(146_000_000)

    def test_from_dicts_skips_bad(self):
        wl = WatchList.from_dicts([{"freq_lo_hz": 1, "freq_hi_hz": 2}, 99, None])
        assert len(wl) == 1

    def test_cfg_round_trip(self):
        class _Cfg:
            def __init__(self):
                self._d = {}
            def get(self, k, d=None):
                return self._d.get(k, d)
            def set(self, k, v):
                self._d[k] = v
            def save(self):
                pass
        cfg = _Cfg()
        wl = WatchList()
        wl.add_range(144_000_000, 148_000_000, SOI)
        wl.save_to_cfg(cfg)
        assert WatchList.from_cfg(cfg).is_soi(146_000_000)


class TestCommonSnoi:
    def test_common_snoi_defaults(self):
        wl = WatchList.with_common_snoi()
        assert wl.is_snoi(99_500_000)            # FM broadcast
        assert wl.is_snoi(1_000_000)             # AM broadcast
        assert all(r.kind == SNOI for r in wl.rules)


def test_empty_watchlist_classifies_none():
    wl = WatchList()
    assert wl.classify(146_520_000) is None
    assert wl.snoi_ranges() == []
