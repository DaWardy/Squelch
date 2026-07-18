# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/signal_history.SignalHistory — band-power-over-time recorder
(ROADMAP §14.3, SDR-Console Signal History parity)."""

from pathlib import Path

import numpy as np

from core.signal_history import SignalHistory, WIDEBAND


def _frame(n=1024, floor=-100.0, peak=-40.0, lo=500, hi=525):
    a = np.full(n, floor, dtype=float)
    a[lo:hi] = peak
    return a


# geometry: 1024 bins, 2.4 MS/s, centred 100 MHz
SR = 2_400_000
START = 100_000_000 - SR // 2
BIN = SR / 1024


# ── wideband ─────────────────────────────────────────────────────────────────
def test_wideband_peak_and_mean():
    h = SignalHistory()
    h.offer_frame(_frame(), START, BIN, t=0.0)
    series = h.series(WIDEBAND)
    assert len(series) == 1
    t, peak, mean = series[0]
    assert peak == -40.0                      # the injected block
    assert -100.0 <= mean < -40.0


def test_accumulates_over_time():
    h = SignalHistory()
    for i in range(5):
        h.offer_frame(_frame(), START, BIN, t=float(i))
    assert len(h.series(WIDEBAND)) == 5
    assert [t for t, _, _ in h.series(WIDEBAND)] == [0.0, 1.0, 2.0, 3.0, 4.0]


# ── channels ─────────────────────────────────────────────────────────────────
def test_channel_band_power():
    h = SignalHistory(track_wideband=False)
    # the peak block is at bins 500..524 → that frequency window
    lo_hz = int(START + 500 * BIN)
    hi_hz = int(START + 524 * BIN)
    h.add_channel("target", lo_hz, hi_hz)
    h.offer_frame(_frame(), START, BIN, t=0.0)
    series = h.series("target")
    assert len(series) == 1
    assert series[0][1] == -40.0              # peak inside the occupied block


def test_channel_outside_frame_skipped():
    h = SignalHistory(track_wideband=False)
    h.add_channel("elsewhere", 400_000_000, 400_100_000)   # not in this frame
    h.offer_frame(_frame(), START, BIN, t=0.0)
    assert h.series("elsewhere") == []


def test_add_channel_updates_existing():
    h = SignalHistory()
    h.add_channel("a", 1, 2)
    h.add_channel("a", 10, 20)
    assert len(h.channels) == 1
    assert h.channels[0].lo_hz == 10 and h.channels[0].hi_hz == 20


# ── rolling caps ─────────────────────────────────────────────────────────────
def test_count_cap():
    h = SignalHistory(max_samples=3)
    for i in range(10):
        h.offer_frame(_frame(), START, BIN, t=float(i))
    assert h.sample_count == 3
    # only the newest 3 timestamps survive
    assert [t for t, _, _ in h.series(WIDEBAND)] == [7.0, 8.0, 9.0]


def test_age_cap():
    h = SignalHistory(max_age_s=5.0)
    for i in range(10):
        h.offer_frame(_frame(), START, BIN, t=float(i))     # t=0..9
    ts = [t for t, _, _ in h.series(WIDEBAND)]
    assert min(ts) >= 4.0                     # older than now(9) - 5 pruned


# ── query + reset ────────────────────────────────────────────────────────────
def test_window_query():
    h = SignalHistory()
    for i in range(10):
        h.offer_frame(_frame(), START, BIN, t=float(i))
    win = h.window(3.0, 6.0)
    assert {s.t for s in win} == {3.0, 4.0, 5.0, 6.0}


def test_reset():
    h = SignalHistory()
    h.offer_frame(_frame(), START, BIN, t=0.0)
    h.reset()
    assert h.sample_count == 0


# ── robustness ───────────────────────────────────────────────────────────────
def test_bad_frame_safe():
    h = SignalHistory()
    assert h.offer_frame([], START, BIN, t=0.0) == 0
    assert h.offer_frame(_frame(), START, 0.0, t=0.0) == 0     # bin_hz<=0
    assert h.sample_count == 0


# ── CSV export ───────────────────────────────────────────────────────────────
def test_csv_export(tmp_path):
    h = SignalHistory()
    h.add_channel("ch1", int(START + 500 * BIN), int(START + 524 * BIN))
    h.offer_frame(_frame(), START, BIN, t=1.5)
    out = tmp_path / "hist.csv"
    assert h.export_csv(out) is True
    text = out.read_text(encoding="utf-8")
    assert text.startswith("time_s,channel,peak_db,mean_db")
    assert "wideband" in text and "ch1" in text
    assert "1.500" in text


def test_csv_formula_injection_safe():
    h = SignalHistory(track_wideband=False)
    h.add_channel("=cmd()", int(START + 500 * BIN), int(START + 524 * BIN))
    h.offer_frame(_frame(), START, BIN, t=0.0)
    csv = h.to_csv()
    # csv_safe prefixes a single quote so the cell can't execute as a formula
    assert ",'=cmd()," in csv                  # field neutralised
    assert "\n=cmd()" not in csv               # never a bare formula cell


# ── tab wiring (fake host, no Qt) ────────────────────────────────────────────
def test_tab_history_wiring():
    from core.config import Config
    from ui.tabs.sdr_survey import _SDRSurveyMixin

    class _Host(_SDRSurveyMixin):
        def __init__(self, cfg):
            import threading
            self.cfg = cfg
            self._sample_rate = SR
            self._center_hz = 100_000_000
            self._latest_fft = _frame()
            self._fft_lock = threading.Lock()
            self.location_mgr = None
            self._survey = None
            self._survey_enabled = False
            self._survey_tick_n = 0
            self._alert_monitor = None
            self._survey_alerts = []
            self._signal_history = None

    import tempfile
    cfg = Config(Path(tempfile.mkdtemp()) / "c.json")
    h = _Host(cfg)
    h._on_survey_toggle(True)
    assert h._signal_history is not None
    for _ in range(_SDRSurveyMixin._SURVEY_STRIDE):
        h._survey_tick()
    assert "wideband" in h.survey_history_channels()
    assert len(h.survey_history_series("wideband")) >= 1
