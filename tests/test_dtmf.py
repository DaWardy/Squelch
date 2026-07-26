# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/dtmf.decode_dtmf."""
import numpy as np
from core.dtmf import decode_dtmf, LOW_FREQS, HIGH_FREQS, _KEYS

SR = 8000


def _tone(key, ms=80, gap=40):
    lf = hf = 0.0
    for r in range(4):
        for c in range(4):
            if _KEYS[r][c] == key:
                lf, hf = LOW_FREQS[r], HIGH_FREQS[c]
    n = int(SR * ms / 1000); t = np.arange(n) / SR
    sig = (np.sin(2 * np.pi * lf * t) + np.sin(2 * np.pi * hf * t)) * 0.5
    return np.concatenate([sig, np.zeros(int(SR * gap / 1000))])


def _seq(s):
    return np.concatenate([_tone(k) for k in s]).astype(np.float32)


def test_full_keypad():
    assert decode_dtmf(_seq("1234567890*#ABCD"), SR) == "1234567890*#ABCD"


def test_noise_decodes_nothing():
    n = (np.random.RandomState(0).randn(16000) * 0.3).astype(np.float32)
    assert decode_dtmf(n, SR) == ""


def test_robust_to_noise():
    a = _seq("911") + np.random.RandomState(1).randn(len(_seq("911"))).astype(np.float32) * 0.05
    assert decode_dtmf(a, SR) == "911"


def test_empty_safe():
    assert decode_dtmf(np.zeros(4, np.float32), SR) == ""
    assert decode_dtmf([], 0) == ""
