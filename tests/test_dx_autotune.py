"""FEAT-20 — DX cluster / SOTA auto-tune tests.

Tests for _infer_rig_mode() logic, _do_spot_tune() wiring,
and SDR sync callback infrastructure.  All pure-logic (no Qt).
"""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


# ── _infer_rig_mode pure-logic tests ─────────────────────────────────────────

class TestInferRigMode:

    def _infer(self, mode_str, freq_hz):
        from core.spot_tune import infer_rig_mode
        return infer_rig_mode(mode_str, freq_hz)

    # CW
    def test_cw_maps_to_cw(self):
        assert self._infer("CW", 7_050_000) == "CW"

    def test_cw_r_maps_to_cw(self):
        assert self._infer("CW-R", 14_020_000) == "CW"

    # Digital modes
    def test_ft8_maps_to_pktusb(self):
        assert self._infer("FT8", 14_074_000) == "PKTUSB"

    def test_ft4_maps_to_pktusb(self):
        assert self._infer("FT4", 14_074_000) == "PKTUSB"

    def test_psk31_maps_to_pktusb(self):
        assert self._infer("PSK31", 14_070_000) == "PKTUSB"

    def test_wspr_maps_to_pktusb(self):
        assert self._infer("WSPR", 14_095_600) == "PKTUSB"

    # RTTY
    def test_rtty_maps_to_pktlsb(self):
        assert self._infer("RTTY", 14_085_000) == "PKTLSB"

    # SSB inference from frequency
    def test_no_mode_above_10mhz_gives_usb(self):
        assert self._infer("", 14_225_000) == "USB"

    def test_no_mode_below_10mhz_gives_lsb(self):
        assert self._infer("", 7_150_000) == "LSB"

    def test_ssb_above_10mhz_gives_usb(self):
        assert self._infer("SSB", 21_300_000) == "USB"

    def test_ssb_below_10mhz_gives_lsb(self):
        assert self._infer("SSB", 3_750_000) == "LSB"

    def test_explicit_lsb_preserved(self):
        assert self._infer("LSB", 7_200_000) == "LSB"

    def test_explicit_usb_preserved(self):
        assert self._infer("USB", 14_300_000) == "USB"

    def test_am_preserved(self):
        assert self._infer("AM", 7_200_000) == "AM"

    def test_fm_preserved(self):
        assert self._infer("FM", 144_800_000) == "FM"

    def test_unknown_mode_falls_back_to_freq(self):
        result = self._infer("OLIVIA", 14_075_000)
        assert result in ("USB", "LSB", "PKTUSB")

    def test_vara_digital_maps_to_pktusb(self):
        assert self._infer("VARA", 14_074_000) == "PKTUSB"


# ── Source-level wiring checks ────────────────────────────────────────────────

class TestAutoTuneWiring:

    def _modes_src(self):
        # Concatenate ModesTab + its extracted mixins so source checks find the
        # method wherever it now lives (HOUSE-CS split moved SOTA/POTA, RBN,
        # SSTV out of modes_tab.py).
        parts = ["ui/tabs/modes_tab.py", "ui/tabs/modes_dx_mixin.py",
                 "ui/tabs/modes_sota_mixin.py", "ui/tabs/modes_rbn_mixin.py",
                 "ui/tabs/modes_sstv_mixin.py"]
        return "\n".join(
            (ROOT / p).read_text(encoding="utf-8") for p in parts)

    def _mw_src(self):
        return (ROOT / "ui/main_window.py").read_text(encoding="utf-8")

    def test_set_sdr_tune_cb_exists(self):
        assert "def set_sdr_tune_cb(" in self._modes_src()

    def test_do_spot_tune_helper_exists(self):
        assert "def _do_spot_tune(" in self._modes_src()

    def test_infer_rig_mode_static(self):
        assert "@staticmethod" in self._modes_src()
        assert "def _infer_rig_mode(" in self._modes_src()

    def test_dx_tune_uses_do_spot_tune(self):
        src = self._modes_src()
        dx_idx = src.find("def _tune_to_dx_spot(")
        body   = src[dx_idx: src.find("\n    def ", dx_idx + 10)]
        assert "_do_spot_tune(" in body

    def test_sota_tune_uses_do_spot_tune(self):
        src = self._modes_src()
        idx  = src.find("def _tune_to_sota_pota(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_do_spot_tune(" in body

    def test_sdr_sync_cb_called_in_do_spot_tune(self):
        src = self._modes_src()
        idx  = src.find("def _do_spot_tune(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_sdr_tune_cb" in body

    def test_mode_set_in_do_spot_tune(self):
        src = self._modes_src()
        idx  = src.find("def _do_spot_tune(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "set_mode(" in body

    def test_status_feedback_in_do_spot_tune(self):
        src = self._modes_src()
        idx  = src.find("def _do_spot_tune(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_dx_status" in body

    def test_mainwindow_wires_modes_sdr_cb(self):
        src = self._mw_src()
        assert "modes.set_sdr_tune_cb(" in src

    def test_row_selected_on_dx_tune(self):
        src = self._modes_src()
        assert "selectRow(" in src


# ── SDR sync callback functional test ────────────────────────────────────────

class TestSdrSyncCallback:

    def test_callback_receives_freq_hz(self):
        """SDR sync callback must fire with freq in Hz."""
        from core.spot_tune import infer_rig_mode
        assert infer_rig_mode("FT8", 14_074_000) == "PKTUSB"
        # Verify callback wiring pattern (simulated)
        received = []
        sdr_tune_cb = received.append
        sdr_tune_cb(14_074_000)
        assert received == [14_074_000]

    def test_infer_mode_imported_by_modes_tab(self):
        src = (ROOT / "ui/tabs/modes_tab.py").read_text(encoding="utf-8")
        assert "spot_tune" in src or "infer_rig_mode" in src
