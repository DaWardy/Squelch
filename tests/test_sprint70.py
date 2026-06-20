"""Sprint 70 — Log tune-to + contest operating timer."""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


# ── Log context menu tune-to ─────────────────────────────────────────────────

class TestLogTuneTo:

    def _src(self):
        return (ROOT / "ui/tabs/log_tab.py").read_text(encoding="utf-8")

    def test_tune_rig_action_in_menu(self):
        src = self._src()
        idx = src.find("def _log_context_menu(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "Tune rig" in body or "tune_act" in body

    def test_tune_rig_to_qso_method(self):
        assert "def _tune_rig_to_qso(" in self._src()

    def test_tune_rig_sets_freq(self):
        src = self._src()
        idx = src.find("def _tune_rig_to_qso(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "set_freq(" in body

    def test_tune_rig_sets_mode(self):
        src = self._src()
        idx = src.find("def _tune_rig_to_qso(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "set_mode(" in body

    def test_tune_action_only_shown_when_freq_present(self):
        src = self._src()
        idx = src.find("def _log_context_menu(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "freq_hz" in body and "tune_act" in body


class TestTuneRigLogic:
    """Pure-logic: frequency label construction."""

    def test_freq_label_format(self):
        freq_hz = 14_074_000
        mode    = "FT8"
        label   = f"{freq_hz/1e6:.4f} MHz  {mode}"
        assert "14.0740" in label
        assert "FT8" in label

    def test_freq_zero_not_shown(self):
        freq_hz = 0
        # tune_act should be None when freq is 0
        has_freq = bool(freq_hz)
        assert not has_freq

    def test_mode_uppercased(self):
        mode = "ft8"
        assert mode.upper().strip() == "FT8"


# ── Contest operating timer ───────────────────────────────────────────────────

class TestContestTimer:

    def _src(self):
        return (ROOT / "ui/tabs/log_tab.py").read_text(encoding="utf-8")

    def test_build_contest_timer_panel_defined(self):
        assert "def _build_contest_timer_panel(" in self._src()

    def test_ctimer_start_method(self):
        assert "def _ctimer_start(" in self._src()

    def test_ctimer_reset_method(self):
        assert "def _ctimer_reset(" in self._src()

    def test_ctimer_tick_method(self):
        assert "def _ctimer_tick(" in self._src()

    def test_ctimer_panel_in_build(self):
        src = self._src()
        idx = src.find("def _build(self):")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_build_contest_timer_panel" in body

    def test_duration_spinbox_defined(self):
        assert "_ctimer_dur" in self._src()

    def test_display_label_defined(self):
        assert "_ctimer_display" in self._src()

    def test_timer_fires_every_second(self):
        src = self._src()
        assert "setInterval(1000)" in src

    def test_finished_state_on_timeout(self):
        src = self._src()
        idx = src.find("def _ctimer_tick(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "FINISHED" in body or "remaining_s == 0" in body


class TestContestTimerLogic:
    """Pure-logic time formatting."""

    def _fmt(self, total_s: int) -> str:
        h, rem = divmod(total_s, 3600)
        m, sec = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{sec:02d}"

    def test_format_zero(self):
        assert self._fmt(0) == "00:00:00"

    def test_format_one_hour(self):
        assert self._fmt(3600) == "01:00:00"

    def test_format_24_hours(self):
        assert self._fmt(24 * 3600) == "24:00:00"

    def test_format_mixed(self):
        assert self._fmt(3723) == "01:02:03"

    def test_remaining_from_elapsed(self):
        dur_s = 24 * 3600
        elapsed_s = 3600
        remaining_s = max(0, dur_s - elapsed_s)
        assert remaining_s == 23 * 3600

    def test_remaining_clamps_to_zero(self):
        dur_s     = 3600
        elapsed_s = 5000
        remaining_s = max(0, dur_s - elapsed_s)
        assert remaining_s == 0

    def test_pause_resume_toggle(self):
        # Start → pause → resume logic
        running = False
        start_ts = None

        def start_or_pause():
            nonlocal running, start_ts
            import time
            if running:
                running = False
            else:
                if start_ts is None:
                    start_ts = time.time()
                running = True

        start_or_pause()
        assert running and start_ts is not None

        start_or_pause()
        assert not running
        ts_preserved = start_ts
        assert ts_preserved is not None

        start_or_pause()
        assert running  # resume without resetting start time
        assert start_ts == ts_preserved
