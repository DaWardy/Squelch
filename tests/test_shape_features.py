# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/shape_features — time-domain shape (continuous vs bursty,
duty cycle) used to enrich signal identification (ROADMAP §13.4)."""

import numpy as np

from core.shape_features import analyze_shape, ShapeFeatures

FS = 200_000
N = 200_000
T = np.arange(N) / FS


def test_continuous_carrier():
    s = analyze_shape(np.exp(2j * np.pi * 1000 * T).astype(np.complex64), FS)
    assert s.is_continuous and not s.is_bursty
    assert s.duty_cycle >= 0.95
    assert s.label() == "continuous"


def test_bursty_on_off():
    env = (np.sin(2 * np.pi * 5 * T) > 0).astype(float)   # 5 on/off cycles
    iq = (env * np.exp(2j * np.pi * 1000 * T)).astype(np.complex64)
    s = analyze_shape(iq, FS)
    assert s.is_bursty and not s.is_continuous
    assert 4 <= s.burst_count <= 6
    assert 0.4 <= s.duty_cycle <= 0.6
    assert "bursty" in s.label()


def test_noise_not_bursty():
    n = (np.random.RandomState(0).randn(N)
         + 1j * np.random.RandomState(1).randn(N)).astype(np.complex64)
    s = analyze_shape(n, FS)
    assert s.is_bursty is False           # smoothing prevents false bursts


def test_low_duty_burst():
    # short pulses: on 10% of the time, 3 pulses
    env = np.zeros(N)
    for k in range(3):
        start = int((0.2 + 0.3 * k) * N)
        env[start:start + N // 30] = 1.0
    iq = (env * np.exp(2j * np.pi * 1000 * T)).astype(np.complex64)
    s = analyze_shape(iq, FS)
    assert s.is_bursty and s.burst_count == 3
    assert s.duty_cycle < 0.2


def test_safe_on_bad_input():
    assert isinstance(analyze_shape([], FS), ShapeFeatures)
    assert isinstance(analyze_shape(np.zeros(4, np.complex64), FS), ShapeFeatures)
    assert analyze_shape(np.ones(100, np.complex64), 0).duty_cycle == 0.0


def test_workbench_populates_shape():
    from core.decode_workbench import analyze
    env = (np.sin(2 * np.pi * 5 * T) > 0).astype(float)
    iq = (env * np.exp(2j * np.pi * 1000 * T)).astype(np.complex64)
    res = analyze(iq, FS, 146_000_000)
    assert res.shape != "" and res.duty_cycle > 0.0
