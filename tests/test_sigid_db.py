# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/sigid_db.py — offline signal-identification lookup."""
import json
import pytest

from core.sigid_db import (
    SigIdEntry, SigIdMatch, SigIdDatabase, _family, _mod_match,
)


# ── modulation family matching ────────────────────────────────────────────────

class TestModFamily:
    def test_fsk_variants_same_family(self):
        assert _family("AFSK") == _family("MFSK") == _family("4FSK") == "FSK"

    def test_ook_ask_same(self):
        assert _mod_match("OOK", "ASK")

    def test_psk_variants(self):
        assert _mod_match("BPSK", "PSK")

    def test_unrelated_no_match(self):
        assert not _mod_match("FM", "PSK")

    def test_empty_no_match(self):
        assert not _mod_match("", "FM")


# ── builtin identify ──────────────────────────────────────────────────────────

class TestBuiltinIdentify:
    def setup_method(self):
        self.db = SigIdDatabase.builtin()

    def test_builtin_nonempty(self):
        assert len(self.db) > 10

    def test_noaa_weather(self):
        m = self.db.best_match(162_425_000, modulation="FM")
        assert m is not None
        assert m.entry.name == "NOAA weather radio"
        assert "frequency" in m.reasons and "modulation" in m.reasons

    def test_adsb(self):
        m = self.db.best_match(1_090_000_000)
        assert m.entry.name == "ADS-B (Mode S)"

    def test_aircraft_am(self):
        hits = self.db.identify(120_000_000, modulation="AM")
        assert hits[0].entry.name == "Aircraft VHF voice"

    def test_aprs_by_freq_and_afsk(self):
        m = self.db.best_match(144_390_000, modulation="AFSK", bandwidth_hz=12_000)
        assert m.entry.name == "APRS"
        assert "bandwidth" in m.reasons

    def test_frequency_out_of_range_excluded(self):
        # 500 MHz matches none of the fixed allocations (no mode given)
        hits = self.db.identify(500_000_000)
        names = [h.entry.name for h in hits]
        assert "NOAA weather radio" not in names
        assert "FM broadcast" not in names

    def test_mode_only_entry_matches_any_freq(self):
        # CW is a mode-only entry (freq 0) → matches on modulation regardless
        m = self.db.best_match(50_000_000, modulation="CW")
        assert m is not None
        assert m.entry.name == "Morse (CW)"

    def test_ranked_best_first(self):
        hits = self.db.identify(162_450_000, modulation="FM", limit=5)
        assert hits == sorted(hits, key=lambda h: h.score, reverse=True)
        assert hits[0].entry.name == "NOAA weather radio"

    def test_limit_respected(self):
        assert len(self.db.identify(100_000_000, modulation="FM", limit=2)) <= 2

    def test_no_match_returns_empty(self):
        assert self.db.best_match(0, modulation="") is None


# ── import / attribution (licensing-safe path) ────────────────────────────────

class TestImport:
    def test_import_stamps_source(self):
        db = SigIdDatabase()
        n = db.import_entries(
            [{"name": "Widget telemetry", "freq_lo_hz": 433_000_000,
              "freq_hi_hz": 434_000_000, "modulation": "OOK",
              "bandwidth_hz": 20_000}], source="user")
        assert n == 1
        m = db.best_match(433_500_000, modulation="OOK")
        assert m.entry.name == "Widget telemetry"
        assert m.entry.source == "user"          # attribution preserved

    def test_import_keeps_declared_source(self):
        db = SigIdDatabase()
        db.import_entries([{"name": "X", "modulation": "FM",
                            "source": "sigidwiki", "url": "http://x"}],
                          source="user")
        assert db.entries[0].source == "sigidwiki"
        assert db.entries[0].url == "http://x"

    def test_import_skips_bad_rows(self):
        db = SigIdDatabase()
        n = db.import_entries([{"name": "ok", "freq_lo_hz": 1}, 12345, None])
        assert n == 1

    def test_from_json(self, tmp_path):
        p = tmp_path / "db.json"
        p.write_text(json.dumps({"signals": [
            {"name": "Custom", "freq_lo_hz": 915_000_000,
             "freq_hi_hz": 928_000_000, "modulation": "FSK"}]}),
            encoding="utf-8")
        db = SigIdDatabase.from_json(p)
        assert len(db) == 1
        assert db.best_match(920_000_000, modulation="FSK").entry.name == "Custom"

    def test_builtin_entries_are_attributed_builtin(self):
        assert all(e.source == "builtin"
                   for e in SigIdDatabase.builtin().entries)


# ── robustness ────────────────────────────────────────────────────────────────

def test_never_raises_on_garbage():
    db = SigIdDatabase.builtin()
    for args in [(0, 0, ""), (-1, -1, "???"), (99 ** 9, 0, "FM")]:
        assert isinstance(db.identify(*args), list)


def test_empty_db_identifies_nothing():
    assert SigIdDatabase().identify(162_400_000, modulation="FM") == []
