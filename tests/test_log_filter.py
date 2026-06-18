"""Tests for log tab filter logic — callsign, name, grid matching."""
from __future__ import annotations
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest
from core.log_db import LogDB, QSO


@pytest.fixture()
def db(tmp_path):
    d = LogDB(tmp_path / "test.db")
    yield d
    d.close()


def _make(call, name="", grid="", band="20m", mode="FT8"):
    return QSO(call=call, name=name, grid=grid, band=band, mode=mode)


# ── Mirror of _apply_filter logic ────────────────────────────────────────

def _matches(q: QSO, search: str = "", band: str = "",
             mode: str = "") -> bool:
    """Mirror of the core filter predicate in log_tab._apply_filter."""
    term = search.strip().upper()
    if term:
        if not any(
            term in (v or "").upper()
            for v in (q.call, q.name, q.grid,
                      q.dxcc, q.country, q.state, q.comment)
        ):
            return False
    if band and q.band != band:
        return False
    if mode and q.mode != mode:
        return False
    return True


class TestCallsignFilter:
    def test_full_match(self):
        assert _matches(_make("W1AW"), search="W1AW")

    def test_prefix_match(self):
        assert _matches(_make("W1AW"), search="W1")

    def test_no_match(self):
        assert not _matches(_make("W1AW"), search="K1ABC")

    def test_case_insensitive(self):
        assert _matches(_make("W1AW"), search="w1aw")

    def test_empty_search_matches_all(self):
        assert _matches(_make("W1AW"), search="")


class TestNameFilter:
    def test_name_match(self):
        assert _matches(_make("W1AW", name="John"), search="John")

    def test_name_partial_match(self):
        assert _matches(_make("W1AW", name="Jonathan"), search="JON")

    def test_name_no_match(self):
        assert not _matches(_make("W1AW", name="John"), search="Jane")

    def test_name_empty_no_match(self):
        assert not _matches(_make("W1AW", name=""), search="John")


class TestGridFilter:
    def test_grid_match(self):
        assert _matches(_make("W1AW", grid="DM79"), search="DM79")

    def test_grid_prefix(self):
        assert _matches(_make("W1AW", grid="DM79rr"), search="DM")

    def test_grid_case_insensitive(self):
        assert _matches(_make("W1AW", grid="DM79"), search="dm79")

    def test_grid_empty_no_match(self):
        assert not _matches(_make("W1AW", grid=""), search="DM79")


class TestBandModeFilter:
    def test_band_match(self):
        assert _matches(_make("W1AW", band="20m"), band="20m")

    def test_band_no_match(self):
        assert not _matches(_make("W1AW", band="40m"), band="20m")

    def test_mode_match(self):
        assert _matches(_make("W1AW", mode="FT8"), mode="FT8")

    def test_mode_no_match(self):
        assert not _matches(_make("W1AW", mode="SSB"), mode="FT8")

    def test_combined_filters(self):
        assert _matches(
            _make("W1AW", band="20m", mode="FT8"),
            search="W1", band="20m", mode="FT8")
        assert not _matches(
            _make("W1AW", band="40m", mode="FT8"),
            search="W1", band="20m", mode="FT8")


class TestExtendedSearch:
    """Search now covers DXCC entity, country, state, and comment fields."""

    def test_search_by_dxcc_entity(self):
        q = QSO(call="JA1XYZ", dxcc="Japan")
        assert _matches(q, search="Japan")

    def test_search_by_country(self):
        q = QSO(call="W1AW", country="United States")
        assert _matches(q, search="united states")

    def test_search_by_state(self):
        q = QSO(call="K5ABC", state="TX")
        assert _matches(q, search="TX")

    def test_search_by_comment(self):
        q = QSO(call="K5ABC", comment="FB DX first contact")
        assert _matches(q, search="FB DX")

    def test_unrelated_term_not_matched(self):
        q = QSO(call="W1AW", dxcc="United States",
                country="United States", state="CT",
                comment="nice signal")
        assert not _matches(q, search="Japan")
