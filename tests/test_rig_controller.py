from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Tests for RigController using mocked sockets and subprocess.
No hardware required — all I/O is mocked.
"""

import sys, threading, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from core.rig import RigController, RigStatus, _sanitize_cw_text
from core.config import Config


@pytest.fixture
def cfg(tmp_path):
    cfg = Config(tmp_path / "config.json")
    cfg.callsign = "NR6U"
    cfg.set("rig.hamlib_model", 370)
    cfg.set("rig.poll_interval_ms", 9999)  # disable polling
    return cfg


@pytest.fixture
def rig(cfg):
    return RigController(cfg)


class TestRigControllerInit:
    def test_creates_controller(self, rig):
        assert rig is not None

    def test_starts_disconnected(self, rig):
        assert not rig.is_connected

    def test_state_has_correct_defaults(self, rig):
        assert rig.state.status == RigStatus.DISCONNECTED
        assert rig.state.freq_hz == 14074000
        assert rig.state.ptt is False

    def test_list_ports_returns_list(self):
        ports = RigController.list_ports()
        assert isinstance(ports, list)


class TestRigControllerCommands:
    def test_set_freq_updates_state_when_connected(self, rig):
        """set_freq should update internal state."""
        with patch.object(rig, '_cmd', return_value=""):
            # Set state directly - is_connected checks state
            from core.rig import RigStatus
            rig.state.status = RigStatus.CONNECTED
            rig.set_freq(7074000)
            assert rig.state.freq_hz == 7074000

    def test_set_mode_updates_state(self, rig):
        with patch.object(rig, '_cmd', return_value=""):
            rig.state.status = RigStatus.CONNECTED
            rig.set_mode("CW")
            assert rig.state.mode == "CW"

    def test_set_ptt_true_updates_state(self, rig):
        with patch.object(rig, '_cmd', return_value=""):
            rig.state.status = RigStatus.CONNECTED
            rig.set_ptt(True)
            assert rig.state.ptt is True

    def test_set_ptt_false_clears_state(self, rig):
        with patch.object(rig, '_cmd', return_value=""):
            rig.state.status = RigStatus.CONNECTED
            rig.state.ptt = True
            rig.set_ptt(False)
            assert rig.state.ptt is False


class TestRigCallbacks:
    def test_callback_registered(self, rig):
        fired = []
        rig.on_state_change(lambda s: fired.append(s))
        rig._notify()
        assert len(fired) == 1

    def test_multiple_callbacks(self, rig):
        counts = [0, 0]
        rig.on_state_change(lambda s: counts.__setitem__(0, 1))
        rig.on_state_change(lambda s: counts.__setitem__(1, 1))
        rig._notify()
        assert counts == [1, 1]

    def test_bad_callback_doesnt_crash(self, rig):
        rig.on_state_change(lambda s: 1/0)  # raises
        rig._notify()  # should not propagate


class TestCWSanitizer:
    def test_uppercase_only(self):
        assert _sanitize_cw_text("hello") == "HELLO"

    def test_numbers_allowed(self):
        assert "73" in _sanitize_cw_text("73 DE NR6U")

    def test_strip_invalid_chars(self):
        result = _sanitize_cw_text("CQ CQ #$% DE NR6U")
        assert "#" not in result
        assert "$" not in result
        assert "NR6U" in result

    def test_max_length(self):
        long_text = "A" * 300
        result = _sanitize_cw_text(long_text)
        assert len(result) <= 200

    def test_empty_string(self):
        assert _sanitize_cw_text("") == ""

    def test_spaces_preserved(self):
        result = _sanitize_cw_text("CQ DE NR6U")
        assert " " in result


class TestFreqToBand:
    def test_20m(self):
        from core.rig import _freq_to_band
        assert _freq_to_band(14074000) == "20m"

    def test_40m(self):
        from core.rig import _freq_to_band
        assert _freq_to_band(7074000) == "40m"

    def test_out_of_band(self):
        from core.rig import _freq_to_band
        result = _freq_to_band(999000)
        assert result == "OOB"

    def test_80m(self):
        from core.rig import _freq_to_band
        assert _freq_to_band(3573000) == "80m"
