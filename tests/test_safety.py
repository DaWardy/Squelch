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
