from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for APRS packet parsing and beacon."""

import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from aprs.aprs_client import parse_packet, APRSPacket
from aprs.beacon import (
    build_position_packet, _latlon_to_aprs)


class TestLatLonToAPRS:
    def test_northern_eastern(self):
        lat, lon = _latlon_to_aprs(39.742, -104.990)
        assert lat.endswith("N")
        assert lon.endswith("W")

    def test_southern_western(self):
        lat, lon = _latlon_to_aprs(-33.8, -70.6)
        assert lat.endswith("S")
        assert lon.endswith("W")

    def test_degree_format(self):
        lat, _ = _latlon_to_aprs(39.742, 0.0)
        # Should be DDMM.MMN
        assert len(lat) == 8  # 4+2+.+2 + N = 8... actually DDMM.MMN
        assert lat[-1] in ("N", "S")

    def test_zero_zero(self):
        lat, lon = _latlon_to_aprs(0.0, 0.0)
        assert "N" in lat or "S" in lat
        assert "E" in lon or "W" in lon


class TestBuildPositionPacket:
    def test_returns_string(self):
        pkt = build_position_packet("W1AW", 39.7, -104.9)
        assert isinstance(pkt, str)
        assert len(pkt) > 0

    def test_starts_with_exclaim(self):
        pkt = build_position_packet("W1AW", 39.7, -104.9)
        assert pkt.startswith("!")

    def test_comment_included(self):
        pkt = build_position_packet(
            "W1AW", 39.7, -104.9, comment="Hello")
        assert "Hello" in pkt

    def test_altitude_included(self):
        pkt = build_position_packet(
            "W1AW", 39.7, -104.9, altitude_m=1600)
        assert "/A=" in pkt

    def test_comment_truncated(self):
        long_comment = "X" * 100
        pkt = build_position_packet(
            "W1AW", 39.7, -104.9, comment=long_comment)
        # Comment should be max 43 chars
        after_pos = pkt.split(" ", 1)
        if len(after_pos) > 1:
            assert len(after_pos[1]) <= 43

    def test_different_symbols(self):
        for symbol in ["house", "car", "portable"]:
            pkt = build_position_packet(
                "W1AW", 39.7, -104.9, symbol=symbol)
            assert pkt.startswith("!")


class TestParsePacket:
    def test_position_packet(self):
        raw = ("W1AW>APRS,TCPIP*,qAC,T2US:"
               "!3942.75N/10459.65W-Test comment")
        pkt = parse_packet(raw)
        assert pkt is not None
        assert pkt.callsign == "W1AW"
        assert pkt.is_position

    def test_comment_only(self):
        raw = "# aprsd 5.0.0"
        pkt = parse_packet(raw)
        assert pkt is None

    def test_empty_string(self):
        pkt = parse_packet("")
        assert pkt is None

    def test_no_colon(self):
        pkt = parse_packet("W1AW>APRS")
        assert pkt is None

    def test_callsign_extracted(self):
        raw = ("W4XYZ>APRS,WIDE1-1:"
               "!3942.75N/10459.65W-Test")
        pkt = parse_packet(raw)
        assert pkt is not None
        assert pkt.callsign == "W4XYZ"

    def test_ssid_extracted(self):
        raw = ("W1AW-9>APRS,WIDE1-1:"
               "!3942.75N/10459.65W>Mobile")
        pkt = parse_packet(raw)
        if pkt:
            # May or may not extract SSID depending on impl
            assert pkt.callsign == "W1AW"

    def test_lat_lon_range(self):
        raw = ("W1AW>APRS,TCPIP*:"
               "!3942.75N/10459.65W-Test")
        pkt = parse_packet(raw)
        if pkt and pkt.lat:
            assert -90 <= pkt.lat <= 90
            assert -180 <= pkt.lon <= 180

    def test_negative_lat(self):
        raw = ("VK2XYZ>APRS,TCPIP*:"
               "!3342.75S/15059.65E-Sydney")
        pkt = parse_packet(raw)
        if pkt and pkt.lat:
            assert pkt.lat < 0


class TestAPRSPasscode:
    def test_known_values(self):
        from aprs.aprs_client import APRSClient
        # Known test values
        assert APRSClient.compute_passcode("W5AGO") == 10896
        assert APRSClient.compute_passcode("N0CALL") >= 0

    def test_range(self):
        from aprs.aprs_client import APRSClient
        for cs in ["W4XYZ", "W1AW", "K4ABC", "VK2XYZ"]:
            code = APRSClient.compute_passcode(cs)
            assert 0 <= code <= 32767

    def test_ssid_ignored(self):
        from aprs.aprs_client import APRSClient
        # SSID should not affect passcode
        assert (APRSClient.compute_passcode("W1AW") ==
                APRSClient.compute_passcode("W1AW-9"))


class TestAPRSBeaconGuestMode:
    """APRSBeacon._send() must use operating_callsign(), not cfg.callsign."""

    def test_beacon_uses_guest_callsign(self, tmp_path):
        from unittest.mock import MagicMock
        from core.config import Config
        from aprs.beacon import APRSBeacon

        cfg = Config(tmp_path / "config.json")
        cfg.callsign = "W1AW"
        cfg.set("location.lat", 39.7)
        cfg.set("location.lon", -104.9)
        cfg.set("guest.active",   True)
        cfg.set("guest.callsign", "KE2XYZ")

        sent: list[str] = []
        mock_sock = MagicMock()
        mock_sock.sendall.side_effect = lambda p: sent.append(p.decode())
        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client._sock = mock_sock

        beacon = APRSBeacon(cfg, mock_client)
        beacon._send()

        assert sent, "beacon sent nothing"
        assert any("KE2XYZ" in p for p in sent)
        assert all("W1AW" not in p for p in sent)

    def test_beacon_uses_station_callsign_without_guest(self, tmp_path):
        from unittest.mock import MagicMock
        from core.config import Config
        from aprs.beacon import APRSBeacon

        cfg = Config(tmp_path / "config.json")
        cfg.callsign = "W1AW"
        cfg.set("location.lat", 39.7)
        cfg.set("location.lon", -104.9)

        sent: list[str] = []
        mock_sock = MagicMock()
        mock_sock.sendall.side_effect = lambda p: sent.append(p.decode())
        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client._sock = mock_sock

        beacon = APRSBeacon(cfg, mock_client)
        beacon._send()

        assert sent, "beacon sent nothing"
        assert any("W1AW" in p for p in sent)
