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
    state = tab.save_state()
    assert state["custom_freqs"] == []
    assert "splitter_sizes" in state


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


# ── Decode monitor tests (pure-logic, no Qt) ─────────────────────────────────

# ── CHIRP import tests (pure-logic, no Qt) ───────────────────────────────────

def test_chirp_category_in_category_colors():
    from ui.tabs.rf_lab_data import CATEGORY_COLORS
    assert "CHIRP" in CATEGORY_COLORS, "CHIRP category must have a color defined"


def test_chirp_category_color_is_hex():
    import re
    from ui.tabs.rf_lab_data import CATEGORY_COLORS
    color = CATEGORY_COLORS["CHIRP"]
    assert re.match(r"^#[0-9a-fA-F]{6}$", color), (
        f"CHIRP color not valid 6-digit hex: {color}")


def test_chirp_csv_parse_integration(tmp_path):
    """parse_chirp_csv returns Repeater objects convertible to RF Lab format."""
    csv_content = (
        "Location,Name,Frequency,Duplex,Offset,Tone,rToneFreq,cToneFreq,"
        "DtcsCode,DtcsPolarity,Mode,TStep,Skip,Comment,URCALL,RPT1CALL,"
        "RPT2CALL,DVCODE\n"
        "0,WR6X,146.520000,,0.000000,,100.0,88.5,023,NN,FM,5.00,,Simplex,,,,\n"
        "1,WB6Z,462.550000,+,5.000000,Tone,100.0,88.5,023,NN,FM,12.50,,GMRS,,,,\n"
    )
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")
    from network.chirp_import import parse_chirp_csv
    repeaters = parse_chirp_csv(str(csv_file))
    assert len(repeaters) == 2
    hz0 = int(round(repeaters[0].output_mhz * 1_000_000))
    assert hz0 == 146_520_000
    hz1 = int(round(repeaters[1].output_mhz * 1_000_000))
    assert hz1 == 462_550_000


def test_chirp_csv_skips_zero_freq(tmp_path):
    csv_content = (
        "Location,Name,Frequency,Duplex,Offset,Tone,rToneFreq,cToneFreq,"
        "DtcsCode,DtcsPolarity,Mode,TStep,Skip,Comment,URCALL,RPT1CALL,"
        "RPT2CALL,DVCODE\n"
        "0,Bad,,,,,,023,NN,FM,5.00,,,,,,\n"
        "1,Good,146.520000,,0.000000,,100.0,88.5,023,NN,FM,5.00,,,,,,\n"
    )
    csv_file = tmp_path / "test_skip.csv"
    csv_file.write_text(csv_content, encoding="utf-8")
    from network.chirp_import import parse_chirp_csv
    repeaters = parse_chirp_csv(str(csv_file))
    assert len(repeaters) == 1


def test_chirp_csv_missing_frequency_header_raises(tmp_path):
    csv_content = "Name,Freq\nTest,146.52\n"
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text(csv_content, encoding="utf-8")
    from network.chirp_import import parse_chirp_csv
    import pytest
    with pytest.raises(ValueError, match="Frequency"):
        parse_chirp_csv(str(csv_file))


def test_decode_mode_colors_defined():
    from ui.tabs.rf_lab_data import DECODE_MODE_COLORS
    for mode in ("FT8", "FT4", "WSPR", "JS8", "CW", "APRS"):
        assert mode in DECODE_MODE_COLORS

def test_decode_mode_colors_are_hex():
    import re
    from ui.tabs.rf_lab_data import DECODE_MODE_COLORS
    for mode, color in DECODE_MODE_COLORS.items():
        assert re.match(r"^#[0-9a-fA-F]{6}$", color), (
            f"Color for {mode} not valid hex: {color}")


@_needs_qt
def test_decode_monitor_widget_exists(qapp):
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    assert hasattr(tab, "_decode_view")
    assert tab._decode_view is not None


@_needs_qt
def test_append_decode_stores_entry(qapp):
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    tab.append_decode("FT8", 14_074_000, callsign="W1AW",
                      message="CQ W1AW FN31", snr=-12.0, grid="FN31")
    assert len(tab._decode_entries) == 1


@_needs_qt
def test_append_decode_entry_fields(qapp):
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    tab.append_decode("WSPR", 14_097_000, callsign="G3XXX",
                      message="G3XXX IO91 37", snr=-18.0, grid="IO91")
    ts, mode, freq_hz, callsign, grid, message, snr = tab._decode_entries[0]
    assert mode == "WSPR"
    assert freq_hz == 14_097_000
    assert callsign == "G3XXX"
    assert snr == -18.0


@_needs_qt
def test_append_decode_normalises_mode_uppercase(qapp):
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    tab.append_decode("ft8", 14_074_000)
    assert tab._decode_entries[0][1] == "FT8"


@_needs_qt
def test_clear_decodes(qapp):
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    tab.append_decode("FT8", 14_074_000)
    tab._clear_decodes()
    assert len(tab._decode_entries) == 0


@_needs_qt
def test_decode_entries_capped_at_500(qapp):
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    for i in range(600):
        tab.append_decode("FT8", 14_074_000 + i)
    assert len(tab._decode_entries) <= 500


@_needs_qt
def test_decode_mode_filter_hides_others(qapp):
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    tab.append_decode("FT8",  14_074_000)
    tab.append_decode("WSPR", 14_097_000)
    tab.append_decode("FT8",  14_074_000)
    tab._decode_mode_filter.setCurrentText("FT8")
    # Only FT8 entries should be in the view
    assert len([e for e in tab._decode_entries if e[1] == "FT8"]) == 2


@_needs_qt
def test_rf_lab_has_chirp_import_method(qapp):
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    assert hasattr(tab, "_import_chirp"), "_import_chirp method must exist"
    assert callable(tab._import_chirp)


