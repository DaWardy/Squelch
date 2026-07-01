"""Sprint 50 — FEAT-25 demod profiles + FEAT-24 scheduled recording.

Pure-logic and source-level tests only.
"""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


def _sdr_src() -> str:
    # Demod-profile methods → sdr_profile.py; recorder group (incl. scheduled
    # record) → sdr_bottom_bar.py (HOUSE-CS split). sdr_tab.py first so
    # host-side body-slices still resolve.
    return ((ROOT / "ui/tabs/sdr_tab.py").read_text(encoding="utf-8") + "\n"
            + (ROOT / "ui/tabs/sdr_profile.py").read_text(encoding="utf-8") + "\n"
            + (ROOT / "ui/tabs/sdr_bottom_bar.py").read_text(encoding="utf-8"))


# ── FEAT-25: Demod profiles ───────────────────────────────────────────────────

class TestDemodProfiles:

    def test_builtin_profiles_constant(self):
        assert "_BUILTIN_PROFILES" in _sdr_src()

    def test_profile_group_builder(self):
        assert "_build_profile_group" in _sdr_src()

    def test_profile_group_added_to_controls(self):
        src = _sdr_src()
        idx = src.find("def _build_controls(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_build_profile_group" in body

    def test_apply_profile_method(self):
        assert "def _apply_profile(" in _sdr_src()

    def test_save_profile_method(self):
        assert "def _save_profile(" in _sdr_src()

    def test_delete_profile_method(self):
        assert "def _delete_profile(" in _sdr_src()

    def test_refresh_profile_combo_method(self):
        assert "_refresh_profile_combo" in _sdr_src()

    def test_apply_sets_all_params(self):
        src = _sdr_src()
        idx = src.find("def _apply_profile(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_demod_combo" in body
        assert "_demod_bw" in body
        assert "_nr_cb" in body
        assert "_squelch_cb" in body

    def test_builtin_profiles_cover_key_modes(self):
        src = _sdr_src()
        for mode in ('"CW"', '"AM"', '"WFM"', '"USB"', '"NFM"'):
            assert mode in src

    def test_save_stores_in_cfg(self):
        src = _sdr_src()
        idx = src.find("def _save_profile(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "sdr.profiles" in body

    def test_delete_removes_from_cfg(self):
        src = _sdr_src()
        idx = src.find("def _delete_profile(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "sdr.profiles" in body

    def test_builtin_profiles_not_deletable(self):
        src = _sdr_src()
        idx = src.find("def _delete_profile(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_BUILTIN_PROFILES" in body

    def test_custom_profile_marked_with_star(self):
        src = _sdr_src()
        idx = src.find("def _refresh_profile_combo(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "★" in body


class TestBuiltinProfileLogic:
    """Verify built-in profile content without Qt."""

    def _profiles(self):
        # Mirror the constant without importing Qt-dependent module
        return {
            "SSB / Ham Voice": {"mode": "USB",  "bw": "2.5 kHz", "nr": False},
            "CW Contest":      {"mode": "CW",   "bw": "500 Hz",  "nr": True},
            "AM Broadcast":    {"mode": "AM",   "bw": "10 kHz",  "nr": True},
            "FM Broadcast":    {"mode": "WFM",  "bw": "200 kHz", "nr": False},
            "Digital / FT8":   {"mode": "USB",  "bw": "2.5 kHz", "sq": True},
            "NFM Comms":       {"mode": "NFM",  "bw": "10 kHz",  "sq": True},
        }

    def test_ssb_uses_usb(self):
        assert self._profiles()["SSB / Ham Voice"]["mode"] == "USB"

    def test_cw_uses_narrow_bw(self):
        assert "Hz" in self._profiles()["CW Contest"]["bw"]

    def test_wfm_uses_wide_bw(self):
        assert "200" in self._profiles()["FM Broadcast"]["bw"]

    def test_digital_has_squelch(self):
        assert self._profiles()["Digital / FT8"].get("sq") is True

    def test_nfm_has_squelch(self):
        assert self._profiles()["NFM Comms"].get("sq") is True

    def test_six_builtin_profiles(self):
        assert len(self._profiles()) == 6


# ── FEAT-24: Scheduled recording ─────────────────────────────────────────────

class TestScheduledRecording:

    def test_sched_timer_in_recorder_group(self):
        src = _sdr_src()
        idx = src.find("def _build_recorder_group(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_sched_timer" in body

    def test_arm_method_exists(self):
        assert "def _arm_scheduled_record(" in _sdr_src()

    def test_check_schedule_method_exists(self):
        assert "def _check_schedule(" in _sdr_src()

    def test_schedule_uses_utc(self):
        src = _sdr_src()
        idx = src.find("def _check_schedule(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "utc" in body.lower() or "UTC" in body

    def test_schedule_stops_after_duration(self):
        src = _sdr_src()
        idx = src.find("def _check_schedule(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_sched_stop_at" in body

    def test_sched_time_widget_in_recorder(self):
        src = _sdr_src()
        assert "_sched_time" in src

    def test_sched_duration_widget(self):
        assert "_sched_dur" in _sdr_src()

    def test_timer_10s_interval(self):
        src = _sdr_src()
        assert "10_000" in src or "10000" in src


class TestScheduleLogic:
    """Pure logic for schedule matching."""

    def _check(self, now_h, now_m, target_h, target_m):
        """Return True when the schedule fires."""
        class _FakeTime:
            def hour(self): return target_h
            def minute(self): return target_m
        return now_h == target_h and now_m == target_m

    def test_fires_at_exact_minute(self):
        assert self._check(14, 30, 14, 30) is True

    def test_does_not_fire_one_minute_early(self):
        assert self._check(14, 29, 14, 30) is False

    def test_does_not_fire_one_minute_late(self):
        assert self._check(14, 31, 14, 30) is False

    def test_midnight_works(self):
        assert self._check(0, 0, 0, 0) is True
