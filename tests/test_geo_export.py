# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/geo_export — KML/GPX export of located signals."""

from pathlib import Path

from core.geo_export import (signals_to_kml, signals_to_gpx, points_to_gpx,
                             points_to_kml, save)
from core.signal_model import Signal


def _sigs():
    return [
        Signal(freq_hz=162_550_000, lat=47.6, lon=-122.3,
               classification="NOAA WX", modulation="FM"),
        Signal(freq_hz=146_520_000, lat=0.0, lon=0.0),      # no fix → skipped
        Signal(freq_hz=161_975_000, lat=37.8, lon=-122.34,
               classification="AIS", decoded="mmsi 366053209"),
    ]


def test_signals_to_kml_has_placemarks():
    kml = signals_to_kml(_sigs())
    assert kml.startswith("<?xml")
    assert kml.count("<Placemark>") == 2               # the zero-fix one skipped
    assert "-122.300000,47.600000,0" in kml            # KML is lon,lat


def test_signals_to_gpx_has_waypoints():
    gpx = signals_to_gpx(_sigs())
    assert gpx.count("<wpt ") == 2
    assert 'lat="37.800000" lon="-122.340000"' in gpx


def test_kml_escapes_text():
    s = Signal(freq_hz=1_000_000, lat=1.0, lon=2.0, classification="A & <B>")
    kml = signals_to_kml([s])
    assert "A & <B>" not in kml
    assert "&amp;" in kml and "&lt;B&gt;" in kml


def test_points_to_gpx_track():
    gpx = points_to_gpx([(1.0, 2.0), (1.1, 2.1)], track=True)
    assert "<trkseg>" in gpx and gpx.count("<trkpt ") == 2


def test_points_out_of_range_skipped():
    kml = points_to_kml([(999.0, 0.0), (10.0, 20.0)])
    assert kml.count("<Placemark>") == 1


def test_save_roundtrip(tmp_path):
    p = tmp_path / "out" / "sigs.kml"
    assert save(p, signals_to_kml(_sigs())) is True
    assert Path(p).exists() and "<kml" in p.read_text(encoding="utf-8")
