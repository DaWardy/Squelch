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


class TestExportCSV:
    def test_csv_creates_file(self, db, tmp_path):
        db.log_qso(QSO(call="W1AW", band="20m", mode="FT8",
                       name="Hiram", grid="FN31", cqz=5))
        out = tmp_path / "log.csv"
        count = db.export_csv(out)
        assert count == 1
        assert out.exists()

    def test_csv_has_headers(self, db, tmp_path):
        import csv
        db.log_qso(QSO(call="W1AW", band="20m", mode="FT8"))
        out = tmp_path / "log.csv"
        db.export_csv(out)
        rows = list(csv.reader(out.read_text(encoding="utf-8").splitlines()))
        assert rows[0][0] == "Date"
        assert "Callsign" in rows[0]
        assert "Band" in rows[0]
        assert "Mode" in rows[0]

    def test_csv_data_row(self, db, tmp_path):
        import csv
        db.log_qso(QSO(call="K4ABC", band="40m", mode="CW",
                       freq_hz=7_074_000, name="Test", grid="EM72"))
        out = tmp_path / "log.csv"
        db.export_csv(out)
        rows = list(csv.reader(out.read_text(encoding="utf-8").splitlines()))
        assert rows[1][2] == "K4ABC"
        assert rows[1][3] == "40m"
        assert rows[1][5] == "CW"

    def test_csv_filtered_subset(self, db, tmp_path):
        import csv
        db.log_qso(QSO(call="W1AW",  band="20m", mode="FT8"))
        db.log_qso(QSO(call="K4ABC", band="40m", mode="CW"))
        qsos_20m = [q for q in db.recent_qsos() if q.band == "20m"]
        out = tmp_path / "log_filtered.csv"
        count = db.export_csv(out, qsos=qsos_20m)
        assert count == 1
        rows = list(csv.reader(out.read_text(encoding="utf-8").splitlines()))
        assert len(rows) == 2  # header + 1 data row
        assert rows[1][2] == "W1AW"

    def test_csv_injection_prevention(self, db, tmp_path):
        import csv
        db.log_qso(QSO(call="W1AW", band="20m", mode="FT8",
                       name="=SUM(1+1)", comment="@bad"))
        out = tmp_path / "log.csv"
        db.export_csv(out)
        rows = list(csv.reader(out.read_text(encoding="utf-8").splitlines()))
        # csv_safe() prefixes formula triggers with ' to neutralize them
        name_cell = rows[1][9]   # Name column
        comment_cell = rows[1][20]  # Comment column
        assert name_cell.startswith("'"), f"name not prefixed: {name_cell!r}"
        assert comment_cell.startswith("'"), f"comment not prefixed: {comment_cell!r}"

    def test_csv_returns_count(self, db, tmp_path):
        for i in range(5):
            db.log_qso(QSO(call=f"W{i}AW", band="20m", mode="FT8"))
        out = tmp_path / "log.csv"
        assert db.export_csv(out) == 5

    def test_csv_empty_log(self, db, tmp_path):
        out = tmp_path / "empty.csv"
        count = db.export_csv(out, qsos=[])
        assert count == 0
        import csv
        rows = list(csv.reader(out.read_text(encoding="utf-8").splitlines()))
        assert rows[0][0] == "Date"  # header still written

    def test_adif_export_accepts_qsos_param(self, db, tmp_path):
        db.log_qso(QSO(call="W1AW",  band="20m", mode="FT8"))
        db.log_qso(QSO(call="K4ABC", band="40m", mode="CW"))
        qsos = [q for q in db.recent_qsos() if q.band == "20m"]
        out = tmp_path / "filtered.adi"
        count = db.export_adif(out, qsos=qsos)
        assert count == 1
        text = out.read_text(encoding="utf-8")
        assert "W1AW" in text
        assert "K4ABC" not in text


