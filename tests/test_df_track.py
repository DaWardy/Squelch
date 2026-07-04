# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/df_track.py — DF capture / logging (ROADMAP Phase 3)."""

import math
import pytest

from core.df_track import (
    DFSample, DFTrack, TriggerMode, haversine_m, should_log, now_s,
    DEFAULT_INTERVAL_S, DEFAULT_MIN_DIST_M,
)


def _s(t, lat, lon, rssi, heading=None):
    return DFSample(t=t, lat=lat, lon=lon, rssi_dbm=rssi, heading_deg=heading)


# ── haversine ─────────────────────────────────────────────────────────────────

class TestHaversine:
    def test_zero_for_same_point(self):
        assert haversine_m(40.0, -75.0, 40.0, -75.0) == 0.0

    def test_one_degree_lat_is_about_111km(self):
        d = haversine_m(40.0, -75.0, 41.0, -75.0)
        assert 110_000 < d < 112_000

    def test_short_eastward_hop(self):
        # ~0.001 deg lon at 40N ≈ 85 m
        d = haversine_m(40.0, -75.0, 40.0, -74.999)
        assert 80 < d < 90

    def test_symmetric(self):
        a = haversine_m(51.5, -0.1, 48.85, 2.35)
        b = haversine_m(48.85, 2.35, 51.5, -0.1)
        assert math.isclose(a, b)


# ── should_log (pure trigger) ─────────────────────────────────────────────────

class TestShouldLog:
    def test_manual_never_auto_logs(self):
        assert should_log(TriggerMode.MANUAL, None, _s(0, 40, -75, -50)) is False
        assert should_log(TriggerMode.MANUAL,
                          _s(0, 40, -75, -50), _s(99, 41, -74, -50)) is False

    def test_continuous_always_logs(self):
        assert should_log(TriggerMode.CONTINUOUS, None, _s(0, 40, -75, -50))
        assert should_log(TriggerMode.CONTINUOUS,
                         _s(0, 40, -75, -50), _s(0.1, 40, -75, -50))

    def test_first_point_always_logs(self):
        assert should_log(TriggerMode.TIMED, None, _s(0, 40, -75, -50))
        assert should_log(TriggerMode.DISTANCE, None, _s(0, 40, -75, -50))

    def test_timed_respects_interval(self):
        last = _s(100.0, 40, -75, -50)
        assert should_log(TriggerMode.TIMED, last, _s(104.9, 40, -75, -50),
                          interval_s=5.0) is False
        assert should_log(TriggerMode.TIMED, last, _s(105.0, 40, -75, -50),
                          interval_s=5.0) is True

    def test_distance_respects_threshold(self):
        last = _s(0, 40.0, -75.0, -50)
        near = _s(1, 40.0001, -75.0, -50)     # ~11 m
        far  = _s(1, 40.0005, -75.0, -50)     # ~55 m
        assert should_log(TriggerMode.DISTANCE, last, near, min_dist_m=25.0) is False
        assert should_log(TriggerMode.DISTANCE, last, far,  min_dist_m=25.0) is True

    def test_unknown_mode_logs_nothing(self):
        assert should_log("bogus", None, _s(0, 40, -75, -50)) is False

    def test_negative_thresholds_clamped(self):
        last = _s(0, 40, -75, -50)
        assert should_log(TriggerMode.TIMED, last, _s(0, 40, -75, -50),
                          interval_s=-9) is True


# ── track capture ─────────────────────────────────────────────────────────────

