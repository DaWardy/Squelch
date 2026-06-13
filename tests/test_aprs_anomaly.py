"""Tests for network/aprs_anomaly.py — APRS anomaly detection (C-19)."""
from __future__ import annotations
import sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from network.aprs_anomaly import APRSAnomalyDetector


def _pkt(call="W1AW", lat=None, lon=None, path="WIDE1-1,WIDE2-1",
         symbol="/[", raw=None):
    p = {"from": call, "path": path, "symbol": symbol}
    if lat is not None:
        p["latitude"] = lat
    if lon is not None:
        p["longitude"] = lon
    p["raw"] = raw or f"{call}>APRS:{lat},{lon}"
    return p


# ---------------------------------------------------------------------------
# A1 — rapid beaconing
# ---------------------------------------------------------------------------

def test_a1_rapid_beacon_triggers():
    det = APRSAnomalyDetector()
    alerts = []
    for _ in range(10):
        alerts += det.feed(_pkt("K1FLOOD"))
    rules = [a.rule for a in alerts]
    assert "A1" in rules


def test_a1_normal_rate_no_alert():
    det = APRSAnomalyDetector()
    alerts = []
    for i in range(4):
        alerts += det.feed(_pkt("K1NORM", raw=f"unique{i}"))
    assert not any(a.rule == "A1" for a in alerts)


# ---------------------------------------------------------------------------
# A2 — impossible speed
# ---------------------------------------------------------------------------

def test_a2_impossible_speed_triggers():
    det = APRSAnomalyDetector()
    # Seed last_pos as if packet arrived 15s ago near NYC
    det._last_pos["W2SPD"] = (40.7, -74.0, time.monotonic() - 15)
    # Next packet places station in London — ~5572 km / 15s = impossibly fast
    alerts = det.feed(_pkt("W2SPD", lat=51.5, lon=-0.1))
    assert any(a.rule == "A2" for a in alerts)


def test_a2_slow_speed_no_alert():
    det = APRSAnomalyDetector()
    # Move 1 km over 1 hour — well under threshold
    det._last_pos["W2SLOW"] = (40.700, -74.000, time.monotonic() - 3600)
    alerts = det.feed(_pkt("W2SLOW", lat=40.709, lon=-74.000))
    assert not any(a.rule == "A2" for a in alerts)


def test_a2_no_false_positive_on_rapid_ingest():
    """Packets fed in burst (< 10s apart) skip speed check — avoids false pos."""
    det = APRSAnomalyDetector()
    det._last_pos["K1BURST"] = (40.700, -74.000, time.monotonic() - 1)
    # 0.01 degree lat shift looks fast at 1s gap but should be skipped
    alerts = det.feed(_pkt("K1BURST", lat=40.710, lon=-74.000))
    assert not any(a.rule == "A2" for a in alerts)


# ---------------------------------------------------------------------------
# A3 — path abuse
# ---------------------------------------------------------------------------

def test_a3_extreme_path_triggers():
    det = APRSAnomalyDetector()
    alerts = det.feed(_pkt("K1BAD", path="WIDE7-7,WIDE6-5"))
    assert any(a.rule == "A3" for a in alerts)


def test_a3_normal_path_no_alert():
    det = APRSAnomalyDetector()
    alerts = det.feed(_pkt("K1GOOD", path="WIDE1-1,WIDE2-1"))
    assert not any(a.rule == "A3" for a in alerts)


# ---------------------------------------------------------------------------
# A4 — symbol mismatch
# ---------------------------------------------------------------------------

def test_a4_symbol_change_triggers():
    det = APRSAnomalyDetector()
    det.feed(_pkt("K1SYM", symbol="/["))   # first seen: /[
    alerts = det.feed(_pkt("K1SYM", symbol="/j"))  # different symbol
    assert any(a.rule == "A4" for a in alerts)


def test_a4_same_symbol_no_alert():
    det = APRSAnomalyDetector()
    det.feed(_pkt("K1SYM2", symbol="/["))
    alerts = det.feed(_pkt("K1SYM2", symbol="/["))
    assert not any(a.rule == "A4" for a in alerts)


# ---------------------------------------------------------------------------
# A5 — duplicate / replay
# ---------------------------------------------------------------------------

def test_a5_exact_duplicate_triggers():
    det = APRSAnomalyDetector()
    p = _pkt("K1DUP", raw="K1DUP>APRS:hello")
    det.feed(p)
    alerts = det.feed(p)   # exact same raw
    assert any(a.rule == "A5" for a in alerts)


def test_a5_different_content_no_alert():
    det = APRSAnomalyDetector()
    det.feed(_pkt("K1DIFF", raw="K1DIFF>APRS:msg1"))
    alerts = det.feed(_pkt("K1DIFF", raw="K1DIFF>APRS:msg2"))
    assert not any(a.rule == "A5" for a in alerts)


# ---------------------------------------------------------------------------
# Alert structure
# ---------------------------------------------------------------------------

def test_alert_has_required_fields():
    det = APRSAnomalyDetector()
    p = _pkt("K1FLD", path="WIDE7-7")
    alerts = det.feed(p)
    assert alerts
    a = alerts[0]
    assert a.rule
    assert a.callsign == "K1FLD"
    assert a.description
    assert a.packet is p
    assert str(a).startswith("[")
