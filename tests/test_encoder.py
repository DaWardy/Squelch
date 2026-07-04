# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/encoder.py — frame builder + modulator (ENC-BUILD).

The strongest checks are round-trips: encode a payload, then recover it with
the bit-slicer + framing inspector and confirm it matches. This validates the
encoder against the decoder built in the same phase.
"""
import numpy as np
import pytest

from core.encoder import (
    alternating_preamble, build_frame, modulate, encode_iq, EncodeResult,
)
from core.bitslicer import slice_bits, bits_to_bytes, OOK, FSK, PSK
from core.framing import inspect_frame, _normalize_pattern

FS = 48_000.0
SPS = 40


def _match_or_inverted(got, want):
    want = list(want)
    return got == want or got == [1 - b for b in want]


# ── frame assembly ────────────────────────────────────────────────────────────

class TestBuildFrame:
    def test_preamble_alternating(self):
        assert alternating_preamble(6) == [0, 1, 0, 1, 0, 1]
        assert alternating_preamble(4, first=1) == [1, 0, 1, 0]

    def test_frame_layout_lengths(self):
        bits = build_frame(b"HI", preamble_bits=32, sync_word="D391",
                           crc="CRC-16/CCITT-FALSE")
        # 32 preamble + 16 sync + 16 payload (2 bytes) + 16 crc
        assert len(bits) == 32 + 16 + 16 + 16

    def test_payload_from_hex(self):
        bits = build_frame("4142", preamble_bits=0, sync_word=None, crc=None)
        assert bits_to_bytes(bits) == b"AB"

    def test_crc_appended_matches_framing(self):
        bits = build_frame(b"HELLO", preamble_bits=0, sync_word=None,
                           crc="CRC-16/CCITT-FALSE")
        r = inspect_frame(bits, crc_bits=16)
        assert r.crc_ok is True
        assert "CRC-16/CCITT-FALSE" in r.crc_matches

    def test_no_crc_no_sync(self):
        bits = build_frame(b"X", preamble_bits=8)
        assert len(bits) == 8 + 8


# ── modulation shape ──────────────────────────────────────────────────────────

class TestModulate:
    def test_length_and_dtype(self):
        iq = modulate([1, 0, 1, 1], FS, family=OOK, samples_per_symbol=SPS)
        assert iq.dtype == np.complex64
        assert iq.size == 4 * SPS

    def test_ook_off_is_silent(self):
        iq = modulate([0], FS, family=OOK, samples_per_symbol=SPS)
        assert np.allclose(np.abs(iq), 0.0)

    def test_ook_on_has_power(self):
        iq = modulate([1], FS, family=OOK, samples_per_symbol=SPS,
                      amplitude=1.0)
        assert np.mean(np.abs(iq)) > 0.9

    def test_symbol_rate_from_baud(self):
        iq = modulate([1, 0], FS, family=FSK, symbol_rate=1200.0)
        assert iq.size == 2 * int(FS / 1200)

    def test_empty_bits(self):
        assert modulate([], FS, family=OOK).size == 0

    def test_zero_fs(self):
        assert modulate([1, 0], 0.0, family=OOK).size == 0


# ── round-trips (encode → decode) ─────────────────────────────────────────────

class TestRoundTrip:
    PAYLOAD = b"HI"

    def _frame_bits(self, family, crc="CRC-16/CCITT-FALSE"):
        return build_frame(self.PAYLOAD, preamble_bits=32, sync_word="D391",
                           crc=crc)

    def test_ook_full_frame_round_trip(self):
        bits = self._frame_bits(OOK)
        iq = modulate(bits, FS, family=OOK, samples_per_symbol=SPS)
        got = slice_bits(iq, FS, family=OOK, samples_per_symbol=SPS)
        assert got.bits == bits                    # exact
        r = inspect_frame(got.bits, sync_word="D391", crc_bits=16)
        assert r.crc_ok is True
        assert r.payload.hex == self.PAYLOAD.hex()

    def test_fsk_full_frame_round_trip(self):
        bits = self._frame_bits(FSK)
        iq = modulate(bits, FS, family=FSK, samples_per_symbol=SPS)
        got = slice_bits(iq, FS, family=FSK, samples_per_symbol=SPS)
        assert got.bits == bits                    # FSK sense is deterministic here
        r = inspect_frame(got.bits, sync_word="D391", crc_bits=16)
        assert r.crc_ok is True

    def test_psk_symbols_round_trip_up_to_inversion(self):
        bits = self._frame_bits(PSK)
        iq = modulate(bits, FS, family=PSK, samples_per_symbol=SPS)
        got = slice_bits(iq, FS, family=PSK, samples_per_symbol=SPS)
        assert _match_or_inverted(got.bits, bits)  # BPSK 180° ambiguity

    def test_round_trip_with_estimated_sps(self):
        bits = self._frame_bits(OOK)
        iq = modulate(bits, FS, family=OOK, samples_per_symbol=SPS)
        got = slice_bits(iq, FS, family=OOK)       # let the slicer estimate sps
        assert got.bits == bits


# ── one-shot encode_iq ────────────────────────────────────────────────────────

class TestEncodeIq:
    def test_returns_result_with_iq(self):
        res = encode_iq(b"AB", FS, family=OOK, sync_word="D391",
                        crc="CRC-16/CCITT-FALSE", samples_per_symbol=SPS)
        assert isinstance(res, EncodeResult)
        assert res.iq.dtype == np.complex64
        assert res.family == OOK
        assert res.samples_per_symbol == SPS
        assert res.symbol_rate == pytest.approx(FS / SPS)
        assert res.iq.size == len(res.bits) * SPS

    def test_encode_iq_is_decodable(self):
        res = encode_iq(b"OK", FS, family=OOK, sync_word="D391",
                        crc="CRC-16/CCITT-FALSE", samples_per_symbol=SPS)
        got = slice_bits(res.iq, FS, family=OOK, samples_per_symbol=SPS)
        r = inspect_frame(got.bits, sync_word="D391", crc_bits=16)
        assert r.crc_ok is True
        assert r.payload.hex == b"OK".hex()

    def test_empty_payload_still_valid(self):
        res = encode_iq(b"", FS, family=OOK, preamble_bits=16,
                        samples_per_symbol=SPS)
        assert res.iq.size == len(res.bits) * SPS