class TestCapture:
    def test_add_is_unconditional(self):
        trk = DFTrack(mode=TriggerMode.MANUAL)
        trk.add(_s(0, 40, -75, -50))
        trk.add(_s(0, 40, -75, -50))
        assert len(trk) == 2

    def test_offer_manual_suppresses_stream(self):
        trk = DFTrack(mode=TriggerMode.MANUAL)
        assert trk.offer(_s(0, 40, -75, -50)) is False
        assert len(trk) == 0

    def test_offer_continuous_keeps_all(self):
        trk = DFTrack(mode=TriggerMode.CONTINUOUS)
        for i in range(5):
            assert trk.offer(_s(i, 40, -75, -50)) is True
        assert len(trk) == 5

    def test_offer_timed_decimates(self):
        trk = DFTrack(mode=TriggerMode.TIMED, interval_s=5.0)
        logged = [trk.offer(_s(t, 40, -75, -50)) for t in (0, 2, 5, 6, 10)]
        assert logged == [True, False, True, False, True]
        assert len(trk) == 3

    def test_offer_distance_decimates(self):
        trk = DFTrack(mode=TriggerMode.DISTANCE, min_dist_m=25.0)
        # steps of ~11 m each; every ~3rd step crosses 25 m
        pts = [trk.offer(_s(i, 40.0 + i * 0.0001, -75.0, -50)) for i in range(7)]
        assert pts[0] is True                 # first always logs
        assert sum(pts) < 7                   # some were dropped

    def test_clear(self):
        trk = DFTrack(mode=TriggerMode.CONTINUOUS)
        trk.offer(_s(0, 40, -75, -50))
        trk.clear()
        assert len(trk) == 0

    def test_bad_mode_defaults_to_timed(self):
        assert DFTrack(mode="nope").mode == TriggerMode.TIMED

    def test_created_stamp_autofilled(self):
        assert DFTrack().created.endswith("Z")


# ── estimates ─────────────────────────────────────────────────────────────────

class TestEstimates:
    def test_location_estimate_pulls_toward_strong(self):
        trk = DFTrack(mode=TriggerMode.CONTINUOUS)
        trk.add(_s(0, 40.00, -75.00, -90))   # weak
        trk.add(_s(1, 40.10, -75.00, -30))   # strong
        est = trk.location_estimate()
        assert est is not None
        assert est.method == "rssi-centroid"
        assert est.lat > 40.05                # biased toward the strong sample

    def test_location_estimate_none_when_no_positions(self):
        trk = DFTrack(mode=TriggerMode.CONTINUOUS)
        trk.add(DFSample(t=0, lat=0.0, lon=0.0, rssi_dbm=-50))
        assert trk.location_estimate() is None

    def test_bearing_from_heading_sweep(self):
        trk = DFTrack(mode=TriggerMode.MANUAL)
        for h, r in [(0, -30), (90, -90), (180, -95), (270, -90)]:
            trk.add(_s(0, 40, -75, r, heading=h))
        b = trk.bearing()
        assert b is not None
        assert abs(b.bearing_deg - 0.0) < 20 or abs(b.bearing_deg - 360) < 20

    def test_bearing_none_without_headings(self):
        trk = DFTrack(mode=TriggerMode.CONTINUOUS)
        trk.add(_s(0, 40, -75, -50))
        assert trk.bearing() is None


# ── Signal bridge ─────────────────────────────────────────────────────────────

class TestToSignal:
    def test_to_signal_carries_freq_and_emitter(self):
        trk = DFTrack(freq_hz=146_520_000, emitter_id="W1AW",
                      mode=TriggerMode.CONTINUOUS)
        trk.add(_s(0, 40.0, -75.0, -80))
        trk.add(_s(1, 40.1, -75.0, -40))
        sig = trk.to_signal()
        assert sig is not None
        assert sig.source == "df"
        assert sig.classification == "DF fix"
        assert sig.freq_hz == 146_520_000
        assert sig.emitter_id == "W1AW"
        assert sig.lat != 0.0

    def test_to_signal_none_without_fix(self):
        trk = DFTrack(mode=TriggerMode.CONTINUOUS)
        assert trk.to_signal() is None

    def test_to_signal_accepts_explicit_estimate(self):
        from digital.rfdf import LocationEstimate
        trk = DFTrack(freq_hz=1000, mode=TriggerMode.MANUAL)
        est = LocationEstimate(lat=1.0, lon=2.0, confidence=0.9,
                               method="triangulate", n_inputs=3)
        sig = trk.to_signal(est=est)
        assert sig.lat == 1.0 and sig.lon == 2.0
        assert sig.confidence == 0.9


