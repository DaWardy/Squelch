# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for the SDR live-survey data path (ROADMAP §4.5 I-1).

Two layers:
  * pure-logic — drive `_SDRSurveyMixin` on a minimal fake host (no Qt): the
    engine lifecycle, the throttle, the frame geometry that reaches
    `offer_frame`, snapshot/compare pass-throughs, and a real-engine
    integration frame that must yield a detection.
  * Qt smoke — build the real SDRTab and exercise the toggle + save/restore +
    the plot-timer tick path (skipped when PyQt6 is absent).
"""

import threading
from pathlib import Path

import pytest
import numpy as np

from core.config import Config
from ui.tabs.sdr_survey import _SDRSurveyMixin


# ── helpers ────────────────────────────────────────────────────────────────
def _cfg(tmp_path) -> Config:
    return Config(Path(tmp_path) / "config.json")


def _frame_with_peak(n=1024, floor=-100.0, peak=-40.0, lo=500, hi=525):
    """A flat noise floor with one clearly-occupied block → one detection."""
    a = np.full(n, floor, dtype=float)
    a[lo:hi] = peak
    return a


class _Host(_SDRSurveyMixin):
    """Minimal stand-in for SDRTab providing just the mixin's read contract."""

    def __init__(self, cfg, fft=None, rate=2_400_000, center=100_000_000):
        self.cfg             = cfg
        self._latest_fft     = fft
        self._sample_rate    = rate
        self._center_hz      = center
        self._fft_lock       = threading.Lock()
        self.location_mgr    = None
        self._survey         = None
        self._survey_enabled = False
        self._survey_tick_n  = 0


class _SpyEngine:
    """Records offer_frame calls so we can assert throttle + geometry."""

    def __init__(self):
        self.calls = []
        self.frames_seen = 0

    def offer_frame(self, powers, center, rate, *, lat=0.0, lon=0.0, t=None):
        self.calls.append((len(powers), center, rate, lat, lon))
        self.frames_seen += 1
        return []

    def snapshot(self, label=""):
        return ("snap", label)

    def compare_to(self, reference):
        return ("cmp", reference)

    def reset(self):
        self.calls.clear()


# ── lifecycle ──────────────────────────────────────────────────────────────
def test_toggle_on_builds_engine(tmp_path):
    from core.live_analysis import SurveyEngine
    h = _Host(_cfg(tmp_path))
    assert h._survey is None
    h._on_survey_toggle(True)
    assert h._survey_enabled is True
    assert isinstance(h._survey, SurveyEngine)


def test_toggle_off_keeps_engine(tmp_path):
    """Toggling off preserves the accumulated baseline (engine kept)."""
    h = _Host(_cfg(tmp_path))
    h._on_survey_toggle(True)
    eng = h._survey
    h._on_survey_toggle(False)
    assert h._survey_enabled is False
    assert h._survey is eng           # not torn down


def test_toggle_reenable_reuses_same_engine(tmp_path):
    h = _Host(_cfg(tmp_path))
    h._on_survey_toggle(True)
    eng = h._survey
    h._on_survey_toggle(False)
    h._on_survey_toggle(True)
    assert h._survey is eng           # same sweep continues


# ── throttle + geometry ─────────────────────────────────────────────────────
def test_tick_noop_when_disabled(tmp_path):
    h = _Host(_cfg(tmp_path), fft=_frame_with_peak())
    h._survey = _SpyEngine()
    h._survey_enabled = False
    for _ in range(50):
        h._survey_tick()
    assert h._survey.frames_seen == 0


def test_throttle_offers_every_stride(tmp_path):
    h = _Host(_cfg(tmp_path), fft=_frame_with_peak())
    spy = h._survey = _SpyEngine()
    h._survey_enabled = True
    stride = _SDRSurveyMixin._SURVEY_STRIDE
    # stride-1 ticks → nothing offered yet
    for _ in range(stride - 1):
        h._survey_tick()
    assert spy.frames_seen == 0
    # the stride-th tick offers exactly one frame
    h._survey_tick()
    assert spy.frames_seen == 1
    # another full stride → one more
    for _ in range(stride):
        h._survey_tick()
    assert spy.frames_seen == 2


def test_tick_passes_frame_geometry(tmp_path):
    fft = _frame_with_peak(n=2048)
    h = _Host(_cfg(tmp_path), fft=fft, rate=2_048_000, center=144_500_000)
    spy = h._survey = _SpyEngine()
    h._survey_enabled = True
    for _ in range(_SDRSurveyMixin._SURVEY_STRIDE):
        h._survey_tick()
    assert spy.calls, "a frame should have been offered"
    n_bins, center, rate, _lat, _lon = spy.calls[0]
    assert n_bins == 2048
    assert center == 144_500_000
    assert rate == 2_048_000


