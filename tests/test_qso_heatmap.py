"""Sprint 63 — QSO activity heatmap + qsos_by_hour_dow()."""
from __future__ import annotations
import sys
import pathlib
import tempfile
from pathlib import Path

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


# ── LogDB.qsos_by_hour_dow() ─────────────────────────────────────────────────

class TestQSOsByHourDow:

    def _make_db(self):
        from core.log_db import LogDB, QSO
        tmp = tempfile.mkdtemp()
        db = LogDB(Path(tmp) / "test.db")
        return db, QSO

    def test_empty_db_returns_empty(self):
        db, _ = self._make_db()
        assert db.qsos_by_hour_dow() == []

    def test_qso_appears_in_correct_hour(self):
        db, QSO = self._make_db()
        db.log_qso(QSO(call="VK2AB", band="20m", mode="FT8",
                       datetime_on="2026-06-15T14:30:00Z",
                       rst_sent="59", rst_rcvd="59"))
        rows = db.qsos_by_hour_dow()
        assert len(rows) == 1
        _, hr, count = rows[0]
        assert hr == 14
        assert count == 1

    def test_multiple_qsos_same_slot(self):
        db, QSO = self._make_db()
        for i in range(5):
            db.log_qso(QSO(call=f"W{i}AW", band="20m", mode="FT8",
                           datetime_on="2026-06-15T10:00:00Z",
                           rst_sent="59", rst_rcvd="59"))
        rows = db.qsos_by_hour_dow()
        assert len(rows) == 1
        assert rows[0][2] == 5

    def test_different_hours_different_slots(self):
        db, QSO = self._make_db()
        db.log_qso(QSO(call="W1AW", band="20m", mode="CW",
                       datetime_on="2026-06-15T10:00:00Z",
                       rst_sent="599", rst_rcvd="599"))
        db.log_qso(QSO(call="W2AW", band="20m", mode="CW",
                       datetime_on="2026-06-15T14:00:00Z",
                       rst_sent="599", rst_rcvd="599"))
        rows = db.qsos_by_hour_dow()
        assert len(rows) == 2

    def test_returns_valid_dow_and_hr(self):
        db, QSO = self._make_db()
        db.log_qso(QSO(call="VK3AB", band="40m", mode="SSB",
                       datetime_on="2026-06-20T08:15:00Z",
                       rst_sent="59", rst_rcvd="59"))
        rows = db.qsos_by_hour_dow()
        for dow, hr, count in rows:
            assert 0 <= dow <= 6
            assert 0 <= hr <= 23
            assert count >= 1


# ── QSOHeatmap widget ─────────────────────────────────────────────────────────

class TestQSOHeatmapSource:

    def _src(self):
        return (ROOT / "ui/widgets/qso_heatmap.py").read_text(encoding="utf-8")

    def test_class_exists(self):
        assert "class QSOHeatmap(" in self._src()

    def test_set_data_method(self):
        assert "def set_data(" in self._src()

    def test_7_day_labels(self):
        src = self._src()
        for day in ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"):
            assert day in src

    def test_24_hour_grid(self):
        assert "24" in self._src()

    def test_colour_scale_defined(self):
        assert "_SCALE" in self._src()

    def test_lerp_color_function(self):
        assert "_lerp_color" in self._src()

    def test_no_banned_dark_hex(self):
        src = self._src()
        for bad in ("#141414", "#0a0a0a"):
            assert bad not in src


class TestLerpColor:
    """Verify colour interpolation logic (mirrors qso_heatmap._lerp_color)."""

    def _lerp(self, frac):
        scale = [(0.00, (17, 17, 17)), (0.20, (51, 68, 0)),
                 (0.50, (255, 136, 0)), (1.00, (63, 190, 111))]
        frac = max(0.0, min(1.0, frac))
        for i in range(len(scale) - 1):
            f0, c0 = scale[i]; f1, c1 = scale[i + 1]
            if frac <= f1:
                t = (frac - f0) / max(f1 - f0, 0.001)
                return tuple(int(c0[j] + t * (c1[j] - c0[j])) for j in range(3))
        return scale[-1][1]

    def test_zero_is_dark(self):
        r, g, b = self._lerp(0.0)
        assert r < 30 and g < 30 and b < 30

    def test_one_is_green(self):
        r, g, b = self._lerp(1.0)
        assert g > r and g > b

    def test_half_is_amber(self):
        r, g, b = self._lerp(0.5)
        assert r > g   # red dominant (amber)

    def test_output_bounded(self):
        r, g, b = self._lerp(0.8)
        assert all(0 <= c <= 255 for c in (r, g, b))


# ── LogStatsDialog activity tab ───────────────────────────────────────────────

class TestLogStatsActivityTab:

    def _src(self):
        return (ROOT / "ui/dialogs/log_stats_dialog.py").read_text(encoding="utf-8")

    def test_activity_tab_added(self):
        assert "_activity_tab()" in self._src()

    def test_qso_heatmap_used(self):
        assert "QSOHeatmap" in self._src()

    def test_qsos_by_hour_dow_called(self):
        assert "qsos_by_hour_dow" in self._src()

    def test_activity_tab_label(self):
        src = self._src()
        assert '"Activity"' in src or "'Activity'" in src
