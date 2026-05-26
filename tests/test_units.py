# Squelch tests — UI-wide unit handling (metric/imperial)
# Licensed under GNU GPL v3
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class _Cfg:
    def __init__(self, u): self._u = u
    def get(self, k, d=None): return self._u


def test_distance_metric():
    from core.units import format_distance
    assert format_distance(41.2, _Cfg("metric")) == "41.2 km"

def test_distance_imperial():
    from core.units import format_distance
    out = format_distance(41.2, _Cfg("imperial"))
    assert "mi" in out and out.startswith("25.6")

def test_altitude_imperial():
    from core.units import format_altitude
    assert "ft" in format_altitude(100, _Cfg("imperial"))

def test_suffix_and_pref():
    from core.units import distance_suffix, units_pref
    assert distance_suffix(_Cfg("imperial")) == " mi"
    assert distance_suffix(_Cfg("metric")) == " km"
    assert units_pref(_Cfg("imp")) == "imperial"
    assert units_pref(_Cfg(None)) == "metric"

def test_bad_input_safe():
    from core.units import format_distance
    assert format_distance(None, _Cfg("metric")) == "—"
