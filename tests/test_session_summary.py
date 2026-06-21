"""Tests for session summary: LogDB.session_stats() and dialog."""
from __future__ import annotations
import sys
import sqlite3
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))


def _make_db_with_qsos(qsos: list[tuple]) -> "LogDB":
    """Create an in-memory LogDB and insert
    (call, band, mode, dxcc, lat, lon, my_lat, my_lon, dt) rows.
    Pass lat=lon=0 to get dist_km=0 (no coords).
    """
    from core.log_db import LogDB
    db = LogDB(":memory:")
    for call, band, mode, dxcc, lat, lon, my_lat, my_lon, dt in qsos:
        db._conn.execute(
            "INSERT INTO qso "
            "(call, band, mode, dxcc, lat, lon, my_lat, my_lon, datetime_on) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (call, band, mode, dxcc, lat, lon, my_lat, my_lon, dt))
    db._conn.commit()
    return db


T0 = "2026-06-21T12:00:00Z"   # session start
T1 = "2026-06-21T12:30:00Z"   # 30 min in
T2 = "2026-06-21T13:00:00Z"   # 1 h in
PRE = "2026-06-21T10:00:00Z"  # before session


# lat/lon helpers for distance tests
# NYC ≈ (40.7, -74.0), London ≈ (51.5, 0.0) → ~5570 km
# Tokyo ≈ (35.7, 139.7) → ~10800 km from NYC
_NYC  = (40.7, -74.0)
_LON  = (51.5,   0.0)
_TYO  = (35.7, 139.7)


def _row(call, band, mode, dxcc, lat=0, lon=0, my_lat=0, my_lon=0, dt=T1):
    return (call, band, mode, dxcc, lat, lon, my_lat, my_lon, dt)


class TestSessionStatsEmpty:
    def test_empty_db_returns_zero_total(self):
        db = _make_db_with_qsos([])
        s = db.session_stats(T0)
        assert s["total"] == 0

    def test_empty_db_returns_empty_bands(self):
        db = _make_db_with_qsos([])
        s = db.session_stats(T0)
        assert s["bands"] == {}

    def test_empty_db_returns_zero_new_dxcc(self):
        db = _make_db_with_qsos([])
        s = db.session_stats(T0)
        assert s["new_dxcc"] == 0

    def test_empty_db_no_best_dist(self):
        db = _make_db_with_qsos([])
        s = db.session_stats(T0)
        assert s["best_dist_km"] is None


class TestSessionStatsTotal:
    def test_counts_only_session_qsos(self):
        db = _make_db_with_qsos([
            _row("W1AW",  "20m", "FT8", "W",  dt=T1),
            _row("JA1XX", "15m", "CW",  "JA", dt=T2),
            _row("VK2XX", "40m", "SSB", "VK", dt=PRE),  # before session
        ])
        s = db.session_stats(T0)
        assert s["total"] == 2

    def test_pre_session_qsos_excluded(self):
        db = _make_db_with_qsos([
            _row("VK2XX", "40m", "SSB", "VK", dt=PRE),
        ])
        s = db.session_stats(T0)
        assert s["total"] == 0


class TestSessionStatsBands:
    def test_band_counts_correct(self):
        db = _make_db_with_qsos([
            _row("W1AW",  "20m", "FT8", "W",  dt=T1),
            _row("K1ABC", "20m", "FT8", "W",  dt=T2),
            _row("JA1XX", "15m", "CW",  "JA", dt=T1),
        ])
        s = db.session_stats(T0)
        assert s["bands"]["20m"] == 2
        assert s["bands"]["15m"] == 1

    def test_bands_sorted_by_count_desc(self):
        db = _make_db_with_qsos([
            _row("W1AW",  "20m", "FT8", "W",  dt=T1),
            _row("K1AA",  "20m", "FT8", "W",  dt=T2),
            _row("JA1XX", "15m", "CW",  "JA", dt=T1),
        ])
        s = db.session_stats(T0)
        bands = list(s["bands"].keys())
        assert bands[0] == "20m"


class TestSessionStatsNewDXCC:
    def test_new_dxcc_when_none_pre_session(self):
        db = _make_db_with_qsos([
            _row("JA1XX", "20m", "FT8", "JA", dt=T1),
            _row("VK2XX", "40m", "SSB", "VK", dt=T2),
        ])
        s = db.session_stats(T0)
        assert s["new_dxcc"] == 2

    def test_new_dxcc_excludes_previously_worked(self):
        db = _make_db_with_qsos([
            _row("JA9XX",  "40m", "SSB", "JA", dt=PRE),  # before session
            _row("JA1XXX", "20m", "FT8", "JA", dt=T1),   # same entity — not new
            _row("VK2XX",  "20m", "CW",  "VK", dt=T2),   # new entity
        ])
        s = db.session_stats(T0)
        assert s["new_dxcc"] == 1

    def test_new_dxcc_ignores_empty_entity(self):
        db = _make_db_with_qsos([
            _row("W1XYZ", "20m", "FT8", "", dt=T1),
        ])
        s = db.session_stats(T0)
        assert s["new_dxcc"] == 0


class TestSessionStatsBestDX:
    def test_best_dist_found(self):
        # NYC→London ~5570 km; NYC→Tokyo ~10800 km
        db = _make_db_with_qsos([
            _row("G3ABC",  "20m", "CW", "G",
                 lat=_LON[0], lon=_LON[1],
                 my_lat=_NYC[0], my_lon=_NYC[1], dt=T1),
            _row("JA1XX",  "15m", "FT8", "JA",
                 lat=_TYO[0], lon=_TYO[1],
                 my_lat=_NYC[0], my_lon=_NYC[1], dt=T2),
        ])
        s = db.session_stats(T0)
        assert s["best_dist_km"] is not None
        assert s["best_dist_km"] > 9000   # Tokyo is further
        assert s["best_dist_call"] == "JA1XX"

    def test_best_dist_none_when_no_coords(self):
        # lat/lon all 0 → _has_coords() returns False → dist_km = 0.0
        db = _make_db_with_qsos([
            _row("W1AW", "20m", "FT8", "W", dt=T1),
        ])
        s = db.session_stats(T0)
        assert s["best_dist_km"] is None
