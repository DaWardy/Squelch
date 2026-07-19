# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/demod — the IQ→audio demodulator engine and the MultiVFO
multi-receiver core (ROADMAP §14.4). Each mode is validated by synthesising a
modulated signal and checking the recovered audio tone."""

import numpy as np

from core.demod import (
    demodulate, demod_ssb, frequency_shift, lowpass_decimate,
    MultiVFO, VFOChannel, AUDIO_RATE)

SR = 240_000
AR = 48_000
N = 48_000
T = np.arange(N) / SR
FA = 3000.0                       # modulating tone
OFF = 30_000                      # carrier offset within the IQ


def _dominant_hz(audio, rate=AR):
    if len(audio) < 16:
        return 0.0
    w = np.hanning(len(audio))
    sp = np.abs(np.fft.rfft(audio * w))
    sp[0] = 0                     # ignore DC
    f = np.fft.rfftfreq(len(audio), 1 / rate)
    return float(f[np.argmax(sp)])


def _energy(x):
    return float(np.sum(np.abs(x) ** 2))


# ── building blocks ──────────────────────────────────────────────────────────
def test_frequency_shift_moves_tone_to_baseband():
    iq = np.exp(2j * np.pi * OFF * T).astype(np.complex64)
    bb = frequency_shift(iq, SR, OFF)
    assert abs(np.mean(bb).real - 1.0) < 0.05        # now a DC term


def test_lowpass_decimate_reduces_rate():
    iq = (np.random.RandomState(0).randn(N)
          + 1j * np.random.RandomState(1).randn(N)).astype(np.complex64)
    out, rate = lowpass_decimate(iq, SR, 10_000, AR)
    assert rate == AR                                # 240k / 5
    assert len(out) == N // (SR // AR)


# ── per-mode recovery ────────────────────────────────────────────────────────
def test_am_recovers_tone():
    iq = ((1 + 0.6 * np.cos(2 * np.pi * FA * T))
          * np.exp(2j * np.pi * OFF * T)).astype(np.complex64)
    a = demodulate(iq, SR, "AM", offset_hz=OFF, bandwidth_hz=10_000, audio_rate=AR)
    assert abs(_dominant_hz(a) - FA) < 100


def test_fm_recovers_tone():
    beta = 5000 / FA
    iq = np.exp(1j * (2 * np.pi * OFF * T
                      + beta * np.sin(2 * np.pi * FA * T))).astype(np.complex64)
    a = demodulate(iq, SR, "NBFM", offset_hz=OFF, bandwidth_hz=12_500, audio_rate=AR)
    assert abs(_dominant_hz(a) - FA) < 100


def test_usb_recovers_tone():
    iq = np.exp(2j * np.pi * (OFF + 1500) * T).astype(np.complex64)
    a = demodulate(iq, SR, "USB", offset_hz=OFF, bandwidth_hz=2700, audio_rate=AR)
    assert abs(_dominant_hz(a) - 1500) < 100


def test_lsb_recovers_tone():
    iq = np.exp(2j * np.pi * (OFF - 1200) * T).astype(np.complex64)
    a = demodulate(iq, SR, "LSB", offset_hz=OFF, bandwidth_hz=2700, audio_rate=AR)
    assert abs(_dominant_hz(a) - 1200) < 100


def test_cw_produces_bfo_tone():
    iq = np.exp(2j * np.pi * OFF * T).astype(np.complex64)   # bare carrier
    a = demodulate(iq, SR, "CW", offset_hz=OFF, bandwidth_hz=500, audio_rate=AR)
    from core.demod import CW_BFO_HZ
    assert abs(_dominant_hz(a) - CW_BFO_HZ) < 100


def test_ssb_rejects_opposite_sideband():
    """USB selection zeroes negative-freq energy (and vice-versa)."""
    bb = np.exp(-2j * np.pi * 1200 * T / 1).astype(np.complex64)  # a −freq tone
    # normalise timebase: use baseband directly
    bb = np.exp(-2j * np.pi * (1200 / AR) * np.arange(N)).astype(np.complex64)
    wrong = demod_ssb(bb, upper=True)     # asks for USB on an LSB-only tone
    right = demod_ssb(bb, upper=False)    # LSB — matches
    assert _energy(wrong) < 0.1 * _energy(right)


# ── normalisation + robustness ───────────────────────────────────────────────
def test_output_is_bounded_float32():
    iq = (np.random.RandomState(2).randn(N)
          + 1j * np.random.RandomState(3).randn(N)).astype(np.complex64)
    a = demodulate(iq, SR, "AM", offset_hz=0, bandwidth_hz=10_000, audio_rate=AR)
    assert a.dtype == np.float32
    assert np.max(np.abs(a)) <= 1.0


def test_empty_and_bad_input_safe():
    assert len(demodulate(np.zeros(0, np.complex64), SR, "FM")) == 0
    assert len(demodulate([1 + 1j, 2 + 0j], SR, "bogus-mode")) >= 0   # no raise


# ── MultiVFO ─────────────────────────────────────────────────────────────────
def test_multivfo_separates_channels():
    am = ((1 + 0.6 * np.cos(2 * np.pi * FA * T))
          * np.exp(2j * np.pi * 30_000 * T))
    fm = np.exp(1j * (2 * np.pi * (-40_000) * T
                      + (6000 / FA) * np.sin(2 * np.pi * FA * T)))
    mix = (am + fm).astype(np.complex64)
    center = 100_000_000
    m = MultiVFO(audio_rate=AR)
    m.add(center + 30_000, "AM", 10_000, "a")
    m.add(center - 40_000, "NBFM", 12_500, "b")
    out = m.process(mix, SR, center)
    assert set(out.keys()) == {"a", "b"}
    assert abs(_dominant_hz(out["a"]) - FA) < 100
    assert abs(_dominant_hz(out["b"]) - FA) < 100


def test_multivfo_skips_out_of_band_channel():
    m = MultiVFO()
    m.add(100_000_000, "FM", label="in")
    m.add(200_000_000, "FM", label="out")          # far outside the IQ span
    iq = np.exp(2j * np.pi * 1000 * T).astype(np.complex64)
    out = m.process(iq, SR, 100_000_000)
    assert "in" in out and "out" not in out


def test_multivfo_add_remove():
    m = MultiVFO()
    m.add(1, "AM"); m.add(2, "FM")
    assert len(m.channels) == 2
    assert m.remove(0) is True
    assert len(m.channels) == 1
    assert m.remove(5) is False


def test_multivfo_uses_index_key_without_label():
    m = MultiVFO()
    m.add(100_000_000, "FM")                        # no label
    iq = np.exp(2j * np.pi * 1000 * T).astype(np.complex64)
    out = m.process(iq, SR, 100_000_000)
    assert "vfo0" in out


# ── integration with the simulated source ────────────────────────────────────
def test_demod_of_sim_signal_is_audible():
    from sdr.sim_source import SimSource
    iq = SimSource(sample_rate=SR, seed=1).generate(N, 100_000_000, t=0.0)
    # the sim's 'carrier' signal sits at −300 kHz, but SR here is 240k so use an
    # in-band offset signal: −? — just demod the strongest content near 0.
    a = demodulate(iq, SR, "AM", offset_hz=0, bandwidth_hz=20_000, audio_rate=AR)
    assert a.size > 0 and np.all(np.isfinite(a))
    assert _energy(a) > 0.0
