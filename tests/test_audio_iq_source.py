"""Tests for sdr/audio_iq_source.py — no hardware required."""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# AudioIQSource unit tests
# ---------------------------------------------------------------------------

def _make_src():
    from sdr.audio_iq_source import AudioIQSource
    return AudioIQSource()


def test_default_state():
    src = _make_src()
    assert src._mode == "mono"
    assert src._sample_rate == 48000
    assert not src.is_running
    assert src._device is None


def test_set_mode_valid():
    src = _make_src()
    src.set_mode("iq_stereo")
    assert src._mode == "iq_stereo"
    src.set_mode("mono")
    assert src._mode == "mono"


def test_set_mode_invalid():
    import pytest
    src = _make_src()
    with pytest.raises(ValueError):
        src.set_mode("quadrature_nine_channel")


def test_set_device_default():
    src = _make_src()
    src.set_device("Default")
    assert src._device is None


def test_set_device_named():
    src = _make_src()
    src.set_device("USB Audio CODEC")
    assert src._device == "USB Audio CODEC"


def test_set_sample_rate():
    src = _make_src()
    src.set_sample_rate(192000)
    assert src._sample_rate == 192000


def test_set_center_hz():
    src = _make_src()
    src.set_center_hz(14_097_000)
    assert src._center_hz == 14_097_000


def test_display_name_mono():
    src = _make_src()
    src.set_device("Test Device")
    name = src.display_name
    assert "Test Device" in name
    assert "Mono" in name


def test_display_name_iq_stereo():
    src = _make_src()
    src.set_device("FUNcube")
    src.set_mode("iq_stereo")
    name = src.display_name
    assert "IQ Stereo" in name


def test_on_samples_property():
    src = _make_src()
    cb = MagicMock()
    src.on_samples = cb
    assert src.on_samples is cb


def test_start_fails_gracefully_without_sounddevice():
    """start() must return False if sounddevice is not installed."""
    src = _make_src()
    import sdr.audio_iq_source as mod
    orig = mod.HAS_SD
    try:
        mod.HAS_SD = False
        assert src.start() is False
        assert not src.is_running
    finally:
        mod.HAS_SD = orig


def test_start_fails_gracefully_without_numpy():
    src = _make_src()
    import sdr.audio_iq_source as mod
    orig_sd, orig_np = mod.HAS_SD, mod.HAS_NUMPY
    try:
        mod.HAS_SD = True
        mod.HAS_NUMPY = False
        assert src.start() is False
    finally:
        mod.HAS_SD = orig_sd
        mod.HAS_NUMPY = orig_np


def test_stop_is_safe_when_not_started():
    src = _make_src()
    src.stop()  # should not raise
    assert not src.is_running


def test_enumerate_inputs_returns_list_without_sounddevice():
    from sdr.audio_iq_source import AudioIQSource
    import sdr.audio_iq_source as mod
    orig = mod.HAS_SD
    try:
        mod.HAS_SD = False
        result = AudioIQSource.enumerate_inputs()
        assert result == []
    finally:
        mod.HAS_SD = orig


# ---------------------------------------------------------------------------
# find_rig_audio_device tests
# ---------------------------------------------------------------------------

def test_find_rig_returns_none_without_sounddevice():
    from sdr.audio_iq_source import find_rig_audio_device
    import sdr.audio_iq_source as mod
    orig = mod.HAS_SD
    try:
        mod.HAS_SD = False
        assert find_rig_audio_device("IC-7100") is None
    finally:
        mod.HAS_SD = orig


def test_find_rig_matches_hint():
    from sdr.audio_iq_source import find_rig_audio_device
    import sdr.audio_iq_source as mod
    fake_sd = MagicMock()
    fake_sd.query_devices.return_value = [
        {"name": "USB Audio CODEC", "max_input_channels": 2},
        {"name": "Realtek Audio", "max_input_channels": 2},
    ]
    with patch.object(mod, "HAS_SD", True), \
         patch.object(mod, "sd", fake_sd, create=True):
        result = find_rig_audio_device("IC-7100")
        assert result == "USB Audio CODEC"


def test_find_rig_no_match_returns_none():
    from sdr.audio_iq_source import find_rig_audio_device
    import sdr.audio_iq_source as mod
    fake_sd = MagicMock()
    fake_sd.query_devices.return_value = [
        {"name": "Built-in Microphone", "max_input_channels": 1},
    ]
    with patch.object(mod, "HAS_SD", True), \
         patch.object(mod, "sd", fake_sd, create=True):
        result = find_rig_audio_device("IC-7100")
        assert result is None


# ---------------------------------------------------------------------------
# IQ callback logic (without actually opening a stream)
# ---------------------------------------------------------------------------

def test_mono_callback_delivers_samples():
    """_audio_callback with mono data calls on_samples."""
    try:
        import numpy as np
    except ImportError:
        return  # numpy not available; skip
    from sdr.audio_iq_source import AudioIQSource
    src = AudioIQSource()
    src.set_mode("mono")
    src.set_center_hz(7_100_000)
    received = []
    src.on_samples = lambda s, sr, hz: received.append((s, sr, hz))

    # Simulate sounddevice callback: shape (blocksize, channels=1)
    indata = np.random.uniform(-0.5, 0.5, (2048, 1)).astype("float32")
    src._audio_callback(indata, 2048, None, None)

    assert len(received) == 1
    samples, sr, hz = received[0]
    assert samples.dtype == np.complex64
    assert len(samples) == 2048
    assert hz == 7_100_000


def test_iq_stereo_callback_delivers_complex_samples():
    try:
        import numpy as np
    except ImportError:
        return
    from sdr.audio_iq_source import AudioIQSource
    src = AudioIQSource()
    src.set_mode("iq_stereo")
    src.set_center_hz(14_200_000)
    received = []
    src.on_samples = lambda s, sr, hz: received.append(s)

    indata = np.random.uniform(-1, 1, (1024, 2)).astype("float32")
    src._audio_callback(indata, 1024, None, None)

    assert len(received) == 1
    samples = received[0]
    assert samples.dtype == np.complex64
    # I channel should be real part
    assert abs(samples[0].real - indata[0, 0]) < 1e-6
    assert abs(samples[0].imag - indata[0, 1]) < 1e-6
