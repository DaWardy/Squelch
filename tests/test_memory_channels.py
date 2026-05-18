from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for memory channel management and CHIRP export."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import tempfile
from core.memory_channels import (
    MemoryChannel, MemoryBank)


class TestMemoryChannel:
    def test_defaults(self):
        ch = MemoryChannel(number=1)
        assert ch.number == 1
        assert ch.mode == "FM"
        assert ch.duplex == ""

    def test_rx_freq_simplex(self):
        ch = MemoryChannel(number=1, freq_mhz=146.520)
        assert ch.rx_mhz == 146.520

    def test_rx_freq_positive_offset(self):
        ch = MemoryChannel(number=1, freq_mhz=146.940,
                           duplex="+", offset_mhz=0.600)
        assert abs(ch.rx_mhz - 147.540) < 0.001

    def test_rx_freq_negative_offset(self):
        ch = MemoryChannel(number=1, freq_mhz=146.940,
                           duplex="-", offset_mhz=0.600)
        assert abs(ch.rx_mhz - 146.340) < 0.001

    def test_is_digital_fm(self):
        ch = MemoryChannel(number=1, mode="FM")
        assert not ch.is_digital

    def test_is_digital_dv(self):
        ch = MemoryChannel(number=1, mode="DV")
        assert ch.is_digital

    def test_is_digital_dmr(self):
        ch = MemoryChannel(number=1, mode="DMR")
        assert ch.is_digital


class TestMemoryBank:
    def test_empty(self):
        bank = MemoryBank()
        assert len(bank) == 0

    def test_add_channel(self):
        bank = MemoryBank()
        ch   = MemoryChannel(number=1,
                             freq_mhz=146.520,
                             name="SIMP")
        bank.add(ch)
        assert len(bank) == 1

    def test_get_channel(self):
        bank = MemoryBank()
        ch   = MemoryChannel(number=5,
                             freq_mhz=146.520)
        bank.add(ch)
        assert bank.get(5) is ch
        assert bank.get(9) is None

    def test_remove_channel(self):
        bank = MemoryBank()
        bank.add(MemoryChannel(number=1, freq_mhz=146.52))
        bank.remove(1)
        assert len(bank) == 0

    def test_next_free(self):
        bank = MemoryBank()
        bank.add(MemoryChannel(number=0, freq_mhz=1.0))
        bank.add(MemoryChannel(number=1, freq_mhz=1.0))
        bank.add(MemoryChannel(number=2, freq_mhz=1.0))
        assert bank.next_free() == 3

    def test_all_channels_sorted(self):
        bank = MemoryBank()
        bank.add(MemoryChannel(number=5, freq_mhz=5.0))
        bank.add(MemoryChannel(number=1, freq_mhz=1.0))
        bank.add(MemoryChannel(number=3, freq_mhz=3.0))
        nums = [ch.number for ch in bank.all_channels()]
        assert nums == [1, 3, 5]

    def test_iter(self):
        bank = MemoryBank()
        for i in range(3):
            bank.add(MemoryChannel(number=i,
                                   freq_mhz=float(i)))
        channels = list(bank)
        assert len(channels) == 3


class TestChirpExport:
    def test_to_chirp_csv_has_header(self):
        bank = MemoryBank()
        bank.add(MemoryChannel(
            number=0, name="TEST",
            freq_mhz=146.520, mode="FM"))
        csv = bank.to_chirp_csv()
        assert "Location" in csv
        assert "Frequency" in csv
        assert "Duplex" in csv

    def test_to_chirp_csv_has_data(self):
        bank = MemoryBank()
        bank.add(MemoryChannel(
            number=0, name="RPTR",
            freq_mhz=146.940, duplex="-",
            offset_mhz=0.600, ctcss_tone=100.0,
            tone_mode="Tone"))
        csv = bank.to_chirp_csv()
        assert "146.940" in csv
        assert "RPTR" in csv

    def test_save_chirp_csv(self, tmp_path):
        bank = MemoryBank()
        bank.add(MemoryChannel(
            number=0, freq_mhz=146.520))
        bank.add(MemoryChannel(
            number=1, freq_mhz=147.120))
        out = tmp_path / "test.csv"
        count = bank.save_chirp_csv(out)
        assert count == 2
        assert out.exists()
        content = out.read_text()
        assert "146.520" in content
        assert "147.120" in content

    def test_empty_bank_csv(self):
        bank = MemoryBank()
        csv  = bank.to_chirp_csv()
        # Should have header even with no data
        assert "Location" in csv
        lines = csv.strip().splitlines()
        assert len(lines) == 1  # header only
