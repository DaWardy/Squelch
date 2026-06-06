# Squelch tests — network activity log (consumer req C-12, Priya)
# Licensed under GNU GPL v3
from __future__ import annotations
"""Verify the network activity logger records and classifies connections."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_records_and_classifies():
    from core import netlog
    netlog._RING.clear()
    netlog.record_connection("noaa.gov", purpose="bands", user_initiated=False)
    netlog.record_connection("qrz.com", purpose="lookup", user_initiated=True)
    events = netlog.recent_events()
    assert len(events) == 2
    assert events[0]["host"] == "noaa.gov"
    assert events[0]["user_initiated"] is False
    assert events[1]["user_initiated"] is True

def test_auto_count():
    from core import netlog
    netlog._RING.clear()
    netlog.record_connection("a", user_initiated=False)
    netlog.record_connection("b", user_initiated=False)
    netlog.record_connection("c", user_initiated=True)
    assert netlog.auto_connection_count() == 2

def test_credentials_redacted():
    from core import netlog
    netlog._RING.clear()
    netlog.record_connection("lotw.arrl.org/x?login=W1AW&password=secret",
                            user_initiated=True)
    ev = netlog.recent_events()[-1]
    assert "secret" not in ev["host"]
    assert "***" in ev["host"]

def test_never_raises_on_bad_input():
    from core import netlog
    # Must not raise even with odd input
    netlog.record_connection(None)  # type: ignore
    netlog.record_connection(12345)  # type: ignore
