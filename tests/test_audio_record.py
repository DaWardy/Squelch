# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/audio_record — demodulated audio → WAV (ROADMAP §14.7). Lets a
user HEAR a signal via a .wav with no audio hardware or UI."""

import wave
from pathlib import Path

import numpy as np

from core.audio_record import write_wav, AudioRecorder

SR = 240_000
AR = 48_000
OFF = 30_000


def _read_wav(path):
    with wave.open(str(path), "rb") as w:
        n = w.getnframes()
        rate = w.getframerate()
        pcm = np.frombuffer(w.readframes(n), dtype="<i2")
    return pcm.astype(np.float32) / 32767.0, rate


def _dominant_hz(audio, rate):
    if len(audio) < 16:
        return 0.0
    win = np.hanning(len(audio))
    sp = np.abs(np.fft.rfft(audio * win))
    sp[0] = 0
    return float(np.fft.rfftfreq(len(audio), 1 / rate)[np.argmax(sp)])


def _fm_frame(fa, n=24_000):
    t = np.arange(n) / SR
    beta = 5000 / fa
    return np.exp(1j * (2 * np.pi * OFF * t
                        + beta * np.sin(2 * np.pi * fa * t))).astype(np.complex64)


# ── write_wav ────────────────────────────────────────────────────────────────
def test_write_wav_round_trip(tmp_path):
    audio = (0.5 * np.cos(2 * np.pi * 1000 * np.arange(AR) / AR)).astype(np.float32)
    p = tmp_path / "a.wav"
    assert write_wav(p, audio, AR) is True
    back, rate = _read_wav(p)
    assert rate == AR
    assert len(back) == len(audio)
    assert np.allclose(back, audio, atol=1e-3)          # 16-bit quantisation


def test_write_wav_clips_out_of_range(tmp_path):
    p = tmp_path / "clip.wav"
    write_wav(p, np.array([2.0, -2.0, 0.0], dtype=np.float32), AR)
    back, _ = _read_wav(p)
    assert back.max() <= 1.0 and back.min() >= -1.0


# ── AudioRecorder ────────────────────────────────────────────────────────────
def test_recorder_writes_audible_wav(tmp_path):
    """Record an FM signal; the WAV plays back the modulating tone."""
    rec = AudioRecorder(mode="NBFM", offset_hz=OFF, bandwidth_hz=12_500,
                        audio_rate=AR)
    rec.start()
    fa = 2000.0
    for _ in range(4):                                  # several frames
        rec.feed(_fm_frame(fa), SR, 100_000_000)
    assert rec.is_recording is True
    out = rec.stop(tmp_path / "sig.wav")
    assert out is not None and Path(out).exists()
    audio, rate = _read_wav(out)
    assert abs(_dominant_hz(audio, rate) - fa) < 120     # the recovered tone


def test_recorder_duration_tracks_frames(tmp_path):
    rec = AudioRecorder(mode="AM", offset_hz=OFF, bandwidth_hz=10_000, audio_rate=AR)
    rec.start()
    rec.feed(_fm_frame(1000.0), SR, 0)                   # 24000 in-samples → /5
    assert rec.sample_count > 0
    assert rec.duration_s > 0.0


def test_feed_before_start_is_noop(tmp_path):
    rec = AudioRecorder(mode="FM")
    rec.feed(_fm_frame(1000.0), SR, 0)                   # not started
    assert rec.sample_count == 0
    assert rec.stop(tmp_path / "none.wav") is None       # nothing captured


def test_stop_with_no_audio_returns_none(tmp_path):
    rec = AudioRecorder(mode="FM")
    rec.start()
    assert rec.stop(tmp_path / "empty.wav") is None


def test_recorder_auto_notch_option(tmp_path):
    """auto_notch flag runs the notch path without crashing (het removed)."""
    rec = AudioRecorder(mode="AM", offset_hz=OFF, bandwidth_hz=10_000,
                        audio_rate=AR, auto_notch=True)
    rec.start()
    rec.feed(_fm_frame(1500.0), SR, 0)
    out = rec.stop(tmp_path / "notch.wav")
    assert out is not None and Path(out).exists()


# ── tab wiring (skipped without PyQt6) ───────────────────────────────────────
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


@pytest.mark.skipif(not HAS_QT, reason="PyQt6 not installed")
def test_tab_audio_record_button_writes_wav(qt_app, tmp_path):
    import tempfile
    from unittest.mock import MagicMock
    from core.config import Config
    from ui.tabs.sdr_tab import SDRTab, HAS_PG
    if not HAS_PG:
        pytest.skip("pyqtgraph not installed")
    cfg = Config(Path(tempfile.mkdtemp()) / "config.json")
    cfg.set("paths.iq_recordings", str(tmp_path))       # WAV lands here
    rig = MagicMock(); rig.is_connected = False; rig.state = MagicMock()
    tab = SDRTab(cfg, rig)
    if not hasattr(tab, "_audio_rec_btn"):
        pytest.skip("toolbar not built")
    tab._demod_combo.setCurrentText("NFM")
    tab._audio_rec_btn.setChecked(True)                 # → start recording
    assert tab._audio_rec is not None and tab._audio_rec.is_recording
    for _ in range(4):
        tab._audio_rec.feed(_fm_frame(2000.0), SR, 100_000_000)
    tab._audio_rec_btn.setChecked(False)                # → stop + write WAV
    wavs = list(Path(tmp_path).glob("audio_*.wav"))
    assert wavs, "expected an audio_*.wav to be written"


@pytest.mark.skipif(not HAS_QT, reason="PyQt6 not installed")
def test_tab_raw_iq_mode_refuses_audio_record(qt_app, tmp_path):
    import tempfile
    from unittest.mock import MagicMock
    from core.config import Config
    from ui.tabs.sdr_tab import SDRTab, HAS_PG
    if not HAS_PG:
        pytest.skip("pyqtgraph not installed")
    cfg = Config(Path(tempfile.mkdtemp()) / "config.json")
    rig = MagicMock(); rig.is_connected = False; rig.state = MagicMock()
    tab = SDRTab(cfg, rig)
    if not hasattr(tab, "_audio_rec_btn"):
        pytest.skip("toolbar not built")
    tab._demod_combo.setCurrentText("Raw IQ")
    tab._audio_rec_btn.setChecked(True)                 # refused → unchecks
    assert tab._audio_rec is None
    assert tab._audio_rec_btn.isChecked() is False
