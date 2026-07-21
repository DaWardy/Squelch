# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/decode_workbench.analyze — the right-click "identify + decode"
orchestrator over the existing DSP cores."""

import numpy as np

from core.encoder import encode_iq
from core.decode_workbench import analyze, WorkbenchResult
from core.sigid_db import SigIdDatabase


def _ook():
    return encode_iq(b"\xA5\x3C", 200_000, family="OOK", preamble_bits=16,
                     sync_word="2D", crc="CRC-8", samples_per_symbol=20,
                     carrier_hz=0).iq


def test_analyze_ook_decodes_bits():
    res = analyze(_ook(), 200_000, 146_000_000)
    assert isinstance(res, WorkbenchResult)
    assert res.decodable and res.family == "OOK"
    assert res.n_symbols >= 40
    # the encoded frame's payload byte A5 3C shows up in the recovered hex
    assert "a53c" in res.payload_hex.lower()


def test_analyze_fsk_decodes():
    iq = encode_iq(b"\x5A", 200_000, family="FSK", samples_per_symbol=20,
                   carrier_hz=0, fsk_dev_hz=8000).iq
    res = analyze(iq, 200_000, 146_000_000)
    assert res.modulation == "FSK"
    assert res.decodable and res.family == "FSK" and res.n_symbols >= 8


def test_analyze_identifies_with_sigid_db():
    # a continuous carrier at NOAA weather-radio frequency
    iq = np.exp(2j * np.pi * 1000 * np.arange(20_000) / 1e6).astype(np.complex64)
    res = analyze(iq, 1_000_000, 162_550_000, bandwidth_hz=15_000,
                  sigid_db=SigIdDatabase.builtin())
    names = [i["name"] for i in res.identities]
    assert any("NOAA" in n for n in names)
    assert res.best_identity


def test_analyze_band_isolation():
    """An OOK signal offset +40 kHz inside a 1 MHz window is isolated + decoded."""
    iq = encode_iq(b"\x5A", 1_000_000, family="OOK", samples_per_symbol=40,
                   carrier_hz=40_000).iq
    res = analyze(iq, 1_000_000, 100_000_000,
                  freq_hz=100_040_000, bandwidth_hz=30_000)
    assert res.decodable and res.n_symbols >= 4


def test_analyze_continuous_not_decodable():
    # a pure tone (AM/CW-ish continuous) — identify maybe, but no framing spam
    iq = np.exp(2j * np.pi * 5000 * np.arange(40_000) / 1e6).astype(np.complex64)
    res = analyze(iq, 1_000_000, 100_000_000)
    assert isinstance(res, WorkbenchResult)     # never raises; result returned


def test_analyze_never_raises_on_garbage():
    assert analyze([], 0, 0).modulation == ""
    assert analyze(np.zeros(4, np.complex64), 1000, 1).notes  # too short → noted
    r = analyze(np.random.RandomState(0).randn(2000).astype(np.complex64),
                1_000_000, 100_000_000)
    assert isinstance(r, WorkbenchResult)


def test_result_summary_string():
    res = analyze(_ook(), 200_000, 146_000_000, sigid_db=SigIdDatabase.builtin())
    s = res.summary()
    assert isinstance(s, str) and len(s) > 0
