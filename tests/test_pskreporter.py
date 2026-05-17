from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for PSKReporter spot submission."""

import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from network.pskreporter import (
    PSKReporter, ReceptionReport,
    _xml_escape, _utc_str)


class TestReceptionReport:
    def test_defaults(self):
        r = ReceptionReport(
            dx_call="W4XYZ",
            freq_hz=14074000,
            mode="FT8")
        assert r.dx_call == "W4XYZ"
        assert r.freq_hz == 14074000
        assert r.mode == "FT8"

    def test_timestamp_auto_set(self):
        before = time.time()
        r = ReceptionReport("NR6U", 14074000, "FT8")
        assert r.timestamp >= before

    def test_default_snr(self):
        r = ReceptionReport("NR6U", 14074000, "FT8")
        assert r.snr_db == -99


class TestPSKReporterXML:
    def setup_method(self):
        from core.config import Config
        import tempfile
        self._tmp = tempfile.mkdtemp()
        self.cfg  = Config(
            Path(self._tmp) / "config.json")
        self.cfg.callsign = "NR6U"
        self.cfg.grid     = "DM79rr"
        self.psk = PSKReporter(self.cfg)

    def test_build_xml_payload(self):
        spots = [
            ReceptionReport("W4XYZ", 14074000,
                            "FT8", snr_db=-10)]
        xml = self.psk._build_xml_payload(spots)
        assert "receptionReport" in xml
        assert "W4XYZ" in xml
        assert "NR6U" in xml
        assert "14074000" in xml

    def test_xml_has_receiver(self):
        spots = []
        xml = self.psk._build_xml_payload(spots)
        assert "receiverInfo" in xml
        assert "NR6U" in xml

    def test_xml_well_formed(self):
        import xml.etree.ElementTree as ET
        spots = [
            ReceptionReport("W4XYZ", 14074000, "FT8")]
        xml = self.psk._build_xml_payload(spots)
        # Should parse without error
        root = ET.fromstring(xml)
        assert root is not None

    def test_add_spot_deduplicates(self):
        self.psk.add_spot(
            ReceptionReport("W4XYZ", 14074000, "FT8",
                            snr_db=-10))
        self.psk.add_spot(
            ReceptionReport("W4XYZ", 14074500, "FT8",
                            snr_db=-5))
        assert self.psk.pending_count == 1

    def test_add_spot_different_calls(self):
        self.psk.add_spot(
            ReceptionReport("W4XYZ", 14074000, "FT8"))
        self.psk.add_spot(
            ReceptionReport("K4ABC", 14074000, "FT8"))
        assert self.psk.pending_count == 2


class TestXMLEscape:
    def test_ampersand(self):
        assert _xml_escape("A&B") == "A&amp;B"

    def test_lt_gt(self):
        assert _xml_escape("<tag>") == "&lt;tag&gt;"

    def test_quotes(self):
        assert "&quot;" in _xml_escape('"hello"')

    def test_clean_string(self):
        assert _xml_escape("NR6U") == "NR6U"


class TestUTCStr:
    def test_returns_string(self):
        s = _utc_str(time.time())
        assert isinstance(s, str)
        assert "T" in s
        assert "Z" in s

    def test_format(self):
        import re
        s = _utc_str(1000000000)
        assert re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', s)
