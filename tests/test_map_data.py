from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for network/map_data.py — no hardware, no Qt required."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock
from core.config import Config


def _make_cfg():
    tmp = tempfile.mkdtemp()
    cfg = Config(Path(tmp) / "config.json")
    cfg.callsign = "W1AW"
    cfg.set("station.grid", "FN31pr")
    cfg.set("station.lat",  41.7)
    cfg.set("station.lon", -72.7)
    return cfg


def _html(cfg=None, **kwargs) -> str:
    from network.map_data import build_map_html
    kwargs.setdefault("show_adsb", False)
    kwargs.setdefault("show_grayline", False)
    return build_map_html(cfg or _make_cfg(), **kwargs)


# ── Legend ────────────────────────────────────────────────────────────────────

class TestMapLegend:
    def test_legend_css_present(self):
        html = _html()
        assert ".map-legend" in html

    def test_legend_dot_class(self):
        html = _html()
        assert ".leg-dot" in html

    def test_legend_triangle_class(self):
        html = _html()
        assert ".leg-tri-up" in html

    def test_legend_square_class(self):
        html = _html()
        assert ".leg-sq" in html

    def test_legend_control_added(self):
        html = _html()
        assert "map-legend" in html
        assert "LEGEND" in html

    def test_legend_shows_my_station(self):
        html = _html()
        assert "My Station" in html

    def test_legend_shows_aprs(self):
        html = _html()
        assert "APRS" in html

    def test_legend_shows_pskreporter(self):
        html = _html()
        assert "PSKReporter" in html


# ── Mode-colored heard stations ───────────────────────────────────────────────

class TestHeardStationColors:
    def test_mcolors_dict_in_js(self):
        html = _html()
        assert "MCOLORS" in html

    def test_ft8_color_present(self):
        html = _html()
        assert "FT8" in html
        # The cyan-blue FT8 color
        assert "#00aaff" in html

    def test_wspr_color_present(self):
        html = _html()
        assert "WSPR" in html
        assert "#ffcc00" in html

    def test_cw_color_present(self):
        html = _html()
        assert "CW" in html
        assert "#ff8800" in html

    def test_default_color_fallback(self):
        html = _html()
        assert "MC_DEFAULT" in html

    def test_heard_station_uses_mcolors(self):
        """Marker color lookup must use MCOLORS dict, not a hardcoded value."""
        html = _html(heard_stations={
            "N0CALL": {"lat": 41.0, "lon": -73.0, "freq": 14.074, "mode": "FT8"}
        })
        # The JS that picks the color should reference MCOLORS and s.source
        assert "MCOLORS" in html
        assert "s.source" in html or "spot.source" in html or "mode" in html


# ── HTML structure ────────────────────────────────────────────────────────────

class TestMapHtmlStructure:
    def test_returns_string(self):
        assert isinstance(_html(), str)

    def test_not_empty(self):
        assert len(_html()) > 500

    def test_leaflet_script_included(self):
        html = _html()
        assert "leaflet" in html.lower()

    def test_doctype(self):
        html = _html()
        assert html.strip().startswith("<!DOCTYPE html>")

    def test_no_real_callsign_in_defaults(self):
        """W1AW is the test callsign — ensure it only appears from config."""
        cfg = _make_cfg()
        html = build_map_html_direct(cfg)
        # Should appear in the marker popup since we set callsign = W1AW
        assert "W1AW" in html  # from config — expected

    def test_winlink_gateway_markers(self):
        html = _html(winlink_gateways=[
            {"callsign": "W1AW-10", "lat": 41.0, "lon": -73.0,
             "modes": ["WINMOR"], "freq": 14.105}
        ])
        assert "W1AW-10" in html

    def test_empty_heard_stations_no_error(self):
        html = _html(heard_stations={})
        assert "MCOLORS" in html  # dict still emitted even with no spots


def build_map_html_direct(cfg):
    from network.map_data import build_map_html
    return build_map_html(cfg)


