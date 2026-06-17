"""Tests for LogDB duplicate detection — is_duplicate() and worked_before()."""
from __future__ import annotations
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest
from datetime import datetime, timezone, timedelta
from core.log_db import LogDB, QSO


@pytest.fixture()
def db(tmp_path):
    d = LogDB(tmp_path / "test.db")
    yield d
    d.close()


def _qso(call, band="20m", mode="FT8", hours_ago=1):
    dt = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return QSO(
        call=call, band=band, mode=mode,
        datetime_on=dt.strftime("%Y-%m-%dT%H:%M:%SZ"))


class TestWorkedBefore:
    def test_empty_log(self, db):
        assert not db.worked_before("W1AW")

    def test_returns_true_after_add(self, db):
        db.log_qso(_qso("W1AW"))
        assert db.worked_before("W1AW")

    def test_case_insensitive(self, db):
        db.log_qso(_qso("W1AW"))
        assert db.worked_before("w1aw")

    def test_different_call_not_found(self, db):
        db.log_qso(_qso("W1AW"))
        assert not db.worked_before("K1ABC")

    def test_different_band_still_found(self, db):
        db.log_qso(_qso("W1AW", band="40m"))
        assert db.worked_before("W1AW")


class TestIsDuplicate:
    def test_empty_log(self, db):
        assert not db.is_duplicate("W1AW", "20m", "FT8")

    def test_recent_same_band_mode(self, db):
        db.log_qso(_qso("W1AW", band="20m", mode="FT8", hours_ago=1))
        assert db.is_duplicate("W1AW", "20m", "FT8", hours=24)

    def test_old_qso_not_dupe(self, db):
        db.log_qso(_qso("W1AW", band="20m", mode="FT8", hours_ago=48))
        assert not db.is_duplicate("W1AW", "20m", "FT8", hours=24)

    def test_different_band_not_dupe(self, db):
        db.log_qso(_qso("W1AW", band="40m", mode="FT8", hours_ago=1))
        assert not db.is_duplicate("W1AW", "20m", "FT8", hours=24)

    def test_different_mode_not_dupe(self, db):
        db.log_qso(_qso("W1AW", band="20m", mode="CW", hours_ago=1))
        assert not db.is_duplicate("W1AW", "20m", "FT8", hours=24)

    def test_case_insensitive(self, db):
        db.log_qso(_qso("W1AW", band="20m", mode="FT8", hours_ago=1))
        assert db.is_duplicate("w1aw", "20m", "FT8", hours=24)

    def test_hours_boundary(self, db):
        db.log_qso(_qso("W1AW", band="20m", mode="FT8", hours_ago=2))
        assert db.is_duplicate("W1AW", "20m", "FT8", hours=3)
        assert not db.is_duplicate("W1AW", "20m", "FT8", hours=1)

    def test_multiple_calls(self, db):
        db.log_qso(_qso("W1AW", band="20m", mode="FT8", hours_ago=1))
        db.log_qso(_qso("K1ABC", band="20m", mode="FT8", hours_ago=1))
        assert db.is_duplicate("W1AW", "20m", "FT8")
        assert db.is_duplicate("K1ABC", "20m", "FT8")
        assert not db.is_duplicate("VK2XYZ", "20m", "FT8")


# ── Dupe label predicate (mirrors _check_dupe logic in log_tab) ──────────────

def _dupe_text(call: str, band: str, mode: str,
               db: LogDB, hours: int = 24) -> str:
    """Mirror of the dupe indicator logic in _wire_dupe_check."""
    call = call.strip().upper()
    if not call:
        return ""
    if db.is_duplicate(call, band, mode, hours=hours):
        return f"⚠ Worked {call} on {band}/{mode} in last {hours}h"
    if db.worked_before(call):
        return f"ℹ Worked {call} before (different band/mode)"
    return ""


class TestDupeLabelLogic:
    def test_no_prior_qsos(self, db):
        assert _dupe_text("W1AW", "20m", "FT8", db) == ""

    def test_recent_dupe_shows_warning(self, db):
        db.log_qso(_qso("W1AW", band="20m", mode="FT8", hours_ago=1))
        text = _dupe_text("W1AW", "20m", "FT8", db)
        assert "⚠" in text
        assert "W1AW" in text

    def test_old_worked_shows_info(self, db):
        db.log_qso(_qso("W1AW", band="20m", mode="FT8", hours_ago=48))
        text = _dupe_text("W1AW", "20m", "FT8", db)
        assert "ℹ" in text
        assert "W1AW" in text

    def test_different_band_shows_info(self, db):
        db.log_qso(_qso("W1AW", band="40m", mode="FT8", hours_ago=1))
        text = _dupe_text("W1AW", "20m", "FT8", db)
        assert "ℹ" in text

    def test_empty_callsign(self, db):
        assert _dupe_text("", "20m", "FT8", db) == ""
