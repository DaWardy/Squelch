# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/audio_dsp — manual + auto notch on demodulated audio
(ROADMAP §14.5, SDR-Console DSP parity)."""

import numpy as np

from core.audio_dsp import notch, auto_notch

SR = 48_000
N = 48_000
T = np.arange(N) / SR


def _band_energy(x, f, w=80):
    sp = np.abs(np.fft.rfft(x))
    fr = np.fft.rfftfreq(len(x), 1 / SR)
    return float(np.sum(sp[(fr >= f - w) & (fr <= f + w)] ** 2))


# ── manual notch ─────────────────────────────────────────────────────────────
def test_notch_removes_target_keeps_rest():
    a = (np.cos(2 * np.pi * 1000 * T)
         + 0.8 * np.cos(2 * np.pi * 3000 * T)).astype(np.float32)
    b = notch(a, SR, 3000, width_hz=120)
    assert _band_energy(b, 3000) < 0.01 * _band_energy(a, 3000)   # gone
    assert _band_energy(b, 1000) > 0.9 * _band_energy(a, 1000)    # kept


def test_notch_dtype_float32():
    a = np.cos(2 * np.pi * 1000 * T).astype(np.float32)
    assert notch(a, SR, 1000).dtype == np.float32


def test_notch_safe_edges():
    assert len(notch(np.zeros(0, np.float32), SR, 1000)) == 0
    a = np.cos(2 * np.pi * 1000 * T).astype(np.float32)
    # freq<=0 or bad sr → returned unchanged, no raise
    assert np.allclose(notch(a, SR, 0), a)
    assert np.allclose(notch(a, 0, 1000), a)


# ── auto-notch ───────────────────────────────────────────────────────────────
def _noise(scale=0.1, seed=0):
    return (np.random.RandomState(seed).randn(N) * scale).astype(np.float32)


def test_auto_notch_removes_het():
    a = (_noise() + 2.0 * np.cos(2 * np.pi * 5000 * T)).astype(np.float32)
    out, removed = auto_notch(a, SR)
    assert removed and abs(removed[0] - 5000) < 120
    assert _band_energy(out, 5000) < 0.01 * _band_energy(a, 5000)


def test_auto_notch_ignores_pure_noise():
    out, removed = auto_notch(_noise(seed=1), SR)
    assert removed == []


def test_auto_notch_removes_two_hets():
    a = (_noise() + 1.5 * np.cos(2 * np.pi * 1200 * T)
         + 1.5 * np.cos(2 * np.pi * 5000 * T)).astype(np.float32)
    _, removed = auto_notch(a, SR)
    got = sorted(round(f) for f in removed)
    assert any(abs(f - 1200) < 120 for f in got)
    assert any(abs(f - 5000) < 120 for f in got)


def test_auto_notch_max_notches_cap():
    a = (_noise()
         + 1.5 * np.cos(2 * np.pi * 1000 * T)
         + 1.5 * np.cos(2 * np.pi * 3000 * T)
         + 1.5 * np.cos(2 * np.pi * 5000 * T)).astype(np.float32)
    _, removed = auto_notch(a, SR, max_notches=2)
    assert len(removed) == 2


def test_auto_notch_respects_min_hz():
    a = (_noise() + 2.0 * np.cos(2 * np.pi * 120 * T)      # below min_hz
         + 2.0 * np.cos(2 * np.pi * 3000 * T)).astype(np.float32)
    _, removed = auto_notch(a, SR, min_hz=200)
    assert all(f >= 200 for f in removed)
    assert any(abs(f - 3000) < 120 for f in removed)


def test_auto_notch_safe_short_input():
    out, removed = auto_notch(np.zeros(4, np.float32), SR)
    assert removed == [] and out.dtype == np.float32
