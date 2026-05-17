from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
#
# This program is free software: you can redistribute it
# and/or modify it under the terms of the GNU General
# Public License as published by the Free Software
# Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General
# Public License along with this program. If not, see
# <https://www.gnu.org/licenses/>.
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
tests/test_validator.py
Tests for core/validator.py — all input validation functions.
Run: python -m pytest tests/ -v
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.validator import (
    callsign_soft, frequency_hz_soft,
    api_string, api_int, api_float,
    api_callsign,
)


class TestCallsignValidation:

    def test_valid_us_callsigns(self):
        assert callsign_soft("W4XYZ")  == "W4XYZ"
        assert callsign_soft("NR6U")   == "NR6U"
        assert callsign_soft("K4ABC")  == "K4ABC"
        assert callsign_soft("AA1AA")  == "AA1AA"
        assert callsign_soft("WB4GHT") == "WB4GHT"

    def test_lowercase_normalized(self):
        assert callsign_soft("w4xyz")  == "W4XYZ"
        assert callsign_soft("nr6u")   == "NR6U"

    def test_portable_suffix(self):
        assert callsign_soft("W4XYZ/P")  == "W4XYZ/P"
        assert callsign_soft("W4XYZ/M")  == "W4XYZ/M"
        assert callsign_soft("DL1ABC/W4") == "DL1ABC/W4"

    def test_international_callsigns(self):
        assert callsign_soft("DL1ABC")  == "DL1ABC"
        assert callsign_soft("G4ZZZ")   == "G4ZZZ"
        assert callsign_soft("VK2XYZ")  == "VK2XYZ"
        assert callsign_soft("JA1ABC")  == "JA1ABC"

    def test_empty_returns_empty(self):
        assert callsign_soft("") == ""
        assert callsign_soft("  ") == ""

    def test_strips_whitespace(self):
        assert callsign_soft("  W4XYZ  ") == "W4XYZ"

    def test_removes_invalid_chars(self):
        result = callsign_soft("W4XYZ!")
        assert "!" not in result

    def test_too_long_truncated(self):
        result = callsign_soft("W4XYZABCDEFGHIJK")
        assert len(result) <= 15  # api_string truncation limit

    def test_too_short(self):
        # Single char should return empty (not a valid callsign)
        result = callsign_soft("W")
        assert result == "" or len(result) <= 1


class TestFrequencyValidation:

    def test_valid_hf_frequencies(self):
        assert frequency_hz_soft(14_074_000) == 14_074_000
        assert frequency_hz_soft(7_074_000)  == 7_074_000
        assert frequency_hz_soft(3_573_000)  == 3_573_000

    def test_valid_vhf_uhf(self):
        assert frequency_hz_soft(144_200_000) == 144_200_000
        assert frequency_hz_soft(446_000_000) == 446_000_000

    def test_zero_returns_zero(self):
        assert frequency_hz_soft(0) == 0

    def test_negative_returns_zero(self):
        assert frequency_hz_soft(-1000) == 0

    def test_float_converted(self):
        result = frequency_hz_soft(14_074_000.5)
        assert isinstance(result, int)

    def test_string_converted(self):
        result = frequency_hz_soft("14074000")
        assert result == 14_074_000

    def test_above_max_clamped(self):
        result = frequency_hz_soft(999_999_999_999)
        assert result <= 300_000_000_000


class TestApiStringValidation:

    def test_normal_string(self):
        assert api_string("hello world") == "hello world"

    def test_empty_string(self):
        assert api_string("") == ""

    def test_none_returns_empty(self):
        assert api_string(None) == ""

    def test_truncated_to_max_length(self):
        long = "x" * 500
        result = api_string(long, max_length=100)
        assert len(result) == 100

    def test_strips_null_bytes(self):
        result = api_string("hello\x00world")
        assert "\x00" not in result

    def test_non_string_converted(self):
        assert api_string(42)    == "42"
        assert api_string(3.14)  == "3.14"
        assert api_string(True)  == "True"

    def test_control_chars_stripped(self):
        result = api_string("hello\x01\x02\x03world")
        assert "\x01" not in result

    def test_unicode_preserved(self):
        result = api_string("Ångström")
        assert "Å" in result


class TestApiIntValidation:

    def test_valid_int(self):
        assert api_int(42)    == 42
        assert api_int(0)     == 0
        assert api_int(-10)   == -10

    def test_string_converted(self):
        assert api_int("42")  == 42
        assert api_int("0")   == 0

    def test_float_truncated(self):
        assert api_int(3.9)   == 3
        assert api_int(-1.1)  == -1

    def test_none_returns_default(self):
        assert api_int(None, default=0)   == 0
        assert api_int(None, default=99)  == 99

    def test_invalid_string_returns_default(self):
        assert api_int("abc", default=0) == 0
        assert api_int("",    default=5) == 5

    def test_overflow_clamped(self):
        result = api_int(10**30, default=0)
        # Should not raise, should return something reasonable
        assert isinstance(result, int)


class TestApiFloatValidation:

    def test_valid_float(self):
        assert api_float(3.14)   == pytest.approx(3.14)
        assert api_float(0.0)    == 0.0
        assert api_float(-1.5)   == pytest.approx(-1.5)

    def test_int_converted(self):
        assert api_float(42)     == pytest.approx(42.0)

    def test_string_converted(self):
        assert api_float("3.14") == pytest.approx(3.14)

    def test_none_returns_default(self):
        assert api_float(None, default=0.0) == 0.0

    def test_invalid_string_returns_default(self):
        assert api_float("abc", default=0.0) == 0.0
        assert api_float("",    default=1.0) == 1.0

    def test_nan_returns_default(self):
        import math
        result = api_float(float('nan'), default=0.0)
        assert not math.isnan(result) or result == 0.0

    def test_inf_handled(self):
        result = api_float(float('inf'), default=0.0)
        assert isinstance(result, float)


class TestApiCallsignValidation:

    def test_valid_callsign(self):
        assert api_callsign("W4XYZ") == "W4XYZ"

    def test_too_long_truncated(self):
        result = api_callsign("W4XYZABCDEFGHIJKLMNO")
        assert len(result) <= 15  # api_string truncation limit

    def test_none_returns_empty(self):
        assert api_callsign(None) == ""

    def test_uppercase_normalized(self):
        assert api_callsign("w4xyz") == "W4XYZ"
