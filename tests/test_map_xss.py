"""Security tests — map HTML/JS injection (XSS) hardening in network/map_data.py.

RF/network-sourced strings (APRS comments, DX-cluster callsigns, etc.) are
concatenated into Leaflet popup HTML by the embedded map's JS. They must be
HTML-escaped before embedding so a malicious payload cannot inject markup or
script into the QWebEngine view.
"""
from __future__ import annotations
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _make_cfg():
    from core.config import Config
    tmp = tempfile.mkdtemp()
    cfg = Config(Path(tmp) / "config.json")
    cfg.callsign = "W1AW"
    cfg.set("station.grid", "FN31pr")
    cfg.set("station.lat", 41.7)
    cfg.set("station.lon", -72.7)
    return cfg


def _html(**kwargs) -> str:
    from network.map_data import build_map_html
    kwargs.setdefault("show_adsb", False)      # no network
    kwargs.setdefault("show_grayline", False)
    return build_map_html(_make_cfg(), **kwargs)


class TestEscDeep:
    def test_escapes_angle_brackets(self):
        from network.map_data import _esc_deep
        assert _esc_deep("<script>") == "&lt;script&gt;"

    def test_escapes_quotes(self):
        from network.map_data import _esc_deep
        out = _esc_deep('"x" \'y\'')
        assert '"' not in out and "'" not in out
        assert "&quot;" in out and "&#x27;" in out

    def test_escapes_ampersand(self):
        from network.map_data import _esc_deep
        assert _esc_deep("a & b") == "a &amp; b"

    def test_recurses_into_list(self):
        from network.map_data import _esc_deep
        assert _esc_deep(["<b>", "ok"]) == ["&lt;b&gt;", "ok"]

    def test_recurses_into_dict(self):
        from network.map_data import _esc_deep
        out = _esc_deep({"call": "<img>", "lat": 40.7})
        assert out["call"] == "&lt;img&gt;"
        assert out["lat"] == 40.7  # numbers untouched

    def test_recurses_nested(self):
        from network.map_data import _esc_deep
        out = _esc_deep({"aprs": [{"call": "K1<x>", "comment": "hi<svg>"}]})
        assert out["aprs"][0]["call"] == "K1&lt;x&gt;"
        assert out["aprs"][0]["comment"] == "hi&lt;svg&gt;"

    def test_numbers_and_bools_untouched(self):
        from network.map_data import _esc_deep
        assert _esc_deep(42) == 42
        assert _esc_deep(3.14) == 3.14
        assert _esc_deep(True) is True
        assert _esc_deep(None) is None


class TestBuildMapHtmlEscapes:
    """End-to-end through the public build_map_html (real render path)."""

    def test_malicious_aprs_comment_is_escaped(self):
        payload = '<img src=x onerror=alert(1)>'
        out = _html(aprs_stations=[{"call": "K1ABC", "lat": 1.0, "lon": 2.0,
                                    "comment": payload}])
        assert payload not in out          # raw payload must not survive
        assert "&lt;img" in out            # escaped form present

    def test_malicious_aprs_callsign_is_escaped(self):
        payload = '<script>steal()</script>'
        out = _html(aprs_stations=[{"call": payload, "lat": 1.0, "lon": 2.0,
                                    "comment": "hi"}])
        assert "<script>steal()" not in out
        assert "&lt;script&gt;" in out

    def test_satellite_name_escaped(self):
        out = _html(satellites=[{"name": '"><b>pwn', "lat": 1.0, "lon": 2.0,
                                 "visible": True}])
        assert '"><b>pwn' not in out

    def test_winlink_callsign_escaped(self):
        out = _html(winlink_gateways=[{"callsign": "<i>x</i>", "grid": "FN31",
                                       "lat": 1.0, "lon": 2.0}])
        assert "<i>x</i>" not in out

    def test_grayline_json_not_corrupted_when_present(self):
        # With grayline on, GRAYLINE must remain valid JSON (not HTML-escaped)
        out = _html(show_grayline=True)
        assert "var GRAYLINE" in out
        # the JS assignment must not contain HTML entities from over-escaping
        line = [ln for ln in out.splitlines() if "var GRAYLINE" in ln][0]
        assert "&quot;" not in line and "&lt;" not in line

    def test_station_coords_render_as_numbers(self):
        import re
        out = _html()
        # MY_LAT / MY_LON must be bare numeric literals, not quoted/escaped
        m_lat = re.search(r"var MY_LAT\s*=\s*([^;]+);", out)
        m_lon = re.search(r"var MY_LON\s*=\s*([^;]+);", out)
        assert m_lat and m_lon
        for tok in (m_lat.group(1).strip(), m_lon.group(1).strip()):
            assert '"' not in tok and "&" not in tok  # not a string / not escaped
            float(tok)  # parses as a number
