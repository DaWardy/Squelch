"""Sprint 54 + 61 + 67 — Satellite pass prediction, rotor auto-track, pass countdown."""
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
            assert expected in fields

    def test_duration_min_property(self):
        from network.satellites import SatPass
        now = datetime.now(timezone.utc)
        sp  = SatPass("ISS", now, now + timedelta(minutes=10),
                      45.0, now + timedelta(minutes=5), 30.0, 250.0)
        assert abs(sp.duration_min - 10.0) < 0.01

    def test_duration_short_pass(self):
        from network.satellites import SatPass
        now = datetime.now(timezone.utc)
        sp  = SatPass("AO-91", now, now + timedelta(minutes=3.5),
                      22.0, now + timedelta(minutes=1.75), 180.0, 270.0)
        assert abs(sp.duration_min - 3.5) < 0.01


# ── SatTracker._compute_next_pass ────────────────────────────────────────────

class TestNextPassSource:

    def _src(self):
        return (ROOT / "network/satellites.py").read_text(encoding="utf-8")

    def test_compute_next_pass_defined(self):
        assert "def _compute_next_pass(" in self._src()

    def test_pass_cache_initialised(self):
        assert "_pass_cache" in self._src()

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

    def test_next_pass_in_position(self):
        src = self._src()
        idx = src.find("def _compute_position(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "next_pass" in body


# ── main_window_network wiring ────────────────────────────────────────────────

class TestNextPassMainWindowWiring:

    def _src(self):
        return (ROOT / "ui/main_window_network.py").read_text(encoding="utf-8")

    def test_next_pass_key_in_sat_dict(self):
        assert '"next_pass"' in self._src()

    def test_az_deg_in_sat_dict(self):
        assert '"az_deg"' in self._src()

    def test_rig_tab_update_called(self):
        assert "update_from_sat_position" in self._src()


# ── Sprint 61: Rotor satellite auto-track ────────────────────────────────────

class TestRotorSatTrack:

    def _src(self):
        return (
            (ROOT / "ui/tabs/rig_tab.py").read_text(encoding="utf-8") + "\n" +
            (ROOT / "ui/tabs/rig_rotor_mixin.py").read_text(encoding="utf-8"))

    def test_sat_combo_defined(self):
        assert "_rotor_sat_combo" in self._src()

    def test_auto_track_button(self):
        assert "_rotor_auto_btn" in self._src()

    def test_rotor_auto_toggled_method(self):
        assert "def _rotor_auto_toggled(" in self._src()

    def test_update_from_sat_position_method(self):
        assert "def update_from_sat_position(" in self._src()

    def test_iss_in_combo_choices(self):
        assert "ISS (ZARYA)" in self._src()

    def test_wired_in_main_window_network(self):
        net = (ROOT / "ui/main_window_network.py").read_text(encoding="utf-8")
        assert "update_from_sat_position" in net


# ── Sprint 67: Pass countdown panel ──────────────────────────────────────────

class TestPassCountdownPanel:

    def _src(self):
        return (
            (ROOT / "ui/tabs/rig_tab.py").read_text(encoding="utf-8") + "\n" +
            (ROOT / "ui/tabs/rig_rotor_mixin.py").read_text(encoding="utf-8"))

    def test_pass_lbl_widget_defined(self):
        assert "_pass_lbl" in self._src()

    def test_pass_progress_widget_defined(self):
        assert "_pass_progress" in self._src()

    def test_update_pass_countdown_method(self):
        assert "def _update_pass_countdown(" in self._src()

    def test_pass_in_progress_detected(self):
        src = self._src()
        idx = src.find("def _update_pass_countdown(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "el >= 0" in body or "PASS IN PROGRESS" in body

    def test_countdown_shows_aos_los(self):
        src = self._src()
        idx = src.find("def _update_pass_countdown(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "AOS" in body and "LOS" in body

    def test_update_called_regardless_of_tracking(self):
        src = self._src()
        idx = src.find("def update_from_sat_position(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        # _update_pass_countdown must appear BEFORE the auto-track guard
        cnt_pos   = body.find("_update_pass_countdown(")
        track_pos = body.find("set_sat_track_cb_enabled()")
        assert cnt_pos < track_pos, \
            "pass countdown should run before the auto-track enabled check"


# ── Sprint 67: Session notes ──────────────────────────────────────────────────

class TestSessionNotesPanel:

    def _src(self):
        # Session-notes panel was extracted to _LogPanelsMixin (HOUSE-CS split).
        parts = ["ui/tabs/log_tab.py", "ui/tabs/log_panels_mixin.py"]
        return "\n".join(
            (ROOT / p).read_text(encoding="utf-8") for p in parts)

    def test_build_session_notes_defined(self):
        assert "def _build_session_notes_panel(" in self._src()

    def test_save_session_notes_defined(self):
        assert "def _save_session_notes(" in self._src()

    def test_notes_panel_in_build(self):
        src = self._src()
        idx = src.find("def _build(self):")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_build_session_notes_panel" in body

    def test_notes_persisted_to_cfg(self):
        src = self._src()
        idx = src.find("def _save_session_notes(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "log.session_notes" in body

    def test_notes_restored_from_cfg(self):
        src = self._src()
        idx = src.find("def _build_session_notes_panel(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "log.session_notes" in body

    def test_textchanged_wired(self):
        src = self._src()
        idx = src.find("def _build_session_notes_panel(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "textChanged.connect" in body


# ── Map satellite popup ───────────────────────────────────────────────────────

class TestMapSatPopup:

    def _src(self):
        return (ROOT / "network/map_data.py").read_text(encoding="utf-8")

    def test_next_pass_in_popup(self):
        src = self._src()
        assert "next_pass" in src or "np.aos" in src

    def test_aos_los_labels(self):
        src = self._src()
        assert "AOS" in src and "LOS" in src

    def test_sstv_image_viewer_in_modes(self):
        # SSTV viewer was extracted to modes_sstv_mixin.py (HOUSE-CS split).
        src = (ROOT / "ui/tabs/modes_sstv_mixin.py").read_text(encoding="utf-8")
        assert "def _build_sstv_image_panel(" in src
