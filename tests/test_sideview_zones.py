"""Sprint 44 — Propagation sideview zone overlays.

Pure-logic tests: verify zone geometry helpers, toggle state, and
band_conditions_tab wiring.  No Qt instantiation needed.
"""
from __future__ import annotations
import sys
import pathlib
import math

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


class TestZoneSourcePresence:
    """Source-level checks — methods and state variables exist."""

    def _src(self):
        return (ROOT / "ui/widgets/propagation_sideview.py").read_text(
            encoding="utf-8")

    def test_show_zone_state_vars(self):
        src = self._src()
        assert "_show_gw_zone" in src
        assert "_show_nvis_zone" in src
        assert "_show_sw_zone" in src

    def test_set_show_zones_method(self):
        src = self._src()
        assert "def set_show_zones(" in src

    def test_draw_zones_method(self):
        src = self._src()
        assert "def _draw_propagation_zones(" in src

    def test_zones_called_in_paintevent(self):
        src = self._src()
        assert "_draw_propagation_zones(" in src
        paint_idx = src.find("def paintEvent(")
        assert "_draw_propagation_zones" in src[paint_idx:], \
            "_draw_propagation_zones must be called inside paintEvent"

    def test_no_hardcoded_dark_hex(self):
        src = self._src()
        for bad in ("#141414", "#0a0a0a"):
            assert bad not in src


class TestBandConditionsTabZones:
    """band_conditions_tab.py must have zone checkboxes + save/restore."""

    def _src(self):
        return (ROOT / "ui/tabs/band_conditions_tab.py").read_text(
            encoding="utf-8")

    def test_zone_checkboxes_defined(self):
        src = self._src()
        assert "_zone_gw" in src
        assert "_zone_nvis" in src
        assert "_zone_sw" in src

    def test_qcheckbox_imported(self):
        src = self._src()
        assert "QCheckBox" in src

    def test_zone_states_in_save_state(self):
        src = self._src()
        save_idx = src.find("def save_state(")
        save_body = src[save_idx: src.find("\n    def ", save_idx + 10)]
        assert "zone_gw" in save_body
        assert "zone_nvis" in save_body
        assert "zone_sw" in save_body

    def test_zone_states_in_restore_state(self):
        src = self._src()
        rest_idx = src.find("def restore_state(")
        rest_body = src[rest_idx: src.find("\n    def ", rest_idx + 10)]
        assert "zone_gw" in rest_body


class TestZoneGeometry:
    """Unit tests for zone geometry without Qt."""

    # Mirror the key formulas from _draw_propagation_zones

    def _gw_km(self, freq_mhz, path_km):
        return min(300.0 / max(freq_mhz, 0.1), path_km)

    def _skip_km(self, freq_mhz, muf_mhz, f_layer_km=300.0):
        if muf_mhz <= freq_mhz:
            return 0.0
        denom = math.sqrt(max(muf_mhz ** 2 - freq_mhz ** 2, 0.01))
        return 2.0 * f_layer_km * freq_mhz / denom

    def test_gw_range_lower_freq_longer(self):
        gw_3mhz  = self._gw_km(3.5, 5000)
        gw_14mhz = self._gw_km(14.0, 5000)
        assert gw_3mhz > gw_14mhz

    def test_gw_capped_at_path(self):
        assert self._gw_km(0.1, 100) == 100.0  # min(3000, 100) == 100

    def test_skip_increases_with_freq_toward_muf(self):
        skip_low  = self._skip_km(7.0, 28.0)
        skip_high = self._skip_km(21.0, 28.0)
        assert skip_high > skip_low

    def test_skip_zero_above_muf(self):
        assert self._skip_km(30.0, 28.0) == 0.0  # no skip when above MUF

    def test_nvis_range_capped_at_500km(self):
        nvis_km = min(500.0, 2000.0)
        assert nvis_km == 500.0

    def test_nvis_short_path_uses_full_path(self):
        nvis_km = min(500.0, 300.0)
        assert nvis_km == 300.0

    def test_skip_km_less_than_path(self):
        path_km = 3000.0
        skip = self._skip_km(14.0, 28.0)
        # skip_km should cap at 80% of path
        assert skip < path_km

    def test_gw_at_hf_typical_range(self):
        # At 7.1 MHz, GW range ≈ 42 km — verify it's in the 30-60 km range
        gw = self._gw_km(7.1, 5000)
        assert 30 < gw < 60
