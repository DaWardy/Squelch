from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for core/gps.py — NMEA parsing, fix→grid, and the serial read loop.

All hardware/OS access is mocked, so these run on any machine with no GPS,
no pyserial, and no PyQt6.
"""
import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core import gps
from core.gps import (
    GPSFix, nmea_checksum_ok, nmea_to_decimal,
    parse_gpgga, parse_gprmc, parse_nmea,
    windows_location_available, list_serial_ports,
    SerialGPSReader,
)

# Canonical NMEA examples (with correct checksums) — Munich, ~48.117N 11.517E
GGA = "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"
RMC = "$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A"
GNGGA = "$GNGGA,001043.00,4404.14036,N,12118.85961,W,1,12,0.98,1113.0,M,-21.3,M,,*47"


def _cs(body: str) -> str:
    """Return ``$body*HH`` with a freshly computed NMEA checksum."""
    calc = 0
    for ch in body:
        calc ^= ord(ch)
    return f"${body}*{calc:02X}"


class TestChecksum:

    def test_known_good(self):
        assert nmea_checksum_ok(GGA) is True
        assert nmea_checksum_ok(RMC) is True

    def test_corrupted_fails(self):
        bad = GGA[:-2] + "00"        # wrong checksum digits
        assert nmea_checksum_ok(bad) is False

    def test_missing_checksum_allowed(self):
        assert nmea_checksum_ok("$GPGGA,123519,4807.038,N") is True

    def test_helper_roundtrip(self):
        assert nmea_checksum_ok(_cs("GPRMC,001,V,,,,")) is True


class TestNmeaToDecimal:

    def test_latitude_north(self):
        assert abs(nmea_to_decimal("4807.038", "N") - 48.1173) < 1e-3

    def test_longitude_east(self):
        assert abs(nmea_to_decimal("01131.000", "E") - 11.5167) < 1e-3

    def test_south_is_negative(self):
        assert nmea_to_decimal("3358.000", "S") < 0

    def test_west_is_negative(self):
        assert nmea_to_decimal("12118.000", "W") < 0

    def test_empty_field(self):
        assert nmea_to_decimal("", "N") is None

    def test_garbage_field(self):
        assert nmea_to_decimal("abc", "N") is None


class TestParseGGA:

    def test_lat_lon(self):
        fix = parse_gpgga(GGA)
        assert fix is not None
        assert abs(fix.lat - 48.1173) < 1e-3
        assert abs(fix.lon - 11.5167) < 1e-3

    def test_metadata(self):
        fix = parse_gpgga(GGA)
        assert fix.fix_quality == 1
        assert fix.satellites == 8
        assert abs(fix.altitude_m - 545.4) < 1e-3

    def test_multiconstellation_talker(self):
        fix = parse_gpgga(GNGGA)
        assert fix is not None
        assert fix.lat > 0 and fix.lon < 0      # NW hemisphere

    def test_no_fix_quality_zero(self):
        line = _cs("GPGGA,123519,,,,,0,00,,,M,,M,,")
        assert parse_gpgga(line) is None

    def test_wrong_type_returns_none(self):
        assert parse_gpgga(RMC) is None


class TestParseRMC:

    def test_active_fix(self):
        fix = parse_gprmc(RMC)
        assert fix is not None
        assert abs(fix.lat - 48.1173) < 1e-3
        assert abs(fix.lon - 11.5167) < 1e-3

    def test_void_status_rejected(self):
        line = _cs("GPRMC,123519,V,4807.038,N,01131.000,E,0,0,230394,,")
        assert parse_gprmc(line) is None

    def test_wrong_type_returns_none(self):
        assert parse_gprmc(GGA) is None


class TestParseNmeaDispatch:

    def test_dispatch_gga(self):
        assert parse_nmea(GGA) is not None

    def test_dispatch_rmc(self):
        assert parse_nmea(RMC) is not None

    def test_unknown_sentence(self):
        assert parse_nmea("$GPGSV,3,1,11,01,40,083,46*7B") is None

    def test_empty(self):
        assert parse_nmea("") is None

    def test_corrupt_checksum_not_parsed(self):
        assert parse_nmea(GGA[:-2] + "00") is None


class TestGPSFix:

    def test_grid_derivation(self):
        fix = GPSFix(lat=48.1173, lon=11.5167)
        # 48.11N 11.52E → Munich area, JN58
        assert fix.grid.startswith("JN58"), fix.grid

    def test_defaults(self):
        fix = GPSFix(lat=0.0, lon=0.0)
        assert fix.valid is True
        assert fix.source == "gps"


class TestWindowsAvailability:

    def test_returns_bool_without_raising(self):
        assert isinstance(windows_location_available(), bool)

    def test_get_fix_none_when_unavailable(self, monkeypatch):
        monkeypatch.setattr(gps, "_import_geolocation", lambda: None)
        assert gps.get_windows_fix(timeout_s=0.1) is None


class TestSerialPortList:

    def test_returns_list(self):
        assert isinstance(list_serial_ports(), list)


# ── Serial read loop (mocked pyserial) ─────────────────────────────────────

class _FakePort:
    """Yields each queued NMEA line once, then blocks-with-timeout (b'')."""

    def __init__(self, lines):
        self._lines = list(lines)
        self.closed = False

    def readline(self):
        if self._lines:
            return self._lines.pop(0)
        time.sleep(0.01)
        return b""

    def close(self):
        self.closed = True


class _FakeSerialModule:
    def __init__(self, lines):
        self._lines = lines

    def Serial(self, *a, **k):
        return _FakePort(self._lines)


class TestSerialGPSReader:

    def _patch_serial(self, monkeypatch, lines):
        monkeypatch.setattr(gps, "HAS_SERIAL", True)
        monkeypatch.setattr(gps, "_serial", _FakeSerialModule(lines),
                            raising=False)

    def test_delivers_parsed_fix(self, monkeypatch):
        self._patch_serial(monkeypatch, [GGA.encode() + b"\r\n"])
        got = []
        done = threading.Event()
        reader = SerialGPSReader()
        reader.fix_received.connect(lambda f: (got.append(f), done.set()))
        assert reader.start("COMTEST", 4800) is True
        # Under real PyQt6 the fix is delivered from the daemon read-thread via a
        # queued cross-thread signal, so the receiving slot only runs when an
        # event loop is pumped. Headless (_FallbackSignal) delivery is synchronous,
        # so this loop simply returns immediately. Production has a live loop.
        import time as _t
        try:
            from PyQt6.QtCore import QCoreApplication
            _app = QCoreApplication.instance()
        except Exception:
            _app = None
        _deadline = _t.time() + 2.0
        while not done.is_set() and _t.time() < _deadline:
            if _app is not None:
                _app.processEvents()
            _t.sleep(0.01)
        assert done.is_set(), "no fix delivered"
        reader.stop()
        assert abs(got[0].lat - 48.1173) < 1e-3

    def test_start_false_without_pyserial(self, monkeypatch):
        monkeypatch.setattr(gps, "HAS_SERIAL", False)
        errors = []
        reader = SerialGPSReader()
        reader.error_occurred.connect(errors.append)
        assert reader.start("COMTEST", 4800) is False
        assert errors and "pyserial" in errors[0]

    def test_start_false_without_port(self, monkeypatch):
        monkeypatch.setattr(gps, "HAS_SERIAL", True)
        reader = SerialGPSReader()
        assert reader.start("", 4800) is False

    def test_stop_is_idempotent(self, monkeypatch):
        self._patch_serial(monkeypatch, [])
        reader = SerialGPSReader()
        reader.start("COMTEST", 4800)
        reader.stop()
        reader.stop()        # second stop must not raise
        assert reader.is_running is False


# ── LocationManager GPS integration ────────────────────────────────────────

class _FakeCfg:
    def __init__(self):
        self._d = {}

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value

    def save(self):
        pass

    @property
    def grid(self):
        return self._d.get("location.grid", "")

    @grid.setter
    def grid(self, v):
        self._d["location.grid"] = v


class TestLocationManagerGPS:

    def test_apply_gps_fix_sets_latlon_and_grid(self):
        from core.location import LocationManager, LocationSource
        lm = LocationManager(_FakeCfg())
        grid = lm.apply_gps_fix(GPSFix(lat=48.1173, lon=11.5167), notify=False)
        assert grid.startswith("JN58"), grid
        assert abs(lm.location.lat - 48.1173) < 1e-3
        assert lm.location.source == LocationSource.GPS_SERIAL
        assert lm.last_fix is not None

    def test_on_gps_fix_respects_auto_grid_off(self):
        from core.location import LocationManager
        cfg = _FakeCfg()
        cfg.set("location.gps_auto_grid", False)
        lm = LocationManager(cfg)
        lm._on_gps_fix(GPSFix(lat=48.1173, lon=11.5167))
        assert lm.last_fix is not None
        assert lm.location.grid == ""        # not applied

    def test_on_gps_fix_applies_when_auto_grid_on(self):
        from core.location import LocationManager
        cfg = _FakeCfg()
        cfg.set("location.gps_auto_grid", True)
        lm = LocationManager(cfg)
        lm._on_gps_fix(GPSFix(lat=48.1173, lon=11.5167))
        assert lm.location.grid.startswith("JN58")

    def test_start_gps_serial_false_without_port(self):
        from core.location import LocationManager
        lm = LocationManager(_FakeCfg())
        assert lm.start_gps_serial() is False
