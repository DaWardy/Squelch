# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/rds.py — RDS/RBDS protocol decode.

Groups are encoded with valid checkwords and round-tripped back through the
synchroniser + decoder, so PS/RadioText/PI/PTY come out exactly.
"""
import pytest

from core.rds import (
    make_block, check_block, decode_group, bits_to_groups, RDSDecoder,
    OFFSETS, PTY_RBDS,
)


def _int_to_bits(v, n):
    return [(v >> (n - 1 - i)) & 1 for i in range(n)]


def _encode_group(info, version="A"):
    offs = [OFFSETS["A"], OFFSETS["B"],
            OFFSETS["Cp"] if version == "B" else OFFSETS["C"], OFFSETS["D"]]
    bits = []
    for w, off in zip(info, offs):
        bits += _int_to_bits(make_block(w, off), 26)
    return bits


def _ps_bits(ps8, pi=0x1234, pty=10, tp=0):
    ps8 = (ps8 + " " * 8)[:8]
    bits = []
    for seg in range(4):
        b = (0 << 12) | (tp << 10) | (pty << 5) | seg
        d = (ord(ps8[2 * seg]) << 8) | ord(ps8[2 * seg + 1])
        bits += _encode_group((pi, b, 0x0000, d))
    return bits


def _rt_bits(rt, pi=0x1234, pty=10, ab=0):
    rt = (rt + " " * 64)[:64]
    nseg = (len(rt.rstrip()) + 3) // 4
    bits = []
    for seg in range(nseg):
        b = (2 << 12) | (pty << 5) | (ab << 4) | seg
        s = rt[seg * 4:seg * 4 + 4]
        c = (ord(s[0]) << 8) | ord(s[1])
        d = (ord(s[2]) << 8) | ord(s[3])
        bits += _encode_group((pi, b, c, d))
    return bits


# ── block checkword ───────────────────────────────────────────────────────────

class TestBlock:
    def test_make_then_check_round_trip(self):
        for info in (0x0000, 0x1234, 0xABCD, 0xFFFF):
            blk = make_block(info, OFFSETS["A"])
            assert check_block(blk, OFFSETS["A"]) == info

    def test_wrong_offset_rejected(self):
        blk = make_block(0x1234, OFFSETS["A"])
        assert check_block(blk, OFFSETS["B"]) is None

    def test_corrupt_block_rejected(self):
        blk = make_block(0x1234, OFFSETS["C"]) ^ 0b1000   # flip a check bit
        assert check_block(blk, OFFSETS["C"]) is None


# ── group parse ───────────────────────────────────────────────────────────────

class TestDecodeGroup:
    def test_fields(self):
        b = (2 << 12) | (1 << 11) | (1 << 10) | (5 << 5) | 3   # 2B, TP=1, PTY=5
        g = decode_group((0x3ABC, b, 0x1111, 0x2222))
        assert g.pi == 0x3ABC
        assert g.group_type == 2 and g.version == "B"
        assert g.tp == 1 and g.pty == 5

    def test_short_input_none(self):
        assert decode_group((1, 2)) is None
        assert decode_group(None) is None


# ── synchroniser ──────────────────────────────────────────────────────────────

class TestSync:
    def test_syncs_and_recovers_group(self):
        bits = _encode_group((0x1234, 0x0400, 0x0000, 0x4142))
        groups = bits_to_groups(bits)
        assert len(groups) == 1
        assert groups[0].pi == 0x1234

    def test_syncs_past_leading_garbage(self):
        bits = [1, 0, 1, 1, 0] + _encode_group((0x1234, 0x0400, 0, 0x4142))
        groups = bits_to_groups(bits)
        assert len(groups) == 1 and groups[0].pi == 0x1234

    def test_empty_and_short(self):
        assert bits_to_groups([]) == []
        assert bits_to_groups([1, 0, 1]) == []


# ── PS name accumulation ──────────────────────────────────────────────────────

class TestProgrammeService:
    def test_ps_name_recovered(self):
        dec = RDSDecoder()
        dec.feed_bits(_ps_bits("SQUELCH!", pi=0x53D9, pty=15))
        assert dec.ps == "SQUELCH!"
        assert dec.pi == 0x53D9
        assert dec.pty == 15
        assert dec.pty_name == "Classical"

    def test_partial_ps(self):
        dec = RDSDecoder()
        dec.feed_bits(_ps_bits("WXYZ", pty=5))       # 4 chars + spaces
        assert dec.ps == "WXYZ"


# ── RadioText accumulation ────────────────────────────────────────────────────

class TestRadioText:
    def test_radiotext_recovered(self):
        dec = RDSDecoder()
        dec.feed_bits(_rt_bits("Squelch RDS OK"))
        assert dec.radiotext == "Squelch RDS OK"

    def test_ab_flag_clears_text(self):
        dec = RDSDecoder()
        dec.feed_bits(_rt_bits("First message", ab=0))
        dec.feed_bits(_rt_bits("Second", ab=1))       # A/B toggled → cleared
        assert dec.radiotext == "Second"


# ── state + robustness ────────────────────────────────────────────────────────

class TestStateAndRobustness:
    def test_state_dict(self):
        dec = RDSDecoder()
        dec.feed_bits(_ps_bits("KTST", pi=0x1AAA, pty=1))
        s = dec.state()
        assert s["ps"] == "KTST"
        assert s["pi_hex"] == "1AAA"
        assert s["pty_name"] == "News"

    def test_pty_table_full(self):
        assert len(PTY_RBDS) == 32

    def test_feed_none_and_garbage_safe(self):
        dec = RDSDecoder()
        dec.feed(None)                    # must not raise
        dec.feed_bits([1, 0] * 300)       # random-ish, no valid sync
        assert dec.ps == "" and dec.radiotext == ""
