from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for FT8 engine state machine."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock
from modes.ft8 import FT8Engine, AutoSeqState


@pytest.fixture
def cfg(tmp_path):
    from core.config import Config
    c = Config(tmp_path / "config.json")
    c.callsign = "W1AW"
    c.grid     = "DM79rr"
    return c


@pytest.fixture
def engine(cfg):
    rig = MagicMock()
    rig.is_connected = False
    return FT8Engine(cfg, rig)


class TestFT8EngineInit:
    def test_creates_engine(self, engine):
        assert engine is not None

    def test_starts_idle(self, engine):
        assert engine.state == AutoSeqState.IDLE

    def test_not_wsjtx_connected(self, engine):
        assert not engine._wsjtx_connected


class TestFT8EngineCQGuard:
    def test_cq_blocked_without_wsjtx(self, engine):
        """CQ should not fire if WSJT-X not connected."""
        initial = engine.state
        engine.send_cq()
        assert engine.state == AutoSeqState.IDLE

    def test_cq_blocked_without_callsign(self, engine):
        engine.cfg.callsign = ""
        engine._wsjtx_connected = True
        engine.send_cq()
        assert engine.state == AutoSeqState.IDLE

    def test_cq_fires_when_connected(self, engine):
        engine._wsjtx_connected = True
        engine.cfg.callsign = "W1AW"
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(engine, "_queue_tx",
                       lambda msg: None)
            engine.send_cq()
        assert engine.state == AutoSeqState.CQ_SENT

    def test_halt_sets_halted_flag(self, engine):
        engine.halt_tx()
        assert engine._halted is True

    def test_reconnect_returns_to_idle(self, engine):
        engine._state = AutoSeqState.CQ_SENT
        engine.reconnect()
        assert engine.state == AutoSeqState.IDLE


class TestFT8CQTimeout:
    def test_timeout_check_decrements(self, engine):
        engine._state    = AutoSeqState.CQ_SENT
        engine._cq_timeout = 2
        engine._check_cq_timeout()
        assert engine._cq_timeout == 1

    def test_timeout_returns_to_idle(self, engine):
        engine._state      = AutoSeqState.CQ_SENT
        engine._cq_timeout = 0
        engine._check_cq_timeout()
        assert engine.state == AutoSeqState.IDLE


class TestFT8SessionVarWiring:
    def test_dx_callsign_set_on_reply_decoded(self, cfg, engine):
        """When FT8 engine starts a QSO, session.dx_callsign written to config."""
        from modes.ft8 import DecodedSignal
        engine._wsjtx_connected = True
        decode = DecodedSignal(
            callsign="K1DX", grid="FN31", snr=-5,
            dt=0.0, freq_hz=1250, message="K1DX W1AW -05",
            is_cq=False, is_reply_to="W1AW",
        )
        engine._handle_idle(decode, "W1AW")
        assert cfg.get("session.dx_callsign") == "K1DX"

    def test_dx_callsign_set_on_cq_answer(self, cfg, engine):
        """Auto-CQ: answering a CQ also writes session.dx_callsign."""
        from modes.ft8 import DecodedSignal
        engine._wsjtx_connected = True
        engine._auto_cq = True
        decode = DecodedSignal(
            callsign="VE3XYZ", grid="EN82", snr=3,
            dt=0.0, freq_hz=1400, message="CQ VE3XYZ EN82",
            is_cq=True, is_reply_to=None,
        )
        engine._handle_idle(decode, "W1AW")
        assert cfg.get("session.dx_callsign") == "VE3XYZ"
