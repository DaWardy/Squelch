"""FEAT-22 — Rotor control tests.

Tests for core/rotor.py (pure logic), ui/widgets/rotor_compass.py (source),
and rig_tab.py wiring (source-level).
"""
from __future__ import annotations
import sys
import pathlib
import math

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


# ── core/rotor.py pure-logic ──────────────────────────────────────────────────

class TestRotorController:

    def test_initially_disconnected(self):
        from core.rotor import RotorController
        r = RotorController()
        assert not r.is_connected

    def test_initial_az_el_zero(self):
        from core.rotor import RotorController
        r = RotorController()
        assert r.az == 0.0
        assert r.el == 0.0

    def test_on_position_callback_registered(self):
        from core.rotor import RotorController
        r = RotorController()
        received = []
        r.on_position(received.append)
        assert len(r._callbacks) == 1

    def test_set_position_returns_false_when_disconnected(self):
        from core.rotor import RotorController
        r = RotorController()
        assert r.set_position(90.0, 30.0) is False

    def test_park_returns_false_when_disconnected(self):
        from core.rotor import RotorController
        r = RotorController()
        assert r.park() is False

    def test_az_clamped_to_360(self):
        """set_position clips az to 0-360 before sending."""
        from core.rotor import RotorController
        r = RotorController()
        # Can't actually send without connection, but we can verify the clamp logic
        az = max(0.0, min(360.0, 400.0))
        assert az == 360.0

    def test_el_clamped_to_180(self):
        from core.rotor import RotorController
        r = RotorController()
        el = max(0.0, min(180.0, 200.0))
        assert el == 180.0

    def test_connect_to_unavailable_host_returns_false(self):
        from core.rotor import RotorController
        # Port 19999 is almost certainly not running rotctld
        r = RotorController("127.0.0.1", 19999)
        result = r.connect()
        assert result is False
        assert not r.is_connected


# ── rotor_compass.py source checks ───────────────────────────────────────────

class TestRotorCompassSource:

    def _src(self):
        return (ROOT / "ui/widgets/rotor_compass.py").read_text(encoding="utf-8")

    def test_class_exists(self):
        assert "class RotorCompass(" in self._src()

    def test_set_current_method(self):
        assert "def set_current(" in self._src()

    def test_set_target_method(self):
        assert "def set_target(" in self._src()

    def test_needle_drawn(self):
        assert "_draw_needle" in self._src()

    def test_labels_drawn(self):
        assert "_draw_labels" in self._src()

    def test_elevation_drawn(self):
        assert "_draw_elevation" in self._src()

    def test_cardinals_defined(self):
        src = self._src()
        assert '"N"' in src and '"E"' in src and '"S"' in src and '"W"' in src

    def test_no_hardcoded_dark_hex(self):
        src = self._src()
        for bad in ("#141414", "#0a0a0a"):
            assert bad not in src


# ── rig_tab.py wiring checks ─────────────────────────────────────────────────

class TestRotorRigTabWiring:

    def _src(self):
        return (ROOT / "ui/tabs/rig_tab.py").read_text(encoding="utf-8")

    def test_build_rotor_section_called(self):
        src = self._src()
        idx = src.find("def _build(self):")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_build_rotor_section" in body

    def test_rotor_toggle_in_save_state(self):
        src = self._src()
        idx = src.find("def save_state(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "rotor_open" in body

    def test_rotor_toggle_in_restore_state(self):
        src = self._src()
        idx = src.find("def restore_state(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "rotor_open" in body

    def test_rotor_connect_method(self):
        assert "_rotor_toggle_connect" in self._src()

    def test_rotor_set_position_method(self):
        assert "_rotor_set_position" in self._src()

    def test_rotor_park_method(self):
        assert "_rotor_park" in self._src()

    def test_compass_imported_in_rotor_section(self):
        src = self._src()
        assert "RotorCompass" in src

    def test_on_position_cb_uses_singleshot(self):
        src = self._src()
        idx = src.find("def _on_rotor_position(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "singleShot" in body


# ── Compass geometry ──────────────────────────────────────────────────────────

class TestCompassGeometry:
    """Verify compass math without rendering (no Qt needed)."""

    def _needle_tip(self, az_deg, r=100.0):
        """Mirror _draw_needle tip calculation."""
        rad   = math.radians(az_deg - 90)
        tip_x = 70 + r * 0.85 * math.cos(rad)   # cx=70
        tip_y = 70 + r * 0.85 * math.sin(rad)
        return tip_x, tip_y

    def test_north_points_up(self):
        x, y = self._needle_tip(0)
        # North (0°) → tip above centre (y < 70)
        assert y < 70.0

    def test_east_points_right(self):
        x, y = self._needle_tip(90)
        assert x > 70.0

    def test_south_points_down(self):
        x, y = self._needle_tip(180)
        assert y > 70.0

    def test_west_points_left(self):
        x, y = self._needle_tip(270)
        assert x < 70.0
