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
