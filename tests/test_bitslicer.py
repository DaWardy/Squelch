# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/bitslicer.py — generic OOK/FSK/PSK bit-slicer (DEC-GENERIC).

Signals are synthesised deterministically (fixed seed) so the recovered symbol
stream can be checked exactly. Slicing uses a known samples-per-symbol where
we want an exact match, and the estimator is exercised separately.
"""
import numpy as np
import pytest

from core.bitslicer import (
    slice_bits, estimate_sps, bits_to_bytes, bits_to_hex, SliceResult,
    OOK, FSK, PSK,
)

FS = 48_000.0
SPS = 40                    # samples per symbol → 1200 baud at 48 kHz
PATTERN = [1, 0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 1, 1, 0, 1, 0]


# ── signal synthesis ──────────────────────────────────────────────────────────

def _upsample(bits, sps):
    return np.repeat(np.asarray(bits, dtype=float), sps)


def _ook(bits, sps=SPS, f0=3000.0, noise=0.0):
    sym = _upsample(bits, sps)
    t = np.arange(sym.size) / FS
    carrier = np.exp(2j * np.pi * f0 * t)
    iq = (0.05 + sym) * carrier            # "off" is a small residual, "on" ~1
    if noise:
        rng = np.random.default_rng(1)
        iq = iq + noise * (rng.standard_normal(iq.size)
                           + 1j * rng.standard_normal(iq.size))
    return iq.astype(np.complex64)


def _fsk(bits, sps=SPS, f_lo=-4000.0, f_hi=4000.0):
    sym = _upsample(bits, sps)
    inst_f = np.where(sym > 0.5, f_hi, f_lo)
    phase = np.cumsum(2 * np.pi * inst_f / FS)
    return np.exp(1j * phase).astype(np.complex64)


def _bpsk(bits, sps=SPS):
    # absolute BPSK: bit 1 → phase 0, bit 0 → phase π (no carrier offset)
    sym = _upsample(bits, sps)
    phase = np.where(sym > 0.5, 0.0, np.pi)
    return np.exp(1j * phase).astype(np.complex64)


def _match_or_inverted(got, want):
    want = list(want)
    inv = [1 - b for b in want]
    return got == want or got == inv


# ── OOK / ASK ─────────────────────────────────────────────────────────────────

class TestOOK:
    def test_exact_recovery_known_sps(self):
        iq = _ook(PATTERN)
        r = slice_bits(iq, FS, family=OOK, samples_per_symbol=SPS)
        assert r.family == OOK
        assert r.bits == PATTERN
        assert r.n_symbols == len(PATTERN)

    def test_symbol_rate_reported(self):
        iq = _ook(PATTERN)
        r = slice_bits(iq, FS, family=OOK, samples_per_symbol=SPS)
        assert r.symbol_rate == pytest.approx(FS / SPS)     # 1200 baud

    def test_high_confidence_clean(self):
        iq = _ook(PATTERN)
        r = slice_bits(iq, FS, family=OOK, samples_per_symbol=SPS)
        assert r.confidence > 0.7

    def test_recovery_survives_light_noise(self):
        iq = _ook(PATTERN, noise=0.05)
        r = slice_bits(iq, FS, family=OOK, samples_per_symbol=SPS)
        assert r.bits == PATTERN


# ── FSK ───────────────────────────────────────────────────────────────────────

class TestFSK:
    def test_exact_recovery_known_sps(self):
        iq = _fsk(PATTERN)
        r = slice_bits(iq, FS, family=FSK, samples_per_symbol=SPS)
        assert r.family == FSK
        # FSK sense (which tone = 1) is convention; accept either polarity
        assert _match_or_inverted(r.bits, PATTERN)

    def test_symbol_count(self):
        iq = _fsk(PATTERN)
        r = slice_bits(iq, FS, family=FSK, samples_per_symbol=SPS)
        assert r.n_symbols == len(PATTERN)


# ── PSK (coherent BPSK, 180° ambiguity) ───────────────────────────────────────

class TestPSK:
    def test_recovery_up_to_inversion(self):
        iq = _bpsk(PATTERN)
        r = slice_bits(iq, FS, family=PSK, samples_per_symbol=SPS)
        assert r.family == PSK
        assert _match_or_inverted(r.bits, PATTERN)

    def test_alternating_pattern(self):
        alt = [1, 0] * 12
        iq = _bpsk(alt)
        r = slice_bits(iq, FS, family=PSK, samples_per_symbol=SPS)
        assert _match_or_inverted(r.bits, alt)


# ── symbol-rate estimation ────────────────────────────────────────────────────

class TestEstimateSps:
    def test_estimates_true_sps_ook(self):
        iq = _ook(PATTERN)
        r = slice_bits(iq, FS, family=OOK)          # no sps hint → estimate
        assert r.samples_per_symbol == pytest.approx(SPS, abs=2)

    def test_estimates_true_sps_fsk(self):
        iq = _fsk(PATTERN)
        r = slice_bits(iq, FS, family=FSK)
        assert r.samples_per_symbol == pytest.approx(SPS, abs=2)

    def test_symbol_rate_from_symbol_rate_arg(self):
        iq = _ook(PATTERN)
        r = slice_bits(iq, FS, family=OOK, symbol_rate=FS / SPS)
        assert r.samples_per_symbol == pytest.approx(SPS)
        assert r.bits == PATTERN

    def test_empty_stream_estimator(self):
        assert estimate_sps(np.zeros(0, dtype=np.int8)) == 0.0


# ── auto family detection ─────────────────────────────────────────────────────

class TestAutoFamily:
    def test_ook_detected_without_family(self):
        iq = _ook(PATTERN)
        r = slice_bits(iq, FS, samples_per_symbol=SPS)   # family auto
        assert r.family in (OOK, FSK, PSK)
        # OOK should be the pick for an on/off amplitude signal
        assert r.family == OOK
        assert r.bits == PATTERN


# ── bit packing ───────────────────────────────────────────────────────────────

class TestBitPacking:
    def test_bytes_msb_first(self):
        bits = [0, 1, 0, 0, 0, 0, 0, 1]      # 0x41 = 'A'
        assert bits_to_bytes(bits) == b"\x41"

    def test_bytes_lsb_first(self):
        bits = [1, 0, 0, 0, 0, 0, 1, 0]      # reversed → 0x41
        assert bits_to_bytes(bits, msb_first=False) == b"\x41"

    def test_partial_trailing_byte_dropped(self):
        bits = [1] * 8 + [1, 0, 1]
        assert bits_to_bytes(bits) == b"\xff"

    def test_hex_helper(self):
        bits = [0, 1, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 1, 0]
        assert bits_to_hex(bits) == "4142"    # "AB"

    def test_result_as_hex(self):
        r = SliceResult(bits=[0, 1, 0, 0, 0, 0, 0, 1])
        assert r.as_hex() == "41"


# ── robustness ────────────────────────────────────────────────────────────────

class TestRobustness:
    def test_empty_iq(self):
        r = slice_bits(np.zeros(0, dtype=np.complex64), FS, family=OOK)
        assert r.bits == [] and r.n_symbols == 0

    def test_too_short(self):
        r = slice_bits(np.ones(2, dtype=np.complex64), FS, family=OOK)
        assert r.bits == []

    def test_zero_fs(self):
        iq = _ook(PATTERN)
        assert slice_bits(iq, 0.0, family=OOK).bits == []

    def test_unknown_family_falls_back(self):
        iq = _ook(PATTERN)
        r = slice_bits(iq, FS, family="BOGUS", samples_per_symbol=SPS)
        assert r.family == OOK
        assert r.bits == PATTERN

    def test_never_raises_on_garbage(self):
        rng = np.random.default_rng(0)
        junk = (rng.standard_normal(500)
                + 1j * rng.standard_normal(500)).astype(np.complex64)
        for fam in (OOK, FSK, PSK):
            r = slice_bits(junk, FS, family=fam)      # must not raise
            assert isinstance(r, SliceResult)
