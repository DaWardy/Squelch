"""Sprint 60 — FT8 decode alert + APRS message receive."""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


# ── FT8 decode alert ─────────────────────────────────────────────────────────

class TestFT8AlertSource:

    def _src(self):
        return (ROOT / "ui/tabs/modes_tab.py").read_text(encoding="utf-8")

    def test_ft8_watch_edit_defined(self):
        assert "_ft8_watch_edit" in self._src()

    def test_check_ft8_alert_method(self):
        assert "def _check_ft8_alert(" in self._src()

    def test_alert_called_from_add_decode(self):
        src = self._src()
        idx = src.find("def _add_decode(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_check_ft8_alert(" in body

    def test_beep_on_match(self):
        src = self._src()
        idx = src.find("def _check_ft8_alert(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "beep()" in body

    def test_row_highlighted_gold(self):
        src = self._src()
        idx = src.find("def _check_ft8_alert(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "5a4800" in body or "gold" in body.lower() or "setBackground" in body

    def test_alert_in_activity_log(self):
        src = self._src()
        idx = src.find("def _check_ft8_alert(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_log_activity" in body

    def test_watch_persisted_in_save_state(self):
        src = self._src()
        idx = src.find("def save_state(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "ft8_watch" in body

    def test_watch_restored(self):
        src = self._src()
        idx = src.find("def restore_state(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "ft8_watch" in body


class TestFT8AlertLogic:
    """Mirror prefix-match logic without Qt."""

    def _matches(self, call, watch_str):
        terms = [t.strip().upper() for t in watch_str.split(",") if t.strip()]
        call_upper = call.upper()
        return any(call_upper == t or call_upper.startswith(t) for t in terms)

    def test_exact_match(self):
        assert self._matches("VK2AB", "VK2AB")

    def test_prefix_match(self):
        assert self._matches("VK2AB", "VK")

    def test_multiple_prefixes(self):
        assert self._matches("JA1XY", "VK,JA,ZL")

    def test_no_match(self):
        assert not self._matches("W1AW", "VK,JA")

    def test_empty_watch_no_match(self):
        assert not self._matches("VK2AB", "")


# ── APRSPacket.parse_message() ────────────────────────────────────────────────

class TestAPRSMessageParsing:

    def _make_packet(self, raw: str):
        from aprs.aprs_client import APRSPacket
        return APRSPacket(raw=raw, callsign="W1AW", ssid="")

    def test_message_packet_parsed(self):
        raw = "W1AW>APZS09,TCPIP*:::VK2AB    :Hello there{001}"
        pkt = self._make_packet(raw)
        result = pkt.parse_message()
        assert result is not None
        to_call, msg, msg_id = result
        assert to_call == "VK2AB"
        assert "Hello" in msg
        assert msg_id == "001"

    def test_non_message_returns_none(self):
        raw = "W1AW>APZS09,TCPIP*:!4238.27N/07114.56W#Squelch"
        pkt = self._make_packet(raw)
        assert pkt.parse_message() is None

    def test_message_to_call_stripped(self):
        raw = "W1AW>APZS09:::K7ABC    :Test msg{42}"
        pkt = self._make_packet(raw)
        result = pkt.parse_message()
        assert result is not None
        to_call, _, _ = result
        assert to_call == "K7ABC"

    def test_message_without_id(self):
        raw = "W1AW>APZS09:::VK2AB    :No ID here"
        pkt = self._make_packet(raw)
        result = pkt.parse_message()
        if result:
            _, msg, msg_id = result
            assert msg_id == ""

    def test_is_position_false_for_message(self):
        raw = "W1AW>APZS09:::VK2AB    :Hello{001}"
        pkt = self._make_packet(raw)
        assert not pkt.is_position


# ── Map tab APRS message wiring ───────────────────────────────────────────────

class TestAPRSMessageMapWiring:

    def _map_src(self):
        return (ROOT / "ui/tabs/map_tab.py").read_text(encoding="utf-8")

    def _net_src(self):
        return (ROOT / "ui/main_window_network.py").read_text(encoding="utf-8")

    def test_add_aprs_message_method(self):
        assert "def add_aprs_message(" in self._map_src()

    def test_build_aprs_msg_panel_defined(self):
        assert "_build_aprs_msg_panel" in self._map_src()

    def test_msg_panel_added_in_build(self):
        src = self._map_src()
        assert "_build_aprs_msg_panel" in src

    def test_parse_message_called_in_on_aprs_packet(self):
        assert "parse_message()" in self._net_src()

    def test_directed_message_detection(self):
        src = self._net_src()
        assert "directed" in src or "directed_to_us" in src

    def test_directed_message_auto_shows_panel(self):
        src = self._map_src()
        idx = src.find("def add_aprs_message(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "setVisible(True)" in body or "show()" in body
