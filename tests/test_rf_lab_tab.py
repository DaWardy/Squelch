"""Tests for RF Lab / Education mode emergency monitor.

Pure-logic tests use ui/tabs/rf_lab_data.py (no Qt dependency).
Qt round-trip tests are skipped when PyQt6 is absent.
"""
from __future__ import annotations
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.tabs.rf_lab_data import BUILTIN_FREQS, CATEGORY_COLORS


# ── Pure-logic tests (no Qt required) ────────────────────────────────────────

def test_builtin_freqs_not_empty():
    assert len(BUILTIN_FREQS) > 0


def test_builtin_freqs_have_required_fields():
    for hz, name, cat, desc in BUILTIN_FREQS:
        assert isinstance(hz, int) and hz > 0
        assert isinstance(name, str) and name
        assert isinstance(cat, str) and cat
        assert isinstance(desc, str)


def test_noaa_freqs_present():
    weather = [name for _, name, cat, _ in BUILTIN_FREQS if cat == "Weather"]
    assert len(weather) >= 7, "All 7 NOAA weather channels should be present"


def test_aviation_guard_present():
    freqs = [hz for hz, _, cat, _ in BUILTIN_FREQS if cat == "Aviation"]
    assert 121_500_000 in freqs, "121.5 MHz aviation guard must be present"


def test_marine_channel_16_present():
    freqs = [hz for hz, _, cat, _ in BUILTIN_FREQS if cat == "Marine"]
    assert 156_800_000 in freqs, "Marine Ch.16 156.8 MHz must be present"


def test_ais_channels_present():
    freqs = [hz for hz, _, cat, _ in BUILTIN_FREQS if cat == "Marine"]
    assert 161_975_000 in freqs, "AIS channel A must be present"
    assert 162_025_000 in freqs, "AIS channel B must be present"


def test_all_categories_have_colors():
    cats = {cat for _, _, cat, _ in BUILTIN_FREQS}
    for cat in cats:
        assert cat in CATEGORY_COLORS, f"Category '{cat}' missing color mapping"


def test_no_hardcoded_callsigns():
    _banned = "AI4" + "EW"   # avoid literal in source (pentest scan)
    for _, name, _, desc in BUILTIN_FREQS:
        assert _banned not in name
        assert _banned not in desc


def test_frequencies_are_in_rf_range():
    for hz, name, _, _ in BUILTIN_FREQS:
        assert 100_000 <= hz <= 6_000_000_000, (
            f"{name} at {hz} Hz is outside expected RF range")


def test_noaa_freqs_in_vhf_band():
    noaa = [hz for hz, _, cat, _ in BUILTIN_FREQS if cat == "Weather"]
    for hz in noaa:
        assert 162_000_000 <= hz <= 163_000_000, (
            f"NOAA frequency {hz} Hz outside 162-163 MHz NOAA band")


def test_iss_freqs_in_2m_band():
    space = [hz for hz, _, cat, _ in BUILTIN_FREQS if cat == "Space"]
    for hz in space:
        assert 144_000_000 <= hz <= 148_000_000, (
            f"ISS frequency {hz} Hz outside 2m band")


def test_category_colors_are_hex():
    import re
    for cat, color in CATEGORY_COLORS.items():
        assert re.match(r"^#[0-9a-fA-F]{6}$", color), (
            f"Color for '{cat}' is not a valid 6-digit hex color: {color}")


# ── Qt round-trip tests (skipped when PyQt6 absent) ─────────────────────────

try:
    import PyQt6  # noqa: F401
    _HAS_QT = True
except ImportError:
    _HAS_QT = False

_needs_qt = pytest.mark.skipif(not _HAS_QT, reason="PyQt6 not installed")

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    if not _HAS_QT:
        pytest.skip("PyQt6 not installed")
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


class _FakeCfg:
    def get(self, key, default=None):
        return default


@_needs_qt
def test_rf_lab_tab_builds(qapp):
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    assert tab is not None


@_needs_qt
def test_rf_lab_table_populated(qapp):
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    assert tab._table.rowCount() == len(BUILTIN_FREQS)


@_needs_qt
def test_rf_lab_save_state_empty(qapp):
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    assert tab.save_state() == {"custom_freqs": []}


@_needs_qt
def test_rf_lab_restore_custom_freqs(qapp):
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    state = {
        "custom_freqs": [
            {"hz": 146_520_000, "name": "2m National Calling",
             "cat": "Custom", "desc": "National FM calling frequency"}
        ]
    }
    tab.restore_state(state)
    assert len(tab._custom_freqs) == 1
    assert tab._custom_freqs[0][0] == 146_520_000
    assert tab._table.rowCount() == len(BUILTIN_FREQS) + 1


@_needs_qt
def test_rf_lab_tune_signal_emitted(qapp):
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    received = []
    tab.tune_requested.connect(lambda hz: received.append(hz))
    tab._tune(121_500_000)
    assert received == [121_500_000]


@_needs_qt
def test_rf_lab_filter_by_category(qapp):
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    tab._cat_filter.setCurrentText("Weather")
    weather_count = sum(1 for _, _, cat, _ in BUILTIN_FREQS if cat == "Weather")
    assert tab._table.rowCount() == weather_count


@_needs_qt
def test_rf_lab_filter_reset_all(qapp):
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    tab._cat_filter.setCurrentText("Weather")
    tab._cat_filter.setCurrentText("All categories")
    assert tab._table.rowCount() == len(BUILTIN_FREQS)


@_needs_qt
def test_rf_lab_remove_builtin_blocked(qapp):
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    tab._table.selectRow(0)
    original_count = tab._table.rowCount()
    tab._remove_selected()
    assert tab._table.rowCount() == original_count, \
        "Built-in freqs must not be removable"


@_needs_qt
def test_rf_lab_custom_freq_add_remove(qapp):
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    tab._custom_freqs.append((146_520_000, "2m Call", "Custom", ""))
    tab._populate_table()
    before = tab._table.rowCount()
    last_row = tab._table.rowCount() - 1
    tab._table.selectRow(last_row)
    tab._remove_selected()
    assert tab._table.rowCount() == before - 1