class TestDistinctCallsigns:
    def test_empty_log(self, db):
        assert db.distinct_callsigns() == []

    def test_single_call(self, db):
        db.log_qso(QSO(call="W1AW", band="20m", mode="FT8"))
        calls = db.distinct_callsigns()
        assert calls == ["W1AW"]

    def test_deduplicates(self, db):
        db.log_qso(QSO(call="W1AW", band="20m", mode="FT8"))
        db.log_qso(QSO(call="W1AW", band="40m", mode="CW"))
        assert db.distinct_callsigns().count("W1AW") == 1

    def test_sorted(self, db):
        for call in ["W4XYZ", "K4ABC", "W1AW"]:
            db.log_qso(QSO(call=call, band="20m", mode="FT8"))
        assert db.distinct_callsigns() == ["K4ABC", "W1AW", "W4XYZ"]

    def test_prefix_filter(self, db):
        db.log_qso(QSO(call="W1AW",  band="20m", mode="FT8"))
        db.log_qso(QSO(call="W4XYZ", band="20m", mode="FT8"))
        db.log_qso(QSO(call="K4ABC", band="20m", mode="FT8"))
        assert db.distinct_callsigns(prefix="W") == ["W1AW", "W4XYZ"]

    def test_prefix_case_insensitive(self, db):
        db.log_qso(QSO(call="W1AW", band="20m", mode="FT8"))
        assert db.distinct_callsigns(prefix="w") == ["W1AW"]

    def test_prefix_no_match(self, db):
        db.log_qso(QSO(call="W1AW", band="20m", mode="FT8"))
        assert db.distinct_callsigns(prefix="K") == []


class TestLastQSOWith:
    def test_no_prior_qso(self, db):
        assert db.last_qso_with("W1AW") is None

    def test_returns_most_recent(self, db):
        db.log_qso(QSO(call="W1AW", band="20m", mode="FT8",
                       name="Old", datetime_on="2024-01-01T10:00:00Z"))
        db.log_qso(QSO(call="W1AW", band="40m", mode="CW",
                       name="New", datetime_on="2024-06-01T10:00:00Z"))
        q = db.last_qso_with("W1AW")
        assert q is not None
        assert q.name == "New"
        assert q.band == "40m"

    def test_case_insensitive(self, db):
        db.log_qso(QSO(call="W1AW", band="20m", mode="FT8", grid="FN31"))
        assert db.last_qso_with("w1aw") is not None

    def test_returns_grid(self, db):
        db.log_qso(QSO(call="W1AW", band="20m", mode="FT8", grid="FN31"))
        q = db.last_qso_with("W1AW")
        assert q.grid == "FN31"

    def test_unrelated_call_not_returned(self, db):
        db.log_qso(QSO(call="K4ABC", band="20m", mode="FT8"))
        assert db.last_qso_with("W1AW") is None


