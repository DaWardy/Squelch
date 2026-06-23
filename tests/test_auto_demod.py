"""Tests for core/auto_demod.py — auto demod/bandwidth by frequency."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

_BW_COMBO = ["200 Hz", "500 Hz", "1 kHz", "2.5 kHz",
             "5 kHz", "10 kHz", "15 kHz", "200 kHz"]


class TestBroadcastAndAirband:
    def test_fm_broadcast_wfm(self):
        from core.auto_demod import suggest_demod
        s = suggest_demod(98_500_000)
        assert s.mode == "WFM"
        assert s.bandwidth_hz == 200_000
        assert "FM Broadcast" in s.label

    def test_airband_am(self):
        from core.auto_demod import suggest_demod
        s = suggest_demod(124_000_000)
        assert s.mode == "AM"
        assert s.label == "Airband"

    def test_am_broadcast(self):
        from core.auto_demod import suggest_demod
        s = suggest_demod(1_010_000)
        assert s.mode == "AM"
        assert "AM Broadcast" in s.label

    def test_shortwave_broadcast_am(self):
        from core.auto_demod import suggest_demod
        s = suggest_demod(9_500_000)
        assert s.mode == "AM"
        assert "Shortwave" in s.label


class TestAmateur:
    def test_20m_ssb_usb(self):
        from core.auto_demod import suggest_demod
        s = suggest_demod(14_074_000)
        assert s.mode == "USB"

    def test_80m_lsb(self):
        from core.auto_demod import suggest_demod
        s = suggest_demod(3_900_000)
        assert s.mode == "LSB"

    def test_40m_cw_narrow(self):
        from core.auto_demod import suggest_demod
        s = suggest_demod(7_030_000)
        assert s.mode == "CW"
        assert s.bandwidth_hz == 500

    def test_2m_fm_nfm(self):
        from core.auto_demod import suggest_demod
        s = suggest_demod(146_520_000)
        assert s.mode == "NFM"
        assert s.bandwidth_hz == 15_000

    def test_70cm_nfm(self):
        from core.auto_demod import suggest_demod
        assert suggest_demod(446_000_000).mode == "NFM"


class TestSubmode:
    def test_ft8_is_data(self):
        from core.auto_demod import suggest_demod
        s = suggest_demod(14_074_000)
        assert s.mode == "USB"
        assert s.submode == "data"
        assert s.bandwidth_hz == 3_000
        assert "data" in s.label

    def test_ssb_voice(self):
        from core.auto_demod import suggest_demod
        s = suggest_demod(14_230_000)      # 20m SSB voice segment
        assert s.mode == "USB"
        assert s.submode == "voice"
        assert s.bandwidth_hz == 2_500
        assert "voice" in s.label

    def test_lsb_voice_submode(self):
        from core.auto_demod import suggest_demod
        s = suggest_demod(3_900_000)
        assert s.mode == "LSB"
        assert s.submode == "voice"

    def test_fm_has_no_submode(self):
        from core.auto_demod import suggest_demod
        assert suggest_demod(146_520_000).submode == ""

    def test_cw_has_no_submode(self):
        from core.auto_demod import suggest_demod
        assert suggest_demod(7_030_000).submode == ""

    def test_broadcast_no_submode(self):
        from core.auto_demod import suggest_demod
        assert suggest_demod(98_500_000).submode == ""


class TestServiceAndKnown:
    def test_noaa_nfm(self):
        from core.auto_demod import suggest_demod
        s = suggest_demod(162_550_000)
        assert s.mode == "NFM"
        assert "NOAA" in s.label

    def test_cb_am(self):
        from core.auto_demod import suggest_demod
        assert suggest_demod(27_185_000).mode == "AM"

    def test_frs_nfm(self):
        from core.auto_demod import suggest_demod
        assert suggest_demod(462_562_500).mode == "NFM"


class TestFallbacksAndEdge:
    def test_zero_freq(self):
        from core.auto_demod import suggest_demod
        s = suggest_demod(0)
        assert s.mode == "NFM"
        assert s.confidence == 0.0

    def test_unknown_vhf_nfm(self):
        from core.auto_demod import suggest_demod
        # 220 MHz region not in tables → VHF/UHF default NFM
        s = suggest_demod(223_000_000)
        assert s.mode == "NFM"

    def test_mode_always_valid(self):
        from core.auto_demod import suggest_demod
        valid = {"AM", "NFM", "WFM", "USB", "LSB", "CW"}
        for f in (50_000, 500_000, 5_000_000, 50_000_000,
                  150_000_000, 500_000_000, 1_000_000_000):
            assert suggest_demod(f).mode in valid


class TestBwLabelMatching:
    def test_parse_bw_label(self):
        from core.auto_demod import parse_bw_label
        assert parse_bw_label("2.5 kHz") == 2500
        assert parse_bw_label("500 Hz") == 500
        assert parse_bw_label("200 kHz") == 200_000
        assert parse_bw_label("garbage") == 0

    def test_nearest_bw_label(self):
        from core.auto_demod import nearest_bw_label
        assert nearest_bw_label(200_000, _BW_COMBO) == "200 kHz"
        assert nearest_bw_label(500, _BW_COMBO) == "500 Hz"
        assert nearest_bw_label(2_500, _BW_COMBO) == "2.5 kHz"
        # 9 kHz (SW) → nearest available is 10 kHz
        assert nearest_bw_label(9_000, _BW_COMBO) == "10 kHz"
        # 15 kHz NFM exact
        assert nearest_bw_label(15_000, _BW_COMBO) == "15 kHz"

    def test_nearest_handles_empty(self):
        from core.auto_demod import nearest_bw_label
        assert nearest_bw_label(1000, []) == ""

    def test_suggestion_bw_maps_into_combo(self):
        from core.auto_demod import suggest_demod, nearest_bw_label
        # Every suggestion's bw should map to a real combo entry
        for f in (98_500_000, 124_000_000, 14_074_000, 7_030_000,
                  146_520_000, 1_010_000):
            s = suggest_demod(f)
            assert nearest_bw_label(s.bandwidth_hz, _BW_COMBO) in _BW_COMBO
