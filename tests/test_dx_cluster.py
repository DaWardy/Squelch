from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for DX cluster spot structure."""

import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from network.dx_cluster import DXSpot


class TestDXSpot:
    def test_create_spot(self):
        spot = DXSpot(
            callsign="W4XYZ",
            freq_hz=14074000,
            spotter="W1AW",
            mode="FT8")
        assert spot.callsign == "W4XYZ"
        assert spot.freq_hz == 14074000
        assert spot.spotter == "W1AW"

    def test_band_from_freq(self):
        from core.band_plan import band_at_freq
        assert band_at_freq(14074000).name == "20m"
        assert band_at_freq(7074000).name  == "40m"
        assert band_at_freq(3573000).name  == "80m"
        assert band_at_freq(28074000).name == "10m"

    def test_defaults(self):
        spot = DXSpot(callsign="W4XYZ",
                      freq_hz=14074000,
                      spotter="W1AW")
        assert spot.is_new_dxcc is False
        assert spot.is_wanted is False
        assert spot.timestamp > 0

    def test_source_field(self):
        spot = DXSpot(callsign="W4XYZ",
                      freq_hz=14074000,
                      spotter="W1AW",
                      source="PSKReporter")
        assert spot.source == "PSKReporter"
