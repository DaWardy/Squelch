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
    c.callsign = "NR6U"
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
        engine.cfg.callsign = "NR6U"
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
