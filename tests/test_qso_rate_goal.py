from __future__ import annotations
"""Tests for the daily QSO rate goal feature (pure-logic)."""
import sys
import pytest
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))


def _today_prefix() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")


# ── Pure-logic: color threshold rules ────────────────────────────────────────

class TestGoalColorThresholds:
    def _color(self, today, goal) -> str:
        if not goal:
            return "none"
        pct = today / goal
        if pct >= 1.0:
            return "green"
        elif pct >= 0.5:
            return "amber"
        return "red"

    def test_no_goal_returns_no_color(self):
        assert self._color(5, 0) == "none"

    def test_goal_met_is_green(self):
        assert self._color(25, 25) == "green"

    def test_over_goal_is_green(self):
        assert self._color(30, 25) == "green"

    def test_halfway_is_amber(self):
        assert self._color(13, 25) == "amber"

    def test_exactly_half_is_amber(self):
        assert self._color(12, 24) == "amber"   # 0.5 exactly → amber

    def test_below_half_is_red(self):
        assert self._color(5, 25) == "red"

    def test_zero_qsos_with_goal_is_red(self):
        assert self._color(0, 25) == "red"

    def test_one_below_goal_is_amber(self):
        assert self._color(24, 25) == "amber"


# ── Pure-logic: display format ───────────────────────────────────────────────

class TestGoalDisplayFormat:
    def _fmt(self, today, goal) -> str:
        if goal:
            return f"{today}/{goal}"
        return str(today)

    def test_no_goal_shows_plain_count(self):
        assert self._fmt(7, 0) == "7"

    def test_with_goal_shows_ratio(self):
        assert self._fmt(15, 25) == "15/25"

    def test_goal_met_shows_ratio(self):
        assert self._fmt(25, 25) == "25/25"

    def test_zero_with_goal_shows_zero_ratio(self):
        assert self._fmt(0, 10) == "0/10"


# ── Pure-logic: today count from QSO list ────────────────────────────────────

class TestTodayQSOCount:
    def _count_today(self, qsos):
        today_start = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
        return sum(
            1 for q in qsos
            if q and q >= today_start)

    def test_empty_list_returns_zero(self):
        assert self._count_today([]) == 0

    def test_old_qso_not_counted(self):
        assert self._count_today(["2020-01-01T12:00:00Z"]) == 0

    def test_todays_qso_counted(self):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT12:00:00Z")
        assert self._count_today([ts]) == 1

    def test_mixed_dates(self):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT10:00:00Z")
        assert self._count_today(["2020-01-01T00:00:00Z", ts, ts]) == 2


# ── Pure-logic: config key contract ──────────────────────────────────────────

class TestGoalConfigKey:
    def test_default_is_zero(self, tmp_path):
        from core.config import Config
        cfg = Config(tmp_path / "config.json")
        assert cfg.get("log.daily_goal", 0) == 0

    def test_can_roundtrip(self, tmp_path):
        from core.config import Config
        cfg = Config(tmp_path / "config.json")
        cfg.set("log.daily_goal", 42)
        assert cfg.get("log.daily_goal", 0) == 42
