# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/survey_session.SurveyStore — the saved-baseline library that
lets the survey/compare workflow span sessions and locations (ROADMAP §4.5 I-1,
§13.1)."""

from pathlib import Path

import pytest

from core.rf_baseline import Baseline, baseline_from_spectrum
from core.survey_session import SurveyStore, SurveyEntry, _slug, _compact


def _baseline(label="site-a", floor=-100.0, peak=-40.0, lo=500, hi=525,
              center_lo=99_000_000):
    """A baseline with one occupied segment."""
    n = 1024
    powers = [floor] * n
    for i in range(lo, hi):
        powers[i] = peak
    bin_hz = 2_400_000 / n
    return baseline_from_spectrum(powers, center_lo, bin_hz, label=label)


# ── save / list / load ───────────────────────────────────────────────────────
def test_save_returns_entry(tmp_path):
    store = SurveyStore(tmp_path)
    entry = store.save(_baseline("home"), "home")
    assert isinstance(entry, SurveyEntry)
    assert entry.label == "home"
    assert entry.n_segments >= 1
    assert Path(entry.path).exists()


def test_list_newest_first(tmp_path):
    store = SurveyStore(tmp_path)
    b1 = _baseline("a"); b1.created = "2026-07-01T00:00:00Z"
    b2 = _baseline("b"); b2.created = "2026-07-18T00:00:00Z"
    store.save(b1); store.save(b2)
    ids = [e.label for e in store.list()]
    assert ids == ["b", "a"]           # newest (2026-07-18) first


def test_load_round_trip(tmp_path):
    store = SurveyStore(tmp_path)
    entry = store.save(_baseline("rt"))
    loaded = store.load(entry.id)
    assert isinstance(loaded, Baseline)
    assert loaded.label == "rt"
    assert len(loaded.segments) >= 1


def test_delete(tmp_path):
    store = SurveyStore(tmp_path)
    entry = store.save(_baseline("gone"))
    assert store.delete(entry.id) is True
    assert store.load(entry.id) is None
    assert store.delete(entry.id) is False        # already gone


def test_unique_stems_no_collision(tmp_path):
    store = SurveyStore(tmp_path)
    b = _baseline("dup"); b.created = "2026-07-18T12:00:00Z"
    e1 = store.save(Baseline.from_dict(b.to_dict()))
    e2 = store.save(Baseline.from_dict(b.to_dict()))
    assert e1.id != e2.id
    assert len(store.list()) == 2


def test_list_empty_dir(tmp_path):
    assert SurveyStore(tmp_path / "nope").list() == []


def test_list_skips_bad_files(tmp_path):
    store = SurveyStore(tmp_path)
    store.save(_baseline("good"))
    (tmp_path / "junk.json").write_text("{not valid json", encoding="utf-8")
    entries = store.list()
    assert len(entries) == 1
    assert entries[0].label == "good"


# ── compare ──────────────────────────────────────────────────────────────────
def test_compare_live_vs_saved_finds_new(tmp_path):
    store = SurveyStore(tmp_path)
    ref_entry = store.save(_baseline("ref", lo=500, hi=525))
    # current has an ADDITIONAL signal the reference lacked
    cur = _baseline("live", lo=500, hi=525)
    extra = _baseline("x", lo=800, hi=820).segments[0]
    cur.segments.append(extra)
    diff = store.compare(ref_entry.id, cur)
    assert diff is not None
    assert diff.anomaly_count >= 1
    assert any(d.center_hz == int(extra.center_hz) for d in diff.new)


def test_compare_ids_two_saved(tmp_path):
    store = SurveyStore(tmp_path)
    a = store.save(_baseline("A", lo=500, hi=525))
    b_bl = _baseline("B", lo=500, hi=525)
    b_bl.segments.append(_baseline("x", lo=800, hi=820).segments[0])
    b = store.save(b_bl)
    diff = store.compare_ids(a.id, b.id)
    assert diff is not None and diff.anomaly_count >= 1


def test_compare_missing_ref_returns_none(tmp_path):
    store = SurveyStore(tmp_path)
    assert store.compare("does-not-exist", _baseline()) is None
    assert store.compare("x", None) is None


# ── safety: path traversal is rejected ───────────────────────────────────────
@pytest.mark.parametrize("bad", [
    "../evil", "..\\evil", "a/b", "a\\b", "..", "foo/../bar", ""])
def test_unsafe_ids_rejected(tmp_path, bad):
    store = SurveyStore(tmp_path)
    assert store.load(bad) is None
    assert store.delete(bad) is False


# ── helpers ──────────────────────────────────────────────────────────────────
def test_slug_and_compact():
    assert _slug("Home QTH!") == "home-qth"
    assert _slug("") == "baseline"
    assert _compact("2026-07-18T12:34:56Z") == "20260718-123456"
    assert _compact("") == "baseline"
