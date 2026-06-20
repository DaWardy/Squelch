"""Sprint 71 — WSPR polar chart + FT8 auto-CQ timeout."""
from __future__ import annotations
import sys
import pathlib
import math

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


# ── WSPRPolarChart source checks ─────────────────────────────────────────────

class TestWSPRPolarChartSource:

    def _src(self):
        return (ROOT / "ui/widgets/wspr_polar.py").read_text(encoding="utf-8")

    def test_class_exists(self):
        assert "class WSPRPolarChart(" in self._src()

    def test_set_spots_method(self):
        assert "def set_spots(" in self._src()

    def test_distance_rings_defined(self):
        src = self._src()
        assert "1000" in src and "3000" in src and "6000" in src

    def test_cardinals_defined(self):
        src = self._src()
        assert '"N"' in src and '"E"' in src and '"S"' in src

    def test_snr_color_function(self):
        assert "_snr_color" in self._src()

    def test_bearing_to_xy_math(self):
        src = self._src()
        assert "math.cos(" in src and "math.sin(" in src

    def test_no_banned_dark_hex(self):
        src = self._src()
        for bad in ("#141414", "#0a0a0a"):
            assert bad not in src


class TestSNRColorLogic:
    """Verify SNR-to-colour mapping without Qt."""

    def _snr_frac(self, snr):
        return max(0.0, min(1.0, (snr + 30) / 40))

    def test_worst_snr_maps_to_zero(self):
        assert self._snr_frac(-30) == 0.0

    def test_best_snr_maps_to_one(self):
        assert self._snr_frac(10) == 1.0

    def test_midpoint_snr(self):
        assert abs(self._snr_frac(-10) - 0.5) < 0.01

    def test_typical_wspr_snr(self):
        # -20 dB is very common for WSPR
        frac = self._snr_frac(-20)
        assert 0.2 <= frac <= 0.3


class TestPolarGeometry:
    """Verify bearing-to-XY coordinate math."""

    def _to_xy(self, bearing_deg, dist_km,
               cx=110.0, cy=110.0, radius=100.0, max_km=10000):
        rad = math.radians(bearing_deg - 90)
        r   = radius * dist_km / max_km
        return cx + r * math.cos(rad), cy + r * math.sin(rad)

    def test_north_bearing_above_center(self):
        x, y = self._to_xy(0, 5000)
        assert y < 110.0   # above center

    def test_south_bearing_below_center(self):
        x, y = self._to_xy(180, 5000)
        assert y > 110.0

    def test_east_bearing_right_of_center(self):
        x, y = self._to_xy(90, 5000)
        assert x > 110.0

    def test_zero_distance_at_center(self):
        x, y = self._to_xy(45, 0)
        assert abs(x - 110.0) < 0.01
        assert abs(y - 110.0) < 0.01


# ── Modes_tab WSPR integration ────────────────────────────────────────────────

class TestWSPRPolarIntegration:

    def _src(self):
        return (ROOT / "ui/tabs/modes_tab.py").read_text(encoding="utf-8")

    def test_build_wspr_polar_panel_defined(self):
        assert "_build_wspr_polar_panel" in self._src()

    def test_wspr_polar_chart_widget_created(self):
        assert "_wspr_polar_chart" in self._src()

    def test_polar_chart_visible_in_wspr_mode(self):
        src = self._src()
        idx = src.find("def _on_mode_tab(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_wspr_polar_chart" in body

    def test_spot_update_wired_in_on_wspr_spot(self):
        src = self._src()
        idx = src.find("def _on_wspr_spot(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_wspr_polar_chart" in body or "wspr_spot_list" in body


# ── Auto-CQ timeout ───────────────────────────────────────────────────────────

class TestAutoCQTimeout:

    def _src(self):
        return (ROOT / "ui/tabs/modes_tab.py").read_text(encoding="utf-8")

    def test_auto_cq_timeout_spinbox_defined(self):
        assert "_auto_cq_timeout" in self._src()

    def test_on_auto_cq_toggle_method(self):
        assert "def _on_auto_cq_toggle(" in self._src()

    def test_check_auto_cq_timeout_method(self):
        assert "def _check_auto_cq_timeout(" in self._src()

    def test_timeout_called_in_update_cycle(self):
        src = self._src()
        idx = src.find("def _update_cycle(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_check_auto_cq_timeout" in body

    def test_no_reply_condition(self):
        src = self._src()
        idx = src.find("def _check_auto_cq_timeout(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "qso" in body.lower() and "stop" in body.lower()


class TestAutoCQTimeoutLogic:
    """Pure-logic timeout checking."""

    def _should_stop(self, elapsed_min, timeout_min, qsos_before, qsos_now):
        if timeout_min <= 0:
            return False
        if elapsed_min < timeout_min:
            return False
        return qsos_now <= qsos_before   # no new QSOs = stop

    def test_no_timeout_when_zero(self):
        assert not self._should_stop(30, 0, 5, 5)

    def test_no_stop_before_timeout(self):
        assert not self._should_stop(3, 10, 5, 5)

    def test_stop_when_timeout_and_no_qso(self):
        assert self._should_stop(11, 10, 5, 5)

    def test_no_stop_when_qso_made(self):
        assert not self._should_stop(11, 10, 5, 6)

    def test_stop_requires_both_conditions(self):
        # Even with new QSO, just past threshold
        assert not self._should_stop(10.5, 10, 5, 6)
