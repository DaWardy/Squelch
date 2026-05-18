from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for propagation data structures (offline)."""

import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from network.propagation import SolarData, BandCondition


class TestSolarData:
    def test_defaults(self):
        s = SolarData()
        assert s.sfi == 0.0
        assert s.k_index == 0.0
        assert s.a_index == 0.0

    def test_conditions_summary_returns_string(self):
        s = SolarData()
        s.sfi = 65.0
        s.k_index = 1.0
        summary = s.conditions_summary
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_good_conditions_summary(self):
        s = SolarData()
        s.sfi = 150.0
        s.k_index = 0.0
        assert isinstance(s.conditions_summary, str)

    def test_fetched_at(self):
        s = SolarData()
        assert s.fetched_at >= 0


class TestBandCondition:
    def test_defaults(self):
        bc = BandCondition(band="20m", condition="good")
        assert bc.band == "20m"

    def test_condition_field(self):
        bc = BandCondition(band="20m", condition="good")
        assert bc.condition == "good"

    def test_color_field(self):
        bc = BandCondition(band="20m",
                           condition="good",
                           color="#3fbe6f")
        assert bc.color == "#3fbe6f"
