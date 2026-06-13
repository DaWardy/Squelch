"""Tests for network/signal_id.py — SignalIdentifier matching logic."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from pytest import approx as pytest_approx
except ImportError:
    def pytest_approx(x, rel=None):  # type: ignore[misc]
        return x

from network.signal_id import SignalIdentifier, SignalMatch, get_identifier


# ---------------------------------------------------------------------------
# _parse_hz
# ---------------------------------------------------------------------------

def test_parse_hz_plain():
    assert SignalIdentifier._parse_hz("500") == 500.0

def test_parse_hz_khz():
    assert SignalIdentifier._parse_hz("10KHZ") == 10_000.0

def test_parse_hz_mhz():
    assert SignalIdentifier._parse_hz("14.225MHZ") == pytest_approx(14_225_000.0)

def test_parse_hz_ghz():
    assert SignalIdentifier._parse_hz("1.4GHZ") == pytest_approx(1_400_000_000.0)

def test_parse_hz_with_spaces():
    assert SignalIdentifier._parse_hz("  2.4 KHz  ") == pytest_approx(2_400.0, rel=0.01)

def test_parse_hz_hz_suffix():
    assert SignalIdentifier._parse_hz("200HZ") == 200.0

def test_parse_hz_bad_returns_zero():
    assert SignalIdentifier._parse_hz("NOT_A_NUMBER") == 0.0

def test_parse_hz_empty():
    assert SignalIdentifier._parse_hz("") == 0.0

def test_parse_hz_comma_separated():
    assert SignalIdentifier._parse_hz("10,000") == pytest_approx(10_000.0)

# ---------------------------------------------------------------------------
# Matching logic with synthetic DB
# ---------------------------------------------------------------------------

_WSPR_SIG = {
    "name": "WSPR",
    "modulation": "USB",
    "bandwidth": "200HZ",
    "frequency_lower": "1MHZ",
    "frequency_upper": "30MHZ",
    "category": "Amateur",
    "description": "Weak Signal Propagation Reporter",
    "url": "https://sigidwiki.com/wiki/WSPR",
}

_VOR_SIG = {
    "name": "VOR",
    "modulation": "AM+FM",
    "bandwidth": "50KHZ",
    "frequency_lower": "108MHZ",
    "frequency_upper": "118MHZ",
    "category": "Aviation",
    "description": "VHF Omnidirectional Range",
    "url": "",
}


def _make_identifier(records: list) -> SignalIdentifier:
    ident = SignalIdentifier()
    ident._db = records
    ident._loaded = True
    return ident


def test_exact_bw_match():
    ident = _make_identifier([_WSPR_SIG])
    results = ident.identify(200, freq_hz=14_097_000)
    assert len(results) == 1
    assert results[0].name == "WSPR"


def test_bw_within_tolerance_matches():
    ident = _make_identifier([_WSPR_SIG])
    # 240 Hz is 20% above 200 Hz — within default 30% tolerance
    results = ident.identify(240, freq_hz=14_097_000)
    assert len(results) == 1


def test_bw_outside_tolerance_no_match():
    ident = _make_identifier([_WSPR_SIG])
    # 5000 Hz is way outside ±30% of 200 Hz
    results = ident.identify(5000, freq_hz=14_097_000)
    assert len(results) == 0


def test_freq_outside_range_no_match():
    ident = _make_identifier([_WSPR_SIG])
    # WSPR is 1-30 MHz; 150 MHz is aviation band
    results = ident.identify(200, freq_hz=150_000_000)
    assert len(results) == 0


def test_freq_zero_skips_freq_filter():
    ident = _make_identifier([_WSPR_SIG])
    # freq_hz=0 means "don't filter by frequency"
    results = ident.identify(200, freq_hz=0)
    assert len(results) == 1


def test_multiple_signals_sorted_by_confidence():
    # Add a second signal with same BW but slightly different
    wspr_close = dict(_WSPR_SIG, name="WSPR-Close", bandwidth="210HZ")
    ident = _make_identifier([wspr_close, _WSPR_SIG])
    results = ident.identify(200)
    # WSPR (exact 200Hz) should be first — higher confidence
    assert results[0].name == "WSPR"


def test_confidence_is_between_0_and_1():
    ident = _make_identifier([_WSPR_SIG, _VOR_SIG])
    for sig in [_WSPR_SIG]:
        results = ident.identify(200)
        assert all(0.0 <= m.confidence <= 1.0 for m in results)


def test_exact_match_has_high_confidence():
    ident = _make_identifier([_WSPR_SIG])
    results = ident.identify(200, freq_hz=14_097_000)
    assert results[0].confidence >= 0.9


def test_results_capped_at_10():
    # Create 15 identical signals; identify should return at most 10
    sigs = [dict(_WSPR_SIG, name=f"Sig{i}") for i in range(15)]
    ident = _make_identifier(sigs)
    results = ident.identify(200)
    assert len(results) <= 10


def test_match_fields_populated():
    ident = _make_identifier([_WSPR_SIG])
    m = ident.identify(200, freq_hz=14_097_000)[0]
    assert m.name == "WSPR"
    assert m.modulation == "USB"
    assert m.bandwidth_hz == 200
    assert m.category == "Amateur"
    assert "sigidwiki" in m.url
    assert m.source == "artemis"


def test_aviation_signal_matches_at_right_freq():
    ident = _make_identifier([_WSPR_SIG, _VOR_SIG])
    results = ident.identify(50_000, freq_hz=112_000_000)
    assert len(results) == 1
    assert results[0].name == "VOR"


def test_broken_db_entry_skipped_gracefully():
    broken = {"name": None, "bandwidth": "not_a_number", "modulation": None}
    ident = _make_identifier([broken, _WSPR_SIG])
    results = ident.identify(200, freq_hz=14_097_000)
    # Should still find WSPR, ignoring the broken entry
    assert any(m.name == "WSPR" for m in results)


# ---------------------------------------------------------------------------
# load_db from local file
# ---------------------------------------------------------------------------

def test_load_db_from_local_file(tmp_path, monkeypatch):
    db_file = tmp_path / "artemis_signals.json"
    db_file.write_text(json.dumps([_WSPR_SIG]), encoding="utf-8")
    import network.signal_id as mod
    monkeypatch.setattr(mod, "ARTEMIS_LOCAL", db_file)
    ident = SignalIdentifier()
    ok = ident.load_db()
    assert ok is True
    assert ident.signal_count == 1


def test_load_db_missing_file_returns_false_without_requests(tmp_path, monkeypatch):
    import network.signal_id as mod
    monkeypatch.setattr(mod, "ARTEMIS_LOCAL", tmp_path / "missing.json")
    monkeypatch.setattr(mod, "HAS_REQUESTS", False)
    ident = SignalIdentifier()
    ok = ident.load_db()
    assert ok is False
    assert not ident.is_loaded


# ---------------------------------------------------------------------------
# get_identifier singleton
# ---------------------------------------------------------------------------

def test_get_identifier_returns_same_instance():
    a = get_identifier()
    b = get_identifier()
    assert a is b


