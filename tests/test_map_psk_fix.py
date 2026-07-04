from __future__ import annotations
# Squelch — RF / SDR signal platform
# Licensed under GNU GPL v3 — see LICENSE
"""Regression tests for the PSKReporter 'hearing you' crash in MapTab.

Bug: `MapTab._on_psk_spots() missing 1 required positional argument: 'spots'`
— a queued cross-thread signal could invoke the slot with zero arguments (and
the worker QObject could be garbage-collected before it emitted). The slot must
tolerate a 0-arg call, and the worker must be kept referenced.
"""
import ast
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
ROOT = Path(__file__).parent.parent
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

MAP_SRC = (ROOT / "ui/tabs/map_tab.py").read_text(encoding="utf-8")


# ── source-level guards ───────────────────────────────────────────────────────

class TestSlotSignature:
    def test_on_psk_spots_has_default_arg(self):
        """The slot must accept a zero-argument call (spots defaulted)."""
        tree = ast.parse(MAP_SRC)
        fn = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "_on_psk_spots"),
                  None)
        assert fn is not None, "_on_psk_spots not found"
        # exactly one non-self positional, and it has a default
        posargs = fn.args.args[1:]          # drop self
        assert len(posargs) == 1
        assert len(fn.args.defaults) >= 1, "spots must have a default value"

    def test_worker_reference_kept(self):
        """The worker QObject must be stored on self so it is not GC'd before
        it emits across the thread boundary."""
        assert "self._psk_worker = w" in MAP_SRC

    def test_iterates_spots_safely(self):
        # guards against None (spots or [])
        assert "spots or []" in MAP_SRC


# ── behavioural (Qt) ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
    pytest.importorskip("PyQt6", reason="PyQt6 not installed")
    from PyQt6.QtWidgets import QApplication
    a = QApplication.instance() or QApplication([])
    yield a


class TestSlotBehaviour:
    def _tab(self, app):
        from core.config import Config
        from ui.tabs.map_tab import MapTab
        return MapTab(Config())

    def test_zero_arg_call_does_not_raise(self, app):
        tab = self._tab(app)
        tab._on_psk_spots()                 # the crashing call — must be safe now
        assert tab._hearing_me == {}

    def test_none_is_safe(self, app):
        tab = self._tab(app)
        tab._on_psk_spots(None)
        assert tab._hearing_me == {}

    def test_populates_from_spots(self, app):
        tab = self._tab(app)
        tab._on_psk_spots([{"callsign": "W1AW", "grid": "FN31",
                            "freq_hz": 14_074_000, "mode": "FT8", "snr": -5}])
        assert "W1AW" in tab._hearing_me
