# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/pocsag — pager decode (round-trip via the matching encoder)."""
import numpy as np
from core.pocsag import (
    encode_frame, decode_pocsag_bits, decode_pocsag,
    encode_codeword, _valid)


def _ric(msgs):
    return {m.ric: m.text for m in msgs}


def test_bch_codeword_round_trips():
    for d in (0, 0x1FFFFF, 0b101010101010101010101, 12345):
        assert _valid(encode_codeword(d))


def test_numeric_message():
    msgs = decode_pocsag_bits(encode_frame(1234568, "12345", function=0))
    assert _ric(msgs) == {1234568: "12345"}


def test_numeric_long():
    msgs = decode_pocsag_bits(encode_frame(42, "1234567890", function=0))
    assert msgs and msgs[0].text == "1234567890"


def test_alpha_message():
    msgs = decode_pocsag_bits(
        encode_frame(999999, "HELLO PAGER", function=3, alpha=True))
    assert msgs and msgs[0].kind == "alpha" and msgs[0].text == "HELLO PAGER"


def test_alpha_spans_multiple_batches():
    txt = "EMERGENCY CALL STATION 42 NOW"
    msgs = decode_pocsag_bits(encode_frame(1000, txt, function=3, alpha=True))
    assert msgs and msgs[0].text == txt


def test_decode_via_iq():
    bits = encode_frame(1234568, "ALERT 42", function=3, alpha=True)
    fs, baud = 38400, 1200
    stream = np.repeat(np.array(bits), int(fs / baud))
    iq = np.exp(1j * 2 * np.pi
                * np.cumsum(np.where(stream == 1, 4500, -4500)) / fs
                ).astype(np.complex64)
    msgs = decode_pocsag(iq, fs)
    assert msgs and msgs[0].text == "ALERT 42"


def test_noise_decodes_nothing():
    n = (np.random.RandomState(0).randn(20000)
         + 1j * np.random.RandomState(1).randn(20000)).astype(np.complex64)
    assert decode_pocsag(n, 38400) == []


def test_empty_safe():
    assert decode_pocsag_bits([]) == []
    assert decode_pocsag(np.zeros(8, np.complex64), 38400) == []
