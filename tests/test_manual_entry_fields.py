"""Tests for manual QSO entry helper logic — no Qt required."""
from __future__ import annotations
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest
from core.band_plan import band_at_freq


# ── Frequency → band auto-fill ───────────────────────────────────────────

def _freq_to_band(text: str) -> str | None:
    """Mirror of the _freq_to_band closure in _build_manual_entry_fields."""
    clean = text.strip().replace(",", ".")
    try:
        hz = int(float(clean) * 1_000_000)
        b = band_at_freq(hz)
        return b.name if b else None
    except (ValueError, TypeError):
        return None


class TestFreqToBand:
    def test_ft8_20m(self):
        assert _freq_to_band("14.074") == "20m"

    def test_ft8_40m(self):
        assert _freq_to_band("7.074") == "40m"

    def test_ssb_20m(self):
        assert _freq_to_band("14.225") == "20m"

    def test_cw_80m(self):
        assert _freq_to_band("3.55") == "80m"

    def test_2m_calling(self):
        assert _freq_to_band("144.200") == "2m"

    def test_70cm(self):
        assert _freq_to_band("446.000") == "70cm"

    def test_out_of_band_returns_none(self):
        assert _freq_to_band("13.0") is None

    def test_empty_returns_none(self):
        assert _freq_to_band("") is None

    def test_non_numeric_returns_none(self):
        assert _freq_to_band("abc") is None

    def test_comma_decimal_separator(self):
        # European-style decimal comma
        assert _freq_to_band("14,074") == "20m"


# ── freq_hz parsing (from form text to int Hz) ───────────────────────────

def _parse_freq_hz(text: str) -> int:
    try:
        return int(float(text.strip().replace(",", ".")) * 1_000_000)
    except (ValueError, TypeError):
        return 0


class TestParseFreqHz:
    def test_ft8_20m(self):
        assert _parse_freq_hz("14.074") == 14_074_000

    def test_six_decimals(self):
        assert _parse_freq_hz("14.074500") == 14_074_500

    def test_empty_gives_zero(self):
        assert _parse_freq_hz("") == 0

    def test_non_numeric_gives_zero(self):
        assert _parse_freq_hz("abc") == 0

    def test_comma_separator(self):
        assert _parse_freq_hz("14,074") == 14_074_000


# ── datetime string formatting ───────────────────────────────────────────

from datetime import datetime, timezone


def _dt_to_iso(year, month, day, hour=0, minute=0, second=0) -> str:
    dt = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class TestDatetimeFormatting:
    def test_basic_format(self):
        assert _dt_to_iso(2024, 5, 4, 14, 32, 0) == "2024-05-04T14:32:00Z"

    def test_midnight(self):
        assert _dt_to_iso(2024, 1, 1, 0, 0, 0) == "2024-01-01T00:00:00Z"

    def test_end_of_year(self):
        assert _dt_to_iso(2024, 12, 31, 23, 59, 59) == "2024-12-31T23:59:59Z"
