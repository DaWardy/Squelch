from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for Winlink message templates."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from winlink.templates import (
    ics213, ics214, ics309, radiogram, welfare,
    winlink_wednesday, ares_checkin, p2p_message,
    position_report, TEMPLATE_LIST, TEMPLATE_CATEGORIES,
    WinlinkMessage)


class TestWinlinkMessage:
    def test_dataclass(self):
        m = WinlinkMessage(to="W4XYZ", subject="Test", body="Hi")
        assert m.to == "W4XYZ"
        assert m.subject == "Test"
        assert m.body == "Hi"

    def test_header_block(self):
        m = WinlinkMessage(to="W4XYZ", subject="Test", body="Hi")
        h = m.header_block
        assert "W4XYZ" in h
        assert "Test" in h


class TestICS213:
    def test_returns_message(self):
        msg = ics213(incident="TEST", my_callsign="W1AW")
        assert isinstance(msg, WinlinkMessage)

    def test_contains_callsign(self):
        msg = ics213(my_callsign="W1AW")
        assert "W1AW" in msg.body

    def test_contains_incident(self):
        msg = ics213(incident="FIRE 2024")
        assert "FIRE 2024" in msg.body

    def test_subject_format(self):
        msg = ics213(incident="FLOOD", my_callsign="W4XYZ")
        assert "ICS-213" in msg.subject
        assert "W4XYZ" in msg.subject


class TestICS214:
    def test_returns_message(self):
        msg = ics214(incident="TEST")
        assert isinstance(msg, WinlinkMessage)

    def test_contains_incident(self):
        msg = ics214(incident="HURRICANE")
        assert "HURRICANE" in msg.body

    def test_contains_period(self):
        msg = ics214(op_period="Day 1")
        assert "Day 1" in msg.body


class TestICS309:
    def test_returns_message(self):
        msg = ics309(incident="TEST")
        assert isinstance(msg, WinlinkMessage)

    def test_subject_contains_309(self):
        msg = ics309(incident="FIRE")
        assert "309" in msg.subject


class TestRadiogram:
    def test_returns_message(self):
        msg = radiogram(to_name="John", message="Test")
        assert isinstance(msg, WinlinkMessage)

    def test_contains_radiogram_header(self):
        msg = radiogram()
        assert "RADIOGRAM" in msg.body.upper()

    def test_contains_message(self):
        msg = radiogram(message="Hello world")
        assert "Hello world" in msg.body

    def test_subject_has_radiogram(self):
        msg = radiogram(my_callsign="W1AW")
        assert "RADIOGRAM" in msg.subject.upper()


class TestWelfare:
    def test_returns_message(self):
        msg = welfare(to_name="Jane", to_city="Denver")
        assert isinstance(msg, WinlinkMessage)

    def test_contains_recipient(self):
        msg = welfare(to_name="Jane Smith")
        assert "Jane Smith" in msg.body

    def test_subject_welfare(self):
        msg = welfare(to_name="Test")
        assert "WELFARE" in msg.subject.upper()


class TestWinlinkWednesday:
    def test_returns_message(self):
        msg = winlink_wednesday(my_callsign="W4XYZ")
        assert isinstance(msg, WinlinkMessage)

    def test_contains_callsign(self):
        msg = winlink_wednesday(my_callsign="W1AW")
        assert "W1AW" in msg.body

    def test_contains_grid(self):
        msg = winlink_wednesday(grid="DM79")
        assert "DM79" in msg.body

    def test_to_winlink(self):
        msg = winlink_wednesday()
        assert "WINLINK" in msg.to.upper() or "@" in msg.to


class TestP2PMessage:
    def test_returns_message(self):
        msg = p2p_message(to_callsign="W4XYZ",
                          my_callsign="W1AW")
        assert isinstance(msg, WinlinkMessage)

    def test_p2p_type(self):
        msg = p2p_message(to_callsign="W4XYZ")
        assert msg.msg_type == "P2P"

    def test_to_is_destination(self):
        msg = p2p_message(to_callsign="W4XYZ")
        assert "W4XYZ" in msg.to


class TestPositionReport:
    def test_returns_message(self):
        msg = position_report(my_callsign="W1AW",
                               grid="DM79")
        assert isinstance(msg, WinlinkMessage)

    def test_contains_grid(self):
        msg = position_report(grid="DM79rr")
        assert "DM79rr" in msg.body


class TestTemplateList:
    def test_not_empty(self):
        assert len(TEMPLATE_LIST) > 0

    def test_each_is_3tuple(self):
        for item in TEMPLATE_LIST:
            assert len(item) == 3

    def test_each_has_name_and_desc(self):
        for name, fn, desc in TEMPLATE_LIST:
            assert name
            assert callable(fn)
            assert desc

    def test_has_ics213(self):
        names = [n for n, _, _ in TEMPLATE_LIST]
        assert any("ICS-213" in n or "213" in n
                   for n in names)

    def test_has_p2p(self):
        names = [n for n, _, _ in TEMPLATE_LIST]
        assert any("P2P" in n or "p2p" in n.lower()
                   for n in names)


class TestTemplateCategories:
    def test_categories_exist(self):
        assert len(TEMPLATE_CATEGORIES) >= 3

    def test_emcomm_category(self):
        cats = [c.name for c in TEMPLATE_CATEGORIES]
        assert "EmComm" in cats

    def test_p2p_category(self):
        cats = [c.name for c in TEMPLATE_CATEGORIES]
        assert any("P2P" in c or "Direct" in c
                   for c in cats)
