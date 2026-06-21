"""Tests for core/signal_classify.py — allocation-based ID (ID-CLASSIFY)."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _sig(**kw):
    from core.signal_model import Signal
    return Signal(**kw)


# ── classify_by_allocation ───────────────────────────────────────────────────


class TestKnownFrequencies:
    def test_noaa_weather(self):
        from core.signal_classify import classify_by_allocation
        c = classify_by_allocation(162_550_000)
        assert c.label == "NOAA WX-7"
        assert c.category == "Weather"
        assert c.modulation == "FM"
        assert c.confidence >= 0.9
        assert c.is_known

    def test_aviation_guard(self):
        from core.signal_classify import classify_by_allocation
        c = classify_by_allocation(121_500_000)
        assert "GUARD" in c.label
        assert c.modulation == "AM"

    def test_near_known_within_tolerance(self):
        from core.signal_classify import classify_by_allocation
        # 2 kHz off the NOAA channel still matches
        c = classify_by_allocation(162_552_000)
        assert c.label == "NOAA WX-7"

    def test_outside_tolerance_not_known(self):
        from core.signal_classify import classify_by_allocation
        # 20 kHz off — should not match the fixed channel
        c = classify_by_allocation(162_570_000, known_tol_hz=6000)
        assert c.label != "NOAA WX-7"


class TestAmateur:
    def test_20m_digital(self):
        from core.signal_classify import classify_by_allocation
        c = classify_by_allocation(14_074_000)
        assert c.category == "Amateur"
        assert c.label.startswith("20m")
        assert c.modulation == "PKTUSB"

    def test_2m_simplex_fm(self):
        from core.signal_classify import classify_by_allocation
        c = classify_by_allocation(146_520_000)
        assert c.category == "Amateur"
        assert c.label.startswith("2m")
        assert c.modulation == "FM"


class TestServiceBands:
    def test_frs_gmrs(self):
        from core.signal_classify import classify_by_allocation
        c = classify_by_allocation(462_562_500)
        assert c.category == "FRS/GMRS"
        assert c.modulation == "FM"
        assert c.confidence == 0.5

    def test_cb(self):
        from core.signal_classify import classify_by_allocation
        c = classify_by_allocation(27_185_000)
        assert c.category == "CB"
        assert c.modulation == "AM"

    def test_murs(self):
        from core.signal_classify import classify_by_allocation
        c = classify_by_allocation(151_940_000)
        assert c.category == "MURS"

    def test_amateur_takes_precedence_over_overlapping_ism(self):
        from core.signal_classify import classify_by_allocation
        # 433.92 MHz is ISM but also inside 70cm amateur — amateur wins
        c = classify_by_allocation(433_920_000)
        assert c.category == "Amateur"


class TestUnknownAndEdge:
    def test_unknown_hf(self):
        from core.signal_classify import classify_by_allocation
        c = classify_by_allocation(2_500_000)
        assert c.label == "" and c.confidence == 0.0
        assert not c.is_known

    def test_zero_freq(self):
        from core.signal_classify import classify_by_allocation
        c = classify_by_allocation(0)
        assert c.label == ""


# ── apply_classification ─────────────────────────────────────────────────────


class TestApplyClassification:
    def test_enriches_generic_occupied(self):
        from core.signal_classify import apply_classification
        s = _sig(freq_hz=162_550_000, source="survey",
                 classification="occupied")
        apply_classification(s)
        assert s.classification == "NOAA WX-7"
        assert s.modulation == "FM"

    def test_does_not_overwrite_specific(self):
        from core.signal_classify import apply_classification
        s = _sig(freq_hz=162_550_000, source="ft8", classification="FT8")
        apply_classification(s)
        assert s.classification == "FT8"     # left alone

    def test_keeps_existing_modulation(self):
        from core.signal_classify import apply_classification
        s = _sig(freq_hz=162_550_000, source="survey",
                 classification="occupied", modulation="NFM")
        apply_classification(s)
        assert s.classification == "NOAA WX-7"
        assert s.modulation == "NFM"          # not overwritten

    def test_unknown_freq_leaves_generic(self):
        from core.signal_classify import apply_classification
        s = _sig(freq_hz=2_500_000, source="survey", classification="occupied")
        apply_classification(s)
        assert s.classification == "occupied"

    def test_returns_signal_for_chaining(self):
        from core.signal_classify import apply_classification
        s = _sig(freq_hz=1, source="survey", classification="occupied")
        assert apply_classification(s) is s

    def test_never_raises(self):
        from core.signal_classify import apply_classification
        # Bad object — must be swallowed
        apply_classification(object())
