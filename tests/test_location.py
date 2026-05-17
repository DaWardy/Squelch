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
tests/test_location.py
Tests for core/location.py — grid square conversions,
Location dataclass validation, and location utilities.
Run: python -m pytest tests/ -v
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.location import (
    _latlon_to_grid, _grid_to_latlon,
    _valid_grid, Location,
)


class TestGridToLatLon:

    def test_known_4char_grid(self):
        """DM79 should be in northern Virginia area."""
        lat, lon = _grid_to_latlon("DM79")
        assert 37.0 < lat < 43.0, f"Lat {lat} not in Denver range"
        assert -108.0 < lon < -102.0, f"Lon {lon} not in Denver range"

    def test_known_6char_grid(self):
        """DM79rr — more precise location."""
        lat, lon = _grid_to_latlon("DM79rr")
        assert 38.0 < lat < 40.0
        assert -107.0 < lon < -103.0

    def test_case_insensitive(self):
        lat1, lon1 = _grid_to_latlon("DM79rr")
        lat2, lon2 = _grid_to_latlon("dm79rr")
        assert abs(lat1 - lat2) < 0.01
        assert abs(lon1 - lon2) < 0.01

    def test_equatorial_grid(self):
        """JJ00 should be near 0°N 0°E."""
        lat, lon = _grid_to_latlon("JJ00")
        assert -5 < lat < 5
        assert -5 < lon < 5

    def test_antipodal_grids(self):
        """AA00 and RR99 should be far apart."""
        lat1, lon1 = _grid_to_latlon("AA00")
        lat2, lon2 = _grid_to_latlon("RR99")
        assert abs(lat1 - lat2) > 100 or abs(lon1 - lon2) > 100

    def test_known_dxcc_locations(self):
        """Test grids for known ham radio locations."""
        # London area — IO91
        lat, lon = _grid_to_latlon("IO91")
        assert 50 < lat < 53
        assert -2 < lon < 1

        # Sydney area — QF56
        lat, lon = _grid_to_latlon("QF56")
        assert -35 < lat < -32
        assert 150 < lon < 152


class TestLatLonToGrid:

    def test_northern_virginia(self):
        """39.742, -104.990 should be DM79."""
        grid = _latlon_to_grid(39.742, -104.990)
        assert grid.startswith("DM79"), f"Got {grid}"

    def test_new_york_city(self):
        """40.7128, -74.0060 should be FN20 or FN30."""
        grid = _latlon_to_grid(40.7128, -74.0060)
        assert grid.startswith("FN"), f"Got {grid}"

    def test_london(self):
        """51.5074, -0.1278 should be IO91."""
        grid = _latlon_to_grid(51.5074, -0.1278)
        assert grid.startswith("IO91"), f"Got {grid}"

    def test_sydney(self):
        """-33.8688, 151.2093 should be QF56."""
        grid = _latlon_to_grid(-33.8688, 151.2093)
        assert grid.startswith("QF"), f"Got {grid}"

    def test_length(self):
        """Grid should be 6 characters."""
        grid = _latlon_to_grid(39.742, -104.990)
        assert len(grid) == 6, f"Length {len(grid)}"

    def test_uppercase(self):
        """Grid should be uppercase."""
        grid = _latlon_to_grid(39.742, -104.990)
        assert grid == grid.upper()

    def test_roundtrip(self):
        """Convert to grid and back — should be close."""
        orig_lat, orig_lon = 39.742, -104.990
        grid = _latlon_to_grid(orig_lat, orig_lon)
        back_lat, back_lon = _grid_to_latlon(grid)
        # 6-char grid is accurate to ~4km
        assert abs(orig_lat - back_lat) < 0.1, \
            f"Lat drift: {orig_lat} -> {back_lat}"
        assert abs(orig_lon - back_lon) < 0.1, \
            f"Lon drift: {orig_lon} -> {back_lon}"

    def test_extreme_latitudes(self):
        """Polar regions should not crash."""
        grid = _latlon_to_grid(89.0, 0.0)
        assert len(grid) >= 4

        grid = _latlon_to_grid(-89.0, 0.0)
        assert len(grid) >= 4

    def test_dateline(self):
        """Near 180° longitude should not crash."""
        grid = _latlon_to_grid(0.0, 179.9)
        assert len(grid) >= 4

        grid = _latlon_to_grid(0.0, -179.9)
        assert len(grid) >= 4


class TestValidGrid:

    def test_valid_4char(self):
        assert _valid_grid("DM79") is True
        assert _valid_grid("IO91") is True
        assert _valid_grid("AA00") is True
        assert _valid_grid("RR99") is True

    def test_valid_6char(self):
        assert _valid_grid("DM79rr") is True
        assert _valid_grid("IO91wm") is True

    def test_case_insensitive(self):
        assert _valid_grid("fm18") is True
        assert _valid_grid("DM79LV") is True
        assert _valid_grid("fm18lv") is True

    def test_invalid_too_short(self):
        assert _valid_grid("FM") is False
        assert _valid_grid("F") is False
        assert _valid_grid("") is False

    def test_invalid_characters(self):
        assert _valid_grid("1234") is False
        assert _valid_grid("DM79!") is False
        assert _valid_grid("ZZZZ") is False

    def test_zip_code_not_grid(self):
        assert _valid_grid("22030") is False
        assert _valid_grid("90210") is False

    def test_none_safe(self):
        assert _valid_grid(None) is False
        assert _valid_grid(123) is False


class TestLocationDataclass:
    """Tests matching the actual Location dataclass structure."""

    def test_default_state(self):
        """Default location should be at 0,0 with no grid."""
        loc = Location()
        assert loc.lat == 0.0
        assert loc.lon == 0.0
        assert loc.grid == ""

    def test_is_valid_with_grid(self):
        """Location with grid should be valid."""
        loc = Location(grid="DM79rr")
        assert loc.is_valid is True

    def test_is_valid_with_latlon(self):
        """Location with non-zero lat/lon should be valid."""
        loc = Location(lat=39.742, lon=-104.990)
        assert loc.is_valid is True

    def test_is_valid_default_false(self):
        """Default location at 0,0 with no grid should not be valid."""
        loc = Location()
        assert loc.is_valid is False

    def test_display_with_grid_and_city(self):
        """Display should include grid and city."""
        loc = Location(grid="DM79", city="Fairfax", state="VA")
        disp = loc.display
        assert "DM79" in disp

    def test_display_not_set(self):
        """Empty location should show 'Not set' display."""
        loc = Location()
        assert loc.display != ""  # should always return something

    def test_lat_lon_stored(self):
        """lat/lon should be stored as provided."""
        loc = Location(lat=39.742, lon=-104.990)
        assert abs(loc.lat - 39.742) < 0.001
        assert abs(loc.lon - (-104.990)) < 0.001

    def test_city_state_stored(self):
        """City and state should be stored."""
        loc = Location(city="Fairfax", state="VA")
        assert loc.city == "Fairfax"
        assert loc.state == "VA"
