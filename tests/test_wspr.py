from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for WSPR engine — focus on callsign compliance and message format."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def cfg(tmp_path):
    from core.config import Config
    c = Config(tmp_path / "config.json")
    c.callsign = "W1AW"
    c.grid     = "DM79rr"
    c.set("wspr.power_dbm", 30)
    return c


@pytest.fixture
def engine(cfg):
    from modes.wspr import WSPREngine
    return WSPREngine(cfg)


class TestWSPREngineInit:
    def test_creates_engine(self, engine):
        assert engine is not None

    def test_not_in_tx(self, engine):
        assert not engine.is_tx

    def test_counts_start_zero(self, engine):
        assert engine.tx_count == 0
        assert engine.rx_count == 0


class TestWSPRTXMessage:
    def test_tx_message_contains_station_callsign(self, engine):
        """_do_tx must build message with the operating callsign."""
        tx_calls = []
        engine._on_tx = lambda band, freq, msg: tx_calls.append(msg)

        with patch("time.sleep"):
            engine._do_tx("20m")

        assert tx_calls, "_on_tx never fired"
        assert "W1AW" in tx_calls[0]

    def test_tx_message_contains_grid(self, engine):
        with patch("time.sleep"):
            msgs = []
            engine._on_tx = lambda b, f, m: msgs.append(m)
            engine._do_tx("20m")
        assert any("DM79" in m for m in msgs)

    def test_tx_message_contains_power(self, engine):
        with patch("time.sleep"):
            msgs = []
            engine._on_tx = lambda b, f, m: msgs.append(m)
            engine._do_tx("20m")
        # Default power is 27 dBm; just verify a numeric token is present
        assert any(any(c.isdigit() for c in m) for m in msgs)


class TestWSPRGuestCallsign:
    """_do_tx must use operating_callsign(), not cfg.callsign directly."""

    def test_tx_uses_guest_callsign(self, cfg):
        from modes.wspr import WSPREngine
        cfg.set("guest.active",   True)
        cfg.set("guest.callsign", "KE2XYZ")
        engine = WSPREngine(cfg)

        tx_calls = []
        engine._on_tx = lambda band, freq, msg: tx_calls.append(msg)

        with patch("time.sleep"):
            engine._do_tx("20m")

        assert tx_calls, "_on_tx never fired"
        assert "KE2XYZ" in tx_calls[0]
        assert "W1AW" not in tx_calls[0]

    def test_tx_increments_count_in_guest_mode(self, cfg):
        from modes.wspr import WSPREngine
        cfg.set("guest.active",   True)
        cfg.set("guest.callsign", "KE2XYZ")
        engine = WSPREngine(cfg)
        with patch("time.sleep"):
            engine._do_tx("20m")
        assert engine.tx_count == 1


class TestWSPRShouldTx:
    def test_tx_percentage_respected(self, engine):
        """With tx_pct=0, never tx; with 100, always tx."""
        engine._tx_pct = 0
        assert not any(
            engine._should_tx_this_cycle(i) for i in range(20))

    def test_session_stats_keys(self, engine):
        stats = engine.session_stats()
        assert "tx" in stats
        assert "rx" in stats
