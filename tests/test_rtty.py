# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/rtty.decode_rtty (best-effort ITA2 FSK decode)."""
import numpy as np
from core.rtty import decode_rtty, _LTRS

SR = 8000
_CH = {v: k for k, v in _LTRS.items() if v.isalpha() or v == " "}


def _rtty_iq(text, baud=45.45, mark=2125, space=2295):
    spb = SR / baud; stream = [1] * int(spb * 5)
    for ch in text.upper():
        code = _CH.get(ch)
        if not code:
            continue
        stream += [0] * int(round(spb))
        for b in code:
            stream += [1 if b == "1" else 0] * int(round(spb))
        stream += [1] * int(round(spb * 1.5))
    stream += [1] * int(spb * 5)
    freq = np.where(np.array(stream) == 1, mark, space)
    return np.exp(1j * 2 * np.pi * np.cumsum(freq) / SR).astype(np.complex64)


def test_decodes_clean_message():
    out = decode_rtty(_rtty_iq("TEST DE STATION"), SR)
    assert "TEST DE" in out and "STATION" in out


def test_decodes_sentence_high_accuracy():
    txt = "THE QUICK BROWN FOX"
    out = decode_rtty(_rtty_iq(txt), SR)
    correct = sum(1 for a, b in zip(txt, out) if a == b)
    assert correct >= int(0.8 * len(txt))          # best-effort ≥80% chars


def test_reversed_polarity_still_decodes():
    # swap mark/space tones — decoder auto-tries both polarities. A longer
    # message gives the correct polarity a clear printable-char advantage.
    out = decode_rtty(_rtty_iq("CQ CQ DE STATION", mark=2295, space=2125), SR)
    assert "STATION" in out or "CQ" in out


def test_empty_safe():
    assert decode_rtty(np.zeros(16, np.complex64), SR) == ""
