"""Tests for ADIF import helpers and LogDB.has_qso_at / search_qsos date filter."""
from __future__ import annotations
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest
from datetime import datetime, timezone

# ── _adif_to_iso helper (tested without Qt) ──────────────────────────────────

def _adif_to_iso(date_str: str, time_str: str) -> str:
    """Mirror of ui/tabs/log_tab._adif_to_iso for isolated testing."""
    if not date_str or len(date_str) < 8:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        y = int(date_str[:4])
        m = int(date_str[4:6])
        d = int(date_str[6:8])
        h  = int(time_str[:2]) if len(time_str) >= 2 else 0
        mn = int(time_str[2:4]) if len(time_str) >= 4 else 0
        sc = int(time_str[4:6]) if len(time_str) >= 6 else 0
        return f"{y:04d}-{m:02d}-{d:02d}T{h:02d}:{mn:02d}:{sc:02d}Z"
    except (ValueError, TypeError):
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class TestAdifToIso:
    def test_basic_hhmm(self):
        assert _adif_to_iso("20240504", "1432") == "2024-05-04T14:32:00Z"

    def test_basic_hhmmss(self):
        assert _adif_to_iso("20240101", "092345") == "2024-01-01T09:23:45Z"

    def test_midnight_time(self):
        assert _adif_to_iso("20241231", "0000") == "2024-12-31T00:00:00Z"

    def test_missing_time_defaults_zero(self):
        result = _adif_to_iso("20240601", "")
        assert result == "2024-06-01T00:00:00Z"

    def test_empty_date_returns_current_time(self):
        result = _adif_to_iso("", "1200")
        # Just check it parses as a datetime (not empty)
        dt = datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ")
        assert dt.year >= 2024

    def test_invalid_date_returns_current_time(self):
        result = _adif_to_iso("BADDATE", "1200")
        dt = datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ")
        assert dt.year >= 2024

    def test_short_date_returns_current_time(self):
        result = _adif_to_iso("2024", "1200")
        dt = datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ")
        assert dt.year >= 2024


# ── LogDB.has_qso_at ─────────────────────────────────────────────────────────

from core.log_db import LogDB, QSO


@pytest.fixture()
def db(tmp_path):
    d = LogDB(tmp_path / "test.db")
    yield d
    d.close()


class TestHasQsoAt:
    def test_returns_false_when_empty(self, db):
        assert db.has_qso_at("W1AW", "2024-05-04T14:32") is False

    def test_returns_true_after_insert(self, db):
        q = QSO(call="W1AW", band="20m", mode="FT8",
                datetime_on="2024-05-04T14:32:00Z")
        db.log_qso(q)
        assert db.has_qso_at("W1AW", "2024-05-04T14:32") is True

    def test_prefix_match_only(self, db):
        q = QSO(call="W1AW", band="20m", mode="FT8",
                datetime_on="2024-05-04T14:32:00Z")
        db.log_qso(q)
        # Different minute — should not match
        assert db.has_qso_at("W1AW", "2024-05-04T14:33") is False

    def test_case_insensitive_call(self, db):
        q = QSO(call="W1AW", band="20m", mode="FT8",
                datetime_on="2024-05-04T14:32:00Z")
        db.log_qso(q)
        assert db.has_qso_at("w1aw", "2024-05-04T14:32") is True

    def test_different_call_not_matched(self, db):
        q = QSO(call="W1AW", band="20m", mode="FT8",
                datetime_on="2024-05-04T14:32:00Z")
        db.log_qso(q)
        assert db.has_qso_at("K1ABC", "2024-05-04T14:32") is False


# ── search_qsos date filter ───────────────────────────────────────────────────

class TestSearchQsosDateFilter:
    def _add(self, db, call, dt):
        q = QSO(call=call, band="20m", mode="FT8", datetime_on=dt)
        db.log_qso(q)

    def test_date_from_excludes_older(self, db):
        self._add(db, "W1AW",  "2023-06-01T10:00:00Z")
        self._add(db, "K1ABC", "2024-06-01T10:00:00Z")
        results = db.search_qsos(date_from="2024-01-01")
        calls = [q.call for q in results]
        assert "K1ABC" in calls
        assert "W1AW" not in calls

    def test_date_to_excludes_newer(self, db):
        self._add(db, "W1AW",  "2023-06-01T10:00:00Z")
        self._add(db, "K1ABC", "2024-06-01T10:00:00Z")
        results = db.search_qsos(date_to="2023-12-31")
        calls = [q.call for q in results]
        assert "W1AW" in calls
        assert "K1ABC" not in calls

    def test_date_range_inclusive(self, db):
        self._add(db, "W1AW",  "2024-03-15T10:00:00Z")
        self._add(db, "K1ABC", "2024-06-01T10:00:00Z")
        self._add(db, "N0XYZ", "2024-09-20T10:00:00Z")
        results = db.search_qsos(date_from="2024-03-15", date_to="2024-06-01")
        calls = [q.call for q in results]
        assert "W1AW"  in calls
        assert "K1ABC" in calls
        assert "N0XYZ" not in calls

    def test_no_date_filter_returns_all(self, db):
        self._add(db, "W1AW",  "2020-01-01T00:00:00Z")
        self._add(db, "K1ABC", "2024-06-01T10:00:00Z")
        results = db.search_qsos()
        assert len(results) == 2
