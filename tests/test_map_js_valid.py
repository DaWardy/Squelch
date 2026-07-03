# Squelch — RF / SDR signal platform
# Licensed under GNU GPL v3 — see LICENSE.
"""Regression guard: the generated map page's inline JavaScript must PARSE.

A single JS syntax error in build_map_html() aborts the whole Leaflet script and
the map renders black — and it is invisible to the string-based map tests and to
headless Qt (WebEngine can't render offscreen). This test parses the emitted
inline script with a real JS parser so such a break fails CI, not the user.

Skips cleanly if `esprima` (pure-Python JS parser) isn't installed.
"""

import pytest

esprima = pytest.importorskip("esprima")

from core.config import Config
from network.map_data import build_map_html


def _inline_script(html: str) -> str:
    lines = html.split("\n")
    start = next(i for i, l in enumerate(lines) if l.strip() == "<script>")
    end = next(i for i in range(start + 1, len(lines))
               if lines[i].strip() == "</script>")
    return "\n".join(lines[start + 1:end])


def _build(**kw) -> str:
    return build_map_html(config=Config(), **kw)


def test_empty_map_js_parses():
    esprima.parseScript(_inline_script(_build()))


def test_satellite_marker_js_parses():
    # The satellite marker block was the historical break (var statements inside
    # an object literal). Exercise it with real satellite data.
    sats = [
        {"name": "ISS (ZARYA)", "lat": 10.0, "lon": 20.0, "alt_km": 420.0,
         "el_deg": 12.0, "is_visible": True,
         "next_pass": {"aos": "12:00", "los": "12:10",
                       "max_el": 45.0, "aos_az": 270.0}},
        {"name": "AO-91", "lat": -5.0, "lon": 100.0, "alt_km": 800.0,
         "el_deg": None, "is_visible": False, "next_pass": None},
    ]
    esprima.parseScript(_inline_script(_build(satellites=sats)))


def test_populated_map_js_parses():
    # A grab-bag of overlays to exercise the marker-building loops.
    heard = {"AA1BB": {"lat": 40.0, "lon": -75.0, "grid": "FN20", "count": 3}}
    aprs = [{"call": "N0CALL-9", "lat": 33.0, "lon": -117.0,
             "comment": "test", "symbol": ">"}]
    dx = [{"dx": "DL1ABC", "freq": 14074.0, "spotter": "W1AW",
           "lat": 51.0, "lon": 10.0}]
    esprima.parseScript(_inline_script(
        _build(heard_stations=heard, aprs_stations=aprs, dx_spots=dx)))
