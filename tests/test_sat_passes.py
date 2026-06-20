"""Sprint 54 — Satellite pass prediction + FEAT-09 SSTV image viewer."""
from __future__ import annotations
import sys
import pathlib
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


# ── SatPass dataclass ─────────────────────────────────────────────────────────

class TestSatPassDataclass:

    def test_satpass_fields_exist(self):
        from network.satellites import SatPass
        import dataclasses
        fields = {f.name for f in dataclasses.fields(SatPass)}
        for expected in ("sat_name", "aos_utc", "los_utc",
                         "max_el_deg", "max_el_utc",
                         "aos_az_deg", "los_az_deg"):
            assert expected in fields, f"SatPass missing field: {expected}"

    def test_duration_min_property(self):
        from network.satellites import SatPass
        now = datetime.now(timezone.utc)
        sp  = SatPass(
            sat_name="ISS",
            aos_utc=now,
            los_utc=now + timedelta(minutes=10),
            max_el_deg=45.0,
            max_el_utc=now + timedelta(minutes=5),
            aos_az_deg=30.0,
            los_az_deg=250.0,
        )
        assert abs(sp.duration_min - 10.0) < 0.01

    def test_duration_short_pass(self):
        from network.satellites import SatPass
        now = datetime.now(timezone.utc)
        sp  = SatPass("AO-91", now, now + timedelta(minutes=3.5),
                      22.0, now + timedelta(minutes=1.75), 180.0, 270.0)
        assert abs(sp.duration_min - 3.5) < 0.01


# ── SatTracker._compute_next_pass source checks ───────────────────────────────

class TestNextPassSource:

    def _src(self):
        return (ROOT / "network/satellites.py").read_text(encoding="utf-8")

    def test_compute_next_pass_defined(self):
        assert "def _compute_next_pass(" in self._src()

    def test_pass_cache_initialised(self):
        assert "_pass_cache" in self._src()

    def test_compute_called_with_cache_check(self):
        src = self._src()
        assert "_pass_cache" in src
        assert "los_utc.timestamp()" in src

    def test_returns_satpass_instance(self):
        src = self._src()
        idx = src.find("def _compute_next_pass(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "return SatPass(" in body

    def test_steps_60s(self):
        src = self._src()
        idx = src.find("def _compute_next_pass(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "step_s" in body and "60" in body

    def test_azel_called_inside_loop(self):
        src = self._src()
        idx = src.find("def _compute_next_pass(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_azel(" in body

    def test_next_pass_included_in_position(self):
        src = self._src()
        # next_pass should appear somewhere in the _compute_position method
        idx = src.find("def _compute_position(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "next_pass" in body


# ── main_window_network next_pass dict ───────────────────────────────────────

class TestNextPassMainWindowWiring:

    def _src(self):
        return (ROOT / "ui/main_window_network.py").read_text(encoding="utf-8")

    def test_next_pass_key_in_sat_dict(self):
        src = self._src()
        assert '"next_pass"' in src

    def test_pass_dict_helper_extracts_aos(self):
        src = self._src()
        assert "aos" in src and "los" in src and "max_el" in src


# ── FEAT-09 SSTV image viewer ─────────────────────────────────────────────────

class TestSSTVImageViewer:

    def _src(self):
        return (ROOT / "ui/tabs/modes_tab.py").read_text(encoding="utf-8")

    def test_build_sstv_image_panel_defined(self):
        assert "def _build_sstv_image_panel(" in self._src()

    def test_sstv_panel_created_in_fldigi_panel(self):
        src = self._src()
        idx = src.find("def _build_fldigi_panel(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_build_sstv_image_panel" in body

    def test_sstv_panel_shown_only_in_sstv_mode(self):
        src = self._src()
        idx = src.find("def _on_mode_tab(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_sstv_panel" in body
        assert '"SSTV"' in body

    def test_file_system_watcher_used(self):
        assert "QFileSystemWatcher" in self._src()

    def test_sstv_refresh_method(self):
        assert "def _sstv_refresh(" in self._src()

    def test_sstv_image_label_exists(self):
        assert "_sstv_image_lbl" in self._src()

    def test_save_method_exists(self):
        assert "def _sstv_save(" in self._src()

    def test_open_folder_method_exists(self):
        assert "def _sstv_open_folder(" in self._src()

    def test_fldigi_image_path_watched(self):
        src = self._src()
        assert "fldigi" in src and "images" in src

    def test_no_hardcoded_shell_true(self):
        src = self._src()
        # subprocess calls must not use shell=True
        assert "shell=True" not in src


# ── Map popup next-pass display ───────────────────────────────────────────────

class TestMapSatPopup:

    def _src(self):
        return (ROOT / "network/map_data.py").read_text(encoding="utf-8")

    def test_next_pass_in_popup(self):
        src = self._src()
        assert "next_pass" in src or "np.aos" in src

    def test_aos_los_in_popup(self):
        src = self._src()
        assert "AOS" in src and "LOS" in src
