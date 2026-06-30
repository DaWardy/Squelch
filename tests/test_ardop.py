from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for the ARDOP soundcard-TNC interface.

Protocol-level only — every networked path is exercised with a mocked socket,
so no ARDOP TNC (ardopcf/ardopc) hardware or process is required.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock
from winlink.ardop import ARDOPModem, ARDOPState


class TestARDOPModemInit:
    def test_name(self):
        m = ARDOPModem()
        assert m.name == "ARDOP"

    def test_default_ports(self):
        m = ARDOPModem()
        assert m._cmd_port == 8515
        assert m._dat_port == 8516

    def test_custom_host_port(self):
        m = ARDOPModem(host="192.168.1.5", port=9000)
        assert m._host == "192.168.1.5"
        assert m._cmd_port == 9000
        assert m._dat_port == 9001

    def test_starts_disconnected(self):
        m = ARDOPModem()
        assert m.state == ARDOPState.DISCONNECTED
        assert not m.is_connected


class TestARDOPModemConnect:
    def test_connect_fails_gracefully_when_tnc_not_running(self):
        """Should return False and set ERROR state, not raise."""
        m = ARDOPModem(port=8599)  # nothing listening here
        result = m.connect()
        assert result is False
        assert m.state == ARDOPState.ERROR

    def test_is_running_false_without_tnc(self):
        assert ARDOPModem.is_running(port=8599) is False

    def test_connect_records_netlog(self):
        """Outbound connect must hit core.netlog (project rule)."""
        m = ARDOPModem(port=8599)
        with patch("core.netlog.record_connection") as rec:
            m.connect()
        assert rec.called
        host_arg = rec.call_args.args[0]
        assert "8599" in str(host_arg)


class TestARDOPModemState:
    def test_state_callback_called(self):
        m    = ARDOPModem()
        seen = []
        m.on_state(lambda s: seen.append(s))
        m._set_state(ARDOPState.IDLE)
        assert ARDOPState.IDLE in seen

    def test_callback_receives_enum_not_string(self):
        m    = ARDOPModem()
        seen = []
        m.on_state(lambda s: seen.append(s))
        m._set_state(ARDOPState.CONNECTED)
        assert seen and isinstance(seen[0], ARDOPState)

    def test_version_parsed(self):
        m = ARDOPModem()
        m._handle_response("VERSION 1.0.4.1")
        assert m.version == "1.0.4.1"

    def test_handle_connected(self):
        m    = ARDOPModem()
        conn = []
        m.on_connect(lambda r: conn.append(r))
        m._handle_response("CONNECTED W4XYZ 500")
        assert m.state == ARDOPState.CONNECTED
        assert conn == ["W4XYZ 500"]

    def test_handle_disconnected(self):
        m = ARDOPModem()
        m._state = ARDOPState.CONNECTED
        m._handle_response("DISCONNECTED")
        assert m.state == ARDOPState.IDLE

    def test_newstate_iss_is_connected(self):
        m = ARDOPModem()
        m._handle_response("NEWSTATE ISS")
        assert m.state == ARDOPState.CONNECTED

    def test_newstate_irs_is_connected(self):
        m = ARDOPModem()
        m._handle_response("NEWSTATE IRS")
        assert m.state == ARDOPState.CONNECTED

    def test_newstate_disc_from_idle_stays_idle(self):
        m = ARDOPModem()
        m._state = ARDOPState.IDLE
        m._handle_response("NEWSTATE DISC")
        assert m.state == ARDOPState.IDLE

    def test_busy_true_from_idle(self):
        m = ARDOPModem()
        m._state = ARDOPState.IDLE
        m._handle_response("BUSY TRUE")
        assert m.state == ARDOPState.BUSY

    def test_busy_false_clears_to_idle(self):
        m = ARDOPModem()
        m._state = ARDOPState.BUSY
        m._handle_response("BUSY FALSE")
        assert m.state == ARDOPState.IDLE

    def test_busy_does_not_clobber_active_session(self):
        m = ARDOPModem()
        m._state = ARDOPState.CONNECTED
        m._handle_response("BUSY TRUE")
        assert m.state == ARDOPState.CONNECTED

    def test_fault_sets_error(self):
        m = ARDOPModem()
        m._handle_response("FAULT 5 Tuning timeout")
        assert m.state == ARDOPState.ERROR

    def test_empty_line_ignored(self):
        m = ARDOPModem()
        m._handle_response("")
        assert m.state == ARDOPState.DISCONNECTED


