"""Sprint 72 — FT8 auto-tune on band change + scanner squelch gate."""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


# ── FT8 auto-tune checkbox ────────────────────────────────────────────────────

class TestAutoTuneBandChange:

    def _src(self):
        return (ROOT / "ui/tabs/modes_tab.py").read_text(encoding="utf-8")

    def test_auto_tune_checkbox_defined(self):
        assert "_auto_tune_cb" in self._src()

    def test_auto_tune_in_band_freq_panel(self):
        src = self._src()
        idx = src.find("def _build_band_freq_panel(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_auto_tune_cb" in body

    def test_auto_tune_wired_in_on_band_change(self):
        src = self._src()
        idx = src.find("def _on_band_change(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_auto_tune_cb" in body

    def test_rig_set_freq_called_on_autotune(self):
        src = self._src()
        idx = src.find("def _on_band_change(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "set_freq(" in body

    def test_pktusb_mode_set_on_autotune(self):
        src = self._src()
        idx = src.find("def _on_band_change(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "PKTUSB" in body

    def test_auto_tune_persisted_in_save_state(self):
        src = self._src()
        idx = src.find("def save_state(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "auto_tune" in body

    def test_auto_tune_restored(self):
        src = self._src()
        idx = src.find("def restore_state(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "auto_tune" in body


class TestFT8FrequencyMapping:
    """Verify FT8 standard frequencies exist for key bands."""

    def test_20m_ft8_frequency(self):
        from core.constants import FT8_FREQUENCIES
        assert FT8_FREQUENCIES.get("20m") == 14_074_000

    def test_40m_ft8_frequency(self):
        from core.constants import FT8_FREQUENCIES
        assert FT8_FREQUENCIES.get("40m") == 7_074_000

    def test_80m_ft8_frequency(self):
        from core.constants import FT8_FREQUENCIES
        assert FT8_FREQUENCIES.get("80m") == 3_573_000

    def test_10m_ft8_frequency(self):
        from core.constants import FT8_FREQUENCIES
        assert FT8_FREQUENCIES.get("10m") == 28_074_000

    def test_all_bands_have_frequencies(self):
        from core.constants import FT8_FREQUENCIES
        assert len(FT8_FREQUENCIES) >= 6


# ── Scanner squelch gate ─────────────────────────────────────────────────────

class TestScannerSquelch:

    def _src(self):
        # Scanner code lives in rig_scanner_mixin.py (HOUSE-CS split).
        return (ROOT / "ui/tabs/rig_scanner_mixin.py").read_text(encoding="utf-8")

    def test_scan_squelch_open_method(self):
        assert "def _scan_squelch_open(" in self._src()

    def test_squelch_gate_in_scan_step(self):
        src = self._src()
        idx = src.find("def _scan_step(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_scan_squelch_open" in body

    def test_signal_indicator_in_status(self):
        src = self._src()
        idx = src.find("def _scan_step(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "SIGNAL" in body

    def test_scan_sql_spinbox_exists(self):
        src = self._src()
        assert "_scan_sql" in src

    def test_dbm_conversion_used(self):
        src = self._src()
        idx = src.find("def _scan_squelch_open(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_DBM" in body or "dbm" in body.lower()

    def test_smeter_level_read(self):
        src = self._src()
        idx = src.find("def _scan_squelch_open(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "s_meter" in body


class TestScannerSquelchLogic:
    """Pure-logic: S-level to dBm comparison."""

    def _is_open(self, s_level, sql_dbm):
        """Mirror _scan_squelch_open logic."""
        _DBM = [-127, -121, -115, -109, -103, -97, -91, -85,
                -79,  -73,   -63,  -53,   -33,  -13]
        level_dbm = _DBM[max(0, min(13, s_level))]
        return level_dbm >= sql_dbm

    def test_s9_above_minus_80_dbm(self):
        assert self._is_open(9, -80)   # S9 = -73 dBm > -80 dBm

    def test_s0_below_minus_80_dbm(self):
        assert not self._is_open(0, -80)   # S0 = -127 dBm < -80 dBm

    def test_s7_at_threshold(self):
        # S7 = -85 dBm; threshold -85: equal → open
        assert self._is_open(7, -85)

    def test_s6_below_minus_85_threshold(self):
        # S6 = -91 dBm < -85 → closed
        assert not self._is_open(6, -85)

    def test_weak_threshold_catches_most(self):
        # Threshold -120 dBm: S1+ (-121 dBm+) should trigger
        # S0 = -127 dBm < -120 dBm → closed; S1 = -121 dBm < -120 dBm → closed
        # S2 = -115 dBm > -120 dBm → open
        for s in range(2, 14):
            assert self._is_open(s, -120), f"S{s} should be above -120 dBm"
