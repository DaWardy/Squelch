# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for survey detection enrichment — attaching an offline signal-ID
identity + a frequency-database station name to detections."""
import pytest

from core.signal_model import Signal, SignalStore
from core.sigid_db import apply_sigid, SigIdDatabase
from core.freq_database import apply_freq_database, FreqDatabase, FreqEntry
from core.live_analysis import SurveyEngine

CENTER = 146_000_000
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


# ── apply_sigid ───────────────────────────────────────────────────────────────

class TestApplySigid:
    def test_names_a_known_signal(self):
        db = SigIdDatabase.builtin()
        sig = Signal(freq_hz=146_520_000, modulation="FM",
                     classification="occupied")
        apply_sigid(sig, db)
        # 2m simplex → matched to a builtin entry; generic label replaced
        assert sig.classification != "occupied"
        assert sig.confidence > 0

    def test_does_not_override_specific_label(self):
        db = SigIdDatabase.builtin()
        sig = Signal(freq_hz=146_520_000, modulation="FM",
                     classification="APRS")           # already specific
        apply_sigid(sig, db)
        assert sig.classification == "APRS"           # not overwritten

    def test_no_db_is_noop(self):
        sig = Signal(freq_hz=1, classification="occupied")
        assert apply_sigid(sig, None) is sig
        assert sig.classification == "occupied"

    def test_none_signal_safe(self):
        assert apply_sigid(None, SigIdDatabase.builtin()) is None


# ── apply_freq_database ───────────────────────────────────────────────────────

class TestApplyFreqDb:
    def _db(self):
        db = FreqDatabase()
        db.add(FreqEntry(freq_hz=9_420_000, station="Voice of Greece",
                         source="eibi"))
        return db

    def test_attaches_station_name(self):
        sig = Signal(freq_hz=9_420_000, source="survey")
        apply_freq_database(sig, self._db())
        assert sig.decoded == "Voice of Greece"
        assert "freqdb" in sig.tags

    def test_no_match_noop(self):
        sig = Signal(freq_hz=1_000_000)
        apply_freq_database(sig, self._db())
        assert sig.decoded == ""

    def test_no_db_safe(self):
        sig = Signal(freq_hz=1)
        assert apply_freq_database(sig, None) is sig


# ── SurveyEngine end-to-end enrichment ────────────────────────────────────────

class TestSurveyEnrichment:
    def test_detection_carries_sigid_identity(self):
        # put a signal on the 2m calling channel and survey it with sigid on
        f = 146_520_000
        # tune so bin 600 lands on 146.520 MHz
        center = f - int((600 - NBINS / 2) * (RATE / NBINS))
        eng = SurveyEngine(ingest=False, sigid_db=SigIdDatabase.builtin())
        dets = eng.offer_frame(_frame([600]), center, RATE)
        assert len(dets) == 1
        assert dets[0].signal.classification != "occupied"

    def test_detection_carries_station_name(self):
        f = _bin_freq(600)
        fdb = FreqDatabase()
        fdb.add(FreqEntry(freq_hz=f, station="Test Station", source="user"))
        eng = SurveyEngine(ingest=False, freq_db=fdb)
        dets = eng.offer_frame(_frame([600]), CENTER, RATE)
        assert dets[0].signal.decoded == "Test Station"

    def test_enrichment_into_store(self):
        store = SignalStore(":memory:")
        fdb = FreqDatabase()
        fdb.add(FreqEntry(freq_hz=_bin_freq(600), station="WTest"))
        eng = SurveyEngine(store=store, ingest=True, freq_db=fdb,
                           sigid_db=SigIdDatabase.builtin())
        eng.offer_frame(_frame([600]), CENTER, RATE)
        rec = store.recent()[0]
        assert rec.decoded == "WTest"

    def test_no_catalogues_still_works(self):
        eng = SurveyEngine(ingest=False)          # no sigid/freq db
        dets = eng.offer_frame(_frame([600]), CENTER, RATE)
        assert len(dets) == 1                     # plain occupancy detection
