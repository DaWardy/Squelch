from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
# Squelch tests — core/log_db.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import tempfile
from datetime import datetime, timezone
from core.log_db import LogDB, QSO


@pytest.fixture
def db(tmp_path):
    """Fresh in-memory QSO database for each test."""
    db_path = tmp_path / "test_log.db"
    return LogDB(str(db_path))


class TestQSODataclass:
    def test_defaults(self):
        q = QSO(call="W4XYZ", band="20m", mode="FT8")
        assert q.call == "W4XYZ"
        assert q.band == "20m"
        assert q.mode == "FT8"

    def test_callsign_uppercased(self):
        q = QSO(call="w4xyz", band="20m", mode="SSB")
        assert q.call == "W4XYZ"

    def test_datetime_set_automatically(self):
        q = QSO(call="W4XYZ", band="20m", mode="CW")
        assert q.datetime_on
        assert "T" in q.datetime_on or "-" in q.datetime_on

    def test_grid_derives_lat_lon(self):
        """QSO with grid should auto-derive lat/lon."""
        q = QSO(call="W4XYZ", band="20m",
                mode="FT8", grid="DM79rr")
        # Should have derived lat/lon from grid
        assert q.lat != 0.0 or q.lon != 0.0

    def test_empty_grid_no_crash(self):
        q = QSO(call="W4XYZ", band="20m", mode="FT8", grid="")
        assert q.lat == 0.0

    def test_dist_km_zero_without_coords(self):
        q = QSO(call="W4XYZ", band="20m", mode="FT8")
        assert q.dist_km == 0.0

    def test_dist_km_zero_without_my_coords(self):
        q = QSO(call="W4XYZ", band="20m", mode="FT8",
                lat=51.5, lon=-0.1)
        assert q.dist_km == 0.0

    def test_dist_km_london_to_nyc(self):
        """London (51.5°N, 0°W) to NYC (40.7°N, 74°W) ≈ 5570 km."""
        q = QSO(call="W4XYZ", band="20m", mode="FT8",
                my_lat=51.5, my_lon=0.0,
                lat=40.7, lon=-74.0)
        assert 5400 < q.dist_km < 5800

    def test_dist_km_zero_distance(self):
        """Same location → 0 km."""
        q = QSO(call="W4XYZ", band="20m", mode="FT8",
                my_lat=40.0, my_lon=-74.0,
                lat=40.0, lon=-74.0)
        assert q.dist_km < 1.0

    def test_bearing_deg_zero_without_coords(self):
        q = QSO(call="W4XYZ", band="20m", mode="FT8")
        assert q.bearing_deg == 0.0

    def test_bearing_deg_north(self):
        """Station due north → bearing ≈ 0°."""
        q = QSO(call="W4XYZ", band="20m", mode="FT8",
                my_lat=1.0, my_lon=1.0,
                lat=10.0, lon=1.0)
        assert q.bearing_deg < 1.0 or q.bearing_deg > 359.0

    def test_bearing_deg_east(self):
        """Station due east → bearing ≈ 90°."""
        q = QSO(call="W4XYZ", band="20m", mode="FT8",
                my_lat=1.0, my_lon=1.0,
                lat=1.0, lon=10.0)
        assert 85 < q.bearing_deg < 95

    def test_bearing_deg_in_range(self):
        q = QSO(call="W4XYZ", band="20m", mode="FT8",
                my_lat=51.5, my_lon=0.0,
                lat=40.7, lon=-74.0)
        assert 0 <= q.bearing_deg < 360


class TestLogDB:
    def test_create_db(self, db):
        assert db is not None

    def test_log_and_retrieve(self, db):
        q = QSO(call="W4XYZ", band="20m", mode="FT8",
                rst_sent="-10", rst_rcvd="-12")
        db.log_qso(q)
        recent = db.recent_qsos(limit=1)
        assert len(recent) == 1
        assert recent[0].call == "W4XYZ"

    def test_multiple_qsos(self, db):
        for call in ["W4XYZ", "K4ABC", "N4DEF"]:
            db.log_qso(QSO(call=call, band="20m", mode="FT8"))
        recent = db.recent_qsos(limit=10)
        assert len(recent) == 3

    def test_total_qsos(self, db):
        assert db.total_qsos() == 0
        db.log_qso(QSO(call="W4XYZ", band="20m", mode="SSB"))
        assert db.total_qsos() == 1

    def test_search_by_callsign(self, db):
        db.log_qso(QSO(call="W4XYZ", band="20m", mode="FT8"))
        db.log_qso(QSO(call="K4ABC", band="40m", mode="CW"))
        results = db.search_qsos(call="W4XYZ")
        assert len(results) == 1
        assert results[0].call == "W4XYZ"

    def test_search_by_band(self, db):
        db.log_qso(QSO(call="W4XYZ", band="20m", mode="FT8"))
        db.log_qso(QSO(call="K4ABC", band="40m", mode="FT8"))
        results = db.search_qsos(band="20m")
        assert len(results) == 1
        assert results[0].band == "20m"

    def test_search_by_mode(self, db):
        db.log_qso(QSO(call="W4XYZ", band="20m", mode="FT8"))
        db.log_qso(QSO(call="K4ABC", band="20m", mode="SSB"))
        ft8 = db.search_qsos(mode="FT8")
        assert all(q.mode == "FT8" for q in ft8)

    def test_adif_export(self, db):
        db.log_qso(QSO(call="W4XYZ", band="20m",
                       mode="FT8", grid="DM79"))
        import tempfile, os
        with tempfile.NamedTemporaryFile(
                suffix='.adif', delete=False) as f:
            tmp = f.name
        db.export_adif(Path(tmp))
        adif = Path(tmp).read_text()
        os.unlink(tmp)
        assert "W4XYZ" in adif
        assert "<CALL:" in adif
        assert "<BAND:" in adif
        assert "<MODE:" in adif

    def test_thread_safe(self, db):
        """Multiple threads can log simultaneously."""
        import threading
        errors = []
        def log_qso(call):
            try:
                db.log_qso(QSO(call=call, band="20m",
                               mode="FT8"))
            except Exception as e:
                errors.append(e)
        threads = [
            threading.Thread(target=log_qso, args=(f"W{i}XYZ",))
            for i in range(10)]
        for t in threads: t.start()
        for t in threads: t.join()
        assert len(errors) == 0
        assert db.total_qsos() == 10


class TestWAZCount:
    def test_empty_log(self, db):
        assert db.waz_count() == 0

    def test_single_zone(self, db):
        db.log_qso(QSO(call="W1AW", band="20m", mode="FT8", cqz=5))
        assert db.waz_count() == 1

    def test_deduplicates_zones(self, db):
        db.log_qso(QSO(call="W1AW", band="20m", mode="FT8", cqz=5))
        db.log_qso(QSO(call="W4XYZ", band="40m", mode="CW", cqz=5))
        assert db.waz_count() == 1

    def test_multiple_zones(self, db):
        for zone in [3, 5, 14, 25]:
            db.log_qso(QSO(call="W1AW", band="20m", mode="FT8", cqz=zone))
        assert db.waz_count() == 4

    def test_zero_cqz_excluded(self, db):
        db.log_qso(QSO(call="W1AW", band="20m", mode="FT8", cqz=0))
        assert db.waz_count() == 0

    def test_stats_includes_waz(self, db):
        db.log_qso(QSO(call="W1AW", band="20m", mode="FT8", cqz=5))
        stats = db.stats()
        assert "waz_worked" in stats
        assert stats["waz_worked"] == 1
