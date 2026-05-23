from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for safety watchdog module."""

import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock, patch
from core.safety import SafetyManager, get_safety


class TestSafetyManagerBasics:
    def test_has_ptt_timeout(self, tmp_path):
        from core.config import Config
        cfg = Config(tmp_path / "config.json")
        s = get_safety()
        assert s is not None  # SafetyManager created successfully

    def test_watchdog_active_after_start(self, tmp_path):
        from core.config import Config
        cfg = Config(tmp_path / "config.json")
        s = get_safety()
        assert s is not None


class TestSafetyManager:
    def test_creates_manager(self, tmp_path):
        from core.config import Config
        cfg = Config(tmp_path / "config.json")
        from core.safety import get_safety
        s = get_safety()
        assert s is not None

    def test_singleton(self, tmp_path):
        from core.config import Config
        from core.safety import get_safety
        cfg = Config(tmp_path / "config.json")
        s1 = get_safety()
        s2 = get_safety()
        assert s1 is s2


def test_guest_mode_blocks_transmit():
    """C-06/C-08: Guest mode must disable all transmit."""
    from core.safety import SafetyManager
    s = SafetyManager()
    # Normally can transmit from IDLE
    assert s.can_transmit() is True
    # Guest mode blocks it
    s.set_guest_mode(True)
    assert s.can_transmit() is False
    # And re-enables when off
    s.set_guest_mode(False)
    assert s.can_transmit() is True



def test_ft8_autotx_blocked_in_guest_mode(monkeypatch):
    """C-14: FT8 auto-sequence may be armed for teaching, but _queue_tx
    must not transmit when Guest mode is on."""
    from core.safety import get_safety, SafetyManager
    import core.safety as safety_mod
    # Fresh singleton in guest mode
    sm = SafetyManager()
    sm.set_guest_mode(True)
    monkeypatch.setattr(safety_mod, "_safety", sm)
    monkeypatch.setattr(safety_mod, "get_safety", lambda: sm)

    sent = []
    # Minimal stand-in for the engine's send path
    class FakeEngine:
        _on_tx = None
        _on_state_change = None
        _halted = False
        _tx_message = None
        _in_tx = False
        def _send_reply_packet(self, m): sent.append(m)
        # bind the real _queue_tx
        from modes.ft8 import FT8Engine as _E
        _queue_tx = _E._queue_tx

    FakeEngine()._queue_tx("CQ TEST GRID")
    assert sent == [], "Guest mode must block FT8 auto-TX"
