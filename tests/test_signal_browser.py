"""Tests for core/signal_browser.py — pure presenter for SIG-BROWSER."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _sig(**kw):
    from core.signal_model import Signal
    return Signal(**kw)


class TestColumns:
    def test_columns_stable(self):
        from core.signal_browser import COLUMNS, format_row
        s = _sig(freq_hz=14_074_000, source="ft8")
        assert len(format_row(s)) == len(COLUMNS)


class TestFreqFormat:
    def test_mhz(self):
        from core.signal_browser import format_freq_mhz
        assert "14.074" in format_freq_mhz(14_074_000)

    def test_zero_safe(self):
        from core.signal_browser import format_freq_mhz
        assert format_freq_mhz(0)  # no exception, non-empty


class TestShortTime:
    def test_iso_shortened(self):
        from core.signal_browser import _short_time
        assert _short_time("2026-06-21T14:32:00Z") == "06-21 14:32"

    def test_passthrough_on_odd(self):
        from core.signal_browser import _short_time
        assert _short_time("") == ""
        assert _short_time("garbage") == "garbage"


class TestFormatRow:
    def test_fields_mapped(self):
        from core.signal_browser import format_row
        s = _sig(freq_hz=14_074_000, source="ft8", classification="FT8",
                 emitter_id="W1AW", snr_db=-12.0, count=3,
                 decoded="CQ W1AW", last_seen="2026-06-21T14:32:00Z")
        row = format_row(s)
        assert row[2] == "ft8"
        assert row[3] == "FT8"
        assert row[4] == "W1AW"
        assert row[5] == "-12"          # +.0f of negative → "-12"
        assert row[7] == "3"
        assert row[8] == "CQ W1AW"

    def test_blank_measurements(self):
        from core.signal_browser import format_row
        s = _sig(freq_hz=1, source="aprs")   # no snr/rssi
        row = format_row(s)
        assert row[5] == "" and row[6] == ""

    def test_decoded_truncated(self):
        from core.signal_browser import format_row
        s = _sig(freq_hz=1, source="a", decoded="x" * 200)
        assert len(format_row(s)[8]) == 80

    def test_positive_snr_has_plus(self):
        from core.signal_browser import format_row
        s = _sig(freq_hz=1, source="rbn", snr_db=18.0)
        assert format_row(s)[5] == "+18"


class TestTextMatch:
    def test_empty_matches_all(self):
        from core.signal_browser import text_match
        assert text_match(_sig(freq_hz=1, source="a"), "")

    def test_matches_emitter(self):
        from core.signal_browser import text_match
        s = _sig(freq_hz=1, source="ft8", emitter_id="W1AW")
        assert text_match(s, "w1aw")
        assert not text_match(s, "k9xyz")

    def test_matches_decoded(self):
        from core.signal_browser import text_match
        s = _sig(freq_hz=1, source="aprs", decoded="EM73 grid")
        assert text_match(s, "em73")

    def test_matches_freq_text(self):
        from core.signal_browser import text_match
        s = _sig(freq_hz=14_074_000, source="ft8")
        assert text_match(s, "14.074")

    def test_matches_classification_and_source(self):
        from core.signal_browser import text_match
        s = _sig(freq_hz=1, source="wspr", classification="WSPR")
        assert text_match(s, "wspr")


class TestFilter:
    def test_filter_preserves_order(self):
        from core.signal_browser import filter_signals
        sigs = [_sig(freq_hz=1, source="ft8", emitter_id="A"),
                _sig(freq_hz=2, source="aprs", emitter_id="B"),
                _sig(freq_hz=3, source="ft8", emitter_id="C")]
        out = filter_signals(sigs, "ft8")
        assert [s.emitter_id for s in out] == ["A", "C"]


class TestSummary:
    def _sigs(self):
        return [
            _sig(freq_hz=1, source="aprs", emitter_id="A"),
            _sig(freq_hz=2, source="aprs", emitter_id="B"),
            _sig(freq_hz=3, source="ft8", emitter_id="A"),
            _sig(freq_hz=4, source="sdr"),
        ]

    def test_totals(self):
        from core.signal_browser import summarize
        s = summarize(self._sigs())
        assert s["total"] == 4
        assert s["by_source"]["aprs"] == 2
        assert s["by_source"]["ft8"] == 1
        assert s["distinct_emitters"] == 2   # A, B (A counted once)

    def test_by_source_sorted_desc(self):
        from core.signal_browser import summarize
        assert list(summarize(self._sigs())["by_source"])[0] == "aprs"

    def test_summary_line(self):
        from core.signal_browser import summary_line
        line = summary_line(self._sigs())
        assert "Signals: 4" in line
        assert "aprs 2" in line
        assert "emitters: 2" in line

    def test_summary_line_empty(self):
        from core.signal_browser import summary_line
        line = summary_line([])
        assert "Signals: 0" in line