def test_tick_noop_without_frame(tmp_path):
    h = _Host(_cfg(tmp_path), fft=None)
    spy = h._survey = _SpyEngine()
    h._survey_enabled = True
    for _ in range(50):
        h._survey_tick()
    assert spy.frames_seen == 0


def test_latlon_from_location_manager(tmp_path):
    class _Loc:
        lat, lon = 38.75, -77.47

    class _LM:
        location = _Loc()

    h = _Host(_cfg(tmp_path))
    h.location_mgr = _LM()
    assert h._survey_latlon() == (38.75, -77.47)


def test_latlon_defaults_zero_when_unknown(tmp_path):
    h = _Host(_cfg(tmp_path))
    assert h._survey_latlon() == (0.0, 0.0)


# ── pass-throughs ────────────────────────────────────────────────────────────
def test_snapshot_compare_none_without_engine(tmp_path):
    h = _Host(_cfg(tmp_path))
    assert h.survey_snapshot() is None
    assert h.survey_compare(object()) is None
    h.survey_reset()                  # must not raise with no engine


def test_build_sigid_db_identifies_known_signal(tmp_path):
    """The survey wires a signal-ID database so detections can be identified."""
    h = _Host(_cfg(tmp_path))
    db = h._build_sigid_db()
    assert db is not None
    # a builtin factual allocation (NOAA weather radio) resolves
    assert db.identify(162_550_000, 15_000, "FM")


def test_survey_engine_has_sigid(tmp_path):
    h = _Host(_cfg(tmp_path))
    h._on_survey_toggle(True)
    assert h._survey._sigid_db is not None      # enrichment enabled


def test_snapshot_compare_delegate_to_engine(tmp_path):
    h = _Host(_cfg(tmp_path))
    h._survey = _SpyEngine()
    assert h.survey_snapshot("A") == ("snap", "A")
    ref = object()
    assert h.survey_compare(ref) == ("cmp", ref)


# ── real-engine integration: a peak frame must produce a detection ───────────
def test_real_engine_detects_peak(tmp_path):
    from core.live_analysis import SurveyEngine
    h = _Host(_cfg(tmp_path), fft=_frame_with_peak(),
              rate=2_400_000, center=100_000_000)
    # bind a real engine with NO store (ingest independent of the singleton)
    h._survey = SurveyEngine(store=None, ingest=False)
    h._survey_enabled = True
    for _ in range(_SDRSurveyMixin._SURVEY_STRIDE):
        h._survey_tick()
    assert h._survey.frames_seen == 1
    assert h._survey.last_detections, "the -40 dB peak should be detected"
    # a baseline accumulated → snapshot works and compare returns a diff
    snap = h.survey_snapshot("ref")
    assert snap is not None
    diff = h.survey_compare(snap)
    assert diff is not None


# ── saved-baseline library via the tab methods ──────────────────────────────
def _host_with_baselines(tmp_path):
    """A host whose survey store points at a temp dir (never the real
    %APPDATA%/Squelch/baselines — see the session's data-isolation lessons)."""
    cfg = _cfg(tmp_path)
    cfg.set("paths.baselines", str(tmp_path / "baselines"))
    return _Host(cfg, fft=_frame_with_peak(), rate=2_400_000,
                 center=100_000_000)


def _accumulate(host, n=None):
    from core.live_analysis import SurveyEngine
    host._survey = SurveyEngine(store=None, ingest=False)
    host._survey_enabled = True
    for _ in range(n or _SDRSurveyMixin._SURVEY_STRIDE):
        host._survey_tick()


def test_save_baseline_none_without_data(tmp_path):
    h = _host_with_baselines(tmp_path)
    assert h.survey_save_baseline("x") is None      # no engine/data yet


def test_save_and_list_baseline(tmp_path):
    h = _host_with_baselines(tmp_path)
    _accumulate(h)
    entry = h.survey_save_baseline("kitchen")
    assert entry is not None and entry.label == "kitchen"
    rows = h.survey_saved_baselines()
    assert [e.label for e in rows] == ["kitchen"]


def test_compare_saved_against_live(tmp_path):
    h = _host_with_baselines(tmp_path)
    _accumulate(h)
    ref = h.survey_save_baseline("ref")
    # keep sweeping — live baseline still matches the saved ref (no new signals)
    for _ in range(_SDRSurveyMixin._SURVEY_STRIDE):
        h._survey_tick()
    diff = h.survey_compare_saved(ref.id)
    assert diff is not None
    assert diff.anomaly_count == 0                   # nothing new appeared


