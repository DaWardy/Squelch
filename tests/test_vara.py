from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for VARA modem interface."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock
from winlink.vara import VARAModem, VARAState


class TestVARAModemInit:
    def test_creates_hf_modem(self):
        m = VARAModem(is_fm=False)
        assert m.name == "VARA HF"
        assert not m.is_connected

    def test_creates_fm_modem(self):
        m = VARAModem(is_fm=True)
        assert m.name == "VARA FM"

    def test_starts_disconnected(self):
        m = VARAModem()
        assert m.state == VARAState.DISCONNECTED

    def test_port_numbers_hf(self):
        m = VARAModem(is_fm=False)
        assert m._cmd_port == 8300
        assert m._dat_port == 8301

    def test_port_numbers_fm(self):
        m = VARAModem(is_fm=True)
        assert m._cmd_port == 8400
        assert m._dat_port == 8401


class TestVARAModemConnect:
    def test_connect_fails_gracefully_when_vara_not_running(self):
        """Should return False and set ERROR state, not raise."""
        m = VARAModem(is_fm=False)
        result = m.connect()
        assert result is False
        assert m.state == VARAState.ERROR

    def test_is_running_false_without_vara(self):
        """Port check should return False when nothing listening."""
        assert VARAModem.is_running(is_fm=False) is False


class TestVARAModemState:
    def test_state_callback_called(self):
        m    = VARAModem()
        seen = []
        m.on_state(lambda s: seen.append(s))
        m._set_state(VARAState.IDLE)
        assert VARAState.IDLE in seen

    def test_handle_iamalive(self):
        m = VARAModem()
        sent = []
        with patch.object(m, '_send',
                          side_effect=sent.append):
            m._handle_response("IAMALIVE")
        assert "IAMALIVE" in sent

    def test_handle_connected(self):
        m    = VARAModem()
        conn = []
        m.on_connect(lambda r: conn.append(r))
        m._handle_response("CONNECTED W4XYZ")
        assert m.state == VARAState.CONNECTED
        assert len(conn) == 1

    def test_handle_disconnected(self):
        m = VARAModem()
        m._state = VARAState.CONNECTED
        m._handle_response("DISCONNECTED")
        assert m.state == VARAState.IDLE

    def test_version_parsed(self):
        m = VARAModem()
        m._handle_response("VERSION VARA HF v4.7.3")
        assert "4.7.3" in m.version or \
               "VARA" in m.version


class TestVARAStateCallbackType:
    """VARAState enum must not crash when passed to on_state consumers.

    Regression for: AttributeError: 'VARAState' object has no attribute 'lower'
    Root cause: winlink_tab._on_vara_state called state.lower() but
    VARAModem passes a VARAState enum (not a plain string) to the callback.
    """

    def test_vara_state_has_string_value(self):
        for member in VARAState:
            assert isinstance(member.value, str), \
                f"{member} .value must be str, got {type(member.value)}"

    def test_callback_receives_enum_not_string(self):
        m    = VARAModem()
        seen = []
        m.on_state(lambda s: seen.append(s))
        m._set_state(VARAState.CONNECTED)
        assert seen and isinstance(seen[0], VARAState)

    def test_consumer_handles_enum_without_crash(self):
        """Simulate the fixed _on_vara_state pattern."""
        state = VARAState.CONNECTED
        state_str = state.value if hasattr(state, "value") else str(state)
        connected = state_str.lower() in ("connected", "linked")
        assert connected is True

    def test_consumer_handles_all_states(self):
        """All VARAState members must be processable as strings."""
        for member in VARAState:
            state_str = member.value if hasattr(member, "value") else str(member)
            _ = state_str.lower()  # must not raise


class TestVARAOnStateSeamContract:
    """End-to-end seam test: VARAModem emits → on_state callback receives → consumer works.

    Reproduces the class of bug where a module emits an enum to a callback but
    the consumer downstream calls string methods on it. Adding new callbacks
    that use .lower()/.upper()/string formatting on the argument MUST be tested
    in a class like this to catch type mismatches before runtime.
    """

    def test_full_chain_connected_state(self):
        """Simulate the exact path: _set_state(CONNECTED) → on_state callback → str ops."""
        m = VARAModem()
        results = []

        def on_state_consumer(state):
            # Replicate what any well-written consumer should do
            state_str = state.value if hasattr(state, "value") else str(state)
            results.append({
                "connected": state_str.lower() in ("connected", "linked"),
                "label":     state_str,
            })

        m.on_state(on_state_consumer)
        for s in [VARAState.IDLE, VARAState.CONNECTED, VARAState.BUSY,
                  VARAState.DISCONNECTED]:
            m._set_state(s)

        assert len(results) == 4
        assert results[1]["connected"] is True    # CONNECTED
        assert results[2]["connected"] is False   # BUSY → TX disabled (transfer active)
        assert results[0]["connected"] is False   # IDLE

    def test_state_label_is_human_readable(self):
        """VARAState.value strings must be title-cased words, not enum names."""
        for member in VARAState:
            assert member.value[0].isupper(), \
                f"{member.name}.value='{member.value}' must start uppercase"
            assert "_" not in member.value, \
                f"{member.name}.value='{member.value}' must not contain underscores"
