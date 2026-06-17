"""Tests for LogDB analytics aggregate methods."""
from __future__ import annotations
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest
from core.log_db import LogDB, QSO


@pytest.fixture()
def db(tmp_path):
    d = LogDB(tmp_path / "test.db")
    yield d
    d.close()


def _add(db, call, band, mode, country="", datetime_on="2024-05-01T10:00:00Z"):
    db.log_qso(QSO(call=call, band=band, mode=mode,
                   country=country, datetime_on=datetime_on))


class TestQsosByBand:
    def test_empty_returns_empty(self, db):
        assert db.qsos_by_band() == []

    def test_single_band(self, db):
        _add(db, "W1AW", "20m", "FT8")
        _add(db, "K1ABC", "20m", "FT8")
        rows = db.qsos_by_band()
        assert len(rows) == 1
        assert rows[0] == ("20m", 2)

    def test_sorted_descending(self, db):
        _add(db, "W1AW",  "40m", "FT8")
        _add(db, "K1ABC", "20m", "FT8")
        _add(db, "N0XYZ", "20m", "SSB")
        rows = db.qsos_by_band()
        counts = [c for _, c in rows]
        assert counts == sorted(counts, reverse=True)

    def test_empty_band_excluded(self, db):
        _add(db, "W1AW", "", "FT8")
        assert db.qsos_by_band() == []

    def test_multiple_bands(self, db):
        for band in ["20m", "40m", "15m"]:
            _add(db, "W1AW", band, "SSB")
        bands = [b for b, _ in db.qsos_by_band()]
        assert set(bands) == {"20m", "40m", "15m"}


class TestQsosByMode:
    def test_empty_returns_empty(self, db):
        assert db.qsos_by_mode() == []

    def test_single_mode(self, db):
        _add(db, "W1AW", "20m", "FT8")
        rows = db.qsos_by_mode()
        assert len(rows) == 1
        assert rows[0][0] == "FT8"

    def test_sorted_descending(self, db):
        for _ in range(3):
            _add(db, "W1AW", "20m", "FT8")
        _add(db, "K1ABC", "20m", "SSB")
        rows = db.qsos_by_mode()
        assert rows[0] == ("FT8", 3)
        assert rows[1] == ("SSB", 1)

    def test_empty_mode_excluded(self, db):
        _add(db, "W1AW", "20m", "")
        assert db.qsos_by_mode() == []


class TestQsosByYear:
    def test_empty_returns_empty(self, db):
        assert db.qsos_by_year() == []

    def test_single_year(self, db):
        _add(db, "W1AW", "20m", "FT8", datetime_on="2024-05-01T10:00:00Z")
        rows = db.qsos_by_year()
        assert rows == [("2024", 1)]

    def test_multiple_years_ascending(self, db):
        _add(db, "W1AW",  "20m", "FT8", datetime_on="2022-01-01T10:00:00Z")
        _add(db, "K1ABC", "20m", "FT8", datetime_on="2024-01-01T10:00:00Z")
        _add(db, "N0XYZ", "40m", "SSB", datetime_on="2023-01-01T10:00:00Z")
        rows = db.qsos_by_year()
        years = [y for y, _ in rows]
        assert years == sorted(years)
        assert years == ["2022", "2023", "2024"]


class TestTopEntities:
    def test_empty_returns_empty(self, db):
        assert db.top_entities() == []

    def test_returns_top_n(self, db):
        for country in ["USA", "UK", "Germany", "Japan", "Australia"]:
            _add(db, "W1AW", "20m", "FT8", country=country)
        rows = db.top_entities(n=3)
        assert len(rows) == 3

    def test_sorted_descending(self, db):
        for _ in range(3):
            _add(db, "W1AW", "20m", "FT8", country="USA")
        _add(db, "G3XYZ", "20m", "FT8", country="UK")
        rows = db.top_entities()
        assert rows[0] == ("USA", 3)
        assert rows[1] == ("UK", 1)

    def test_empty_country_excluded(self, db):
        _add(db, "W1AW", "20m", "FT8", country="")
        assert db.top_entities() == []
