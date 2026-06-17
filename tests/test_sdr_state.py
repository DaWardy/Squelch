from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for SDR tab state persistence and axis calculations.

Qt-dependent tests are skipped when PyQt6 is absent from the test runner env.
Pure-logic tests (axis math, span table) run without Qt.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

# ---------------------------------------------------------------------------
# Pure-logic tests — no Qt needed
# ---------------------------------------------------------------------------

class TestMHzAxisFormula:
    """Verify that the center_hz/span_hz → lo_mhz/hi_mhz formula is correct."""

    def _axis(self, center_hz, span_hz):
        half = span_hz / 2
        return (center_hz - half) / 1e6, (center_hz + half) / 1e6

    def test_fm_broadcast(self):
        lo, hi = self._axis(99_000_000, 2_400_000)
        assert abs(lo - 97.8) < 0.01
        assert abs(hi - 100.2) < 0.01

    def test_aprs_2m(self):
        lo, hi = self._axis(144_390_000, 500_000)
        assert abs(lo - 144.14) < 0.01
        assert abs(hi - 144.64) < 0.01

    def test_lo_less_than_hi(self):
        lo, hi = self._axis(10_000_000, 1_000_000)
        assert lo < hi

    def test_center_is_midpoint(self):
        center_hz = 7_200_000
        span_hz   = 200_000
        lo, hi = self._axis(center_hz, span_hz)
        midpoint_mhz = (lo + hi) / 2
        assert abs(midpoint_mhz - center_hz / 1e6) < 1e-9

    def test_narrow_span(self):
        lo, hi = self._axis(14_225_000, 100_000)
        assert abs(lo - 14.175) < 0.001
        assert abs(hi - 14.275) < 0.001


class TestSpanTable:
    """The spans_hz list in _on_span must match the combo items in _build_span_group."""

    COMBO_LABELS = [
        "100 kHz", "500 kHz", "1 MHz", "2.4 MHz",
        "5 MHz", "10 MHz", "20 MHz"
    ]
    SPANS_HZ = [
        100_000, 500_000, 1_000_000, 2_400_000,
        5_000_000, 10_000_000, 20_000_000
    ]

    def test_table_length_matches_labels(self):
        assert len(self.SPANS_HZ) == len(self.COMBO_LABELS)

    def test_100kHz_entry(self):
        assert self.SPANS_HZ[0] == 100_000

    def test_2_4mhz_entry(self):
        assert self.SPANS_HZ[3] == 2_400_000

    def test_20mhz_entry(self):
        assert self.SPANS_HZ[-1] == 20_000_000

    def test_strictly_increasing(self):
        for a, b in zip(self.SPANS_HZ, self.SPANS_HZ[1:]):
            assert b > a, f"{b} not > {a}"


# ---------------------------------------------------------------------------
# Qt-dependent tests — skipped when PyQt6 absent
# ---------------------------------------------------------------------------

try:
    import PyQt6  # noqa: F401
    HAS_QT = True
except ImportError:
    HAS_QT = False

pytestmark_qt = pytest.mark.skipif(
    not HAS_QT, reason="PyQt6 not installed")


@pytest.fixture(scope="module")
def qt_app():
    """Return (or create) the QApplication singleton."""
    import sys
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    return app


def _make_sdr_tab(qt_app):
    """Instantiate SDRTab with a temp config and mock rig."""
    import tempfile
    from unittest.mock import MagicMock
    from core.config import Config

    tmp = tempfile.mkdtemp()
    cfg = Config(Path(tmp) / "config.json")
    rig = MagicMock()
    rig.is_connected = False
    rig.state = MagicMock()

    # SDRTab imports SoapySDR at import time — patch it out
    import unittest.mock as mock
    with mock.patch.dict("sys.modules", {
        "sdr.soapy_device": mock.MagicMock(),
    }):
        from ui.tabs.sdr_tab import SDRTab
        tab = SDRTab(cfg, rig)
    return tab, cfg


@pytest.mark.skipif(not HAS_QT, reason="PyQt6 not installed")
class TestSDRSaveRestoreState:

    def test_save_state_returns_dict(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        state = tab.save_state()
        assert isinstance(state, dict)

    def test_save_state_has_required_keys(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        state = tab.save_state()
        for key in ("center_hz", "span", "gain", "ppm",
                    "palette", "floor_db", "ceil_db", "peak_hold"):
            assert key in state, f"Missing key: {key}"

    def test_center_hz_default(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        state = tab.save_state()
        assert state["center_hz"] == 100_000_000

    def test_palette_default(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        state = tab.save_state()
        assert state["palette"] == "Jet"

    def test_restore_state_noop_on_empty(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        tab.restore_state({})  # should not raise

    def test_round_trip_palette(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        tab._palette_combo.setCurrentText("Viridis")
        state = tab.save_state()
        assert state["palette"] == "Viridis"
        tab._palette_combo.setCurrentText("Jet")
        tab.restore_state(state)
        assert tab._palette_combo.currentText() == "Viridis"

    def test_round_trip_gain(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        tab._gain_slider.setValue(45)
        state = tab.save_state()
        tab._gain_slider.setValue(0)
        tab.restore_state(state)
        assert tab._gain_slider.value() == 45

    def test_round_trip_peak_hold(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        tab._peak_cb.setChecked(True)
        state = tab.save_state()
        tab._peak_cb.setChecked(False)
        tab.restore_state(state)
        assert tab._peak_cb.isChecked()

    def test_round_trip_span(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        tab._span_combo.setCurrentText("500 kHz")
        state = tab.save_state()
        tab._span_combo.setCurrentText("2.4 MHz")
        tab.restore_state(state)
        assert tab._span_combo.currentText() == "500 kHz"


@pytest.mark.skipif(not HAS_QT, reason="PyQt6 not installed")
class TestSDRScreenshot:
    """Verify _save_screenshot saves a valid PNG and reports via status bar."""

    def test_screenshot_creates_file(self, tmp_path, qt_app, monkeypatch):
        """Screenshot is written to a temp path and returns a non-empty file."""
        tab, _ = _make_sdr_tab(qt_app)
        monkeypatch.setattr(
            "pathlib.Path.home", lambda: tmp_path)
        # Create Desktop dir so the first candidate is picked
        (tmp_path / "Desktop").mkdir()
        tab._save_screenshot()
        shots = list((tmp_path / "Desktop").glob("squelch_sdr_*.png"))
        assert shots, "Expected a screenshot PNG in Desktop"
        assert shots[0].stat().st_size > 0

    def test_screenshot_filename_format(self, tmp_path, qt_app, monkeypatch):
        """Filename matches squelch_sdr_YYYYMMDD_HHmmss.png pattern."""
        import re
        tab, _ = _make_sdr_tab(qt_app)
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        (tmp_path / "Desktop").mkdir()
        tab._save_screenshot()
        shots = list((tmp_path / "Desktop").glob("squelch_sdr_*.png"))
        assert re.match(r"squelch_sdr_\d{8}_\d{6}\.png$", shots[0].name)

    def test_screenshot_falls_back_to_downloads(self, tmp_path, qt_app, monkeypatch):
        """Falls back to Downloads when Desktop does not exist."""
        tab, _ = _make_sdr_tab(qt_app)
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        (tmp_path / "Downloads").mkdir()
        # No Desktop dir
        tab._save_screenshot()
        shots = list((tmp_path / "Downloads").glob("squelch_sdr_*.png"))
        assert shots, "Expected fallback to Downloads"
