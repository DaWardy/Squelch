from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for LoTW sync (offline/unit tests only)."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from network.lotw_sync import LoTWSync, LoTWResult


class TestLoTWResult:
    def test_success_result(self):
        r = LoTWResult(success=True, uploaded=5,
                       message="OK")
        assert r.success is True
        assert r.uploaded == 5

    def test_failure_result(self):
        r = LoTWResult(success=False,
                       error="No credentials")
        assert r.success is False
        assert "credentials" in r.error

    def test_defaults(self):
        r = LoTWResult(success=True)
        assert r.uploaded == 0
        assert r.confirmations == 0
        assert r.error == ""


class TestLoTWSyncInit:
    def test_creates_sync(self, tmp_path):
        from core.config import Config
        cfg_path = tmp_path / "config.json"
        cfg = Config(cfg_path)
        sync = LoTWSync(cfg)
        assert sync is not None

    def test_callbacks_none_by_default(self, tmp_path):
        from core.config import Config
        cfg = Config(tmp_path / "config.json")
        sync = LoTWSync(cfg)
        assert sync._on_progress is None
        assert sync._on_complete is None

    def test_register_callbacks(self, tmp_path):
        from core.config import Config
        cfg = Config(tmp_path / "config.json")
        sync = LoTWSync(cfg)
        called = []
        sync.on_progress(lambda m, p: called.append(("p", m, p)))
        sync.on_complete(lambda r: called.append(("c", r)))
        assert sync._on_progress is not None
        assert sync._on_complete is not None


class TestLoTWSyncNoCredentials:
    def test_upload_no_tqsl(self, tmp_path):
        from core.config import Config
        cfg = Config(tmp_path / "config.json")
        cfg.callsign = "NR6U"
        sync = LoTWSync(cfg)
        # No TQSL path set → should fail gracefully
        result = sync._do_upload(None)
        assert result.success is False
        assert "TQSL" in result.error

    def test_download_no_user(self, tmp_path):
        from core.config import Config
        cfg = Config(tmp_path / "config.json")
        # No callsign, no user → should fail gracefully
        sync = LoTWSync(cfg)
        result = sync._do_download()
        assert result.success is False
