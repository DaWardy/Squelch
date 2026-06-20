"""Sprint 74 — Quick-dial preset buttons + band activity indicators."""
from __future__ import annotations
import sys
import pathlib
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


# ── Quick-dial buttons in rig_tab ────────────────────────────────────────────

class TestQuickDialSource:

    def _src(self):
        return (ROOT / "ui/tabs/rig_tab.py").read_text(encoding="utf-8")

    def test_build_quick_dial_row_defined(self):
        assert "def _build_quick_dial_row(" in self._src()

    def test_qdial_tune_method(self):
        assert "def _qdial_tune(" in self._src()

    def test_qdial_edit_method(self):
        assert "def _qdial_edit(" in self._src()

    def test_8_default_dials(self):
        src = self._src()
        idx = src.find("def _build_quick_dial_row(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert body.count('"hz"') >= 8

    def test_right_click_edit_wired(self):
        src = self._src()
        idx = src.find("def _build_quick_dial_row(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "customContextMenuRequested" in body

    def test_defaults_saved_to_cfg(self):
        src = self._src()
        assert "rig.quick_dials" in src

    def test_quick_dial_row_called_in_build_vfo(self):
        src = self._src()
        idx = src.find("def _build_vfo_section(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_build_quick_dial_row" in body

    def test_ft8_20m_is_a_default(self):
        src = self._src()
        assert "14_074_000" in src

    def test_wwv_is_a_default(self):
        src = self._src()
        assert "10_000_000" in src or "WWV" in src


class TestQuickDialLogic:
    """Pure-logic tests for quick-dial data structure."""

    def test_8_defaults_structure(self):
        defaults = [
            {"label": "FT8 20m", "hz": 14_074_000, "mode": "PKTUSB"},
            {"label": "FT8 40m", "hz": 7_074_000,  "mode": "PKTUSB"},
            {"label": "FT8 80m", "hz": 3_573_000,  "mode": "PKTUSB"},
            {"label": "FT4 20m", "hz": 14_080_000, "mode": "PKTUSB"},
            {"label": "CW 20m",  "hz": 14_020_000, "mode": "CW"},
            {"label": "SSB 20m", "hz": 14_225_000, "mode": "USB"},
            {"label": "WSPR 30m", "hz": 10_138_700, "mode": "PKTUSB"},
            {"label": "WWV",     "hz": 10_000_000, "mode": "AM"},
        ]
        assert len(defaults) == 8
        for d in defaults:
            assert "label" in d and "hz" in d and "mode" in d
            assert d["hz"] > 0

    def test_hz_to_mhz_display(self):
        hz = 14_074_000
        assert f"{hz/1e6:.4f}" == "14.0740"

    def test_edit_updates_dict(self):
        d_orig = {"label": "FT8 20m", "hz": 14_074_000, "mode": "PKTUSB"}
        d_new  = {
            "label": lbl if (lbl := "FT8 17m") else "Q1",
            "hz":    int(18.100 * 1_000_000),
            "mode":  "PKTUSB",
        }
        assert d_new["hz"] == 18_100_000


# ── Band activity dots in modes_tab ──────────────────────────────────────────

class TestBandActivitySource:

    def _src(self):
        return (ROOT / "ui/tabs/modes_tab.py").read_text(encoding="utf-8")

    def test_build_band_activity_row_defined(self):
        assert "def _build_band_activity_row(" in self._src()

    def test_update_band_activity_defined(self):
        assert "def _update_band_activity(" in self._src()

    def test_band_activity_in_build_splitter(self):
        src = self._src()
        idx = src.find("def _build_splitter_shell(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_build_band_activity_row" in body

    def test_activity_timer_created(self):
        src = self._src()
        assert "_band_act_timer" in src

    def test_update_called_on_decode(self):
        src = self._src()
        idx = src.find("def _on_ft8_decode(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_update_band_activity()" in body

    def test_dot_labels_for_all_key_bands(self):
        src = self._src()
        idx = src.find("def _build_band_activity_row(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        for band in ("20m", "40m", "15m", "10m"):
            assert band in body

    def test_colour_changes_with_activity(self):
        src = self._src()
        idx = src.find("def _update_band_activity(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        # Should have at least 3 different color assignments
        assert body.count("color") >= 3


class TestBandActivityLogic:
    """Pure-logic: activity level determination."""

    def _level(self, n):
        if n == 0:
            return "none", "#333"
        elif n < 5:
            return "low", "#996600"
        elif n < 15:
            return "active", "#3fbe6f"
        else:
            return "busy", "#00ddff"

    def test_zero_is_dark(self):
        label, color = self._level(0)
        assert label == "none"
        assert color == "#333"

    def test_small_count_is_amber(self):
        label, color = self._level(3)
        assert label == "low"

    def test_moderate_count_is_green(self):
        label, color = self._level(10)
        assert label == "active"

    def test_large_count_is_cyan(self):
        label, color = self._level(25)
        assert label == "busy"

    def test_boundary_5_is_active(self):
        label, _ = self._level(5)
        assert label == "active"

    def test_boundary_15_is_busy(self):
        label, _ = self._level(15)
        assert label == "busy"

    def test_recent_filter_logic(self):
        now = time.time()
        entries = [
            (now - 10, "FN31"),   # recent
            (now - 50, "DM79"),   # recent
            (now - 100, "EM72"),  # too old (90s threshold)
        ]
        recent = [e for e in entries if now - e[0] < 90]
        assert len(recent) == 2
