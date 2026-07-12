# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Regression tests for the bugs the adversarial review confirmed:
  1/2  framing.inspect_frame — alternating-run bled into payload / sync
  3    bitslicer OOK threshold — impulse spike zeroed the stream
  4    live_analysis.correlate_emitters — ignored signals with store+ingest=False
"""
import numpy as np
import pytest

from core.framing import inspect_frame, compute_crc
from core.bitslicer import slice_bits, bits_to_bytes, OOK
from core.live_analysis import SurveyEngine
from core.signal_model import SignalStore


def _bytes_to_bits(data: bytes):
    out = []
    for byte in data:
        out.extend((byte >> i) & 1 for i in range(7, -1, -1))
    return out


def _int_to_bits(v, w):
    return [(v >> i) & 1 for i in range(w - 1, -1, -1)]


# ── framing: preamble-less frame whose payload starts 0x55 ─────────────────────

class TestFramingPayloadStartsAlternating:
    def test_no_preamble_alternating_payload_crc_ok(self):
        payload = b"\x55\x48\x49"                 # starts with 0x55 (01010101)
        crc = _int_to_bits(compute_crc(payload, "CRC-16/CCITT-FALSE"), 16)
        bits = _bytes_to_bits(payload) + crc
        r = inspect_frame(bits, crc_bits=16)      # no preamble, no sync
        assert r.crc_ok is True                   # was False before the fix
        assert r.payload.hex == payload.hex()     # first byte not eaten
        assert r.preamble is None


# ── framing: sync word whose first bit continues the preamble alternation ──────

class TestFramingSyncStartsWithZero:
    def test_sync_starting_zero_after_preamble(self):
        preamble = [0, 1] * 16                     # ends in 1
        from core.framing import _normalize_pattern
        sync = _normalize_pattern("2DD4")         # 0x2DD4 starts with 0
        payload = b"\xde\xad"
        crc = _int_to_bits(compute_crc(payload, "CRC-16/CCITT-FALSE"), 16)
        bits = preamble + sync + _bytes_to_bits(payload) + crc
        r = inspect_frame(bits, sync_word="2DD4", crc_bits=16)
        assert r.sync is not None                 # was 'sync word not found'
        assert r.crc_ok is True
        assert r.preamble.length == 32

    def test_control_sync_starting_one_still_works(self):
        preamble = [0, 1] * 16
        from core.framing import _normalize_pattern
        sync = _normalize_pattern("D391")         # starts with 1
        payload = b"\xbe\xef"
        crc = _int_to_bits(compute_crc(payload, "CRC-16/CCITT-FALSE"), 16)
        bits = preamble + sync + _bytes_to_bits(payload) + crc
        r = inspect_frame(bits, sync_word="D391", crc_bits=16)
        assert r.crc_ok is True and r.preamble.length == 32


# ── bitslicer: impulse noise must not zero an OOK burst ────────────────────────

class TestBitslicerImpulseNoise:
    def _ook(self, bits, sps=40, fs=48000.0, f0=3000.0, amp=1.0):
        sym = np.repeat(np.array(bits, dtype=float), sps)
        t = np.arange(sym.size) / fs
        return ((0.05 + amp * sym) * np.exp(2j * np.pi * f0 * t)).astype(np.complex64)

    def test_single_impulse_does_not_zero_stream(self):
        pattern = [1, 0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 1, 1, 0, 1, 0]
        iq = self._ook(pattern)
        iq = iq.copy()
        iq[123] = 10.0 + 0j                       # one impulse spike (amp 10)
        r = slice_bits(iq, 48000.0, family=OOK, samples_per_symbol=40)
        assert r.bits == pattern                  # was all-zeros before the fix

    def test_clean_ook_still_exact(self):
        pattern = [1, 0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 1, 1, 0, 1, 0]
        r = slice_bits(self._ook(pattern), 48000.0, family=OOK,
                       samples_per_symbol=40)
        assert r.bits == pattern


# ── live_analysis: correlate with a store but ingest=False ─────────────────────

class TestCorrelateStoreIngestFalse:
    def _frame(self, bins, n=1024, floor=-100.0, peak=-40.0, width=3):
        p = [floor] * n
        for b in bins:
            for i in range(b - width // 2, b + width // 2 + 1):
                if 0 <= i < n:
                    p[i] = peak
        return p

    def test_correlates_from_signals_when_not_ingesting(self):
        store = SignalStore(":memory:")           # store present…
        eng = SurveyEngine(store=store, ingest=False)   # …but nothing written
        for i in range(4):
            eng.offer_frame(self._frame([500]), 433_000_000, 2_048_000, t=i * 0.1)
        emitters = eng.correlate_emitters()
        assert len(emitters) >= 1                  # was 0 before the fix (empty store)
