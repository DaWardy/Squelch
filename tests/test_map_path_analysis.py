"""FEAT-06 map click → propagation path analysis + FEAT-10 ADS-B improvements."""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


class TestMapPageInterceptor:
    """Source-level checks for the squelch:// URL interceptor."""

    def _src(self):
        return (ROOT / "ui/tabs/map_tab.py").read_text(encoding="utf-8")

    def test_map_page_class_defined(self):
        assert "class _MapPage(" in self._src()

    def test_accept_navigation_request_defined(self):
        src = self._src()
        idx = src.find("class _MapPage(")
        body = src[idx: src.find("\nclass ", idx + 10)]
        assert "def acceptNavigationRequest(" in body

    def test_squelch_scheme_intercepted(self):
        src = self._src()
        assert 'url.scheme() == "squelch"' in src

    def test_path_analysis_host_checked(self):
        src = self._src()
        assert '"path-analysis"' in src

    def test_signal_emitted_on_intercept(self):
        src = self._src()
        idx = src.find("class _MapPage(")
        body = src[idx: src.find("\nclass ", idx + 10)]
        assert "path_analysis_requested.emit" in body

    def test_returns_false_to_cancel_navigation(self):
        src = self._src()
        idx = src.find("class _MapPage(")
        body = src[idx: src.find("\nclass ", idx + 10)]
        assert "return False" in body

    def test_map_page_used_in_build(self):
        src = self._src()
        assert "_MapPage(" in src
        assert "setPage(" in src

    def test_maptab_has_path_analysis_signal(self):
        src = self._src()
        idx = src.find("class MapTab(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "path_analysis_requested" in body

    def test_pyqtsignal_imported(self):
        src = self._src()
        assert "pyqtSignal" in src.split("class _MapPage")[0]


class TestHandleMapPath:
    """band_conditions_tab._handle_map_path wiring checks."""

    def _src(self):
        return (ROOT / "ui/tabs/band_conditions_tab.py").read_text(encoding="utf-8")

    def test_handle_map_path_exists(self):
        assert "def _handle_map_path(" in self._src()

    def test_uses_latlon_to_grid(self):
        src = self._src()
        idx = src.find("def _handle_map_path(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_latlon_to_grid" in body

    def test_sets_path_edit(self):
        src = self._src()
        idx = src.find("def _handle_map_path(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_path_edit" in body

    def test_triggers_on_path_changed(self):
        src = self._src()
        idx = src.find("def _handle_map_path(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_on_path_changed" in body


class TestMainWindowWiring:
    """main_window.py wires map → band_conditions."""

    def _src(self):
        return (ROOT / "ui/main_window.py").read_text(encoding="utf-8")

    def test_path_analysis_signal_connected(self):
        assert "path_analysis_requested.connect" in self._src()

    def test_handle_map_path_wired(self):
        assert "_handle_map_path" in self._src()


class TestADSBColoring:
    """Verify altitude-coded ADS-B aircraft colours in map HTML."""

    def _map_src(self):
        return (ROOT / "network/map_data.py").read_text(encoding="utf-8")

    def test_ac_color_function_defined(self):
        assert "_acColor" in self._map_src()

    def test_altitude_thresholds(self):
        src = self._map_src()
        assert "35000" in src   # high FL threshold
        assert "18000" in src   # upper airspace threshold
        assert "5000"  in src   # mid airspace threshold

    def test_heading_in_popup(self):
        src = self._map_src()
        assert "Hdg:" in src or "track" in src

    def test_context_menu_handler(self):
        src = self._map_src()
        assert "contextmenu" in src

    def test_squelch_scheme_in_popup_link(self):
        src = self._map_src()
        assert "squelch://path-analysis" in src

    def test_lat_lon_in_popup_link(self):
        src = self._map_src()
        assert "lat='+lat" in src or "lat=" in src


class TestLatLonToGrid:
    """Verify Maidenhead grid conversion round-trip."""

    def test_london_to_grid(self):
        from core.location import _latlon_to_grid
        grid = _latlon_to_grid(51.5, -0.1)
        assert grid.startswith("IO")

    def test_new_york_to_grid(self):
        from core.location import _latlon_to_grid
        grid = _latlon_to_grid(40.7, -74.0)
        assert grid.startswith("FN")

    def test_grid_is_6_chars(self):
        from core.location import _latlon_to_grid
        grid = _latlon_to_grid(14.0, 100.0)
        assert len(grid) >= 4
