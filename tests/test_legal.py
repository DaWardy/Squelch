from __future__ import annotations
# Squelch — RF / SDR signal platform
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for the first-run legal-acknowledgment gate (core/legal.py + wiring)."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
ROOT = Path(__file__).parent.parent
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.legal import (
    needs_legal_ack, record_legal_ack, legal_ack_status,
    DISCLAIMER_VERSION, LEGAL_SUMMARY, _CFG_ACK_VERSION,
)


class _FakeCfg:
    def __init__(self, data=None):
        self._d = dict(data or {})
        self.saved = 0

    def get(self, k, default=None):
        return self._d.get(k, default)

    def set(self, k, v):
        self._d[k] = v

    def save(self):
        self.saved += 1


# ── pure decision ─────────────────────────────────────────────────────────────

class TestNeedsAck:
    def test_fresh_config_needs_ack(self):
        assert needs_legal_ack(_FakeCfg()) is True

    def test_none_cfg_needs_ack(self):
        assert needs_legal_ack(None) is True

    def test_after_record_no_longer_needed(self):
        cfg = _FakeCfg()
        record_legal_ack(cfg)
        assert needs_legal_ack(cfg) is False

    def test_old_version_forces_reack(self):
        cfg = _FakeCfg({_CFG_ACK_VERSION: DISCLAIMER_VERSION - 1})
        assert needs_legal_ack(cfg) is True

    def test_broken_cfg_fails_toward_needing_ack(self):
        class Bad:
            def get(self, *a):
                raise RuntimeError("boom")
        assert needs_legal_ack(Bad()) is True


class TestRecord:
    def test_persists_version_and_timestamp_and_saves(self):
        cfg = _FakeCfg()
        record_legal_ack(cfg)
        assert cfg.get(_CFG_ACK_VERSION) == DISCLAIMER_VERSION
        assert cfg.get("legal.ack_ts", "").endswith("Z")
        assert cfg.saved == 1

    def test_none_cfg_is_noop(self):
        record_legal_ack(None)          # must not raise


class TestStatus:
    def test_status_before_and_after(self):
        cfg = _FakeCfg()
        before = legal_ack_status(cfg)
        assert before["acknowledged"] is False
        assert before["required_version"] == DISCLAIMER_VERSION
        record_legal_ack(cfg)
        after = legal_ack_status(cfg)
        assert after["acknowledged"] is True
        assert after["version"] == DISCLAIMER_VERSION


# ── disclaimer content ────────────────────────────────────────────────────────

class TestDisclaimerDoc:
    def test_disclaimer_file_exists(self):
        assert (ROOT / "DISCLAIMER.md").exists()

    def test_disclaimer_covers_key_points(self):
        txt = (ROOT / "DISCLAIMER.md").read_text(encoding="utf-8").lower()
        for phrase in ("no authorization", "transmit", "receiv",
                       "warranty", "responsib"):
            assert phrase in txt, phrase

    def test_summary_mentions_responsibility_and_full_terms(self):
        assert "responsibilit" in LEGAL_SUMMARY.lower()
        assert "DISCLAIMER.md" in LEGAL_SUMMARY


# ── UI wiring (source-level; no Qt needed) ────────────────────────────────────

class TestWiring:
    def test_firstrun_calls_legal_gate(self):
        src = (ROOT / "ui/main_window_firstrun.py").read_text(encoding="utf-8")
        assert "needs_legal_ack" in src
        assert "_show_legal_ack" in src
        assert "show_legal_ack" in src
        assert "self.close()" in src        # declining quits the app

    def test_legal_ack_module_short_circuits_when_acked(self):
        # already-accepted → returns True without constructing any dialog
        from ui.legal_ack import show_legal_ack
        cfg = _FakeCfg()
        record_legal_ack(cfg)
        assert show_legal_ack(None, cfg) is True
