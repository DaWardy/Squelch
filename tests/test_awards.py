from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for award tracking."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock
from core.awards import AwardTracker, AwardProgress, US_STATES


class TestAwardProgress:
    def test_pct_worked(self):
        ap = AwardProgress("DXCC", "Test", 100, worked=50)
        assert ap.pct_worked == 50.0

    def test_pct_worked_zero(self):
        ap = AwardProgress("DXCC", "Test", 100, worked=0)
        assert ap.pct_worked == 0.0

    def test_is_complete_false(self):
        ap = AwardProgress("DXCC", "Test", 100, worked=50)
        assert not ap.is_complete

    def test_is_complete_true(self):
        ap = AwardProgress("DXCC", "Test", 100, worked=100)
        assert ap.is_complete

    def test_is_complete_over(self):
        ap = AwardProgress("DXCC", "Test", 100, worked=150)
        assert ap.is_complete

    def test_summary_string(self):
        ap = AwardProgress("DXCC", "Test", 100, worked=42)
        s = ap.summary
        assert "42" in s
        assert "100" in s

    def test_entities_set(self):
        entities = {"K", "VE", "G"}
        ap = AwardProgress("DXCC", "Test", 100,
                           worked=3, entities=entities)
        assert len(ap.entities) == 3


class TestUSStates:
    def test_fifty_states(self):
        assert len(US_STATES) == 50

    def test_known_states(self):
        assert "CA" in US_STATES
        assert "TX" in US_STATES
        assert "NY" in US_STATES
        assert "HI" in US_STATES
        assert "AK" in US_STATES

    def test_no_territories(self):
        # Puerto Rico, Guam etc not in WAS
        assert "PR" not in US_STATES
        assert "GU" not in US_STATES


class TestAwardTracker:
    def _make_tracker(self, qsos):
        db = MagicMock()
        db.recent_qsos.return_value = qsos
        return AwardTracker(db)

    def _make_qso(self, call="W4XYZ", band="20m",
                  mode="FT8", dxcc="K", state="",
                  cqz=0, grid="DM79",
                  lotw_status=""):
        q = MagicMock()
        q.call      = call
        q.band      = band
        q.mode      = mode
        q.dxcc      = dxcc
        q.state     = state
        q.cqz       = cqz
        q.grid      = grid
        q.lotw_status = lotw_status
        return q

    def test_empty_log(self):
        tracker = self._make_tracker([])
        awards  = tracker.compute_all()
        assert awards["DXCC"].worked == 0
        assert awards["WAS"].worked  == 0

    def test_dxcc_single_entity(self):
        qsos = [self._make_qso(dxcc="G")]
        tracker = self._make_tracker(qsos)
        dxcc = tracker.compute_dxcc()
        assert dxcc.worked == 1
        assert "G" in dxcc.entities

    def test_dxcc_deduplicates(self):
        qsos = [
            self._make_qso(dxcc="G"),
            self._make_qso(dxcc="G"),  # dupe
            self._make_qso(dxcc="DL"),
        ]
        tracker = self._make_tracker(qsos)
        dxcc = tracker.compute_dxcc()
        assert dxcc.worked == 2

    def test_dxcc_confirmed(self):
        qsos = [
            self._make_qso(dxcc="G",  lotw_status="confirmed"),
            self._make_qso(dxcc="DL", lotw_status=""),
        ]
        tracker = self._make_tracker(qsos)
        dxcc = tracker.compute_dxcc()
        assert dxcc.worked    == 2
        assert dxcc.confirmed == 1

    def test_was_states(self):
        qsos = [
            self._make_qso(state="CA"),
            self._make_qso(state="TX"),
            self._make_qso(state="NY"),
        ]
        tracker = self._make_tracker(qsos)
        was = tracker.compute_was()
        assert was.worked == 3

    def test_was_invalid_state_ignored(self):
        qsos = [
            self._make_qso(state="CA"),
            self._make_qso(state="ZZ"),  # invalid
        ]
        tracker = self._make_tracker(qsos)
        was = tracker.compute_was()
        assert was.worked == 1

    def test_waz_zones(self):
        qsos = [
            self._make_qso(cqz=3),
            self._make_qso(cqz=14),
            self._make_qso(cqz=25),
        ]
        tracker = self._make_tracker(qsos)
        waz = tracker._waz(qsos)
        assert waz.worked == 3

    def test_vucc_grids(self):
        qsos = [
            self._make_qso(band="6m", grid="DM79"),
            self._make_qso(band="6m", grid="FM18"),
            self._make_qso(band="20m", grid="DM79"),  # HF - not counted
        ]
        tracker = self._make_tracker(qsos)
        vucc = tracker._vucc(qsos)
        assert vucc.worked == 2

    def test_dxcc_mode_filter(self):
        qsos = [
            self._make_qso(dxcc="G",  mode="FT8"),
            self._make_qso(dxcc="DL", mode="CW"),
            self._make_qso(dxcc="JA", mode="FT8"),
        ]
        tracker = self._make_tracker(qsos)
        dxcc_ft8 = tracker._dxcc_mode(qsos, "FT8")
        assert dxcc_ft8.worked == 2

    def test_compute_all_returns_dict(self):
        tracker = self._make_tracker([])
        awards  = tracker.compute_all()
        assert "DXCC" in awards
        assert "WAS" in awards
        assert "WAZ" in awards
        assert "VUCC" in awards
        assert "DXCC-FT8" in awards
