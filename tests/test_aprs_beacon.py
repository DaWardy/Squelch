"""Sprint 57 — APRS beacon UI + QSO rate per hour."""
from __future__ import annotations
import sys
import pathlib
import tempfile
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


# ── APRSBeacon pure-logic ─────────────────────────────────────────────────────

class TestAPRSBeaconPacket:
    """Verify build_position_packet output format."""

    def test_basic_position_packet(self):
        from aprs.beacon import build_position_packet
        pkt = build_position_packet("W1AW", 41.7, -72.7)
        assert pkt.startswith("!")
        assert "N" in pkt or "S" in pkt
        assert "E" in pkt or "W" in pkt

    def test_north_latitude_has_N(self):
        from aprs.beacon import build_position_packet
        pkt = build_position_packet("W1AW", 41.7, -72.7)
        assert "N" in pkt

    def test_south_latitude_has_S(self):
        from aprs.beacon import build_position_packet
        pkt = build_position_packet("W1AW", -33.8, 151.0)
        assert "S" in pkt

    def test_comment_appended(self):
        from aprs.beacon import build_position_packet
        pkt = build_position_packet("W1AW", 41.7, -72.7, comment="Test")
        assert "Test" in pkt

    def test_comment_truncated_to_43(self):
        from aprs.beacon import build_position_packet
        long_comment = "X" * 60
        pkt = build_position_packet("W1AW", 0.0, 0.0, comment=long_comment)
        assert "X" * 44 not in pkt   # no more than 43 Xs in a row

    def test_altitude_included(self):
        from aprs.beacon import build_position_packet
        pkt = build_position_packet("W1AW", 41.7, -72.7, altitude_m=100.0)
        assert "/A=" in pkt

    def test_default_no_altitude(self):
        from aprs.beacon import build_position_packet
        pkt = build_position_packet("W1AW", 41.7, -72.7)
        assert "/A=" not in pkt

    def test_symbols_dict_has_house(self):
        from aprs.beacon import SYMBOLS
        assert "house" in SYMBOLS

    def test_symbols_dict_has_car(self):
        from aprs.beacon import SYMBOLS
        assert "car" in SYMBOLS

    def test_beacon_class_exists(self):
        from aprs.beacon import APRSBeacon
        b = APRSBeacon.__new__(APRSBeacon)
        assert b is not None

    def test_min_interval_constant(self):
        from aprs.beacon import MIN_INTERVAL_S
        assert MIN_INTERVAL_S >= 60   # at least 1 minute minimum

    def test_latlon_to_aprs_format(self):
        from aprs.beacon import _latlon_to_aprs
        lat_s, lon_s = _latlon_to_aprs(41.7329, -72.7078)
        # Should be DDMM.MMH format
        assert "N" in lat_s
        assert "W" in lon_s
        # Latitude should have numeric prefix
        assert lat_s[:2].isdigit()


# ── APRS beacon UI wiring ─────────────────────────────────────────────────────

class TestBeaconUISource:

    def _map_src(self):
        return (ROOT / "ui/tabs/map_tab.py").read_text(encoding="utf-8")

    def _apis_src(self):
        return (ROOT / "ui/dialogs/settings_apis_tab.py").read_text(encoding="utf-8")

    def _dialog_src(self):
        return (ROOT / "ui/dialogs/settings_dialog.py").read_text(encoding="utf-8")

    def test_beacon_btn_in_toolbar(self):
        assert "_beacon_btn" in self._map_src()

    def test_on_beacon_toggle_method(self):
        assert "def _on_beacon_toggle(" in self._map_src()

    def test_beacon_countdown_method(self):
        assert "_update_beacon_countdown" in self._map_src()

    def test_beacon_settings_in_apis_tab(self):
        src = self._apis_src()
        assert "_aprs_beacon_comment" in src
        assert "_aprs_beacon_interval" in src
        assert "_aprs_beacon_symbol" in src

    def test_beacon_settings_loaded(self):
        assert "aprs.beacon_comment" in self._dialog_src()

    def test_beacon_settings_saved(self):
        src = self._dialog_src()
        assert "aprs.beacon_interval_s" in src
        assert "aprs.symbol" in src


# ── QSO rate per hour ─────────────────────────────────────────────────────────

class TestQSORate:

    def _make_db(self):
        from pathlib import Path
        from core.log_db import LogDB, QSO
        tmp = tempfile.mkdtemp()
        db = LogDB(Path(tmp) / "test.db")
        return db

    def test_rate_empty_db(self):
        db = self._make_db()
        assert db.rate_per_hour() == 0

    def test_rate_counts_recent_qsos(self):
        from core.log_db import QSO
        db = self._make_db()
        now = datetime.now(timezone.utc)
        for i in range(5):
            t = now - timedelta(minutes=i * 5)
            db.log_qso(QSO(
                call=f"W{i}AW", band="20m", mode="FT8",
                datetime_on=t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                rst_sent="59", rst_rcvd="59"))
        rate = db.rate_per_hour()
        assert rate == 5   # 5 QSOs in last 60 min → 5/hr

    def test_rate_excludes_old_qsos(self):
        from core.log_db import QSO
        db = self._make_db()
        old = datetime.now(timezone.utc) - timedelta(hours=2)
        db.log_qso(QSO(
            call="VK2OLD", band="40m", mode="SSB",
            datetime_on=old.strftime("%Y-%m-%dT%H:%M:%SZ"),
            rst_sent="59", rst_rcvd="59"))
        assert db.rate_per_hour() == 0

    def test_rate_in_stats_dict(self):
        db = self._make_db()
        s = db.stats()
        assert "rate_per_hour" in s
        assert isinstance(s["rate_per_hour"], int)

    def test_log_tab_uses_rate_from_stats(self):
        src = (ROOT / "ui/tabs/log_tab.py").read_text(encoding="utf-8")
        assert "rate_per_hour" in src
