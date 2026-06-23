"""Sprint 46 — FEAT-16 NR slider + FEAT-18 LO offset tests.

All pure-logic (no Qt / no hardware).
"""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest

ROOT = pathlib.Path(__file__).parent.parent


class TestNRSource:
    """Source-level checks for noise reduction wiring."""

    def _src(self):
        return (ROOT / "ui/tabs/sdr_tab.py").read_text(encoding="utf-8")

    def test_nr_state_vars(self):
        src = self._src()
        assert "_nr_enabled" in src
        assert "_nr_level" in src

    def test_nr_widgets_defined(self):
        src = self._src()
        assert "_nr_cb" in src
        assert "_nr_slider" in src
        assert "_nr_lbl" in src

    def test_nr_handler_methods(self):
        src = self._src()
        assert "def _on_nr_toggle(" in src
        assert "def _on_nr_slider(" in src

    def test_nr_applied_in_on_samples(self):
        src = self._src()
        idx = src.find("def _on_samples(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_nr_enabled" in body

    def test_nr_in_save_state(self):
        src = self._src()
        idx = src.find("def save_state(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "nr_enabled" in body
        assert "nr_level" in body

    def test_nr_in_restore_state(self):
        src = self._src()
        idx = src.find("def restore_state(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "nr_enabled" in body


class TestLOOffsetSource:
    """Source-level checks for LO offset wiring."""

    def _sdr(self):
        return (ROOT / "ui/tabs/sdr_tab.py").read_text(encoding="utf-8")

    def _settings_sdr(self):
        return (ROOT / "ui/dialogs/settings_sdr_tab.py").read_text(encoding="utf-8")

    def _settings_dlg(self):
        return (ROOT / "ui/dialogs/settings_dialog.py").read_text(encoding="utf-8")

    def test_lo_hz_property_defined(self):
        assert "def _lo_hz" in self._sdr()

    def test_lo_offset_applied_in_update_plots(self):
        src = self._sdr()
        idx = src.find("def _update_plots(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_lo_hz" in body or "lo_off" in body

    def test_lo_offset_applied_in_update_axes(self):
        src = self._sdr()
        idx = src.find("def _update_axes(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_lo_hz" in body or "lo_off" in body

    def test_lo_offset_applied_in_click_handlers(self):
        src = self._sdr()
        for fn in ("_on_wf_click", "_on_spec_click"):
            idx = src.find(f"def {fn}(")
            body = src[idx: src.find("\n    def ", idx + 10)]
            assert "_lo_hz" in body, f"LO offset not applied in {fn}"

    def test_lo_offset_spinbox_in_settings_sdr(self):
        assert "_lo_offset_spin" in self._settings_sdr()

    def test_sdr_lo_hz_key_in_settings_dialog(self):
        src = self._settings_dlg()
        assert "sdr.lo_offset_hz" in src

    def test_save_sdr_called_on_apply(self):
        src = self._settings_dlg()
        idx = src.find("cfg.save()")
        # _save_sdr should appear before cfg.save()
        assert "_save_sdr(" in src[:idx]


class TestLOOffsetMath:
    """Verify the LO-offset frequency-shift arithmetic."""

    def test_positive_offset_shifts_display_up(self):
        # With LO offset +125 MHz, a 3 MHz hw freq displays as 128 MHz
        center_hz = 3_000_000
        lo_hz     = 125_000_000
        displayed_mhz = (center_hz + lo_hz) / 1e6
        assert abs(displayed_mhz - 128.0) < 0.001

    def test_negative_offset_shifts_display_down(self):
        # With LO offset -125 MHz, a 128 MHz hw freq displays as 3 MHz
        center_hz = 128_000_000
        lo_hz     = -125_000_000
        displayed_mhz = (center_hz + lo_hz) / 1e6
        assert abs(displayed_mhz - 3.0) < 0.001

    def test_zero_offset_no_change(self):
        center_hz = 14_074_000
        lo_hz     = 0
        assert (center_hz + lo_hz) / 1e6 == 14.074

    def test_click_reverses_offset(self):
        # User clicks at displayed 128 MHz; with lo_hz = +125 MHz
        # actual hw freq = 128 - 125 = 3 MHz
        displayed_click_hz = 128_000_000
        lo_hz = 125_000_000
        hw_freq = displayed_click_hz - lo_hz
        assert hw_freq == 3_000_000


class TestNRSmoothing:
    """Verify NR spectral averaging logic (mirrors _on_samples NR block)."""

    def _apply_nr(self, data, level):
        try:
            import numpy as np
        except ImportError:
            pytest.skip("numpy not installed")
        win = 1 + int(level / 100 * 15)
        kernel = np.ones(win) / win
        return np.convolve(data, kernel, mode='same')

    def test_nr_zero_no_change(self):
        try:
            import numpy as np
        except ImportError:
            pytest.skip("numpy not installed")
        data = np.array([1.0, 5.0, 1.0, 5.0, 1.0])
        result = self._apply_nr(data, 0)  # win=1 → kernel=[1] → identity
        np.testing.assert_array_almost_equal(result, data)

    def test_nr_100_strong_smoothing(self):
        try:
            import numpy as np
        except ImportError:
            pytest.skip("numpy not installed")
        data = np.zeros(100)
        data[50] = 100.0
        result = self._apply_nr(data, 100)
        assert result[50] < 20.0

    def test_nr_increases_smoothing_with_level(self):
        try:
            import numpy as np
        except ImportError:
            pytest.skip("numpy not installed")
        # Broadband noise is the right signal to show smoothing: a moving
        # average reduces noise std by ~1/sqrt(window), so a wider (level-90)
        # kernel must leave less interior variance than a narrow (level-10) one.
        # (An alternating 0/100 signal is degenerate — any even window → flat 50.)
        # Compare the INTERIOR only; mode='same' edges have partial-window ramps.
        rng = np.random.default_rng(42)
        data = rng.standard_normal(512) * 10.0
        r_low  = self._apply_nr(data, 10)   # win = 2
        r_high = self._apply_nr(data, 90)   # win = 14
        m = 16   # trim wider than the largest kernel (win <= 14)
        assert float(np.std(r_high[m:-m])) < float(np.std(r_low[m:-m]))
