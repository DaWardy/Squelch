# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Universal IQ playback (ROADMAP §14.1) — playback honours the recording's
datatype so ANY SigMF / foreign capture plays, not just Squelch's cf32. This is
the "no SDR needed" enabler: the whole pipeline runs on downloaded sample files.

All headless — synthesises small IQ files on disk and checks the streaming
decode + the IQPlayer thread deliver correct complex64 samples."""

import time
from pathlib import Path

import numpy as np
import pytest

from core.sigmf_io import bytes_per_sample, decode_iq_bytes


# ── bytes_per_sample ─────────────────────────────────────────────────────────
def test_bytes_per_sample_common_formats():
    assert bytes_per_sample("cf32_le") == 8
    assert bytes_per_sample("cf64_le") == 16
    assert bytes_per_sample("ci16_le") == 4
    assert bytes_per_sample("ci8") == 2
    assert bytes_per_sample("cu8") == 2
    assert bytes_per_sample("rf32_le") == 4      # real → itemsize * 1


def test_bytes_per_sample_bad_defaults_cf32():
    assert bytes_per_sample("garbage") == 8
    assert bytes_per_sample("") == 8


# ── decode_iq_bytes ──────────────────────────────────────────────────────────
def test_decode_cf32_exact():
    iq = np.array([1 + 2j, -3 + 0.5j], dtype=np.complex64)
    raw = iq.astype(np.complex64).tobytes()
    out = decode_iq_bytes(raw, "cf32_le")
    assert np.allclose(out, iq)


def test_decode_cu8_formula():
    # cu8: (byte - 128) / 128 for each of I, Q
    raw = bytes([128, 128, 255, 128, 0, 128])     # → 0+0j, ~+1+0j, -1+0j
    out = decode_iq_bytes(raw, "cu8")
    assert len(out) == 3
    assert abs(out[0]) < 1e-6
    assert abs(out[1].real - (255 - 128) / 128) < 1e-6
    assert abs(out[2].real - (-1.0)) < 1e-6


def test_decode_ci16_scaled():
    # ci16: value / 32768
    vals = np.array([32767, 0, -16384, 100], dtype="<i2")
    out = decode_iq_bytes(vals.tobytes(), "ci16_le")
    assert len(out) == 2
    assert abs(out[0].real - 32767 / 32768) < 1e-4
    assert abs(out[1].real - (-16384 / 32768)) < 1e-4


def test_decode_drops_partial_sample():
    # 5 bytes of cu8 (needs pairs) → 2 complete samples, trailing byte dropped
    out = decode_iq_bytes(bytes([10, 20, 30, 40, 50]), "cu8")
    assert len(out) == 2


def test_decode_bad_datatype_is_safe():
    out = decode_iq_bytes(b"\x00\x01\x02\x03", "not-a-type")
    assert out.dtype == np.complex64                # cf32 fallback, no raise


def test_decode_matches_read_iq(tmp_path):
    """Streaming decode of the whole file == the one-shot read_iq path."""
    from core.sigmf_io import write_iq, read_iq
    iq = (np.random.RandomState(1).randn(500)
          + 1j * np.random.RandomState(2).randn(500)).astype(np.complex64)
    base = tmp_path / "cap"
    write_iq(iq, base, sample_rate=2_400_000, center_hz=100_000_000)
    whole, _ = read_iq(base)
    streamed = decode_iq_bytes(
        Path(str(base) + ".sigmf-data").read_bytes(), "cf32_le")
    assert np.allclose(whole, streamed)


# ── IQPlayer honours datatype end-to-end ─────────────────────────────────────
def _play_collect(rec, timeout=6.0):
    from sdr.iq_recorder import IQPlayer
    got, done = [], {"end": False}
    p = IQPlayer()
    assert p.load(rec)
    p.on_samples(lambda s, sr, c: got.append(np.asarray(s).copy()))
    p.on_end(lambda: done.__setitem__("end", True))
    p.play(speed=4.0)
    t0 = time.time()
    while not done["end"] and (time.time() - t0) < timeout:
        time.sleep(0.02)
    p.stop()
    return np.concatenate(got) if got else np.empty(0, np.complex64)


def _rec(data_path, datatype, sr=2_400_000):
    from sdr.iq_recorder import Recording
    return Recording(
        name=data_path.stem, data_path=data_path, meta_path=data_path,
        center_hz=100_000_000, sample_rate=sr, datatype=datatype,
        file_size=data_path.stat().st_size)


def test_player_plays_cf32(tmp_path):
    iq = (np.random.RandomState(3).randn(40_000)
          + 1j * np.random.RandomState(4).randn(40_000)).astype(np.complex64)
    p = tmp_path / "a.cf32"
    iq.tofile(p)
    out = _play_collect(_rec(p, "cf32_le"))
    assert len(out) == 40_000
    assert np.allclose(out, iq, atol=1e-5)


def test_player_plays_ci16(tmp_path):
    """A 16-bit interleaved capture (common foreign format) plays correctly."""
    n = 20_000
    vals = np.random.RandomState(5).randint(-30000, 30000, n * 2).astype("<i2")
    p = tmp_path / "b.iq"
    vals.tofile(p)
    out = _play_collect(_rec(p, "ci16_le"))
    expected = decode_iq_bytes(p.read_bytes(), "ci16_le")
    assert len(out) == n
    assert np.allclose(out, expected, atol=1e-4)


def test_player_plays_cu8(tmp_path):
    """An RTL-SDR-style cu8 dump plays correctly (was garbage before §14.1)."""
    raw = np.random.RandomState(6).randint(0, 256, 30_000 * 2).astype(np.uint8)
    p = tmp_path / "rtl.bin"
    raw.tofile(p)
    out = _play_collect(_rec(p, "cu8"))
    expected = decode_iq_bytes(p.read_bytes(), "cu8")
    assert len(out) == 30_000
    assert np.allclose(out, expected, atol=1e-4)


def _ramp_recording(tmp_path, n):
    """A cf32 recording whose sample values are 0,1,2,… so order is checkable."""
    from sdr.iq_recorder import Recording
    data = np.arange(n, dtype=np.float32).astype(np.complex64)
    p = tmp_path / "ramp.cf32"
    data.tofile(p)
    return Recording(name="ramp", data_path=p, meta_path=p,
                     center_hz=100_000_000, sample_rate=2_400_000,
                     datatype="cf32_le", file_size=p.stat().st_size)


def _collect(player, timeout=6.0):
    got, done = [], {"end": False}
    player.on_samples(lambda s, sr, c: got.append(np.asarray(s).copy()))
    player.on_end(lambda: done.__setitem__("end", True))
    t0 = time.time()
    while not done["end"] and (time.time() - t0) < timeout:
        time.sleep(0.02)
    player.stop()
    return np.concatenate(got) if got else np.empty(0, np.complex64)


def test_reverse_playback_plays_backwards(tmp_path):
    from sdr.iq_recorder import IQPlayer
    n = 16384 * 4
    p = IQPlayer()
    assert p.load(_ramp_recording(tmp_path, n))
    p.play(speed=8.0, reverse=True)               # auto-jumps to the end
    out = _collect(p)
    assert len(out) > 0
    # first delivered samples are the highest indices, last are the lowest
    assert out[0].real > out[-1].real
    assert out[0].real >= n * 0.7                  # started near the end


def test_reverse_hits_start_and_ends(tmp_path):
    from sdr.iq_recorder import IQPlayer
    p = IQPlayer()
    p.load(_ramp_recording(tmp_path, 16384 * 3))
    done = {"end": False}
    p.on_end(lambda: done.__setitem__("end", True))
    p.play(speed=8.0, reverse=True)
    t0 = time.time()
    while not done["end"] and time.time() - t0 < 6.0:
        time.sleep(0.02)
    p.stop()
    assert done["end"] is True                     # reached the beginning


def test_set_speed_and_reverse_live():
    from sdr.iq_recorder import IQPlayer
    p = IQPlayer()
    p.set_speed(4.0)
    assert p.speed == 4.0
    p.set_speed(99)                                # clamped to 8×
    assert p.speed == 8.0
    p.set_reverse(True)
    assert p.is_reverse is True


try:
    import PyQt6  # noqa: F401
    _HAS_QT = True
except ImportError:
    _HAS_QT = False


@pytest.mark.skipif(not _HAS_QT, reason="PyQt6 not installed")
def test_transport_controls_wire_to_player():
    import sys
    import tempfile
    from unittest.mock import MagicMock
    from PyQt6.QtWidgets import QApplication
    from core.config import Config
    from ui.tabs.sdr_tab import SDRTab, HAS_PG
    if not HAS_PG:
        pytest.skip("pyqtgraph not installed")
    QApplication.instance() or QApplication(sys.argv)
    cfg = Config(Path(tempfile.mkdtemp()) / "config.json")
    rig = MagicMock(); rig.is_connected = False; rig.state = MagicMock()
    tab = SDRTab(cfg, rig)
    if not hasattr(tab, "_rev_btn"):
        pytest.skip("recorder group not built")
    tab._rev_btn.setChecked(True)
    assert tab._player.is_reverse is True
    tab._speed_combo.setCurrentText("4×")
    assert tab._player.speed == 4.0


def test_from_meta_duration_uses_datatype(tmp_path):
    """Recording.from_meta_file duration is correct for a non-cf32 datatype."""
    import json
    from sdr.iq_recorder import Recording
    n = 24_000                                  # 0.01 s at 2.4 MS/s
    (tmp_path / "c.sigmf-data").write_bytes(
        np.zeros(n * 2, dtype="<i2").tobytes())   # ci16 = 4 bytes/sample
    (tmp_path / "c.sigmf-meta").write_text(json.dumps({"global": {
        "core:sample_rate": 2_400_000, "core:datatype": "ci16_le",
        "core:frequency": 100_000_000}}), encoding="utf-8")
    rec = Recording.from_meta_file(tmp_path / "c.sigmf-meta")
    assert rec is not None
    assert abs(rec.duration_s - 0.01) < 1e-4     # would be 0.005 if it assumed cf32