# ── map / analysis helpers ────────────────────────────────────────────────────

class TestHelpers:
    def _drive(self):
        trk = DFTrack(mode=TriggerMode.CONTINUOUS)
        trk.add(_s(0, 40.00, -75.00, -90))
        trk.add(_s(5, 40.01, -75.00, -60))
        trk.add(_s(10, 40.02, -75.00, -40))   # strongest
        return trk

    def test_heatmap_points_normalized(self):
        pts = self._drive().heatmap_points()
        assert len(pts) == 3
        weights = [w for _, _, w in pts]
        assert min(weights) == 0.0 and max(weights) == 1.0

    def test_heatmap_flat_track_all_one(self):
        trk = DFTrack(mode=TriggerMode.CONTINUOUS)
        trk.add(_s(0, 40, -75, -50))
        trk.add(_s(1, 41, -75, -50))
        assert all(w == 1.0 for _, _, w in trk.heatmap_points())

    def test_heatmap_empty(self):
        assert DFTrack().heatmap_points() == []

    def test_strongest(self):
        assert self._drive().strongest().rssi_dbm == -40

    def test_strongest_none_when_empty(self):
        assert DFTrack().strongest() is None

    def test_bbox(self):
        box = self._drive().bbox()
        assert box == (40.0, -75.0, 40.02, -75.0)

    def test_bbox_none_when_empty(self):
        assert DFTrack().bbox() is None

    def test_path_length(self):
        d = self._drive().path_length_m()
        assert 2000 < d < 2500          # two ~1.1 km hops in latitude

    def test_duration(self):
        assert self._drive().duration_s() == 10.0

    def test_duration_zero_with_one_sample(self):
        trk = DFTrack(mode=TriggerMode.MANUAL)
        trk.add(_s(0, 40, -75, -50))
        assert trk.duration_s() == 0.0


# ── persistence ───────────────────────────────────────────────────────────────

class TestPersistence:
    def test_roundtrip_dict(self):
        trk = DFTrack(freq_hz=145_000_000, emitter_id="K1ABC",
                      label="park hunt", mode=TriggerMode.DISTANCE,
                      min_dist_m=30.0)
        trk.add(_s(0, 40.0, -75.0, -70, heading=45))
        trk.add(_s(3, 40.1, -75.1, -50))
        back = DFTrack.from_dict(trk.to_dict())
        assert back.freq_hz == 145_000_000
        assert back.emitter_id == "K1ABC"
        assert back.label == "park hunt"
        assert back.mode == TriggerMode.DISTANCE
        assert back.min_dist_m == 30.0
        assert len(back) == 2
        assert back.samples[0].heading_deg == 45
        assert isinstance(back.samples[1], DFSample)

    def test_save_and_load(self, tmp_path):
        trk = DFTrack(freq_hz=7_040_000, mode=TriggerMode.CONTINUOUS)
        trk.add(_s(0, 40.0, -75.0, -60))
        trk.add(_s(1, 40.1, -75.0, -40))
        p = tmp_path / "sub" / "hunt.json"
        trk.save(p)
        assert p.exists()
        loaded = DFTrack.load(p)
        assert loaded.freq_hz == 7_040_000
        assert len(loaded) == 2
        # estimate still works after a round-trip
        assert loaded.location_estimate() is not None

    def test_from_dict_ignores_unknown_keys(self):
        d = {"freq_hz": 100, "bogus": "x",
             "samples": [{"t": 0, "lat": 1, "lon": 2, "rssi_dbm": -50,
                          "junk": 9}]}
        trk = DFTrack.from_dict(d)
        assert trk.freq_hz == 100
        assert len(trk) == 1
        assert trk.samples[0].rssi_dbm == -50


# ── misc ──────────────────────────────────────────────────────────────────────

def test_defaults_exposed():
    assert DEFAULT_INTERVAL_S > 0
    assert DEFAULT_MIN_DIST_M > 0
    assert set(TriggerMode.ALL) == {"manual", "continuous", "timed", "distance"}


def test_now_s_is_epoch_seconds():
    assert now_s() > 1_700_000_000        # after 2023
