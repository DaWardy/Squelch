# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/emitter_correlate.py — emitter fingerprint correlation
(ROADMAP Phase 3, DF-EMITTER)."""

import pytest

from core.signal_model import Signal, SignalStore
from core.emitter_correlate import (
    Emitter, fingerprint, correlate_emitters, correlate_from_store,
    DEFAULT_FREQ_BUCKET_HZ,
)


def _sig(**kw):
    s = Signal(**{k: v for k, v in kw.items()
                  if k in Signal.__dataclass_fields__})
    return s


# ── fingerprint ───────────────────────────────────────────────────────────────

class TestFingerprint:
    def test_emitter_id_dominates_across_freqs(self):
        a = _sig(freq_hz=145_000_000, emitter_id="W1AW")
        b = _sig(freq_hz=440_000_000, emitter_id="w1aw")   # diff band + case
        assert fingerprint(a) == fingerprint(b) == "id:W1AW"

    def test_anonymous_groups_by_channel_bucket(self):
        a = _sig(freq_hz=146_520_000, source="survey", classification="occupied")
        b = _sig(freq_hz=146_521_000, source="survey", classification="occupied")
        # within one 12.5 kHz bucket
        assert fingerprint(a) == fingerprint(b)
        assert fingerprint(a).startswith("ch:survey:occupied:")

    def test_anonymous_different_buckets_split(self):
        a = _sig(freq_hz=146_520_000, source="survey", classification="occupied")
        b = _sig(freq_hz=147_000_000, source="survey", classification="occupied")
        assert fingerprint(a) != fingerprint(b)

    def test_different_source_splits_anonymous(self):
        a = _sig(freq_hz=146_520_000, source="survey", classification="occupied")
        b = _sig(freq_hz=146_520_000, source="sdr", classification="occupied")
        assert fingerprint(a) != fingerprint(b)


# ── grouping ──────────────────────────────────────────────────────────────────

class TestCorrelate:
    def test_same_emitter_collapses(self):
        sigs = [
            _sig(freq_hz=145_000_000, emitter_id="K1ABC", count=2),
            _sig(freq_hz=440_000_000, emitter_id="K1ABC", count=3),
        ]
        ems = correlate_emitters(sigs)
        assert len(ems) == 1
        e = ems[0]
        assert e.emitter_id == "K1ABC"
        assert e.n_signals == 2
        assert e.n_observations == 5
        assert e.freq_lo == 145_000_000
        assert e.freq_hi == 440_000_000

    def test_distinct_emitters_separate(self):
        sigs = [
            _sig(freq_hz=145_000_000, emitter_id="AA1A"),
            _sig(freq_hz=145_000_000, emitter_id="BB2B"),
        ]
        ems = correlate_emitters(sigs)
        assert {e.emitter_id for e in ems} == {"AA1A", "BB2B"}

    def test_sorted_by_activity(self):
        sigs = [
            _sig(freq_hz=1_000_000, emitter_id="QUIET", count=1),
            _sig(freq_hz=1_000_000, emitter_id="BUSY", count=50),
        ]
        ems = correlate_emitters(sigs)
        assert ems[0].emitter_id == "BUSY"

    def test_min_signals_filter(self):
        sigs = [
            _sig(freq_hz=1_000_000, emitter_id="ONE"),
            _sig(freq_hz=2_000_000, emitter_id="TWO"),
            _sig(freq_hz=2_000_000, emitter_id="TWO"),
        ]
        ems = correlate_emitters(sigs, min_signals=2)
        assert [e.emitter_id for e in ems] == ["TWO"]

    def test_empty_input(self):
        assert correlate_emitters([]) == []

    def test_aggregates_distinct_metadata(self):
        sigs = [
            _sig(freq_hz=145_000_000, emitter_id="X", source="aprs",
                 classification="APRS", modulation="AFSK"),
            _sig(freq_hz=145_000_000, emitter_id="X", source="df",
                 classification="DF fix", modulation=""),
        ]
        e = correlate_emitters(sigs)[0]
        assert set(e.sources) == {"aprs", "df"}
        assert "APRS" in e.classifications and "DF fix" in e.classifications
        assert e.modulations == ["AFSK"]        # blanks dropped

    def test_first_last_seen_span(self):
        sigs = [
            _sig(freq_hz=1_000_000, emitter_id="T",
                 first_seen="2026-07-01T00:00:00Z", last_seen="2026-07-01T00:00:00Z"),
            _sig(freq_hz=1_000_000, emitter_id="T",
                 first_seen="2026-07-04T00:00:00Z", last_seen="2026-07-04T12:00:00Z"),
        ]
        e = correlate_emitters(sigs)[0]
        assert e.first_seen == "2026-07-01T00:00:00Z"
        assert e.last_seen == "2026-07-04T12:00:00Z"

    def test_signal_ids_collected(self):
        s1 = _sig(freq_hz=1_000_000, emitter_id="Z"); s1.id = 11
        s2 = _sig(freq_hz=1_000_000, emitter_id="Z"); s2.id = 22
        e = correlate_emitters([s1, s2])[0]
        assert set(e.signal_ids) == {11, 22}


# ── location estimation ───────────────────────────────────────────────────────

class TestLocation:
    def test_no_position_is_unlocated(self):
        e = correlate_emitters([_sig(freq_hz=1_000_000, emitter_id="NP")])[0]
        assert e.located is False
        assert e.location_method == "none"
        assert e.lat == 0.0 and e.lon == 0.0

    def test_rssi_centroid_when_rssi_present(self):
        sigs = [
            _sig(freq_hz=1e6, emitter_id="R", lat=40.0, lon=-75.0, rssi_dbm=-90),
            _sig(freq_hz=1e6, emitter_id="R", lat=40.1, lon=-75.0, rssi_dbm=-30),
        ]
        e = correlate_emitters(sigs)[0]
        assert e.location_method == "rssi-centroid"
        assert e.lat > 40.05                       # pulled toward the strong one
        assert e.located is True

    def test_plain_centroid_without_rssi(self):
        sigs = [
            _sig(freq_hz=1e6, emitter_id="C", lat=40.0, lon=-75.0),
            _sig(freq_hz=1e6, emitter_id="C", lat=42.0, lon=-77.0),
        ]
        e = correlate_emitters(sigs)[0]
        assert e.location_method == "centroid"
        assert e.lat == pytest.approx(41.0)
        assert e.lon == pytest.approx(-76.0)

    def test_single_rssi_falls_back_to_centroid(self):
        # only one positioned sample carries rssi → not enough for rssi-centroid
        sigs = [
            _sig(freq_hz=1e6, emitter_id="S", lat=40.0, lon=-75.0, rssi_dbm=-40),
            _sig(freq_hz=1e6, emitter_id="S", lat=41.0, lon=-75.0),
        ]
        e = correlate_emitters(sigs)[0]
        assert e.location_method == "centroid"


# ── store convenience ─────────────────────────────────────────────────────────

class TestFromStore:
    def test_correlate_from_store(self):
        st = SignalStore(":memory:")
        st.add(_sig(freq_hz=145_000_000, emitter_id="STORE1", lat=40, lon=-75,
                    rssi_dbm=-50))
        st.add(_sig(freq_hz=440_000_000, emitter_id="STORE1", lat=40.2, lon=-75,
                    rssi_dbm=-40))
        st.add(_sig(freq_hz=7_040_000, emitter_id="STORE2"))
        ems = correlate_from_store(store=st)
        by_id = {e.emitter_id: e for e in ems}
        assert "STORE1" in by_id and "STORE2" in by_id
        assert by_id["STORE1"].n_signals == 2
        assert by_id["STORE1"].located is True
        assert by_id["STORE2"].located is False


def test_emitter_dataclass_defaults():
    e = Emitter(key="id:X")
    assert e.emitter_id == ""
    assert e.located is False
    assert DEFAULT_FREQ_BUCKET_HZ > 0
