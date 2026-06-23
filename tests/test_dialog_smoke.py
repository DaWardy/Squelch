# Squelch QA gate — dialog construction smoke tests (DevSecOps QA/QC)
# Licensed under GNU GPL v3
from __future__ import annotations
"""
Dialogs are built on button-click and were never exercised by tests — the same
untested surface where the QToolButton(text) crash lived. This builds each
dialog under offscreen Qt (no exec(), so no modal loop) and fails if
construction raises. A live QApplication is provided by the autouse fixture in
conftest.py.

Skips where PyQt6 is unavailable. Run via the venv (qa_check does so).
"""
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

pytest.importorskip("PyQt6", reason="PyQt6 not installed")


def _cfg():
    from core.config import Config
    return Config(Path(tempfile.mkdtemp()) / "config.json")


def _logdb():
    from core.log_db import LogDB
    return LogDB(":memory:")


def test_band_plan_dialog_builds():
    from ui.dialogs.band_plan_dialog import BandPlanDialog
    d = BandPlanDialog("Extra")
    assert d is not None
    d.close()


def test_dxcc_needed_dialog_builds():
    from ui.dialogs.dxcc_needed_dialog import DXCCNeededDialog
    d = DXCCNeededDialog(worked={"United States"}, confirmed={"Japan"})
    assert d is not None
    d.close()


def test_grid_calc_dialog_builds():
    from ui.dialogs.grid_calc_dialog import GridCalcDialog
    d = GridCalcDialog(_cfg())
    assert d is not None
    d.close()


def test_log_stats_dialog_builds():
    from ui.dialogs.log_stats_dialog import LogStatsDialog
    d = LogStatsDialog(_logdb())
    assert d is not None
    d.close()


def test_session_summary_dialog_builds():
    from ui.dialogs.session_summary_dialog import SessionSummaryDialog
    d = SessionSummaryDialog(None, _logdb(), datetime.now(timezone.utc))
    assert d is not None
    d.close()


def test_paths_dialog_builds():
    from ui.dialogs.paths_dialog import PathsDialog
    d = PathsDialog(_cfg())
    assert d is not None
    d.close()


def test_settings_dialog_builds():
    """The big one — 7 tab mixins; never exercised before."""
    from ui.dialogs.settings_dialog import SettingsDialog
    d = SettingsDialog(_cfg())
    assert d is not None
    d.close()


def test_log_stats_dialog_with_data():
    """Build the analytics dialog against a DB that has QSOs (exercises the
    per-band/mode/year/entity query + chart paths)."""
    from core.log_db import LogDB, QSO
    from ui.dialogs.log_stats_dialog import LogStatsDialog
    db = LogDB(":memory:")
    db.log_qso(QSO(call="W1AW", band="20m", mode="FT8",
                   datetime_on="2026-01-01T00:00:00Z", dxcc="United States"))
    db.log_qso(QSO(call="JA1XYZ", band="40m", mode="CW",
                   datetime_on="2026-02-01T00:00:00Z", dxcc="Japan"))
    d = LogStatsDialog(db)
    assert d is not None
    d.close()
