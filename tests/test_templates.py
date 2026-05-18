from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
# Squelch tests — winlink/templates.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from winlink.templates import (
    ics213, ics214, winlink_wednesday,
    welfare_message, radiogram,
    WinlinkMessage, TEMPLATE_LIST)


class TestICS213:
    def test_returns_message(self):
        msg = ics213("Test Incident", "NR6U", "Op",
                     "EOC", "EC", "Test message")
        assert isinstance(msg, WinlinkMessage)

    def test_subject_contains_incident(self):
        msg = ics213("FLOOD2026", "NR6U", "Op",
                     "EOC", "EC", "Message")
        assert "FLOOD2026" in msg.subject

    def test_body_contains_fields(self):
        msg = ics213("TEST", "NR6U", "Radio Op",
                     "EOC", "Coordinator",
                     "All clear")
        assert "NR6U" in msg.body
        assert "EOC" in msg.body
        assert "All clear" in msg.body

    def test_to_field_set(self):
        msg = ics213("INC", "NR6U", "Op",
                     "K4EOC", "EC", "Msg",
                     reply_to="K4EOC")
        assert msg.to == "K4EOC"


class TestICS214:
    def test_returns_message(self):
        msg = ics214("Test", "NR6U", "NR6U",
                     "Period 1", ["Checked in"], ["NR6U"])
        assert isinstance(msg, WinlinkMessage)

    def test_body_has_activities(self):
        acts = ["Set up station", "Made contact"]
        msg = ics214("INC", "NR6U", "NR6U",
                     "0800-1600", acts, ["NR6U"])
        assert "Set up station" in msg.body
        assert "Made contact" in msg.body

    def test_to_is_tactical(self):
        msg = ics214("INC", "NR6U", "NR6U",
                     "Period", [], [])
        assert msg.to == "TACTICAL"


class TestWinlinkWednesday:
    def test_returns_message(self):
        msg = winlink_wednesday(
            "NR6U", "DM79rr", "Radio Op",
            "Denver", "CO")
        assert isinstance(msg, WinlinkMessage)

    def test_to_winlink_wednesday(self):
        msg = winlink_wednesday(
            "NR6U", "DM79rr", "Op", "City", "ST")
        assert "WW@winlink.org" in msg.to

    def test_contains_callsign(self):
        msg = winlink_wednesday(
            "NR6U", "DM79rr", "Op", "Denver", "CO")
        assert "NR6U" in msg.body

    def test_contains_grid(self):
        msg = winlink_wednesday(
            "NR6U", "DM79rr", "Op", "Denver", "CO")
        assert "DM79rr" in msg.body


class TestWelfareMessage:
    def test_returns_message(self):
        msg = welfare_message(
            "NR6U", "John", "Jane",
            "jane@example.com", "I am safe")
        assert isinstance(msg, WinlinkMessage)

    def test_body_contains_message(self):
        msg = welfare_message(
            "NR6U", "John", "Jane",
            "jane@example.com", "Safe and well")
        assert "Safe and well" in msg.body

    def test_to_is_email(self):
        msg = welfare_message(
            "NR6U", "John", "Jane",
            "jane@example.com", "OK")
        assert "@" in msg.to


class TestRadiogram:
    def test_returns_message(self):
        msg = radiogram(
            "ROUTINE", "W4XYZ", "John Smith",
            "123 Main St", "555-1234",
            "Test message", "NR6U", "Operator")
        assert isinstance(msg, WinlinkMessage)

    def test_body_has_precedence(self):
        msg = radiogram(
            "PRIORITY", "W4XYZ", "John",
            "123 Main", "555-1234",
            "Urgent message", "NR6U", "Op")
        assert "PRIORITY" in msg.body

    def test_message_uppercase(self):
        msg = radiogram(
            "ROUTINE", "W4XYZ", "John",
            "123 Main", "555-1234",
            "test message", "NR6U", "Op")
        assert "TEST MESSAGE" in msg.body


class TestTemplateList:
    def test_has_entries(self):
        assert len(TEMPLATE_LIST) >= 5

    def test_each_has_name_and_desc(self):
        for item in TEMPLATE_LIST:
            name, desc = item
            assert name
            assert desc

    def test_ics213_present(self):
        names = [t[0] for t in TEMPLATE_LIST]
        assert any("ICS-213" in n for n in names)

    def test_winlink_wednesday_present(self):
        names = [t[0] for t in TEMPLATE_LIST]
        assert any("Wednesday" in n for n in names)
