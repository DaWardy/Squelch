# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/survey_alert.AlertMonitor — the live-alert decision layer for
the survey/hound workflow (ROADMAP §13.3)."""

from dataclasses import dataclass

from core.survey_alert import AlertMonitor, Alert, SOI
from core.rf_baseline import BaselineDiff, SignalDelta


@dataclass
class _Sig:
    freq_hz: int
    rssi_dbm: float = -40.0
    classification: str = "occupied"


@dataclass
class _Det:
    signal: _Sig
    interest: str = "other"


def _soi(freq, peak=-40.0, label="target"):
    return _Det(_Sig(freq, peak, label), interest=SOI)


def _other(freq, peak=-40.0, label="occupied"):
    return _Det(_Sig(freq, peak, label), interest="other")


# ── SOI trigger ──────────────────────────────────────────────────────────────
def test_soi_detection_fires():
    m = AlertMonitor()
    alerts = m.offer_detections([_soi(146_520_000)], t=0.0)
    assert len(alerts) == 1
    assert alerts[0].kind == "soi"
    assert alerts[0].freq_hz == 146_520_000


def test_non_soi_does_not_fire_by_default():
    m = AlertMonitor()                       # on_novel False by default
    assert m.offer_detections([_other(146_520_000)], t=0.0) == []


def test_soi_disabled():
    m = AlertMonitor(on_soi=False)
    assert m.offer_detections([_soi(146_520_000)], t=0.0) == []


# ── novelty trigger ──────────────────────────────────────────────────────────
def test_novel_fires_once_when_enabled():
    m = AlertMonitor(on_novel=True, cooldown_s=60.0)
    a1 = m.offer_detections([_other(100_000_000)], t=0.0)
    assert len(a1) == 1 and a1[0].kind == "novel"
    # same bucket again within cooldown → no repeat
    a2 = m.offer_detections([_other(100_000_000)], t=1.0)
    assert a2 == []


# ── debounce ─────────────────────────────────────────────────────────────────
def test_debounce_within_cooldown():
    m = AlertMonitor(cooldown_s=60.0)
    assert m.offer_detections([_soi(146_520_000)], t=0.0)     # fires
    assert m.offer_detections([_soi(146_520_000)], t=30.0) == []   # too soon
    assert m.offer_detections([_soi(146_520_000)], t=61.0)     # cooldown passed


def test_distinct_frequencies_each_fire():
    m = AlertMonitor()
    alerts = m.offer_detections(
        [_soi(146_520_000), _soi(446_000_000)], t=0.0)
    assert len(alerts) == 2


# ── threshold gate ───────────────────────────────────────────────────────────
def test_min_peak_gate():
    m = AlertMonitor(min_peak_db=-50.0)
    assert m.offer_detections([_soi(146_520_000, peak=-70.0)], t=0.0) == []
    assert m.offer_detections([_soi(146_520_000, peak=-30.0)], t=0.0)


# ── anomaly (baseline compare) ───────────────────────────────────────────────
def _diff_with_new(freq, peak=-40.0, label="new sig"):
    return BaselineDiff(new=[SignalDelta(
        kind="new", center_hz=freq, bandwidth_hz=2500, peak_db=peak,
        ref_peak_db=0.0, delta_db=peak, label=label, category="")])


def test_anomaly_fires_from_diff():
    m = AlertMonitor()
    alerts = m.offer_diff(_diff_with_new(150_000_000), t=0.0)
    assert len(alerts) == 1 and alerts[0].kind == "anomaly"


def test_anomaly_disabled():
    m = AlertMonitor(on_anomaly=False)
    assert m.offer_diff(_diff_with_new(150_000_000), t=0.0) == []


def test_offer_diff_none_safe():
    assert AlertMonitor().offer_diff(None, t=0.0) == []


# ── reset + robustness ───────────────────────────────────────────────────────
def test_reset_clears_history():
    m = AlertMonitor()
    m.offer_detections([_soi(146_520_000)], t=0.0)
    m.reset()
    # after reset, same signal fires again immediately
    assert m.offer_detections([_soi(146_520_000)], t=0.5)


def test_never_raises_on_garbage():
    m = AlertMonitor()
    assert m.offer_detections([object(), None], t=0.0) == []
    assert m.offer_detections(None, t=0.0) == []


def test_alert_freq_mhz():
    a = Alert(kind="soi", freq_hz=146_520_000, peak_db=-40.0,
              label="x", message="y")
    assert a.freq_mhz == 146.52


# ── from_cfg ─────────────────────────────────────────────────────────────────
def test_from_cfg_defaults(tmp_path):
    from core.config import Config
    from pathlib import Path
    m = AlertMonitor.from_cfg(Config(Path(tmp_path) / "c.json"))
    assert m.on_soi is True and m.on_anomaly is True and m.on_novel is False


def test_from_cfg_overrides(tmp_path):
    from core.config import Config
    from pathlib import Path
    cfg = Config(Path(tmp_path) / "c.json")
    cfg.set("survey.alert.on_novel", True)
    cfg.set("survey.alert.cooldown_s", 5)
    cfg.set("survey.alert.min_peak_db", -55)
    m = AlertMonitor.from_cfg(cfg)
    assert m.on_novel is True and m.cooldown_s == 5.0 and m.min_peak_db == -55.0
