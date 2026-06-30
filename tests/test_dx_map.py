"""Sprint 58 — DX spots on map + band opening detection."""
from __future__ import annotations
import sys
import pathlib
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


class TestDXSpotsMapHTML:
    """build_map_html accepts dx_spots and renders DX star markers."""

    def _html(self, dx_spots=None):
        from network.map_data import build_map_html
        import tempfile
        from pathlib import Path
        from core.config import Config
        tmp = tempfile.mkdtemp()
        cfg = Config(Path(tmp) / "c.json")
        cfg.callsign = "W1AW"
        return build_map_html(cfg, show_adsb=False, show_grayline=False,
                              dx_spots=dx_spots or [])

    def test_dx_spots_param_accepted(self):
        html = self._html([])
        assert "DX_SPOTS" in html

    def test_lyr_dx_spots_layer_group(self):
        assert "lyrDxSpots" in self._html()

    def test_dx_spots_in_layer_control(self):
        assert '"DX Spots"' in self._html()

    def test_dx_band_colors_defined(self):
        assert "DX_BAND_COLS" in self._html()

    def test_empty_dx_spots_no_error(self):
        html = self._html([])
        assert "lyrDxSpots" in html

    def test_resolve_dx_spot_locs_function_exists(self):
        from network.map_data import _resolve_dx_spot_locs
        result = _resolve_dx_spot_locs([])
        assert result == []

    def test_map_tab_has_set_dx_spots(self):
        src = (ROOT / "ui/tabs/map_tab.py").read_text(encoding="utf-8")
        assert "def set_dx_spots(" in src

    def test_dx_spots_passed_to_refresh(self):
        src = (ROOT / "ui/tabs/map_tab.py").read_text(encoding="utf-8")
        idx = src.find("def _refresh_map(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "dx_spots" in body

    def test_modes_tab_pushes_to_map(self):
        # DX cluster code moved to modes_dx_mixin.py (HOUSE-CS split).
        src = (ROOT / "ui/tabs/modes_dx_mixin.py").read_text(encoding="utf-8")
        idx = src.find("def _filter_dx_spots(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "set_dx_spots" in body


class TestBandOpeningDetection:
    """Verify band-opening detection logic."""

    def _src(self):
        return (ROOT / "ui/tabs/modes_tab.py").read_text(encoding="utf-8")

    def test_band_grids_dict_initialized(self):
        assert "_band_grids" in self._src()

    def test_band_prev_cnt_initialized(self):
        assert "_band_prev_cnt" in self._src()

    def test_check_band_openings_method(self):
        assert "def _check_band_openings(" in self._src()

    def test_threshold_defined(self):
        src = self._src()
        idx = src.find("def _check_band_openings(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "THRESHOLD" in body

    def test_band_open_timer_started(self):
        src = self._src()
        assert "_band_open_timer" in src

    def test_ft8_decode_tracks_grid(self):
        src = self._src()
        idx = src.find("def _on_ft8_decode(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_band_grids" in body

    def test_beep_on_band_open(self):
        src = self._src()
        idx = src.find("def _check_band_openings(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "beep()" in body

    def test_band_opening_logic_thresholds(self):
        """Mirror the opening detection logic."""
        band_grids = {"20m": []}
        band_prev  = {"20m": 0}
        threshold  = 5
        cutoff     = time.time() - 300

        # Simulate 6 recent decodes with unique grids
        for i in range(6):
            band_grids["20m"].append((time.time(), f"FN{i:02d}ab"))

        recent = [(ts, g) for ts, g in band_grids["20m"] if ts >= cutoff]
        unique = len({g for _, g in recent})
        prev   = band_prev.get("20m", 0)

        assert unique == 6
        assert unique >= threshold
        assert prev < threshold   # would trigger alert

    def test_old_entries_pruned(self):
        """Entries older than 5 minutes are excluded."""
        old_ts = time.time() - 400  # older than 300s
        recent_ts = time.time() - 60
        entries = [(old_ts, "FN00aa"), (recent_ts, "FN01bb")]
        cutoff  = time.time() - 300
        filtered = [(ts, g) for ts, g in entries if ts >= cutoff]
        assert len(filtered) == 1
        assert filtered[0][1] == "FN01bb"