class TestARDOPCommandBytes:
    """Verify command framing on the wire with a mocked control socket."""

    def _modem_with_sock(self):
        m = ARDOPModem()
        m._cmd_sock = MagicMock()
        return m

    def test_set_callsign(self):
        m = self._modem_with_sock()
        m.set_callsign("w4xyz")
        m._cmd_sock.sendall.assert_called_once_with(b"MYCALL W4XYZ\r")

    def test_set_bandwidth(self):
        m = self._modem_with_sock()
        m.set_bandwidth(500)
        m._cmd_sock.sendall.assert_called_once_with(b"ARQBW 500MAX\r")

    def test_listen_on(self):
        m = self._modem_with_sock()
        m.listen(True)
        m._cmd_sock.sendall.assert_called_once_with(b"LISTEN TRUE\r")

    def test_listen_off(self):
        m = self._modem_with_sock()
        m.listen(False)
        m._cmd_sock.sendall.assert_called_once_with(b"LISTEN FALSE\r")

    def test_connect_to_sends_arqcall_and_sets_connecting(self):
        m = self._modem_with_sock()
        m.connect_to("w1aw", repeats=3)
        m._cmd_sock.sendall.assert_called_once_with(b"ARQCALL W1AW 3\r")
        assert m.state == ARDOPState.CONNECTING

    def test_abort(self):
        m = self._modem_with_sock()
        m.abort()
        m._cmd_sock.sendall.assert_called_once_with(b"ABORT\r")

    def test_disconnect_sends_disconnect_and_resets(self):
        m = self._modem_with_sock()
        with patch("time.sleep"):
            m.disconnect()
        assert m._cmd_sock is None
        assert m.state == ARDOPState.DISCONNECTED


class TestARDOPStateContract:
    """ARDOPState must mirror VARAState's human-readable contract."""

    def test_all_values_are_strings(self):
        for member in ARDOPState:
            assert isinstance(member.value, str)

    def test_values_title_cased_no_underscores(self):
        for member in ARDOPState:
            assert member.value[0].isupper()
            assert "_" not in member.value

    def test_consumer_handles_all_states_as_strings(self):
        for member in ARDOPState:
            state_str = member.value if hasattr(member, "value") else str(member)
            _ = state_str.lower()  # must not raise

    def test_mirrors_vara_state_members(self):
        from winlink.vara import VARAState
        assert {s.name for s in ARDOPState} == {s.name for s in VARAState}
        assert {s.value for s in ARDOPState} == {s.value for s in VARAState}


class TestWinlinkTabArdopWiring:
    """Source-level smoke check — no PyQt6 needed.

    Confirms the Winlink tab actually wires the ARDOP modem and builds the
    ARDOP Status section, without importing PyQt6 (so it runs in any env).
    """

    def _src(self) -> str:
        path = (Path(__file__).parent.parent
                / "ui" / "tabs" / "winlink_tab.py")
        return path.read_text(encoding="utf-8")

    def test_imports_ardop(self):
        assert "from winlink.ardop import ARDOPModem" in self._src()

    def test_instantiates_ardop_modem(self):
        assert "ARDOPModem(" in self._src()

    def test_builds_ardop_status_tab(self):
        src = self._src()
        assert "_build_ardop_tab" in src
        assert "ARDOP Status" in src

    def test_has_connect_and_state_handlers(self):
        src = self._src()
        assert "_connect_ardop" in src
        assert "_on_ardop_state" in src

    def test_uses_pyqtsignal_not_qtimer_from_worker(self):
        """ARDOP state must marshal via pyqtSignal, not QTimer.singleShot."""
        src = self._src()
        assert "_ardop_state_sig = pyqtSignal" in src
        assert "self._ardop.on_state(self._ardop_state_sig.emit)" in src
