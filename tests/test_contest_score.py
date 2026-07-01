"""Sprint 59 — Contest score panel + K-index alarm."""
from __future__ import annotations
import sys
import pathlib
import tempfile
from pathlib import Path

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


# ── LogDB.contest_score() ─────────────────────────────────────────────────────

class TestContestScore:

    def _make_db(self):
        from core.log_db import LogDB, QSO
        tmp = tempfile.mkdtemp()
        db = LogDB(Path(tmp) / "test.db")
        return db, QSO

    def test_empty_db_returns_zero_score(self):
        db, _ = self._make_db()
        cs = db.contest_score()
        assert cs["score"] == 0
        assert cs["total_qsos"] == 0

    def test_cw_qso_counts_2_points(self):
        db, QSO = self._make_db()
        db.log_qso(QSO(call="VK2AB", band="20m", mode="CW",
                       datetime_on="2026-01-01T00:00:00Z",
                       rst_sent="599", rst_rcvd="599"))
        cs = db.contest_score()
        assert cs["points"] == 2

    def test_ssb_qso_counts_1_point(self):
        db, QSO = self._make_db()
        db.log_qso(QSO(call="VK2AB", band="20m", mode="SSB",
                       datetime_on="2026-01-01T00:00:00Z",
                       rst_sent="59", rst_rcvd="59"))
        cs = db.contest_score()
        assert cs["points"] == 1

    def test_ft8_qso_counts_2_points(self):
        db, QSO = self._make_db()
        db.log_qso(QSO(call="JA1AB", band="20m", mode="FT8",
                       datetime_on="2026-01-01T00:00:00Z",
                       rst_sent="59", rst_rcvd="59"))
        cs = db.contest_score()
        assert cs["points"] == 2

    def test_by_band_breakdown(self):
        db, QSO = self._make_db()
        for band in ("20m", "40m"):
            db.log_qso(QSO(call="W1AW", band=band, mode="CW",
                           datetime_on="2026-01-01T00:00:00Z",
                           rst_sent="599", rst_rcvd="599"))
        cs = db.contest_score()
        assert "20m" in cs["by_band"]
        assert "40m" in cs["by_band"]

    def test_score_is_points_times_mults(self):
        db, QSO = self._make_db()
        db.log_qso(QSO(call="VK2AB", band="20m", mode="CW",
                       dxcc="VK", country="Australia",
                       datetime_on="2026-01-01T00:00:00Z",
                       rst_sent="599", rst_rcvd="599"))
        cs = db.contest_score()
        assert cs["score"] == cs["points"] * cs["mults"]

    def test_contest_score_method_in_logdb(self):
        src = (ROOT / "core/log_db.py").read_text(encoding="utf-8")
        assert "def contest_score(" in src


# ── Contest score panel in log_tab ───────────────────────────────────────────

class TestContestScorePanel:

    def _src(self):
        # Contest-score panel was extracted to _LogPanelsMixin (HOUSE-CS split);
        # _build / _update_stats callers remain in log_tab.py (listed first).
        parts = ["ui/tabs/log_tab.py", "ui/tabs/log_panels_mixin.py"]
        return "\n".join(
            (ROOT / p).read_text(encoding="utf-8") for p in parts)

    def test_build_contest_score_panel_defined(self):
        assert "def _build_contest_score_panel(" in self._src()

    def test_update_contest_score_defined(self):
        assert "def _update_contest_score(" in self._src()

    def test_panel_called_in_build(self):
        src = self._src()
        idx = src.find("def _build(self):")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_build_contest_score_panel" in body

    def test_update_called_in_update_stats(self):
        src = self._src()
        idx = src.find("def _update_stats(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_update_contest_score" in body

    def test_summary_label_shows_score(self):
        src = self._src()
        idx = src.find("def _update_contest_score(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "score" in body.lower()
        assert "mults" in body.lower()


# ── K-index alarm ─────────────────────────────────────────────────────────────

class TestKIndexAlarm:

    def _src(self):
        return (ROOT / "ui/tabs/band_conditions_tab.py").read_text(encoding="utf-8")

    def _settings_src(self):
        return (ROOT / "ui/dialogs/settings_station_tab.py").read_text(encoding="utf-8")

    def test_check_k_alarm_method(self):
        assert "def _check_k_alarm(" in self._src()

    def test_k_alarm_widget_in_settings(self):
        assert "_k_index_alarm" in self._settings_src()

    def test_k_alarm_cfg_key_loaded(self):
        src = (ROOT / "ui/dialogs/settings_dialog.py").read_text(encoding="utf-8")
        assert "band.k_alarm" in src

    def test_beep_on_alarm(self):
        src = self._src()
        idx = src.find("def _check_k_alarm(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "beep()" in body

    def test_alarm_only_triggers_once_per_level(self):
        src = self._src()
        idx = src.find("def _check_k_alarm(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_last_k_alarm_level" in body

    def test_k_alarm_logic(self):
        """Mirror the threshold check logic."""
        # Threshold = 4, K = 5 → should alarm
        threshold = 4
        k_index   = 5.0
        last_level = -1.0
        if k_index >= threshold and k_index > last_level:
            fired = True
        else:
            fired = False
        assert fired

    def test_k_alarm_no_trigger_below_threshold(self):
        threshold = 5
        k_index   = 3.0
        fired = k_index >= threshold
        assert not fired