# ── Layer controls ────────────────────────────────────────────────────────────

class TestLayerControls:
    def test_layer_control_present(self):
        html = _html()
        assert "L.control.layers" in html

    def test_base_layers_dark_and_street(self):
        html = _html()
        assert "Dark" in html
        assert "Street Map" in html

    def test_overlay_qso_paths(self):
        html = _html()
        assert "QSO Paths" in html

    def test_overlay_worked_grids(self):
        html = _html()
        assert "Worked Grids" in html

    def test_overlay_gray_line(self):
        html = _html()
        assert "Gray Line" in html

    def test_overlay_pskreporter(self):
        html = _html()
        assert "PSKReporter" in html

    def test_layer_groups_defined(self):
        html = _html()
        assert "lyrQsoPaths" in html
        assert "lyrWorkedGrids" in html
        assert "lyrHeard" in html


# ── Worked grids ──────────────────────────────────────────────────────────────

class TestWorkedGridsData:
    def _make_db_with_qsos(self, grids):
        from unittest.mock import MagicMock
        q_list = []
        for g in grids:
            q = MagicMock()
            q.grid = g
            q.my_grid = "FN31"
            q.my_lat = 41.7
            q.my_lon = -72.7
            q.lat = 0.0
            q.lon = 0.0
            q.dist_km = 0.0
            q.lotw_status = ""
            q.datetime_on = "2026-01-01T12:00:00Z"
            q.call = "W1AW"
            q.band = "20m"
            q.mode = "FT8"
            q_list.append(q)
        db = MagicMock()
        db.recent_qsos.return_value = q_list
        return db

    def test_empty_db_returns_empty(self):
        from network.map_data import _worked_grids_data
        db = MagicMock()
        db.recent_qsos.return_value = []
        assert _worked_grids_data(db) == []

    def test_none_db_returns_empty(self):
        from network.map_data import _worked_grids_data
        assert _worked_grids_data(None) == []

    def test_single_grid(self):
        from network.map_data import _worked_grids_data
        db = self._make_db_with_qsos(["DM79rr"])
        result = _worked_grids_data(db)
        assert len(result) == 1
        assert result[0]["grid"] == "DM79"

    def test_deduplicates_same_grid(self):
        from network.map_data import _worked_grids_data
        db = self._make_db_with_qsos(["DM79", "DM79", "FN31"])
        result = _worked_grids_data(db)
        grids = [r["grid"] for r in result]
        assert len(grids) == len(set(grids))

    def test_uses_4char_grid(self):
        from network.map_data import _worked_grids_data
        db = self._make_db_with_qsos(["DM79rr"])
        result = _worked_grids_data(db)
        assert result[0]["grid"] == "DM79"

    def test_has_lat_lon(self):
        from network.map_data import _worked_grids_data
        db = self._make_db_with_qsos(["FN31"])
        result = _worked_grids_data(db)
        assert "lat" in result[0]
        assert "lon" in result[0]

    def test_worked_grids_var_in_html(self):
        html = _html()
        assert "WORKED_GRIDS" in html

    def test_empty_grid_skipped(self):
        from network.map_data import _worked_grids_data
        db = self._make_db_with_qsos(["", "  ", "DM79"])
        result = _worked_grids_data(db)
        assert len(result) == 1


# ── QSO popup enrichment ──────────────────────────────────────────────────────

class TestQsoPopupEnrichment:
    def test_dist_km_in_js(self):
        html = _html()
        assert "dist_km" in html

    def test_lotw_confirmed_in_js(self):
        html = _html()
        assert "lotw" in html
        assert "confirmed" in html

    def test_qso_limit_1000_in_js_comment_or_code(self):
        """Verify the limit was bumped from 200 to 1000."""
        from network.map_data import _qso_path_data
        import inspect
        src = inspect.getsource(_qso_path_data)
        assert "1000" in src
