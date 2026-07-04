# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/framing.py — protocol framing inspector (DEC-FRAMING).

CRC correctness is anchored to the industry-standard check vector: the CRC of
the ASCII string "123456789" is a published constant for each algorithm.
"""
import pytest

from core.framing import (
    bits_to_int, longest_alternating_run, find_preamble, find_sync,
    compute_crc, check_crc, identify_crc, inspect_frame,
    _normalize_pattern, CRC_ALGOS,
)
from core.bitslicer import bits_to_bytes

CHECK = b"123456789"


def _bytes_to_bits(data: bytes) -> list:
    out = []
    for byte in data:
        out.extend((byte >> i) & 1 for i in range(7, -1, -1))
    return out


def _int_to_bits(value: int, width: int) -> list:
    return [(value >> i) & 1 for i in range(width - 1, -1, -1)]


# ── standard CRC check vectors ────────────────────────────────────────────────

class TestCrcCheckVectors:
    # published "check" values for "123456789"
    EXPECTED = {
        "CRC-8":              0xF4,
        "CRC-16/CCITT-FALSE": 0x29B1,
        "CRC-16/XMODEM":      0x31C3,
        "CRC-16/ARC":         0xBB3D,
        "CRC-32":             0xCBF43926,
    }

    def test_all_algorithms_match_published_check(self):
        for name, want in self.EXPECTED.items():
            assert compute_crc(CHECK, name) == want, name

    def test_registry_complete(self):
        assert set(CRC_ALGOS) == set(self.EXPECTED)


# ── bit helpers ───────────────────────────────────────────────────────────────

class TestBitHelpers:
    def test_bits_to_int_msb_first(self):
        assert bits_to_int([1, 0, 0, 0, 0, 0, 0, 1]) == 0x81

    def test_normalize_from_hex(self):
        assert _normalize_pattern("A5") == [1, 0, 1, 0, 0, 1, 0, 1]

    def test_normalize_from_bytes(self):
        assert _normalize_pattern(b"\xa5") == [1, 0, 1, 0, 0, 1, 0, 1]

    def test_normalize_from_bits(self):
        assert _normalize_pattern([1, 0, 1, 0]) == [1, 0, 1, 0]


# ── preamble ──────────────────────────────────────────────────────────────────

class TestPreamble:
    def test_longest_alternating_run(self):
        bits = [0, 0, 1, 0, 1, 0, 1, 0, 1, 1]      # run 01010101 from index 1
        start, length = longest_alternating_run(bits)
        assert length == 8
        assert start == 1

    def test_find_preamble_at_start(self):
        bits = [0, 1] * 12 + [1, 1, 0, 0]
        pre = find_preamble(bits, min_len=8)
        assert pre is not None
        assert pre[0] == 0 and pre[1] == 24

    def test_preamble_too_short_is_none(self):
        assert find_preamble([0, 1, 0, 1, 1, 1, 1, 1], min_len=8) is None

    def test_preamble_too_late_is_none(self):
        bits = [1] * 20 + [0, 1] * 10             # alternating run starts late
        assert find_preamble(bits, min_len=8, max_start=8) is None

    def test_empty(self):
        assert longest_alternating_run([]) == (0, 0)


# ── sync ──────────────────────────────────────────────────────────────────────

class TestSync:
    def test_find_sync_offsets(self):
        pat = [1, 1, 1, 0]
        bits = [0, 0] + pat + [0, 1] + pat
        offs = find_sync(bits, pat)
        assert offs == [2, 8]

    def test_find_sync_hex(self):
        sync = _normalize_pattern("D3")
        bits = [0, 0, 0] + sync + [1, 1]
        assert find_sync(bits, "D3") == [3]

    def test_no_match(self):
        assert find_sync([0, 0, 0, 0], [1, 1]) == []

    def test_pattern_longer_than_bits(self):
        assert find_sync([1, 0], [1, 0, 1, 0]) == []


# ── CRC over bits ─────────────────────────────────────────────────────────────

class TestCrcOverBits:
    def test_check_crc_true(self):
        data_bits = _bytes_to_bits(CHECK)
        crc_bits = _int_to_bits(0x29B1, 16)
        assert check_crc(data_bits, crc_bits, "CRC-16/CCITT-FALSE") is True

    def test_check_crc_false_on_corruption(self):
        data_bits = _bytes_to_bits(CHECK)
        crc_bits = _int_to_bits(0x0000, 16)
        assert check_crc(data_bits, crc_bits, "CRC-16/CCITT-FALSE") is False

    def test_identify_crc_finds_algorithm(self):
        data_bits = _bytes_to_bits(CHECK)
        crc_bits = _int_to_bits(0xBB3D, 16)
        assert "CRC-16/ARC" in identify_crc(data_bits, crc_bits)

    def test_identify_crc_empty_when_none_match(self):
        data_bits = _bytes_to_bits(CHECK)
        crc_bits = _int_to_bits(0x1234, 16)
        assert identify_crc(data_bits, crc_bits) == []

    def test_identify_crc8(self):
        data_bits = _bytes_to_bits(CHECK)
        crc_bits = _int_to_bits(0xF4, 8)
        assert "CRC-8" in identify_crc(data_bits, crc_bits)


# ── end-to-end frame inspection ───────────────────────────────────────────────

class TestInspectFrame:
    def _frame(self, payload: bytes, crc_name="CRC-16/CCITT-FALSE",
               crc_width=16, sync_hex="D391"):
        preamble = [0, 1] * 16
        sync = _normalize_pattern(sync_hex)
        payload_bits = _bytes_to_bits(payload)
        crc_val = compute_crc(payload, crc_name)
        crc_bits = _int_to_bits(crc_val, crc_width)
        return preamble + sync + payload_bits + crc_bits, sync, payload_bits

    def test_full_frame_parsed(self):
        bits, sync, payload_bits = self._frame(b"HELLO")
        r = inspect_frame(bits, sync_word="D391", crc_bits=16)
        assert r.preamble is not None and r.preamble.length == 32
        assert r.sync is not None and r.sync.length == len(sync)
        assert r.payload is not None
        assert r.payload.bits == payload_bits
        assert r.crc_ok is True
        assert "CRC-16/CCITT-FALSE" in r.crc_matches

    def test_payload_hex_recovered(self):
        bits, _, _ = self._frame(b"AB")
        r = inspect_frame(bits, sync_word="D391", crc_bits=16)
        assert r.payload.hex == b"AB".hex()      # "4142"

    def test_corrupt_crc_flagged(self):
        bits, sync, payload_bits = self._frame(b"HELLO")
        bits[-1] ^= 1                              # flip a CRC bit
        r = inspect_frame(bits, sync_word="D391", crc_bits=16)
        assert r.crc_ok is False
        assert "no known CRC matched" in r.notes

    def test_missing_sync_noted(self):
        bits = [0, 1] * 16 + _bytes_to_bits(b"XY")
        r = inspect_frame(bits, sync_word="FFFF")
        assert r.sync is None
        assert "sync word not found" in r.notes

    def test_no_sync_no_crc_all_payload(self):
        # payload starts with 1 (== preamble's trailing bit) so the alternating
        # run ends cleanly at the 32-bit boundary
        bits = [0, 1] * 16 + _bytes_to_bits(b"\xc3\xc3\xc3\xc3")
        r = inspect_frame(bits)
        assert r.preamble.length == 32
        assert r.payload.length == 32              # 4 bytes of payload
        assert r.crc is None

    def test_crc32_frame(self):
        bits, _, payload_bits = self._frame(b"telemetry",
                                            crc_name="CRC-32", crc_width=32)
        r = inspect_frame(bits, sync_word="D391", crc_bits=32)
        assert r.crc_ok is True
        assert "CRC-32" in r.crc_matches

    def test_empty_input(self):
        r = inspect_frame([])
        assert r.total_bits == 0
        assert r.payload is not None and r.payload.length == 0


# ── robustness ────────────────────────────────────────────────────────────────

def test_never_raises_on_random_bits():
    import random
    rng = random.Random(0)
    for _ in range(20):
        bits = [rng.randint(0, 1) for _ in range(rng.randint(0, 200))]
        r = inspect_frame(bits, sync_word="A55A", crc_bits=16)
        assert r is not None
