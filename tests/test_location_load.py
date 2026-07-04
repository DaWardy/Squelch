from __future__ import annotations
# Squelch — RF / SDR signal platform
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for LocationManager.load_from_config — full restore + coordinate
precedence (regression for the 'map defaults to Germany' stale-grid bug)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.location import LocationManager, _latlon_to_grid


class _Cfg:
    def __init__(self, data=None):
        self._d = dict(data or {})

    def get(self, k, default=None):
        return self._d.get(k, default)

    def set(self, k, v):
        self._d[k] = v

    def save(self):
        pass


# Manassas, VA (the user's real location)
MANASSAS = (38.7509, -77.4753)
# JN58SC ≈ Munich, Germany (the stale saved grid that centred the map wrong)


class TestFullRestore:
    def test_city_state_restored(self):
        lm = LocationManager(_Cfg({
            "location.grid": "FM18", "location.lat": MANASSAS[0],
            "location.lon": MANASSAS[1], "location.city": "Manassas",
            "location.state": "Virginia", "location.county": "Prince William",
            "location.country": "US", "location.zip_code": "20110"}))
        lm.load_from_config()
        assert lm.location.city == "Manassas"
        assert lm.location.state == "Virginia"
        assert lm.location.county == "Prince William"
        assert lm.location.country == "US"

    def test_display_is_consistent(self):
        lm = LocationManager(_Cfg({
            "location.lat": MANASSAS[0], "location.lon": MANASSAS[1],
            "location.city": "Manassas", "location.state": "Virginia"}))
        lm.load_from_config()
        # grid and city now agree — both derived from the same coordinates
        assert lm.location.grid.startswith("FM1")
        assert "Manassas, Virginia" in lm.location.display


class TestCoordinatePrecedence:
    def test_stale_grid_overridden_by_coordinates(self):
        """The 'Germany' bug: a stale JN58SC grid must not win over real
        Manassas coordinates."""
        lm = LocationManager(_Cfg({
            "location.grid": "JN58SC",           # stale — Munich
            "location.lat": MANASSAS[0], "location.lon": MANASSAS[1]}))
        lm.load_from_config()
        assert not lm.location.grid.startswith("JN58")
        assert lm.location.grid.startswith("FM1")   # recomputed from coords
        # the map centres on lat/lon, which are the real location
        assert abs(lm.location.lat - MANASSAS[0]) < 0.01
        assert abs(lm.location.lon - MANASSAS[1]) < 0.01

    def test_consistent_grid_and_coords_preserved(self):
        lat, lon = MANASSAS
        grid = _latlon_to_grid(lat, lon)
        lm = LocationManager(_Cfg({
            "location.grid": grid, "location.lat": lat, "location.lon": lon}))
        lm.load_from_config()
        assert lm.location.grid[:4] == grid[:4]

    def test_grid_only_derives_coordinates(self):
        lm = LocationManager(_Cfg({"location.grid": "FM18LV"}))
        lm.load_from_config()
        assert lm.location.grid == "FM18LV"
        assert lm.location.lat != 0.0        # derived from the grid
        assert lm.location.lon != 0.0

    def test_empty_config_is_safe(self):
        lm = LocationManager(_Cfg({}))
        lm.load_from_config()                # must not raise
        assert lm.location.grid == ""
        assert lm.location.lat == 0.0


class TestMismatchWarning:
    def test_warns_on_grid_coord_mismatch(self, caplog):
        import logging
        lm = LocationManager(_Cfg({
            "location.grid": "JN58SC",
            "location.lat": MANASSAS[0], "location.lon": MANASSAS[1]}))
        with caplog.at_level(logging.WARNING):
            lm.load_from_config()
        assert any("disagrees" in r.message for r in caplog.records)

    def test_no_warning_when_consistent(self, caplog):
        import logging
        lat, lon = MANASSAS
        lm = LocationManager(_Cfg({
            "location.grid": _latlon_to_grid(lat, lon),
            "location.lat": lat, "location.lon": lon}))
        with caplog.at_level(logging.WARNING):
            lm.load_from_config()
        assert not any("disagrees" in r.message for r in caplog.records)
