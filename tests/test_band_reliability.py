"""FEAT-26 — Multi-band reliability chart + FEAT-19 scanner squelch-advance.

Pure-logic tests only (no Qt required for the math tests).
"""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


# ── _band_reliability pure-logic tests ───────────────────────────────────────

class TestBandReliability:

    def _r(self, freq, muf=28.0, luf=3.0, path=3000.0):
        from core.band_reliability import band_reliability
        return band_reliability(freq, muf, luf, path)

    def test_below_luf_absorbed(self):
        rel, status = self._r(1.9, muf=28.0, luf=3.0)
        assert rel == 0.0
        assert "absorb" in status.lower() or "D-" in status

    def test_above_muf_zero(self):
        rel, status = self._r(50.0, muf=28.0)
        assert rel == 0.0
        assert "MUF" in status

    def test_good_band_high_reliability(self):
        rel, _ = self._r(14.15, muf=28.0, luf=3.0)
        assert rel >= 0.5

    def test_marginal_band_lower_reliability(self):
        rel_good,     _ = self._r(14.15, muf=28.0)
        rel_marginal, _ = self._r(26.0,  muf=28.0)  # just below MUF
        assert rel_good > rel_marginal

    def test_reliability_bounded_0_to_1(self):
        for freq in (1.9, 3.7, 7.1, 10.1, 14.1, 18.1, 21.2, 24.9, 28.3):
            rel, _ = self._r(freq)
            assert 0.0 <= rel <= 1.0, f"Out of range for {freq} MHz: {rel}"

    def test_nvis_path_caps_muf(self):
        # On a 300 km path, 28 MHz should be above effective MUF (capped to 11 MHz)
        rel, status = self._r(28.3, muf=28.0, path=300.0)
        assert rel == 0.0
        assert "MUF" in status

    def test_nvis_path_low_freq_viable(self):
        # On a 300 km path, 7 MHz is viable if within NVIS range
        rel, _ = self._r(7.1, muf=28.0, luf=2.0, path=300.0)
        assert rel > 0.1

    def test_long_path_muf_reduced(self):
        # On a 7000 km path, MUF is reduced by 15%
        # A frequency just below the original MUF should become "above MUF"
        rel_short, _ = self._r(27.0, muf=28.0, path=3000.0)
        rel_long,  _ = self._r(27.0, muf=28.0, path=7000.0)
        # Long path effective MUF = 28 * 0.85 = 23.8 MHz; 27 > 23.8 → 0
        assert rel_long == 0.0
        assert rel_short > 0.0

    def test_no_data_returns_zero(self):
        rel, status = self._r(14.15, muf=0.0)
        assert rel == 0.0
        assert "data" in status.lower() or status == "No data"


# ── Source-level wiring checks ────────────────────────────────────────────────

class TestBandReliabilityWiring:

    def _src(self):
        return (ROOT / "ui/tabs/band_conditions_tab.py").read_text(encoding="utf-8")

    def test_band_reliability_fn_in_core(self):
        src = (ROOT / "core/band_reliability.py").read_text(encoding="utf-8")
        assert "def band_reliability(" in src

    def test_chart_class_exists(self):
        assert "class BandReliabilityChart(" in self._src()

    def test_group_builder_exists(self):
        assert "_build_path_reliability_group" in self._src()

    def test_chart_wired_in_build_bands_pane(self):
        src = self._src()
        idx = src.find("def _build_bands_pane(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_build_path_reliability_group" in body

    def test_chart_updated_in_update_path_sideview(self):
        src = self._src()
        idx = src.find("def _update_path_sideview(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_reliability_chart" in body
        assert "update_path(" in body

    def test_nvis_logic_in_fn(self):
        src = (ROOT / "core/band_reliability.py").read_text(encoding="utf-8")
        assert "< 400" in src

    def test_long_path_logic_in_fn(self):
        src = (ROOT / "core/band_reliability.py").read_text(encoding="utf-8")
        assert "> 5000" in src

    def test_fot_computed(self):
        src = (ROOT / "core/band_reliability.py").read_text(encoding="utf-8")
        assert "0.85 * eff_muf" in src or "fot" in src


class TestScannerSquelchAdvance:

    def _src(self):
        return (ROOT / "ui/tabs/sdr_scanner.py").read_text(encoding="utf-8")

    def _sdr_src(self):
        return (ROOT / "ui/tabs/sdr_tab.py").read_text(encoding="utf-8")

    def test_squelch_advance_checkbox_in_sdr_tab(self):
        assert "_scan_squelch_cb" in self._sdr_src()

    def test_squelch_advance_check_in_scan_step(self):
        src = self._src()
        idx = src.find("def _scan_step(")
        body = src[idx: src.find("\ndef ", idx + 10)]
        assert "_scan_squelch_cb" in body
        assert "_squelch_open" in body

    def test_held_flag_tracked(self):
        src = self._src()
        assert "_scan_held" in src

    def test_valid_range_check(self):
        src = self._src()
        assert "lo >= hi" in src or "lo < hi" in src

    def test_initial_tune_on_start(self):
        src = self._src()
        idx = src.find("def _start_scan(")
        body = src[idx: src.find("\ndef ", idx + 10)]
        assert "_set_freq(self._scan_cur)" in body