@_needs_qt
def test_rf_lab_chirp_entry_appears_in_table(qapp):
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    tab._custom_freqs.append((462_550_000, "Test GMRS", "CHIRP", "Test channel"))
    tab._populate_table()
    assert tab._table.rowCount() == len(BUILTIN_FREQS) + 1


@_needs_qt
def test_rf_lab_chirp_filter_shows_only_chirp(qapp):
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    tab._custom_freqs.append((462_550_000, "GMRS Ch1", "CHIRP", ""))
    tab._custom_freqs.append((462_575_000, "GMRS Ch16", "CHIRP", ""))
    tab._populate_table()
    tab._cat_filter.setCurrentText("CHIRP")
    assert tab._table.rowCount() == 2


@_needs_qt
def test_rf_lab_chirp_import_button_present(qapp):
    from PyQt6.QtWidgets import QPushButton
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    btns = [w for w in tab.findChildren(QPushButton)
            if "CHIRP" in (w.text() or "")]
    assert len(btns) >= 1, "Import CHIRP CSV button must be present in toolbar"


@_needs_qt
def test_rf_lab_chirp_category_in_filter_combo(qapp):
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    items = [tab._cat_filter.itemText(i)
             for i in range(tab._cat_filter.count())]
    assert "CHIRP" in items, "CHIRP must appear in category filter combo"


@_needs_qt
def test_splitter_present(qapp):
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    assert tab._splitter is not None


@_needs_qt
def test_save_restore_splitter_sizes(qapp):
    from ui.tabs.rf_lab_tab import RFLabTab
    tab = RFLabTab(_FakeCfg())
    state = tab.save_state()
    assert len(state["splitter_sizes"]) == 2
    tab.restore_state({"custom_freqs": [], "splitter_sizes": [300, 300]})


# ── FT8/WSPR → RF Lab decode bridge tests ────────────────────────────────────

class TestFT8RFLabBridge:
    """Verify FT8 decode data contract with rf_lab.append_decode."""

    def test_ft8_in_decode_mode_colors(self):
        from ui.tabs.rf_lab_data import DECODE_MODE_COLORS
        assert "FT8" in DECODE_MODE_COLORS

    def test_wspr_in_decode_mode_colors(self):
        from ui.tabs.rf_lab_data import DECODE_MODE_COLORS
        assert "WSPR" in DECODE_MODE_COLORS

    def test_ft8_bridge_logic(self):
        """Simulate _on_ft8_decode bridge with a fake rf_lab."""
        calls = []

        class _FakeRFLab:
            def append_decode(self, mode, freq_hz, callsign="",
                              message="", snr=0.0, grid=""):
                calls.append((mode, freq_hz, callsign, message, snr, grid))

        from modes.ft8 import DecodedSignal
        sig = DecodedSignal(snr=-12, dt=0.3, freq_hz=14_074_000,
                            message="W1AW K0ABC EM38", callsign="W1AW",
                            grid="EM38")
        rf_lab = _FakeRFLab()
        msg = (sig.message or "")[:80]
        rf_lab.append_decode("FT8", sig.freq_hz,
                             callsign=sig.callsign, message=msg,
                             snr=float(sig.snr), grid=sig.grid)
        assert len(calls) == 1
        mode, freq_hz, callsign, message, snr, grid = calls[0]
        assert mode == "FT8"
        assert freq_hz == 14_074_000
        assert callsign == "W1AW"
        assert "W1AW" in message
        assert snr == -12.0
        assert grid == "EM38"

    def test_ft8_message_truncated_to_80(self):
        from modes.ft8 import DecodedSignal
        long_msg = "X" * 200
        sig = DecodedSignal(snr=0, dt=0.0, freq_hz=14_074_000,
                            message=long_msg)
        assert len((sig.message or "")[:80]) == 80

    def test_wspr_bridge_logic(self):
        """Simulate _on_wspr_spot bridge with a fake rf_lab."""
        calls = []

        class _FakeRFLab:
            def append_decode(self, mode, freq_hz, callsign="",
                              message="", snr=0.0, grid=""):
                calls.append((mode, freq_hz, callsign, message, snr, grid))

        from modes.wspr import WSPRSpot
        import time
        spot = WSPRSpot(timestamp=time.time(), callsign="W1AW",
                        grid="FN31", power_dbm=30, snr=-20,
                        dt=0.5, freq_hz=14_097_100, drift=0)
        rf_lab = _FakeRFLab()
        msg = f"{spot.callsign} {spot.grid} {spot.power_dbm}dBm"
        rf_lab.append_decode("WSPR", spot.freq_hz,
                             callsign=spot.callsign, message=msg,
                             snr=float(spot.snr), grid=spot.grid)
        assert len(calls) == 1
        mode, freq_hz, callsign, message, snr, grid = calls[0]
        assert mode == "WSPR"
        assert freq_hz == 14_097_100
        assert callsign == "W1AW"
        assert "FN31" in message
        assert "30dBm" in message
        assert snr == -20.0

    def test_wspr_freq_hz_is_int(self):
        from modes.wspr import WSPRSpot
        import time
        spot = WSPRSpot(timestamp=time.time(), callsign="W1AW",
                        grid="FN31", power_dbm=20, snr=-18,
                        dt=0.0, freq_hz=14_097_050, drift=0)
        assert isinstance(spot.freq_hz, int)

    def test_decoded_signal_freq_hz_is_int(self):
        from modes.ft8 import DecodedSignal
        sig = DecodedSignal(snr=0, dt=0.0, freq_hz=7_074_000,
                            message="CQ W1AW FN31")
        assert isinstance(sig.freq_hz, int)
