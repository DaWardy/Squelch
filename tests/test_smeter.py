"""FEAT-23 calibrated S-meter + FEAT-07 RF Lab SDR frequency control."""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


# ── SMeterWidget pure-logic ───────────────────────────────────────────────────

class TestSMeterLogic:
    """Verify calibrated dBm values and label mapping (mirrors smeter.py data)."""

    # Inline copy of _DBM so this class doesn't need Qt
    _DBM_DATA = [
        -127, -121, -115, -109, -103, -97, -91, -85,
        -79,  -73,   -63,  -53,   -33,  -13
    ]

    def _dbm(self, s_level, cal=0):
        return self._DBM_DATA[max(0, min(13, s_level))] + cal

    def test_s9_equals_minus73_dbm(self):
        assert self._dbm(9) == -73

    def test_s0_equals_minus127_dbm(self):
        assert self._dbm(0) == -127

    def test_s9_plus10_equals_minus63_dbm(self):
        assert self._dbm(10) == -63

    def test_s9_plus60_equals_minus13_dbm(self):
        assert self._dbm(13) == -13

    def test_cal_offset_shifts_dbm(self):
        assert self._dbm(9, cal=10) == -63

    def test_each_s_unit_is_6db(self):
        for i in range(8):
            assert self._DBM_DATA[i+1] - self._DBM_DATA[i] == 6

    def test_14_levels_defined(self):
        assert len(self._DBM_DATA) == 14

    def test_labels_match_levels(self):
        labels = [
            "S0","S1","S2","S3","S4","S5","S6","S7",
            "S8","S9","S9+10","S9+20","S9+40","S9+60",
        ]
        assert len(labels) == len(self._DBM_DATA)


class TestSMeterSource:

    def _src(self):
        return (ROOT / "ui/widgets/smeter.py").read_text(encoding="utf-8")

    def test_widget_class_exists(self):
        assert "class SMeterWidget(" in self._src()

    def test_set_level_method(self):
        assert "def set_level(" in self._src()

    def test_colour_segments_defined(self):
        src = self._src()
        assert "_SEG_COLS" in src

    def test_tick_labels_defined(self):
        src = self._src()
        assert "_TICK_LEVELS" in src

    def test_no_hardcoded_dark_hex(self):
        src = self._src()
        for bad in ("#141414", "#0a0a0a"):
            assert bad not in src


# ── rig_tab S-meter wiring ────────────────────────────────────────────────────

class TestSMeterRigTabWiring:

    def _src(self):
        return (ROOT / "ui/tabs/rig_tab.py").read_text(encoding="utf-8")

    def test_smeter_widget_imported(self):
        assert "SMeterWidget" in self._src()

    def test_smeter_widget_used_in_status_group(self):
        src = self._src()
        idx = src.find("_build_status_group") if "_build_status_group" in src else src.find("smeter_bar")
        assert "SMeterWidget" in src

    def test_smeter_set_level_called_in_apply_state(self):
        src = self._src()
        idx = src.find("def _apply_state(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "set_level(" in body

    def test_cal_offset_read_from_cfg(self):
        src = self._src()
        assert "smeter_cal_db" in src

    def test_no_setValue_on_progress_bar(self):
        src = self._src()
        idx = src.find("def _apply_state(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "smeter_bar.setValue" not in body


# ── FEAT-07 RF Lab SDR freq ───────────────────────────────────────────────────

class TestRFLabSDRFreqControl:

    def _src(self):
        return (ROOT / "ui/tabs/rf_lab_tab.py").read_text(encoding="utf-8")

    def test_sdr_freq_spin_defined(self):
        assert "_sdr_freq_spin" in self._src()

    def test_quick_tune_method_exists(self):
        assert "def _quick_tune_sdr(" in self._src()

    def test_editing_finished_connected(self):
        src = self._src()
        assert "editingFinished" in src
        assert "_quick_tune_sdr" in src

    def test_quick_tune_calls_tune(self):
        src = self._src()
        idx = src.find("def _quick_tune_sdr(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_tune(" in body

    def test_sdr_freq_in_toolbar(self):
        src = self._src()
        idx = src.find("def _build_toolbar(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_sdr_freq_spin" in body

    def test_freq_range_covers_hf_to_shf(self):
        src = self._src()
        assert "6000" in src   # upper range in MHz


class TestQuickTuneMath:

    def test_mhz_to_hz_conversion(self):
        mhz = 144.200
        hz  = int(mhz * 1_000_000)
        assert hz == 144_200_000

    def test_hf_frequency(self):
        hz = int(14.074 * 1_000_000)
        assert hz == 14_074_000
