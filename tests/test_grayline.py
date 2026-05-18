from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
# Squelch tests — network/grayline.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import math
from datetime import datetime, timezone
from network.grayline import (
    solar_position, sun_elevation,
    gray_line_info, terminator_points,
    day_night_geojson, format_gray_line_status)


class TestSolarPosition:
    def test_declination_range(self):
        """Declination should be between -23.5 and +23.5."""
        for month in range(1, 13):
            dt = datetime(2026, month, 15, 12, 0, tzinfo=timezone.utc)
            sol = solar_position(dt)
            assert -23.5 <= sol.declination_deg <= 23.5

    def test_summer_solstice_positive(self):
        """June 21: declination should be near +23.5."""
        dt = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
        sol = solar_position(dt)
        assert sol.declination_deg > 20

    def test_winter_solstice_negative(self):
        """Dec 21: declination should be near -23.5."""
        dt = datetime(2026, 12, 21, 12, 0, tzinfo=timezone.utc)
        sol = solar_position(dt)
        assert sol.declination_deg < -20

    def test_returns_timestamp(self):
        sol = solar_position()
        assert sol.utc_timestamp > 0


class TestSunElevation:
    def test_noon_positive(self):
        """Sun at local noon should be above horizon."""
        # Denver: lat=39.7, lon=-104.9
        # UTC noon at lon=-105 is ~19:00 UTC
        dt = datetime(2026, 6, 21, 19, 0, tzinfo=timezone.utc)
        elev = sun_elevation(39.7, -104.9, dt)
        assert elev > 0, f"Expected sun above horizon, got {elev}"

    def test_midnight_negative(self):
        """Sun at midnight should be below horizon."""
        dt = datetime(2026, 6, 21, 7, 0, tzinfo=timezone.utc)
        elev = sun_elevation(39.7, -104.9, dt)
        assert elev < 0, f"Expected sun below horizon, got {elev}"

    def test_poles_extreme(self):
        """North pole in June: sun should be above horizon."""
        dt = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
        elev = sun_elevation(89.0, 0.0, dt)
        assert elev > 0

    def test_elevation_range(self):
        """Elevation should always be between -90 and +90."""
        for lat in [-80, -45, 0, 45, 80]:
            for lon in [-180, -90, 0, 90, 180]:
                elev = sun_elevation(lat, lon)
                assert -90 <= elev <= 90


class TestGrayLineInfo:
    def test_returns_grayline_info(self):
        info = gray_line_info(39.7, -104.9)
        assert hasattr(info, 'is_day')
        assert hasattr(info, 'is_gray_line')
        assert hasattr(info, 'sun_elevation')
        assert hasattr(info, 'minutes_to_rise')
        assert hasattr(info, 'minutes_to_set')

    def test_minutes_positive(self):
        info = gray_line_info(39.7, -104.9)
        assert info.minutes_to_rise >= 0
        assert info.minutes_to_set >= 0

    def test_day_night_consistent(self):
        """If sun is above horizon, is_day should be True."""
        info = gray_line_info(39.7, -104.9)
        if info.sun_elevation > 6:
            assert info.is_day is True
        if info.sun_elevation < -6:
            assert info.is_day is False


class TestTerminatorPoints:
    def test_returns_list(self):
        pts = terminator_points()
        assert isinstance(pts, list)
        assert len(pts) > 0

    def test_lat_lon_range(self):
        pts = terminator_points()
        for lat, lon in pts:
            assert -90 <= lat <= 90
            assert -180 <= lon <= 180

    def test_custom_steps(self):
        pts = terminator_points(steps=36)
        assert len(pts) == 37  # steps + 1


class TestDayNightGeoJSON:
    def test_valid_geojson(self):
        gj = day_night_geojson()
        assert gj["type"] == "Feature"
        assert gj["geometry"]["type"] == "Polygon"
        assert "coordinates" in gj["geometry"]

    def test_has_properties(self):
        gj = day_night_geojson()
        assert "declination" in gj["properties"]
        assert "computed_utc" in gj["properties"]


class TestFormatStatus:
    def test_returns_string(self):
        info = gray_line_info(39.7, -104.9)
        s = format_gray_line_status(info)
        assert isinstance(s, str)
        assert len(s) > 0

    def test_contains_sun_symbol(self):
        info = gray_line_info(39.7, -104.9)
        s = format_gray_line_status(info)
        assert any(sym in s for sym in ['☀', '🌙', '🌅'])
