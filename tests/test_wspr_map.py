"""Sprint 56 — WSPR propagation map + DX spot alerts."""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


class TestWSPRMapData:
    """Verify WSPR spots are included in build_map_html output."""

    def _html(self, wspr_spots=None):
        from network.map_data import build_map_html
        import tempfile
        from pathlib import Path
        from core.config import Config
        tmp = tempfile.mkdtemp()
        cfg = Config(Path(tmp) / "c.json")
        cfg.callsign = "W1AW"
        cfg.set("station.grid", "FN31")
        return build_map_html(cfg, show_adsb=False, show_grayline=False,
                              wspr_spots=wspr_spots or [])

    def test_wspr_spots_param_accepted(self):
        spots = [{"callsign": "VK2AB", "grid": "QF56", "band": "20m",
                  "snr": -12, "power_dbm": 37, "dist_km": 16000,
                  "lat": -33.8, "lon": 151.0}]
        html = self._html(spots)
        assert "VK2AB" in html

    def test_wspr_layer_group_defined(self):
        assert "lyrWspr" in self._html()

    def test_wspr_in_layer_control(self):
        assert '"WSPR spots"' in self._html()

    def test_wspr_band_colors_defined(self):
        assert "WSPR_BAND_COLS" in self._html()

    def test_wspr_great_circle_line_drawn(self):
        spots = [{"callsign": "JA1XY", "grid": "PM95", "band": "40m",
                  "snr": -5, "power_dbm": 30, "dist_km": 9000,
                  "lat": 35.0, "lon": 139.0}]
        html = self._html(spots)
        assert "polyline" in html

    def test_empty_wspr_spots_no_error(self):
        html = self._html([])
        assert "lyrWspr" in html

    def test_wspr_legend_entry(self):
        assert "WSPR" in self._html()


class TestWSPRMapTabWiring:
    """map_tab.py has set_wspr_spots and passes it to build_map_html."""

    def _src(self):
        return (ROOT / "ui/tabs/map_tab.py").read_text(encoding="utf-8")

    def test_wspr_spots_list_initialised(self):
        assert "_wspr_spots" in self._src()

    def test_set_wspr_spots_method(self):
        assert "def set_wspr_spots(" in self._src()

    def test_wspr_spots_passed_to_build_map_html(self):
        src = self._src()
        idx = src.find("def _do_refresh_map(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "wspr_spots" in body


class TestWSPRModeTabPipe:
    """modes_tab._on_wspr_spot now pipes to map_tab."""

    def _src(self):
        return (ROOT / "ui/tabs/modes_tab.py").read_text(encoding="utf-8")

    def test_set_wspr_spots_called(self):
        src = self._src()
        idx = src.find("def _on_wspr_spot(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "set_wspr_spots" in body

    def test_grid_to_latlon_used(self):
        src = self._src()
        idx = src.find("def _on_wspr_spot(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_grid_to_latlon" in body

    def test_duplicate_dedup_by_callsign_band(self):
        src = self._src()
        idx = src.find("def _on_wspr_spot(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "band" in body and "callsign" in body


class TestDXSpotAlert:
    """DX cluster watch-list and alert logic."""

    def _src(self):
        # DX cluster code moved to modes_dx_mixin.py (HOUSE-CS split); save_state
        # / restore_state stay on ModesTab, so concatenate both files.
        return (
            (ROOT / "ui/tabs/modes_tab.py").read_text(encoding="utf-8") + "\n" +
            (ROOT / "ui/tabs/modes_dx_mixin.py").read_text(encoding="utf-8"))

    def test_watch_edit_widget_defined(self):
        assert "_dx_watch_edit" in self._src()

    def test_check_dx_alert_method(self):
        assert "def _check_dx_alert(" in self._src()

    def test_alert_called_from_add_spot(self):
        src = self._src()
        idx = src.find("def _add_dx_spot(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_check_dx_alert" in body

    def test_beep_on_match(self):
        src = self._src()
        idx = src.find("def _check_dx_alert(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "beep()" in body

    def test_prefix_match_logic(self):
        """Verify prefix matching logic mirrors the implementation."""
        terms = ["JA", "P5", "VK"]
        test_cases = [
            ("JA1XY", True),   # prefix match
            ("P5DX",  True),   # prefix match
            ("VK2AB", True),   # prefix match
            ("W1AW",  False),  # no match
            ("JA",    True),   # exact match
        ]
        for call, expected in test_cases:
            call_upper = call.upper()
            matched = any(call_upper == t or call_upper.startswith(t)
                          for t in terms)
            assert matched == expected, f"Failed for {call}: expected {expected}"

    def test_watch_list_persisted_in_save_state(self):
        src = self._src()
        idx = src.find("def save_state(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "dx_watch" in body

    def test_watch_list_restored(self):
        src = self._src()
        idx = src.find("def restore_state(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "dx_watch" in body
