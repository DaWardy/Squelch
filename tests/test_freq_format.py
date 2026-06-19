"""FEAT-03 — Frequency unit setting tests.

Tests for core/freq_format.py helpers and the Settings wiring.
All pure-logic (no Qt needed).
"""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from core.freq_format import (
    format_freq, format_freq_cfg, parse_freq_input,
    freq_label, freq_placeholder,
)


class TestFormatFreq:

    def test_mhz_default(self):
        assert format_freq(14_074_000) == "14.074 MHz"

    def test_mhz_precision(self):
        assert format_freq(14_074_000, "MHz", precision=6) == "14.074000 MHz"

    def test_khz(self):
        assert format_freq(14_074_000, "kHz") == "14074.0 kHz"

    def test_hz(self):
        assert format_freq(144_800_000, "Hz") == "144800000 Hz"

    def test_zero_hz(self):
        assert format_freq(0, "MHz") == "0.000 MHz"

    def test_mhz_sub_mhz(self):
        assert format_freq(500_000, "MHz") == "0.500 MHz"


class TestFormatFreqCfg:

    class _Cfg:
        def __init__(self, units):
            self._u = units
        def get(self, key, default=None):
            if key == "display.freq_units":
                return self._u
            return default

    def test_mhz_from_cfg(self):
        assert "MHz" in format_freq_cfg(14_074_000, self._Cfg("MHz"))

    def test_khz_from_cfg(self):
        assert "kHz" in format_freq_cfg(14_074_000, self._Cfg("kHz"))

    def test_hz_from_cfg(self):
        assert "Hz" in format_freq_cfg(14_074_000, self._Cfg("Hz"))

    def test_none_cfg_defaults_to_mhz(self):
        assert "MHz" in format_freq_cfg(14_074_000, None)

    def test_invalid_units_defaults_to_mhz(self):
        assert "MHz" in format_freq_cfg(14_074_000, self._Cfg("GHz"))


class TestParseFreqInput:

    def test_bare_mhz_value(self):
        assert parse_freq_input("14.074", "MHz") == 14_074_000

    def test_bare_hz_large_number(self):
        assert parse_freq_input("14074000", "MHz") == 14_074_000

    def test_suffixed_mhz(self):
        assert parse_freq_input("14.074 MHz", "kHz") == 14_074_000

    def test_suffixed_khz(self):
        assert parse_freq_input("14074 kHz", "MHz") == 14_074_000

    def test_suffixed_hz(self):
        assert parse_freq_input("14074000 Hz", "MHz") == 14_074_000

    def test_khz_mode_bare(self):
        assert parse_freq_input("14074", "kHz") == 14_074_000

    def test_hz_mode_bare(self):
        assert parse_freq_input("14074000", "Hz") == 14_074_000

    def test_empty_string_returns_zero(self):
        assert parse_freq_input("", "MHz") == 0

    def test_garbage_returns_zero(self):
        assert parse_freq_input("notafreq", "MHz") == 0

    def test_commas_stripped(self):
        assert parse_freq_input("14,074,000", "Hz") == 14_074_000


class TestFreqLabelAndPlaceholder:

    def test_label_mhz(self):
        assert freq_label("MHz") == "Freq (MHz)"

    def test_label_khz(self):
        assert freq_label("kHz") == "Freq (kHz)"

    def test_label_hz(self):
        assert freq_label("Hz") == "Freq (Hz)"

    def test_placeholder_mhz(self):
        assert "14" in freq_placeholder("MHz")

    def test_placeholder_khz(self):
        assert "14074" in freq_placeholder("kHz")

    def test_placeholder_hz(self):
        assert "14074000" in freq_placeholder("Hz")


class TestSettingsWiring:

    def test_freq_units_field_in_appearance_tab(self):
        src = (pathlib.Path(__file__).parent.parent
               / "ui/dialogs/settings_appearance_tab.py"
               ).read_text(encoding="utf-8")
        assert "_freq_units" in src, \
            "_freq_units combo missing from settings_appearance_tab.py"

    def test_freq_units_saved_in_dialog(self):
        src = (pathlib.Path(__file__).parent.parent
               / "ui/dialogs/settings_dialog.py"
               ).read_text(encoding="utf-8")
        assert "display.freq_units" in src, \
            "display.freq_units not saved/loaded in settings_dialog.py"

    def test_rf_lab_uses_format_freq_cfg(self):
        src = (pathlib.Path(__file__).parent.parent
               / "ui/tabs/rf_lab_tab.py"
               ).read_text(encoding="utf-8")
        assert "format_freq_cfg" in src, \
            "RF Lab tab must use format_freq_cfg for frequency display"

    def test_log_tab_uses_parse_freq_input(self):
        src = (pathlib.Path(__file__).parent.parent
               / "ui/tabs/log_tab.py"
               ).read_text(encoding="utf-8")
        assert "parse_freq_input" in src, \
            "log_tab must use parse_freq_input for frequency parsing"
