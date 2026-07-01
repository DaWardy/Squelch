"""Sprint 64 — Memory scan mode + grid square calculator."""
from __future__ import annotations
import sys
import pathlib
import math

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


# ── Rig scanner memory mode ───────────────────────────────────────────────────

class TestMemoryScanMode:

    def _src(self):
        # Scanner code lives in rig_scanner_mixin.py (HOUSE-CS split).
        return (ROOT / "ui/tabs/rig_scanner_mixin.py").read_text(encoding="utf-8")

    def test_memory_mode_in_combo(self):
        src = self._src()
        assert '"Memory"' in src

    def test_channel_list_mode_in_combo(self):
        src = self._src()
        assert '"Channel list"' in src

    def test_scan_list_mode_flag_used(self):
        src = self._src()
        assert "_scan_list_mode" in src

    def test_memory_scan_builds_channel_list(self):
        src = self._src()
        idx = src.find("def _start_scan(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_scan_channel_list" in body
        assert "_memories.items()" in body

    def test_channel_list_parses_csv_freqs(self):
        src = self._src()
        idx = src.find("def _start_scan(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "replace" in body or "split" in body   # CSV parsing

    def test_scan_step_uses_channel_index(self):
        src = self._src()
        idx = src.find("def _scan_step(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_scan_channel_idx" in body
        assert "_scan_channel_list" in body

    def test_mode_set_during_memory_scan(self):
        src = self._src()
        idx = src.find("def _scan_step(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "infer_rig_mode" in body or "set_mode" in body

    def test_channel_status_shows_channel_number(self):
        src = self._src()
        idx = src.find("def _scan_step(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "Ch " in body or "ch " in body.lower()


class TestMemoryScanLogic:
    """Pure-logic tests for memory channel list building."""

    def test_memories_sorted_by_slot(self):
        memories = {3: (14_074_000, "FT8", "FT8 calling"),
                    1: (7_074_000, "FT8", "40m FT8"),
                    2: (3_573_000, "FT4", "80m FT4")}
        channels = sorted(memories.items())
        slots = [slot for slot, _ in channels]
        assert slots == [1, 2, 3]

    def test_channel_list_parsed(self):
        raw = "14.074, 7.074, 3.573"
        freqs = []
        for tok in raw.replace(";", ",").split(","):
            tok = tok.strip()
            if tok:
                try:
                    freqs.append(int(float(tok) * 1_000_000))
                except ValueError:
                    pass
        assert freqs == [14_074_000, 7_074_000, 3_573_000]

    def test_channel_index_wraps(self):
        channel_list = [(14_074_000, "FT8", "20m"),
                        (7_074_000,  "FT8", "40m")]
        idx = 0
        for _ in range(5):
            idx = (idx + 1) % len(channel_list)
        # After 5 steps with 2 channels: 1, 0, 1, 0, 1
        assert idx == 1


# ── Grid square calculator ────────────────────────────────────────────────────

class TestGridCalcDialog:

    def _src(self):
        return (ROOT / "ui/dialogs/grid_calc_dialog.py").read_text(encoding="utf-8")

    def test_class_exists(self):
        assert "class GridCalcDialog(" in self._src()

    def test_calc_from_grid_method(self):
        assert "def _calc_from_grid(" in self._src()

    def test_calc_from_latlon_method(self):
        assert "def _calc_from_latlon(" in self._src()

    def test_uses_grid_to_latlon(self):
        assert "_grid_to_latlon" in self._src()

    def test_uses_latlon_to_grid(self):
        assert "_latlon_to_grid" in self._src()

    def test_distance_calculation(self):
        assert "_haversine_km" in self._src()

    def test_compass_point_function(self):
        assert "_compass_point" in self._src()

    def test_show_grid_calc_in_main_window(self):
        # Help-menu label "Grid Square Calculator…" was extracted to
        # main_window_menu.py (HOUSE-CS); the _show_grid_calc handler stays.
        src = ((ROOT / "ui/main_window.py").read_text(encoding="utf-8") + "\n"
               + (ROOT / "ui/main_window_menu.py").read_text(encoding="utf-8"))
        assert "_show_grid_calc" in src
        assert "Grid Square Calculator" in src


class TestGridCalcLogic:
    """Pure-logic tests for compass point and bearing."""

    def _compass(self, deg):
        pts = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
               "S","SSW","SW","WSW","W","WNW","NW","NNW"]
        return pts[int((deg + 11.25) / 22.5) % 16]

    def test_north(self):
        assert self._compass(0) == "N"
        assert self._compass(360) == "N"

    def test_east(self):
        assert self._compass(90) == "E"

    def test_south(self):
        assert self._compass(180) == "S"

    def test_west(self):
        assert self._compass(270) == "W"

    def test_northeast(self):
        assert self._compass(45) == "NE"

    def test_bearing_range(self):
        for deg in range(0, 360, 15):
            pt = self._compass(deg)
            assert pt in ["N","NNE","NE","ENE","E","ESE","SE","SSE",
                          "S","SSW","SW","WSW","W","WNW","NW","NNW"]
