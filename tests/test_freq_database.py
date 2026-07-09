# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/freq_database.py — schedule-aware frequency lookup."""
import json
import pytest

from core.freq_database import (
    FreqEntry, FreqDatabase, _split_time, _to_hz, DEFAULT_FREQ_TOL_HZ,
)

# A small, realistic EiBi-format sample (kHz;time;days;ITU;station;lang;target;…)
EIBI = """\
kHz;Time(UTC);Days;ITU;Station;Language;Target;Remarks;P;Start;Stop
6155;0600-0800;;AUT;ORF;G;Eu;;;;
9420;0000-2400;;GRC;Voice of Greece;GR;Eu;;;;
5000;;;USA;WWV;E;;Time signal;;;
15770;2200-0100;;USA;Radio Miami;E;Am;wrap;;;
"""


# ── time helpers ──────────────────────────────────────────────────────────────

class TestTimeHelpers:
    def test_split_time_range(self):
        assert _split_time("0600-0800") == ("0600", "0800")

    def test_split_time_single(self):
        assert _split_time("0600") == ("0600", "")

    def test_split_time_empty(self):
        assert _split_time("") == ("", "")

    def test_to_hz_units(self):
        assert _to_hz("6155", "khz") == 6_155_000
        assert _to_hz("14.097", "mhz") == 14_097_000
        assert _to_hz("1000", "hz") == 1000


# ── active_at scheduling ──────────────────────────────────────────────────────

class TestActiveAt:
    def test_in_window(self):
        e = FreqEntry(6155000, time_start="0600", time_end="0800")
        assert e.active_at("0700") is True
        assert e.active_at("0500") is False
        assert e.active_at("0800") is False        # end exclusive

    def test_no_time_always_active(self):
        assert FreqEntry(5000000).active_at("1234") is True

    def test_no_query_time_always_active(self):
        e = FreqEntry(6155000, time_start="0600", time_end="0800")
        assert e.active_at(None) is True

    def test_wraparound_window(self):
        # 2200-0100 UTC spans midnight
        e = FreqEntry(15770000, time_start="2200", time_end="0100")
        assert e.active_at("2300") is True
        assert e.active_at("0030") is True
        assert e.active_at("1200") is False

    def test_bad_time_is_active(self):
        e = FreqEntry(6155000, time_start="ZZZZ", time_end="0800")
        assert e.active_at("0700") is True         # unparseable → don't hide it


# ── EiBi import ───────────────────────────────────────────────────────────────

class TestEibiImport:
    def test_imports_rows_skipping_header(self):
        db = FreqDatabase()
        n = db.import_eibi(EIBI)
        assert n == 4                              # header line skipped
        assert len(db) == 4

    def test_parses_fields(self):
        db = FreqDatabase()
        db.import_eibi(EIBI)
        orf = db.best(6_155_000)
        assert orf.station == "ORF"
        assert orf.country == "AUT"
        assert orf.language == "G"
        assert orf.time_start == "0600" and orf.time_end == "0800"
        assert orf.source == "eibi"

    def test_khz_to_hz(self):
        db = FreqDatabase()
        db.import_eibi(EIBI)
        assert db.best(9_420_000).freq_hz == 9_420_000

    def test_bad_rows_skipped(self):
        db = FreqDatabase()
        n = db.import_eibi("not;enough\n;;;;\nabc;0600;;X;Sta;E;;;;;")
        assert n == 0                              # no valid freq in any row


# ── lookup ────────────────────────────────────────────────────────────────────

class TestLookup:
    def _db(self):
        db = FreqDatabase()
        db.import_eibi(EIBI)
        return db

    def test_lookup_within_tolerance(self):
        db = self._db()
        assert db.best(6_155_500, tol_hz=1000).station == "ORF"   # 500 Hz off
        assert db.best(6_160_000, tol_hz=1000) is None            # too far

    def test_lookup_time_filtered(self):
        db = self._db()
        # ORF only 0600-0800 UTC
        assert db.best(6_155_000, utc_hhmm="0700").station == "ORF"
        assert db.best(6_155_000, utc_hhmm="1200") is None        # off air

    def test_lookup_nearest_first(self):
        db = FreqDatabase([FreqEntry(6_155_000, station="A"),
                           FreqEntry(6_154_000, station="B")])
        hits = db.lookup(6_154_800, tol_hz=2000)
        assert hits[0].station == "A"              # 200 Hz vs 800 Hz

    def test_lookup_none(self):
        assert self._db().best(1_000_000) is None


# ── generic CSV import ────────────────────────────────────────────────────────

class TestCsvImport:
    def test_generic_csv_with_mapping(self):
        text = "Frequency,Name,Lang\n909,BBC,E\n1215,Absolute,E\n"
        db = FreqDatabase()
        n = db.import_csv(text, {"freq": "Frequency", "station": "Name",
                                 "language": "Lang"}, source="aoki",
                          freq_unit="khz")
        assert n == 2
        e = db.best(909_000)
        assert e.station == "BBC" and e.source == "aoki"

    def test_csv_mhz_unit(self):
        text = "MHz,Station\n100.1,WXYZ\n"
        db = FreqDatabase()
        db.import_csv(text, {"freq": "MHz", "station": "Station"},
                      freq_unit="mhz")
        assert db.best(100_100_000).station == "WXYZ"

    def test_csv_skips_rows_without_freq(self):
        text = "Frequency,Name\n,NoFreq\n909,Good\n"
        db = FreqDatabase()
        assert db.import_csv(text, {"freq": "Frequency", "station": "Name"},
                             freq_unit="khz") == 1


# ── persistence ───────────────────────────────────────────────────────────────

class TestPersistence:
    def test_round_trip(self, tmp_path):
        db = FreqDatabase()
        db.import_eibi(EIBI)
        p = tmp_path / "sub" / "freqdb.json"
        db.save(p)
        loaded = FreqDatabase.load(p)
        assert len(loaded) == 4
        assert loaded.best(6_155_000).station == "ORF"

    def test_from_dicts_skips_bad(self):
        db = FreqDatabase.from_dicts(
            [{"freq_hz": 909000, "station": "X"}, 5, None, {"junk": 1}])
        # the {"junk":1} builds a FreqEntry missing freq_hz → TypeError → skipped
        assert len(db) == 1
        assert db.entries[0].station == "X"


def test_never_raises_on_garbage():
    db = FreqDatabase()
    db.import_eibi(None or "")
    db.import_csv("", {})
    assert db.lookup(0) == []
    assert db.best(-1) is None
