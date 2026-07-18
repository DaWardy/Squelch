# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/survey_report — HTML/text report of a survey baseline
comparison (ROADMAP §13.2)."""

from pathlib import Path

from core.rf_baseline import BaselineDiff, SignalDelta
from core.survey_report import (
    diff_rows, diff_to_text, diff_to_html, write_report)


def _delta(kind, hz, peak, ref_peak, label="", cat=""):
    return SignalDelta(
        kind=kind, center_hz=hz, bandwidth_hz=2500, peak_db=peak,
        ref_peak_db=ref_peak, delta_db=round(peak - ref_peak, 2),
        label=label, category=cat)


def _diff():
    return BaselineDiff(
        ref_label="home-clean", cur_label="live",
        floor_delta_db=1.5,
        new=[_delta("new", 144_500_000, -42.0, 0.0, "bug?", "unknown")],
        changed=[_delta("changed", 14_074_000, -30.0, -50.0, "FT8", "amateur")],
        missing=[_delta("missing", 100_000_000, -60.0, -60.0, "FM", "broadcast")],
    )


# ── rows ─────────────────────────────────────────────────────────────────────
def test_diff_rows_flattens_all_kinds():
    rows = diff_rows(_diff())
    kinds = sorted(r["kind"] for r in rows)
    assert kinds == ["changed", "missing", "new"]
    new = next(r for r in rows if r["kind"] == "new")
    assert new["freq_mhz"] == 144.5
    assert new["bw_khz"] == 2.5


def test_diff_rows_none_safe():
    assert diff_rows(None) == []


# ── text ─────────────────────────────────────────────────────────────────────
def test_text_report_has_sections_and_meta():
    txt = diff_to_text(_diff(), title="Sweep", location="FM18", when="now")
    assert "Sweep" in txt
    assert "Location:  FM18" in txt
    assert "Appeared (anomalies) (1)" in txt
    assert "Power changed (1)" in txt
    assert "Vanished (1)" in txt
    assert "144.500000 MHz" in txt


def test_text_report_empty_sections():
    txt = diff_to_text(BaselineDiff())
    assert "(none)" in txt
    assert "Anomalies (appeared + changed): 0" in txt


# ── html ─────────────────────────────────────────────────────────────────────
def test_html_report_structure():
    doc = diff_to_html(_diff(), title="Sweep")
    assert doc.startswith("<!doctype html>")
    assert "<title>Sweep</title>" in doc
    assert "Appeared (anomalies) (1)" in doc
    assert "144.500000" in doc


def test_html_escapes_string_fields():
    """RF/user-derived strings must be escaped (map-XSS lesson)."""
    d = BaselineDiff(new=[_delta("new", 100_000_000, -40, 0,
                                 label="<script>x</script>", cat="a&b")])
    doc = diff_to_html(d)
    assert "<script>x</script>" not in doc
    assert "&lt;script&gt;" in doc
    assert "a&amp;b" in doc


def test_html_escapes_meta():
    d = BaselineDiff(ref_label="<b>ref</b>")
    doc = diff_to_html(d, location="<i>loc</i>", when="<u>w</u>")
    assert "<b>ref</b>" not in doc
    assert "&lt;b&gt;ref&lt;/b&gt;" in doc


# ── file output ──────────────────────────────────────────────────────────────
def test_write_html_report(tmp_path):
    p = write_report(_diff(), tmp_path / "r.html", fmt="html")
    assert p is not None and Path(p).exists()
    assert "<!doctype html>" in Path(p).read_text(encoding="utf-8")


def test_write_text_report(tmp_path):
    p = write_report(_diff(), tmp_path / "r.txt", fmt="text")
    assert p is not None
    assert "Appeared (anomalies)" in Path(p).read_text(encoding="utf-8")


def test_write_report_none_diff_safe(tmp_path):
    # None diff still renders an (empty) report rather than raising
    p = write_report(None, tmp_path / "empty.html", fmt="html")
    assert p is not None and Path(p).exists()
