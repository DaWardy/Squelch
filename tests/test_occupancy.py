"""Tests for core/occupancy.py — spectrum occupancy detection (SIG-SURVEY)."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── noise floor ──────────────────────────────────────────────────────────────


class TestNoiseFloor:
    def test_percentile_floor(self):
        from core.occupancy import estimate_noise_floor
        powers = [-100] * 9 + [-20]   # one loud bin
        # 25th percentile should sit in the quiet baseline
        assert estimate_noise_floor(powers) == -100

    def test_empty(self):
        from core.occupancy import estimate_noise_floor
        assert estimate_noise_floor([]) == 0.0

    def test_floor_ignores_strong_bins(self):
        from core.occupancy import estimate_noise_floor
        powers = [-95, -96, -94, -30, -28, -97, -95]
        assert estimate_noise_floor(powers) < -90


# ── segment detection ────────────────────────────────────────────────────────


class TestDetectSegments:
    def _flat(self, n=20, val=-100):
        return [val] * n

    def test_no_signal_empty(self):
        from core.occupancy import detect_segments
        assert detect_segments(self._flat(), 100_000_000, 1000) == []

    def test_single_peak(self):
        from core.occupancy import detect_segments
        p = self._flat()
        p[10] = p[11] = -40          # 2-bin signal
        segs = detect_segments(p, 100_000_000, 1000, threshold_db=6.0)
        assert len(segs) == 1
        s = segs[0]
        assert s.bin_lo == 10 and s.bin_hi == 11
        assert s.bandwidth_hz == 2000

    def test_center_freq_mapping(self):
        from core.occupancy import detect_segments
        p = self._flat()
        p[10] = -40
        # start 100 MHz, 1 kHz bins → bin 10 = 100.010 MHz
        seg = detect_segments(p, 100_000_000, 1000)[0]
        assert seg.center_hz == 100_010_000

    def test_two_separate_segments(self):
        from core.occupancy import detect_segments
        p = self._flat(30)
        p[5] = -40
        p[20] = p[21] = p[22] = -35
        segs = detect_segments(p, 100_000_000, 1000)
        assert len(segs) == 2
        assert segs[0].bin_lo == 5
        assert segs[1].bin_lo == 20 and segs[1].bin_hi == 22

    def test_contiguous_merged(self):
        from core.occupancy import detect_segments
        p = self._flat()
        for i in range(8, 13):
            p[i] = -30
        segs = detect_segments(p, 100_000_000, 1000)
        assert len(segs) == 1
        assert segs[0].bin_hi - segs[0].bin_lo + 1 == 5

    def test_min_width_filter(self):
        from core.occupancy import detect_segments
        p = self._flat()
        p[10] = -40                  # 1-bin signal
        segs = detect_segments(p, 100_000_000, 1000, min_width_bins=2)
        assert segs == []

    def test_snr_computed(self):
        from core.occupancy import detect_segments
        p = self._flat(val=-100)
        p[10] = -40
        seg = detect_segments(p, 100_000_000, 1000)[0]
        assert seg.peak_db == -40
        assert seg.floor_db == -100
        assert seg.snr_db == 60

    def test_explicit_floor(self):
        from core.occupancy import detect_segments
        p = self._flat(val=-50)
        p[10] = -20
        # With floor forced low and threshold modest, the -50 baseline is "occupied"
        segs = detect_segments(p, 100_000_000, 1000,
                               floor_db=-100, threshold_db=6.0)
        assert len(segs) == 1
        assert segs[0].bin_lo == 0 and segs[0].bin_hi == len(p) - 1

    def test_segment_at_end_closed(self):
        from core.occupancy import detect_segments
        p = self._flat()
        p[-1] = p[-2] = -40          # run touches the last bin
        segs = detect_segments(p, 100_000_000, 1000)
        assert len(segs) == 1
        assert segs[0].bin_hi == len(p) - 1

    def test_zero_bin_hz_safe(self):
        from core.occupancy import detect_segments
        assert detect_segments([-40, -40], 100_000_000, 0) == []


# ── occupancy fraction ───────────────────────────────────────────────────────


class TestOccupancyFraction:
    def test_half_occupied(self):
        from core.occupancy import occupancy_fraction
        p = [-100, -100, -30, -30]   # floor ~-100, two loud
        frac = occupancy_fraction(p, threshold_db=6.0)
        assert frac == 0.5

    def test_empty(self):
        from core.occupancy import occupancy_fraction
        assert occupancy_fraction([]) == 0.0

    def test_quiet_band_zero(self):
        from core.occupancy import occupancy_fraction
        assert occupancy_fraction([-100, -101, -99, -100]) == 0.0


# ── feed into Signal store ───────────────────────────────────────────────────


class TestSurveyIngest:
    def test_signal_from_occupancy(self):
        from core.occupancy import detect_segments
        from core.signal_ingest import signal_from_occupancy
        p = [-100] * 20
        p[10] = -40
        seg = detect_segments(p, 100_000_000, 1000)[0]
        s = signal_from_occupancy(seg)
        assert s.source == "survey"
        assert s.classification == "occupied"
        assert s.freq_hz == 100_010_000
        assert s.rssi_dbm == -40
        assert s.snr_db == 60

    def test_survey_merges_same_channel(self):
        from core.occupancy import detect_segments
        from core.signal_ingest import signal_from_occupancy, ingest
        from core.signal_model import SignalStore
        st = SignalStore(":memory:")
        for _ in range(3):
            p = [-100] * 20
            p[10] = -40
            seg = detect_segments(p, 100_000_000, 1000)[0]
            ingest(signal_from_occupancy(seg), store=st)
        # Same freq + classification + no emitter → merged into one row
        assert st.count_total() == 1
        assert st.recent()[0].count == 3
