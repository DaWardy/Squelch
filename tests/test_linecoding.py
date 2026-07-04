# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
"""Tests for core/linecoding.py — Manchester / NRZI / differential (Phase 4).

Each scheme's headline test is a round-trip (encode∘decode == identity); the
rest pin down conventions, phase detection, and known vectors.
"""
import random
import pytest

from core.linecoding import (
    MANCHESTER_IEEE, MANCHESTER_THOMAS, ManchesterResult,
    encode_manchester, decode_manchester,
    encode_nrzi, decode_nrzi,
    encode_differential, decode_differential,
)

DATA = [1, 0, 1, 1, 0, 0, 1, 0, 1, 1, 1, 0]


def _rand_bits(rng, n):
    return [rng.randint(0, 1) for _ in range(n)]


# ── Manchester ────────────────────────────────────────────────────────────────

class TestManchester:
    def test_ieee_chip_mapping(self):
        # bit 1 → [0,1] (rising), bit 0 → [1,0] (falling)
        assert encode_manchester([1, 0]) == [0, 1, 1, 0]

    def test_thomas_is_inverse_mapping(self):
        assert encode_manchester([1, 0], MANCHESTER_THOMAS) == [1, 0, 0, 1]

    def test_round_trip_ieee(self):
        chips = encode_manchester(DATA)
        r = decode_manchester(chips)
        assert r.bits == DATA
        assert r.errors == 0

    def test_round_trip_thomas(self):
        chips = encode_manchester(DATA, MANCHESTER_THOMAS)
        r = decode_manchester(chips, MANCHESTER_THOMAS)
        assert r.bits == DATA
        assert r.errors == 0

    def test_phase_autodetect_with_leading_chip(self):
        # a stray leading chip shifts alignment by one; auto-detect recovers it
        chips = [1] + encode_manchester(DATA)
        r = decode_manchester(chips)          # offset auto
        assert r.offset == 1
        assert r.bits == DATA
        assert r.errors == 0

    def test_invalid_pairs_counted(self):
        # 00 and 11 are non-transitioning → invalid chip pairs.
        # Force offset 0 (auto-detect would slide to a cleaner alignment).
        r = decode_manchester([0, 0, 1, 1, 0, 1], offset=0)
        assert r.errors == 2

    def test_explicit_offset(self):
        chips = encode_manchester(DATA)
        r = decode_manchester(chips, offset=0)
        assert r.bits == DATA

    def test_empty(self):
        assert decode_manchester([]).bits == []
        assert encode_manchester([]) == []

    def test_random_round_trips(self):
        rng = random.Random(1)
        for _ in range(50):
            data = _rand_bits(rng, rng.randint(0, 40))
            assert decode_manchester(encode_manchester(data)).bits == data


# ── NRZI ──────────────────────────────────────────────────────────────────────

class TestNrzi:
    def test_transition_is_one(self):
        # bit 1 flips the level, bit 0 holds it (init level 0)
        assert encode_nrzi([1, 1, 0, 1]) == [1, 0, 0, 1]

    def test_round_trip(self):
        assert decode_nrzi(encode_nrzi(DATA)) == DATA

    def test_transition_bit_zero_variant(self):
        levels = encode_nrzi(DATA, transition_bit=0)
        assert decode_nrzi(levels, transition_bit=0) == DATA

    def test_init_level_respected(self):
        levels = encode_nrzi(DATA, init=1)
        assert decode_nrzi(levels, init=1) == DATA

    def test_empty(self):
        assert encode_nrzi([]) == []
        assert decode_nrzi([]) == []

    def test_random_round_trips(self):
        rng = random.Random(2)
        for _ in range(50):
            data = _rand_bits(rng, rng.randint(0, 40))
            assert decode_nrzi(encode_nrzi(data)) == data


# ── differential ──────────────────────────────────────────────────────────────

class TestDifferential:
    def test_round_trip(self):
        assert decode_differential(encode_differential(DATA)) == DATA

    def test_known_vector(self):
        # coded[i] = coded[i-1] ^ bit[i], init 0
        assert encode_differential([1, 0, 0, 1]) == [1, 1, 1, 0]

    def test_init_respected(self):
        coded = encode_differential(DATA, init=1)
        assert decode_differential(coded, init=1) == DATA

    def test_empty(self):
        assert encode_differential([]) == []
        assert decode_differential([]) == []

    def test_random_round_trips(self):
        rng = random.Random(3)
        for _ in range(50):
            data = _rand_bits(rng, rng.randint(0, 40))
            assert decode_differential(encode_differential(data)) == data


# ── integration with the framing inspector ────────────────────────────────────

def test_manchester_then_framing():
    """Line-decode Manchester chips, then parse the frame — the intended chain."""
    from core.framing import inspect_frame, compute_crc
    from core.bitslicer import bits_to_bytes

    def _int_to_bits(v, w):
        return [(v >> i) & 1 for i in range(w - 1, -1, -1)]

    payload = list("10110010")            # 8 bits
    payload = [int(c) for c in payload]
    crc = _int_to_bits(compute_crc(bits_to_bytes(payload), "CRC-8"), 8)
    frame = [0, 1] * 8 + payload + crc
    chips = encode_manchester(frame)      # transmit-side line coding
    bits = decode_manchester(chips).bits  # receive-side un-coding
    assert bits == frame
    r = inspect_frame(bits, crc_bits=8)
    assert r.crc_ok is True


def test_never_raises_on_garbage():
    rng = random.Random(0)
    for _ in range(20):
        junk = _rand_bits(rng, rng.randint(0, 100))
        assert isinstance(decode_manchester(junk), ManchesterResult)
        assert isinstance(decode_nrzi(junk), list)
        assert isinstance(decode_differential(junk), list)
