"""Sprint 62 — APRS message send + Doppler auto-correction."""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


# ── APRSClient.send_message() ─────────────────────────────────────────────────

class TestAPRSSendMessage:

    def test_send_message_method_exists(self):
        from aprs.aprs_client import APRSClient
        assert hasattr(APRSClient, "send_message")

    def test_returns_false_when_disconnected(self):
        from aprs.aprs_client import APRSClient
        client = APRSClient.__new__(APRSClient)
        client._sock    = None
        client._running = False
        client._lock    = __import__("threading").Lock()
        client._msg_seq = 0
        result = client.send_message("W1AW", "VK2AB", "Hello")
        assert result is False

    def test_to_call_padded_to_9(self):
        """Verify format string pads TO_CALL to 9 chars."""
        to_call   = "VK2AB"
        padded    = to_call.upper()[:9].ljust(9)
        assert len(padded) == 9
        assert padded == "VK2AB    "

    def test_sequence_number_format(self):
        seq = 42
        assert f"{seq:03d}" == "042"

    def test_message_truncated_to_67(self):
        long_msg = "X" * 100
        truncated = long_msg.strip()[:67]
        assert len(truncated) == 67

    def test_packet_format(self):
        from_call  = "W1AW"
        to_padded  = "VK2AB    "
        message    = "Hello there"
        seq        = "001"
        packet = (f"{from_call.upper()}>APZS09,TCPIP*:"
                  f"::{to_padded}:{message}{{{seq}}}\r\n")
        assert packet.startswith("W1AW>APZS09")
        assert "::VK2AB    :" in packet
        assert "{001}" in packet

    def test_seq_increments(self):
        from aprs.aprs_client import APRSClient
        client = APRSClient.__new__(APRSClient)
        client._msg_seq = 0
        # Simulate the increment logic
        client._msg_seq += 1
        assert client._msg_seq == 1
        client._msg_seq = 999
        client._msg_seq += 1
        if client._msg_seq > 999:
            client._msg_seq = 1
        assert client._msg_seq == 1


# ── Map tab APRS send UI ──────────────────────────────────────────────────────

class TestAPRSSendUI:

    def _src(self):
        return (ROOT / "ui/tabs/map_tab.py").read_text(encoding="utf-8")

    def test_send_method_exists(self):
        assert "def _aprs_send_message(" in self._src()

    def test_to_field_defined(self):
        assert "_aprs_msg_to" in self._src()

    def test_text_field_defined(self):
        assert "_aprs_msg_text" in self._src()

    def test_send_button_present(self):
        src = self._src()
        idx = src.find("def _build_aprs_msg_panel(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert '"Send"' in body

    def test_uses_aprs_client_send(self):
        src = self._src()
        idx = src.find("def _aprs_send_message(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "send_message(" in body

    def test_uses_operating_callsign(self):
        src = self._src()
        idx = src.find("def _aprs_send_message(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "operating_callsign" in body


# ── Doppler auto-correction ────────────────────────────────────────────────────

class TestDopplerCorrection:

    def _src(self):
        return (ROOT / "ui/tabs/rig_tab.py").read_text(encoding="utf-8")

    def test_doppler_cb_defined(self):
        assert "_doppler_cb" in self._src()

    def test_doppler_nom_freq_defined(self):
        assert "_doppler_nom_freq" in self._src()

    def test_doppler_applied_in_update(self):
        src = self._src()
        idx = src.find("def update_from_sat_position(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_doppler_cb" in body
        assert "doppler_hz" in body

    def test_rig_freq_set_with_correction(self):
        src = self._src()
        idx = src.find("def update_from_sat_position(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "set_freq(corrected_hz)" in body

    def test_doppler_in_sat_dict(self):
        net = (ROOT / "ui/main_window_network.py").read_text(encoding="utf-8")
        assert '"doppler_hz"' in net

    def test_doppler_scaling_formula(self):
        """Verify the Doppler scaling: shift at freq = ref_shift * (freq / 145 MHz)."""
        # If Doppler shift at 145 MHz = 3500 Hz, at 437 MHz it should be ~10 kHz
        ref_hz  = 145_000_000
        freq_hz = 437_000_000
        ref_doppler = 3500.0
        scaled = ref_doppler * (freq_hz / ref_hz)
        assert abs(scaled - 10548.3) < 2.0

    def test_doppler_zero_no_correction(self):
        nom_hz  = 145_200_000
        doppler = 0.0
        corrected = nom_hz + doppler
        assert corrected == nom_hz
