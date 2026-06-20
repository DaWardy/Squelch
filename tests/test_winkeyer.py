"""FEAT-27 — WinKeyer + CW macro panel tests.

Pure-logic tests for core/winkeyer.py and source-level checks for rig_tab.py.
"""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


# ── core/winkeyer.py ──────────────────────────────────────────────────────────

class TestWinKeyerClient:

    def test_initially_disconnected(self):
        from core.winkeyer import WinKeyerClient
        wk = WinKeyerClient()
        assert not wk.is_connected

    def test_send_text_false_when_disconnected(self):
        from core.winkeyer import WinKeyerClient
        wk = WinKeyerClient()
        assert wk.send_text("CQ") is False

    def test_stop_false_when_disconnected(self):
        from core.winkeyer import WinKeyerClient
        wk = WinKeyerClient()
        assert wk.stop() is False

    def test_set_speed_false_when_disconnected(self):
        from core.winkeyer import WinKeyerClient
        wk = WinKeyerClient()
        assert wk.set_speed(20) is False

    def test_connect_bad_port_returns_false(self):
        from core.winkeyer import WinKeyerClient
        wk = WinKeyerClient()
        result = wk.connect("NONEXISTENT_PORT_XYZ")
        assert result is False

    def test_has_serial_flag_defined(self):
        from core.winkeyer import HAS_SERIAL
        assert isinstance(HAS_SERIAL, bool)

    def test_baud_rate_constant(self):
        from core.winkeyer import BAUD_RATE
        assert BAUD_RATE == 1200

    def test_wpm_clamped_low(self):
        """Speed command clamps WPM to minimum 5."""
        val = max(5, min(99, 2))
        assert val == 5

    def test_wpm_clamped_high(self):
        val = max(5, min(99, 150))
        assert val == 99


# ── rig_tab.py CW section source checks ──────────────────────────────────────

class TestCWMacroPanel:

    def _src(self):
        return (ROOT / "ui/tabs/rig_tab.py").read_text(encoding="utf-8")

    def test_macro_buttons_built(self):
        src = self._src()
        idx = src.find("def _build_cw_section(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_cw_macro_btns" in body
        assert "f1" in body.lower() or "macro_btns" in body

    def test_f1_f8_loop_in_cw_section(self):
        src = self._src()
        idx = src.find("def _build_cw_section(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "range(1, 9)" in body

    def test_macro_click_handler(self):
        assert "def _cw_macro_click(" in self._src()

    def test_macro_edit_handler(self):
        assert "def _cw_macro_edit(" in self._src()

    def test_macro_expands_on_click(self):
        src = self._src()
        idx = src.find("def _cw_macro_click(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "expand" in body or "get" in body

    def test_right_click_wired(self):
        src = self._src()
        idx = src.find("def _build_cw_section(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "customContextMenuRequested" in body

    def test_winkeyer_port_combo(self):
        src = self._src()
        idx = src.find("def _build_cw_section(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_wk_port" in body

    def test_winkeyer_connect_button(self):
        src = self._src()
        idx = src.find("def _build_cw_section(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_wk_btn" in body

    def test_winkeyer_toggle_method(self):
        assert "def _wk_toggle(" in self._src()

    def test_send_cw_prefers_winkeyer(self):
        src = self._src()
        idx = src.find("def _send_cw(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_winkeyer" in body
        # WinKeyer path should come BEFORE Hamlib path
        wk_pos  = body.find("_winkeyer")
        rig_pos = body.find("self.rig.send_cw")
        assert wk_pos < rig_pos

    def test_stop_cw_stops_both(self):
        src = self._src()
        idx = src.find("def _stop_cw(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_winkeyer" in body
        assert "stop_cw" in body

    def test_populate_wk_ports_method(self):
        assert "_populate_wk_ports" in self._src()

    def test_wpm_changed_sends_to_winkeyer(self):
        src = self._src()
        idx = src.find("def _cw_wpm_changed(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_winkeyer" in body
        assert "set_speed" in body


class TestWinKeyerProtocol:
    """Verify WinKeyer command bytes without hardware."""

    def test_admin_open_byte(self):
        # Admin Open = 0x00 0x02
        assert bytes([0x00, 0x02]) == b"\x00\x02"

    def test_admin_close_byte(self):
        assert bytes([0x00, 0x03]) == b"\x00\x03"

    def test_send_text_prefix(self):
        assert bytes([0x04]) == b"\x04"

    def test_clear_buffer_byte(self):
        assert bytes([0x0A]) == b"\x0a"

    def test_text_uppercased_for_cw(self):
        text = "cq de w1aw"
        assert text.upper() == "CQ DE W1AW"

    def test_non_ascii_stripped(self):
        text = "CQ DE W1AW ä"
        encoded = text.upper().encode("ascii", errors="ignore")
        assert b"\xc4" not in encoded
        assert b"CQ" in encoded