def test_compare_saved_unknown_id(tmp_path):
    h = _host_with_baselines(tmp_path)
    _accumulate(h)
    assert h.survey_compare_saved("no-such-id") is None


def test_export_report_writes_file(tmp_path):
    h = _host_with_baselines(tmp_path)
    _accumulate(h)
    diff = h.survey_compare(h.survey_snapshot())      # self-diff (0 anomalies)
    out = h.survey_export_report(tmp_path / "sweep.html", diff, fmt="html")
    assert out is not None and Path(out).exists()
    assert "<!doctype html>" in Path(out).read_text(encoding="utf-8")


def test_export_report_none_diff(tmp_path):
    h = _host_with_baselines(tmp_path)
    assert h.survey_export_report(tmp_path / "x.html", None) is None


# ── live alerts via the tab ──────────────────────────────────────────────────
def test_toggle_builds_alert_monitor(tmp_path):
    h = _Host(_cfg(tmp_path))
    h._survey_alerts = []
    h._alert_monitor = None
    h._on_survey_toggle(True)
    from core.survey_alert import AlertMonitor
    assert isinstance(h._alert_monitor, AlertMonitor)


def test_run_alerts_collects_soi(tmp_path):
    from dataclasses import dataclass
    from core.survey_alert import AlertMonitor, SOI

    @dataclass
    class _Sig:
        freq_hz: int
        rssi_dbm: float = -30.0
        classification: str = "target"

    @dataclass
    class _Det:
        signal: _Sig
        interest: str = SOI

    h = _Host(_cfg(tmp_path))
    h._survey_alerts = []
    h._alert_monitor = AlertMonitor()
    h._survey_run_alerts([_Det(_Sig(146_520_000))])
    assert len(h._survey_alerts) == 1
    assert h.survey_recent_alerts()[-1].kind == "soi"


def test_run_alerts_noop_without_monitor(tmp_path):
    h = _Host(_cfg(tmp_path))
    h._survey_alerts = []
    h._alert_monitor = None
    h._survey_run_alerts([object()])          # must not raise
    assert h._survey_alerts == []


# ── Qt smoke (skipped without PyQt6) ─────────────────────────────────────────
try:
    import PyQt6  # noqa: F401
    HAS_QT = True
except ImportError:
    HAS_QT = False


@pytest.fixture(scope="module")
def qt_app():
    import sys
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


def _make_sdr_tab(tmp_path):
    from unittest.mock import MagicMock
    from ui.tabs.sdr_tab import SDRTab
    cfg = Config(Path(tmp_path) / "config.json")
    rig = MagicMock()
    rig.is_connected = False
    rig.state = MagicMock()
    return SDRTab(cfg, rig)


@pytest.mark.skipif(not HAS_QT, reason="PyQt6 not installed")
class TestSurveyQt:
    def test_toggle_button_enables_survey(self, qt_app, tmp_path):
        tab = _make_sdr_tab(tmp_path)
        assert tab._survey_enabled is False
        if not hasattr(tab, "_survey_btn"):
            pytest.skip("toolbar not built (no-Soapy/no-pyqtgraph fallback)")
        tab._survey_btn.setChecked(True)
        assert tab._survey_enabled is True
        assert tab._survey is not None

    def test_state_round_trip(self, qt_app, tmp_path):
        tab = _make_sdr_tab(tmp_path)
        if not hasattr(tab, "_survey_btn"):
            pytest.skip("toolbar not built")
        tab._survey_btn.setChecked(True)
        st = tab.save_state()
        assert st.get("survey_enabled") is True
        tab2 = _make_sdr_tab(tmp_path)
        tab2.restore_state({"survey_enabled": True})
        assert tab2._survey_enabled is True

    def test_update_plots_runs_survey_tick(self, qt_app, tmp_path):
        """With survey on and a frame present, the plot timer pumps safely."""
        tab = _make_sdr_tab(tmp_path)
        if not hasattr(tab, "_survey_btn"):
            pytest.skip("toolbar not built")
        tab._survey_btn.setChecked(True)
        tab._latest_fft = _frame_with_peak()
        tab._sample_rate = 2_400_000
        tab._center_hz = 100_000_000
        for _ in range(_SDRSurveyMixin._SURVEY_STRIDE):
            tab._update_plots()          # must not raise
        assert tab._survey.frames_seen >= 1
