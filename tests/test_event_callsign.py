"""FEAT-08 — Event / portable callsign tests.

Verifies that operating_callsign() honours the priority order:
  1. guest.callsign (supervised student)
  2. station.event_callsign (portable / special-event override)
  3. cfg.callsign (normal station call)

Also tests sanitisation: only [A-Z0-9/] characters pass through.
"""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from core.guest_op import operating_callsign


class _FakeCfg:
    """Minimal config stub."""

    def __init__(self, callsign="", event="", guest_active=False,
                 guest_call=""):
        self.callsign = callsign
        self._data = {
            "station.event_callsign": event,
            "guest.active": guest_active,
            "guest.callsign": guest_call,
        }

    def get(self, key, default=None):
        return self._data.get(key, default)


class TestOperatingCallsignPriority:

    def test_normal_call_returned(self):
        cfg = _FakeCfg(callsign="W1AW")
        assert operating_callsign(cfg) == "W1AW"

    def test_event_call_overrides_station(self):
        cfg = _FakeCfg(callsign="W1AW", event="W1AW/5")
        assert operating_callsign(cfg) == "W1AW/5"

    def test_event_call_centennial(self):
        cfg = _FakeCfg(callsign="W1AW", event="W100AW")
        assert operating_callsign(cfg) == "W100AW"

    def test_event_call_mobile(self):
        cfg = _FakeCfg(callsign="W1AW", event="W1AW/M")
        assert operating_callsign(cfg) == "W1AW/M"

    def test_guest_call_overrides_event_call(self):
        cfg = _FakeCfg(callsign="W1AW", event="W1AW/5",
                       guest_active=True, guest_call="KD0ABC")
        assert operating_callsign(cfg) == "KD0ABC"

    def test_guest_call_overrides_station_call(self):
        cfg = _FakeCfg(callsign="W1AW", guest_active=True, guest_call="KD0ABC")
        assert operating_callsign(cfg) == "KD0ABC"

    def test_empty_event_call_falls_through_to_station(self):
        cfg = _FakeCfg(callsign="W1AW", event="")
        assert operating_callsign(cfg) == "W1AW"

    def test_blank_whitespace_event_call_ignored(self):
        cfg = _FakeCfg(callsign="W1AW", event="   ")
        assert operating_callsign(cfg) == "W1AW"

    def test_empty_guest_call_falls_through_to_event(self):
        cfg = _FakeCfg(callsign="W1AW", event="W1AW/5",
                       guest_active=True, guest_call="")
        assert operating_callsign(cfg) == "W1AW/5"

    def test_all_empty_returns_empty(self):
        cfg = _FakeCfg(callsign="")
        assert operating_callsign(cfg) == ""


class TestOperatingCallsignSanitisation:

    def test_illegal_chars_stripped_from_event_call(self):
        cfg = _FakeCfg(callsign="W1AW", event="W1AW!#5")
        assert operating_callsign(cfg) == "W1AW5"

    def test_lowercase_event_call_uppercased(self):
        cfg = _FakeCfg(callsign="W1AW", event="w1aw/5")
        assert operating_callsign(cfg) == "W1AW/5"

    def test_slash_preserved_in_event_call(self):
        cfg = _FakeCfg(callsign="W1AW", event="W1AW/P")
        assert operating_callsign(cfg) == "W1AW/P"

    def test_digits_preserved_in_event_call(self):
        cfg = _FakeCfg(callsign="W1AW", event="W100AW")
        assert operating_callsign(cfg) == "W100AW"


class TestEventCallsignSettingsTab:
    """Source-level checks — field wired in station tab and dialog."""

    def test_event_callsign_field_in_station_tab(self):
        src = pathlib.Path(
            __file__).parent.parent / "ui/dialogs/settings_station_tab.py"
        text = src.read_text(encoding="utf-8")
        assert "_event_callsign" in text, \
            "_event_callsign widget missing from settings_station_tab.py"

    def test_event_callsign_saved_in_dialog(self):
        src = pathlib.Path(
            __file__).parent.parent / "ui/dialogs/settings_dialog.py"
        text = src.read_text(encoding="utf-8")
        assert "station.event_callsign" in text, \
            "station.event_callsign not saved in settings_dialog.py"

    def test_operating_callsign_checks_event_key(self):
        src = pathlib.Path(
            __file__).parent.parent / "core/guest_op.py"
        text = src.read_text(encoding="utf-8")
        assert "station.event_callsign" in text, \
            "operating_callsign() must read station.event_callsign"
