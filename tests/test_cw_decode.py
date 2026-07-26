# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/cw_decode.decode_cw."""
import numpy as np
from core.cw_decode import decode_cw, _MORSE

SR = 8000
_CH = {v: k for k, v in _MORSE.items()}


def _morse_iq(text, wpm=20, carrier=600):
    unit = int(SR * 1.2 / wpm); seq = []
    for word in text.split(" "):
        for ch in word:
            m = _CH.get(ch.upper())
            if not m:
                continue
            for el in m:
                seq.append((True, unit if el == "." else 3 * unit))
                seq.append((False, unit))
            seq[-1] = (False, 3 * unit)
        seq[-1] = (False, 7 * unit)
    env = np.concatenate([np.ones(n) if v else np.zeros(n) for v, n in seq])
    t = np.arange(len(env)) / SR
    return (env * np.exp(2j * np.pi * carrier * t)).astype(np.complex64)


def test_sos():
    assert decode_cw(_morse_iq("SOS"), SR) == "SOS"


def test_words():
    assert decode_cw(_morse_iq("CQ CQ DE"), SR) == "CQ CQ DE"


def test_alphanumeric():
    assert decode_cw(_morse_iq("R2D2"), SR) == "R2D2"


def test_from_envelope():
    iq = _morse_iq("TEST")
    assert decode_cw(np.abs(iq), SR, is_envelope=True) == "TEST"


def test_empty_safe():
    assert decode_cw(np.zeros(8, np.complex64), SR) == ""
