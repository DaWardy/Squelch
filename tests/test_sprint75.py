"""Sprint 75 — Squelch-triggered recording + propagation time slider."""
from __future__ import annotations
import sys
import pathlib
import math

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


# ── Squelch-triggered recording ───────────────────────────────────────────────

class TestSquelchTriggerSource:

    def _src(self):
        return (ROOT / "ui/tabs/sdr_tab.py").read_text(encoding="utf-8")

    def test_sqtrig_checkbox_defined(self):
        assert "_sqtrig_cb" in self._src()

    def test_sqtrig_tail_spinbox_defined(self):
        assert "_sqtrig_tail" in self._src()

    def test_check_sqtrig_method(self):
        assert "def _check_sqtrig(" in self._src()

    def test_sqtrig_timer_created(self):
        assert "_sqtrig_check_timer" in self._src()

    def test_sqtrig_opens_recording(self):
        src = self._src()
        idx = src.find("def _check_sqtrig(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_toggle_record()" in body

    def test_sqtrig_checks_squelch_state(self):
        src = self._src()
        idx = src.find("def _check_sqtrig(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_squelch_open" in body

    def test_tail_time_used(self):
        src = self._src()
        idx = src.find("def _check_sqtrig(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_sqtrig_tail" in body or "tail" in body


class TestSquelchTriggerLogic:
    """Pure-logic for squelch trigger timing."""

    def _check(self, squelch_open, is_recording, close_ts, tail_s, now):
        """Mirror _check_sqtrig logic."""
        start = None
        stop  = False
        if squelch_open:
            close_ts = None
            if not is_recording:
                start = now
        else:
            if is_recording:
                if close_ts is None:
                    close_ts = now
                elif now - close_ts >= tail_s:
                    stop = True
                    close_ts = None
        return start, stop, close_ts

    def test_start_on_squelch_open(self):
        start, _, _ = self._check(True, False, None, 5, 100.0)
        assert start is not None

    def test_no_restart_if_already_recording(self):
        start, _, _ = self._check(True, True, None, 5, 100.0)
        assert start is None

    def test_stop_after_tail(self):
        _, stop, _ = self._check(False, True, 90.0, 5, 96.0)
        assert stop  # 96 - 90 = 6 >= tail 5

    def test_no_stop_within_tail(self):
        _, stop, _ = self._check(False, True, 90.0, 5, 93.0)
        assert not stop  # 93 - 90 = 3 < tail 5

    def test_close_ts_set_when_squelch_closes(self):
        _, _, close_ts = self._check(False, True, None, 5, 100.0)
        assert close_ts == 100.0

    def test_close_ts_cleared_when_squelch_reopens(self):
        _, _, close_ts = self._check(True, True, 95.0, 5, 100.0)
        assert close_ts is None


# ── Propagation time-of-day slider ───────────────────────────────────────────

class TestTimeSlidlerSource:

    def _src(self):
        return (ROOT / "ui/tabs/band_conditions_tab.py").read_text(encoding="utf-8")

    def test_time_slider_defined(self):
        assert "_time_slider" in self._src()

    def test_time_label_defined(self):
        assert "_time_lbl" in self._src()

    def test_on_time_slider_changed_method(self):
        assert "def _on_time_slider_changed(" in self._src()

    def test_current_utc_hour_method(self):
        assert "def _current_utc_hour(" in self._src()

    def test_slider_has_24_steps(self):
        src = self._src()
        assert "setRange(0, 23)" in src

    def test_slider_in_sideview_group(self):
        src = self._src()
        idx = src.find("def _build_sideview_group(")
        body = src[idx: src.find("\n    def _build_", idx + 10)]
        assert "_time_slider" in body


class TestTimeMUFFormula:
    """Pure-logic: hourly MUF scaling from the day/night model."""

    def _muf_at(self, hour, sfi=150, k=1, path_km=3000):
        fof2_day   = math.sqrt(sfi / 25.0) * 4.0
        fof2_night = fof2_day * 0.55
        day_f = 0.5 + 0.5 * math.sin(math.radians((hour - 6) * 15))
        fof2  = fof2_night + (fof2_day - fof2_night) * day_f
        path_factor = max(1.5, min(4.5, path_km / 1000.0 + 1.2))
        geo_factor  = max(0.3, 1.0 - 0.08 * k)
        return min(fof2 * geo_factor * path_factor, 35.0)

    def test_noon_higher_than_midnight(self):
        assert self._muf_at(12) > self._muf_at(0)

    def test_muf_below_max(self):
        for h in range(24):
            assert self._muf_at(h) <= 35.0

    def test_muf_positive(self):
        for h in range(24):
            assert self._muf_at(h) > 0

    def test_high_kindex_lowers_muf(self):
        assert self._muf_at(12, k=0) > self._muf_at(12, k=5)

    def test_high_sfi_raises_muf(self):
        assert self._muf_at(12, sfi=200) > self._muf_at(12, sfi=70)

    def test_morning_lower_than_afternoon(self):
        # Solar noon ~ 12:00 UTC; morning (08h) should be lower than midday
        assert self._muf_at(8) < self._muf_at(12)
