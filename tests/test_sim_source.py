# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for sdr/sim_source.SimSource — the synthetic signal generator that lets
the whole SDR stack (waterfall, survey, history, alerts) run with no hardware."""

import time

import numpy as np

from sdr.sim_source import SimSource, SimSignal, default_scene

SR = 2_400_000
FFT = 2048


def _spectrum(iq):
    w = np.hanning(len(iq))
    fft = np.fft.fftshift(np.abs(np.fft.fft(iq * w, FFT)))
    return 20 * np.log10(fft / FFT + 1e-10)


def _bin_for(offset_hz):
    return int(round(FFT * (0.5 + offset_hz / SR)))


def _peak_over_floor(fft_db, offset_hz, half=8):
    b = _bin_for(offset_hz)
    seg = fft_db[max(0, b - half): b + half]
    return float(seg.max()) - float(np.median(fft_db))


# ── generation ───────────────────────────────────────────────────────────────
def test_generate_shape_and_dtype():
    iq = SimSource(sample_rate=SR, seed=1).generate(FFT, 100_000_000, t=0.0)
    assert iq.dtype == np.complex64
    assert len(iq) == FFT


def test_signals_appear_at_offsets():
    fft_db = _spectrum(
        SimSource(sample_rate=SR, seed=2).generate(FFT, 100_000_000, t=0.0))
    for off in (-820_000, -300_000, 150_000, 520_000):
        assert _peak_over_floor(fft_db, off) > 12.0, f"missing signal at {off}"


def test_deterministic_with_seed():
    a = SimSource(sample_rate=SR, seed=7).generate(FFT, 100_000_000, t=0.0)
    b = SimSource(sample_rate=SR, seed=7).generate(FFT, 100_000_000, t=0.0)
    assert np.array_equal(a, b)


def test_intermittent_on_off():
    """The pulsing signal is strong when on, ~noise when off."""
    on = _spectrum(
        SimSource(sample_rate=SR, seed=3).generate(FFT, 100_000_000, t=0.0))
    off = _spectrum(
        SimSource(sample_rate=SR, seed=3).generate(FFT, 100_000_000, t=5.0))
    on_peak = _peak_over_floor(on, 780_000)
    off_peak = _peak_over_floor(off, 780_000)
    assert on_peak > 20.0
    assert off_peak < 12.0
    assert on_peak - off_peak > 10.0


def test_offset_outside_window_skipped():
    """A signal beyond ±sample_rate/2 doesn't blow up (just absent)."""
    s = SimSource(sample_rate=SR, seed=1,
                  scene=[SimSignal(5_000_000, power_db=40)])   # way out of band
    iq = s.generate(FFT, 100_000_000, t=0.0)
    assert np.all(np.isfinite(iq.view(np.float32)))


def test_is_on_duty_cycle():
    sig = SimSignal(0, period_s=10.0, duty=0.3)
    assert sig.is_on(0.0) is True
    assert sig.is_on(2.9) is True
    assert sig.is_on(3.1) is False
    assert sig.is_on(10.0) is True            # wraps


def test_default_scene_has_intermittent():
    assert any(s.period_s > 0 for s in default_scene())


# ── survey integration: the sim feeds real detections ────────────────────────
def test_survey_detects_sim_signals():
    from core.live_analysis import SurveyEngine
    fft_db = _spectrum(
        SimSource(sample_rate=SR, seed=4).generate(FFT, 100_000_000, t=0.0))
    eng = SurveyEngine(store=None, ingest=False)
    dets = eng.offer_frame(fft_db, 100_000_000, SR)
    assert len(dets) >= 2                      # the strong steady signals


# ── streaming thread ─────────────────────────────────────────────────────────
def test_stream_delivers_frames():
    got = []
    s = SimSource(sample_rate=SR, seed=5)
    s.on_samples(lambda iq, sr, c: got.append((iq, sr, c)))
    s.start()
    t0 = time.time()
    while len(got) < 2 and time.time() - t0 < 3.0:
        time.sleep(0.02)
    s.stop()
    assert len(got) >= 1
    iq, sr, c = got[0]
    assert iq.dtype == np.complex64 and sr == SR


def test_stream_uses_live_center():
    """The generator reads the current centre each frame (tuning follows)."""
    seen = []
    s = SimSource(sample_rate=SR, seed=1, get_center=lambda: 144_000_000)
    s.on_samples(lambda iq, sr, c: seen.append(c))
    s.start()
    t0 = time.time()
    while not seen and time.time() - t0 < 3.0:
        time.sleep(0.02)
    s.stop()
    assert seen and seen[0] == 144_000_000


# ── virtual-device wiring in the SDR tab (skipped without PyQt6) ──────────────
try:
    import PyQt6  # noqa: F401
    HAS_QT = True
except ImportError:
    HAS_QT = False

import pytest


@pytest.fixture(scope="module")
def qt_app():
    import sys
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


def _sdr_tab():
    import tempfile
    from pathlib import Path
    from unittest.mock import MagicMock
    from core.config import Config
    from ui.tabs.sdr_tab import SDRTab, HAS_PG
    if not HAS_PG:
        pytest.skip("pyqtgraph not installed")
    cfg = Config(Path(tempfile.mkdtemp()) / "config.json")
    rig = MagicMock(); rig.is_connected = False; rig.state = MagicMock()
    return SDRTab(cfg, rig)


@pytest.mark.skipif(not HAS_QT, reason="PyQt6 not installed")
class TestSimDeviceWiring:
    def test_sim_offered_even_with_no_hardware(self, qt_app):
        from ui.tabs.sdr_device_connect import SIM_DEVICE
        tab = _sdr_tab()
        tab._populate_devices([])                 # simulate zero hardware
        assert SIM_DEVICE in tab._devices
        labels = [tab._dev_combo.itemText(i)
                  for i in range(tab._dev_combo.count())]
        assert any("Simulated" in s for s in labels)

    def test_connect_sim_starts_and_stops(self, qt_app):
        from ui.tabs.sdr_device_connect import SIM_DEVICE
        tab = _sdr_tab()
        tab._populate_devices([])
        idx = tab._devices.index(SIM_DEVICE)
        tab._dev_combo.setCurrentIndex(idx)
        tab._connect_btn.setText("Connect")
        tab._connect_sdr()
        try:
            assert tab._sim_source is not None
            assert tab._sim_source.is_running
            assert tab._connect_btn.text() == "Disconnect"
            # Disconnect stops the source
            tab._connect_sdr()
            assert tab._sim_source.is_running is False
        finally:
            if tab._sim_source is not None:
                tab._sim_source.stop()
