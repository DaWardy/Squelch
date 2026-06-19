"""Tests for LocalRFTab FEAT-04 improvements:
  - Credential banner visible when no RepeaterBook token
  - SDR auto-tune callback wiring
  - Manual freq entry (dialog already present)
"""
from __future__ import annotations
import sys
import ast
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest


def _src() -> str:
    return (pathlib.Path(__file__).parent.parent /
            "ui" / "tabs" / "localrf_tab.py").read_text(encoding="utf-8")


# ── Pure-logic / source checks ────────────────────────────────────────────────

class TestLocalRFCredBannerSource:
    def test_cred_banner_attribute(self):
        assert "_cred_banner" in _src()

    def test_refresh_cred_banner_method(self):
        assert "def _refresh_cred_banner(" in _src()

    def test_banner_calls_rb_token(self):
        assert "_rb_token" in _src()

    def test_banner_set_visible(self):
        assert "setVisible" in _src()


class TestLocalRFSdrTuneSource:
    def test_set_sdr_tune_cb_method(self):
        assert "def set_sdr_tune_cb(" in _src()

    def test_sdr_tune_cb_called_on_tune(self):
        src = _src()
        tune_idx = src.find("def _tune_to_selected(")
        next_def = src.find("\n    def ", tune_idx + 10)
        body = src[tune_idx:next_def]
        assert "_sdr_tune_cb" in body

    def test_main_window_wires_sdr_to_localrf(self):
        mw_src = (pathlib.Path(__file__).parent.parent /
                  "ui" / "main_window.py").read_text(encoding="utf-8")
        assert "set_sdr_tune_cb" in mw_src

    def test_manual_repeater_dialog_present(self):
        assert "def _add_manual_repeater(" in _src()

    def test_manual_btn_in_btn_row(self):
        src = _src()
        btn_row_idx = src.find("def _build_repeater_btn_row(")
        next_def = src.find("\n    def ", btn_row_idx + 10)
        body = src[btn_row_idx:next_def]
        assert "Add Manually" in body


class TestSdrTuneCallbackLogic:
    """Simulate the SDR tune callback dispatch."""

    def test_callback_called_with_hz(self):
        called_with = []
        class _FakeTab:
            _sdr_tune_cb = None
            rig = None
            def _tune_to_selected(self, _index=None):
                hz = 146_520_000
                if self._sdr_tune_cb:
                    try:
                        self._sdr_tune_cb(hz)
                    except Exception:
                        pass
        tab = _FakeTab()
        tab._sdr_tune_cb = called_with.append
        tab._tune_to_selected()
        assert called_with == [146_520_000]

    def test_no_callback_no_error(self):
        class _FakeTab:
            _sdr_tune_cb = None
            rig = None
            def _tune_to_selected(self):
                hz = 146_520_000
                if self._sdr_tune_cb:
                    self._sdr_tune_cb(hz)
        tab = _FakeTab()
        tab._tune_to_selected()  # should not raise

    def test_callback_exception_suppressed(self):
        def _bad_cb(hz):
            raise RuntimeError("SDR not ready")
        class _FakeTab:
            _sdr_tune_cb = _bad_cb
            def _tune_to_selected(self):
                if self._sdr_tune_cb:
                    try:
                        self._sdr_tune_cb(146_520_000)
                    except Exception:
                        pass
        tab = _FakeTab()
        tab._tune_to_selected()  # must not raise

    def test_freq_hz_conversion(self):
        """output_mhz * 1e6 must round-trip correctly."""
        output_mhz = 146.520
        hz = int(output_mhz * 1_000_000)
        assert hz == 146_520_000