class TestExportCabrillo:
    def test_creates_file(self, db, tmp_path):
        db.log_qso(QSO(call="W1AW", band="20m", mode="CW",
                       freq_hz=14_074_000, rst_sent="599", rst_rcvd="599"))
        out = tmp_path / "log.cbr"
        count = db.export_cabrillo(out, my_call="W4XYZ", contest="CQ-WW-CW",
                                   exchange="5NN 4")
        assert count == 1
        assert out.exists()

    def test_header_fields(self, db, tmp_path):
        db.log_qso(QSO(call="W1AW", band="20m", mode="CW", freq_hz=14_025_000))
        out = tmp_path / "log.cbr"
        db.export_cabrillo(out, my_call="W4XYZ", my_grid="EM72",
                           contest="CQ-WW-CW", exchange="5NN 4")
        text = out.read_text(encoding="utf-8")
        assert "START-OF-LOG: 3.0" in text
        assert "CALLSIGN: W4XYZ" in text
        assert "GRID-LOCATOR: EM72" in text
        assert "CONTEST: CQ-WW-CW" in text
        assert "END-OF-LOG:" in text

    def test_qso_line_structure(self, db, tmp_path):
        db.log_qso(QSO(call="W1AW", band="20m", mode="CW",
                       freq_hz=14_025_000, rst_sent="599", rst_rcvd="579",
                       datetime_on="2024-11-16T14:32:00Z"))
        out = tmp_path / "log.cbr"
        db.export_cabrillo(out, my_call="W4XYZ", exchange="5NN 4")
        lines = out.read_text(encoding="utf-8").splitlines()
        qso_lines = [l for l in lines if l.startswith("QSO:")]
        assert len(qso_lines) == 1
        parts = qso_lines[0].split()
        assert parts[0] == "QSO:"
        assert parts[1] == "14025"     # freq kHz
        assert parts[2] == "CW"        # mode
        assert parts[3] == "2024-11-16"  # date
        assert parts[4] == "14:32"     # time

    def test_exchange_sent_in_qso_line(self, db, tmp_path):
        db.log_qso(QSO(call="W1AW", band="20m", mode="CW",
                       freq_hz=14_025_000))
        out = tmp_path / "log.cbr"
        db.export_cabrillo(out, my_call="W4XYZ", exchange="5NN 4")
        text = out.read_text(encoding="utf-8")
        assert "5NN" in text

    def test_exchange_received_from_comment(self, db, tmp_path):
        db.log_qso(QSO(call="W1AW", band="20m", mode="CW",
                       freq_hz=14_025_000, comment="5NN 14"))
        out = tmp_path / "log.cbr"
        db.export_cabrillo(out, my_call="W4XYZ", exchange="5NN 4")
        text = out.read_text(encoding="utf-8")
        # First token of comment used as received exchange
        qso_line = [l for l in text.splitlines() if l.startswith("QSO:")][0]
        assert "5NN" in qso_line

    def test_empty_log_produces_valid_file(self, db, tmp_path):
        out = tmp_path / "empty.cbr"
        count = db.export_cabrillo(out, my_call="W4XYZ", qsos=[])
        assert count == 0
        text = out.read_text(encoding="utf-8")
        assert "START-OF-LOG:" in text
        assert "END-OF-LOG:" in text

    def test_filtered_qsos_honored(self, db, tmp_path):
        db.log_qso(QSO(call="W1AW",  band="20m", mode="CW",  freq_hz=14_025_000))
        db.log_qso(QSO(call="K4ABC", band="40m", mode="SSB", freq_hz=7_200_000))
        qsos_cw = [q for q in db.recent_qsos() if q.mode == "CW"]
        out = tmp_path / "cw.cbr"
        count = db.export_cabrillo(out, qsos=qsos_cw, my_call="W4XYZ")
        assert count == 1
        text = out.read_text(encoding="utf-8")
        assert "W1AW" in text
        assert "K4ABC" not in text

    def test_returns_count(self, db, tmp_path):
        for i in range(5):
            db.log_qso(QSO(call=f"W{i}AW", band="20m", mode="CW",
                           freq_hz=14_025_000))
        out = tmp_path / "log.cbr"
        assert db.export_cabrillo(out, my_call="W4XYZ") == 5


class TestBandsWorked:
    def test_empty_log_returns_zero(self, db):
        assert db.bands_worked() == 0

    def test_single_qso_single_band(self, db):
        db.log_qso(QSO(call="W1AW", band="20m", mode="FT8"))
        assert db.bands_worked() == 1

    def test_multiple_qsos_same_band_counts_once(self, db):
        db.log_qso(QSO(call="W1AW", band="20m", mode="FT8"))
        db.log_qso(QSO(call="K1ABC", band="20m", mode="CW"))
        assert db.bands_worked() == 1

    def test_two_distinct_bands_counted(self, db):
        db.log_qso(QSO(call="W1AW",  band="20m", mode="FT8"))
        db.log_qso(QSO(call="K1ABC", band="40m", mode="CW"))
        assert db.bands_worked() == 2

    def test_empty_band_not_counted(self, db):
        db.log_qso(QSO(call="W1AW", band="", mode="FT8"))
        assert db.bands_worked() == 0

    def test_contest_name_uppercased(self, db, tmp_path):
        db.log_qso(QSO(call="W1AW", band="20m", mode="CW", freq_hz=14_025_000))
        out = tmp_path / "log.cbr"
        db.export_cabrillo(out, my_call="W4XYZ", contest="cq-ww-cw")
        text = out.read_text(encoding="utf-8")
        assert "CONTEST: CQ-WW-CW" in text
