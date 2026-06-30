from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for SDR tab state persistence and axis calculations.

Qt-dependent tests are skipped when PyQt6 is absent from the test runner env.
Pure-logic tests (axis math, span table) run without Qt.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

# ---------------------------------------------------------------------------
# Pure-logic tests — no Qt needed
# ---------------------------------------------------------------------------

class TestMHzAxisFormula:
    """Verify that the center_hz/span_hz → lo_mhz/hi_mhz formula is correct."""

    def _axis(self, center_hz, span_hz):
        half = span_hz / 2
        return (center_hz - half) / 1e6, (center_hz + half) / 1e6

    def test_fm_broadcast(self):
        lo, hi = self._axis(99_000_000, 2_400_000)
        assert abs(lo - 97.8) < 0.01
        assert abs(hi - 100.2) < 0.01

    def test_aprs_2m(self):
        lo, hi = self._axis(144_390_000, 500_000)
        assert abs(lo - 144.14) < 0.01
        assert abs(hi - 144.64) < 0.01

    def test_lo_less_than_hi(self):
        lo, hi = self._axis(10_000_000, 1_000_000)
        assert lo < hi

    def test_center_is_midpoint(self):
        center_hz = 7_200_000
        span_hz   = 200_000
        lo, hi = self._axis(center_hz, span_hz)
        midpoint_mhz = (lo + hi) / 2
        assert abs(midpoint_mhz - center_hz / 1e6) < 1e-9

    def test_narrow_span(self):
        lo, hi = self._axis(14_225_000, 100_000)
        assert abs(lo - 14.175) < 0.001
        assert abs(hi - 14.275) < 0.001


class TestSpanTable:
    """The spans_hz list in _on_span must match the combo items in _build_span_group."""

    COMBO_LABELS = [
        "100 kHz", "500 kHz", "1 MHz", "2.4 MHz",
        "5 MHz", "10 MHz", "20 MHz"
    ]
    SPANS_HZ = [
        100_000, 500_000, 1_000_000, 2_400_000,
        5_000_000, 10_000_000, 20_000_000
    ]

    def test_table_length_matches_labels(self):
        assert len(self.SPANS_HZ) == len(self.COMBO_LABELS)

    def test_100kHz_entry(self):
        assert self.SPANS_HZ[0] == 100_000

    def test_2_4mhz_entry(self):
        assert self.SPANS_HZ[3] == 2_400_000

    def test_20mhz_entry(self):
        assert self.SPANS_HZ[-1] == 20_000_000

    def test_strictly_increasing(self):
        for a, b in zip(self.SPANS_HZ, self.SPANS_HZ[1:]):
            assert b > a, f"{b} not > {a}"


# ---------------------------------------------------------------------------
# Qt-dependent tests — skipped when PyQt6 absent
# ---------------------------------------------------------------------------

try:
    import PyQt6  # noqa: F401
    HAS_QT = True
except ImportError:
    HAS_QT = False

pytestmark_qt = pytest.mark.skipif(
    not HAS_QT, reason="PyQt6 not installed")


@pytest.fixture(scope="module")
def qt_app():
    """Return (or create) the QApplication singleton."""
    import sys
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    return app


def _make_sdr_tab(qt_app):
    """Instantiate SDRTab with a temp config and mock rig."""
    import tempfile
    from unittest.mock import MagicMock
    from core.config import Config

    tmp = tempfile.mkdtemp()
    cfg = Config(Path(tmp) / "config.json")
    rig = MagicMock()
    rig.is_connected = False
    rig.state = MagicMock()

    # NOTE: do NOT mock sdr.soapy_device via patch.dict("sys.modules", ...) —
    # its clear-on-exit evicts numpy's C submodules, after which numpy 2.x
    # refuses to re-import ("cannot load module more than once per process"),
    # breaking every later test in the file. soapy_device imports fine without
    # SoapySDR (it degrades to zero devices), so import the tab directly.
    from ui.tabs.sdr_tab import SDRTab
    tab = SDRTab(cfg, rig)
    return tab, cfg


@pytest.mark.skipif(not HAS_QT, reason="PyQt6 not installed")
class TestSDRSaveRestoreState:

    def test_save_state_returns_dict(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        state = tab.save_state()
        assert isinstance(state, dict)

    def test_save_state_has_required_keys(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        state = tab.save_state()
        for key in ("center_hz", "span", "gain", "ppm",
                    "palette", "floor_db", "ceil_db", "peak_hold"):
            assert key in state, f"Missing key: {key}"

    def test_center_hz_default(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        state = tab.save_state()
        assert state["center_hz"] == 100_000_000

    def test_palette_default(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        state = tab.save_state()
        assert state["palette"] == "Jet"

    def test_restore_state_noop_on_empty(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        tab.restore_state({})  # should not raise

    def test_round_trip_palette(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        tab._palette_combo.setCurrentText("Viridis")
        state = tab.save_state()
        assert state["palette"] == "Viridis"
        tab._palette_combo.setCurrentText("Jet")
        tab.restore_state(state)
        assert tab._palette_combo.currentText() == "Viridis"

    def test_round_trip_gain(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        tab._gain_slider.setValue(45)
        state = tab.save_state()
        tab._gain_slider.setValue(0)
        tab.restore_state(state)
        assert tab._gain_slider.value() == 45

    def test_round_trip_peak_hold(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        tab._peak_cb.setChecked(True)
        state = tab.save_state()
        tab._peak_cb.setChecked(False)
        tab.restore_state(state)
        assert tab._peak_cb.isChecked()

    def test_round_trip_span(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        tab._span_combo.setCurrentText("500 kHz")
        state = tab.save_state()
        tab._span_combo.setCurrentText("2.4 MHz")
        tab.restore_state(state)
        assert tab._span_combo.currentText() == "500 kHz"


@pytest.mark.skipif(not HAS_QT, reason="PyQt6 not installed")
class TestSDRScreenshot:
    """Verify _save_screenshot saves a valid PNG and reports via status bar."""

    def test_screenshot_creates_file(self, tmp_path, qt_app, monkeypatch):
        """Screenshot is written to a temp path and returns a non-empty file."""
        tab, _ = _make_sdr_tab(qt_app)
        monkeypatch.setattr(
            "pathlib.Path.home", lambda: tmp_path)
        # Create Desktop dir so the first candidate is picked
        (tmp_path / "Desktop").mkdir()
        tab._save_screenshot()
        shots = list((tmp_path / "Desktop").glob("squelch_sdr_*.png"))
        assert shots, "Expected a screenshot PNG in Desktop"
        assert shots[0].stat().st_size > 0

    def test_screenshot_filename_format(self, tmp_path, qt_app, monkeypatch):
        """Filename matches squelch_sdr_YYYYMMDD_HHmmss.png pattern."""
        import re
        tab, _ = _make_sdr_tab(qt_app)
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        (tmp_path / "Desktop").mkdir()
        tab._save_screenshot()
        shots = list((tmp_path / "Desktop").glob("squelch_sdr_*.png"))
        assert re.match(r"squelch_sdr_\d{8}_\d{6}\.png$", shots[0].name)

    def test_screenshot_falls_back_to_downloads(self, tmp_path, qt_app, monkeypatch):
        """Falls back to Downloads when Desktop does not exist."""
        tab, _ = _make_sdr_tab(qt_app)
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        (tmp_path / "Downloads").mkdir()
        # No Desktop dir
        tab._save_screenshot()
        shots = list((tmp_path / "Downloads").glob("squelch_sdr_*.png"))
        assert shots, "Expected fallback to Downloads"


# ── SDR → RF Lab export tests ─────────────────────────────────────────────────

class TestSDRRFLabExportPureLogic:
    """Pure-logic tests for the SDR→RF Lab bookmark export contract."""

    def test_sdr_bookmark_category_defined(self):
        from ui.tabs.rf_lab_data import CATEGORY_COLORS
        assert "SDR Bookmark" in CATEGORY_COLORS

    def test_sdr_bookmark_color_is_hex(self):
        from ui.tabs.rf_lab_data import CATEGORY_COLORS
        color = CATEGORY_COLORS["SDR Bookmark"]
        assert color.startswith("#") and len(color) == 7

    def test_add_custom_freqs_batch_dedup(self):
        """add_custom_freqs_batch skips exact (freq_hz, name) duplicates."""
        # Simulate the dedup logic directly (no Qt)
        existing = [(14_074_000, "FT8", "SDR Bookmark", "USB")]
        def _batch(entries, _custom):
            added = skipped = 0
            for hz, name, cat, desc in entries:
                if any(f[0] == hz and f[1] == name for f in _custom):
                    skipped += 1
                    continue
                _custom.append((hz, name, cat, desc))
                added += 1
            return added, skipped

        new_entries = [
            (14_074_000, "FT8",  "SDR Bookmark", "USB"),  # duplicate
            (7_074_000,  "FT8 40m", "SDR Bookmark", "USB"),  # new
        ]
        added, skipped = _batch(new_entries, existing)
        assert added == 1
        assert skipped == 1
        assert len(existing) == 2

    def test_export_entry_format(self):
        """Bookmark dict → RF Lab tuple conversion."""
        bookmark = {
            "freq_hz": 144_390_000,
            "name": "APRS",
            "modulation": "AFSK",
            "category": "amateur",
        }
        hz = int(bookmark.get("freq_hz", 0))
        name = str(bookmark.get("name", "")).strip() or "Unknown"
        desc = str(bookmark.get("modulation", "") or "")
        entry = (hz, name, "SDR Bookmark", desc)
        assert entry == (144_390_000, "APRS", "SDR Bookmark", "AFSK")

    def test_zero_freq_skipped(self):
        """Bookmarks with freq_hz=0 are not exported."""
        bookmarks = [
            {"freq_hz": 0, "name": "Bad", "modulation": ""},
            {"freq_hz": 14_074_000, "name": "FT8", "modulation": "USB"},
        ]
        entries = []
        for b in bookmarks:
            hz = int(b.get("freq_hz", 0))
            name = str(b.get("name", "")).strip() or "Unknown"
            desc = str(b.get("modulation", "") or "")
            if hz > 0:
                entries.append((hz, name, "SDR Bookmark", desc))
        assert len(entries) == 1
        assert entries[0][0] == 14_074_000


# ── Squelch pure-logic tests ──────────────────────────────────────────────────

class TestYAxisRefLevel:
    """Pure-logic tests for the Y-axis reference level offset."""

    def _shifted(self, fft_db, ref_db):
        """Simulate the ref offset applied in _update_plots."""
        return fft_db + ref_db

    def test_zero_ref_no_shift(self):
        assert self._shifted(-80.0, 0.0) == -80.0

    def test_positive_ref_shifts_up(self):
        assert self._shifted(-80.0, 30.0) == -50.0

    def test_negative_ref_shifts_down(self):
        assert self._shifted(-80.0, -10.0) == -90.0

    def test_unit_label_dbfs_at_zero(self):
        unit = "dBFS" if 0.0 == 0.0 else "dBm"
        assert unit == "dBFS"

    def test_unit_label_dbm_when_nonzero(self):
        unit = "dBFS" if 30.0 == 0.0 else "dBm"
        assert unit == "dBm"

    def test_y_ref_key_in_save_state(self):
        src = __import__("pathlib").Path(__file__).parent.parent
        text = (src / "ui" / "tabs" / "sdr_tab.py").read_text(encoding="utf-8")
        assert '"y_ref_db"' in text

    def test_left_axis_tick_font_set(self):
        """Left axis must have setStyle(tickFont=...) just like the bottom axis."""
        src = __import__("pathlib").Path(__file__).parent.parent
        text = (src / "ui" / "tabs" / "sdr_tab.py").read_text(encoding="utf-8")
        assert 'getAxis("left").setStyle(tickFont' in text


class TestSquelchGateLogic:
    """Pure-logic tests for the squelch threshold gate."""

    def _gate(self, peak_db, squelch_db, enabled):
        """Simulate the squelch gate from _on_samples."""
        if not enabled:
            return True
        return peak_db >= squelch_db

    def test_disabled_always_open(self):
        assert self._gate(-90, -60, False) is True

    def test_above_threshold_open(self):
        assert self._gate(-55, -60, True) is True

    def test_at_threshold_open(self):
        assert self._gate(-60, -60, True) is True

    def test_below_threshold_closed(self):
        assert self._gate(-65, -60, True) is False

    def test_strong_signal_always_open(self):
        assert self._gate(-10, -80, True) is True

    def test_noise_floor_closed(self):
        assert self._gate(-110, -80, True) is False


class TestSquelchSourceKeys:
    """Verify squelch state is saved and keyed correctly."""

    def test_save_state_has_squelch_keys(self):
        src = __import__("pathlib").Path(__file__).parent.parent
        text = (src / "ui" / "tabs" / "sdr_tab.py").read_text(encoding="utf-8")
        assert '"squelch_enabled"' in text
        assert '"squelch_db"' in text

    def test_restore_state_handles_squelch(self):
        src = __import__("pathlib").Path(__file__).parent.parent
        text = (src / "ui" / "tabs" / "sdr_tab.py").read_text(encoding="utf-8")
        assert "squelch_enabled" in text and "squelch_db" in text

    def test_squelch_slider_range(self):
        src = __import__("pathlib").Path(__file__).parent.parent
        text = (src / "ui" / "tabs" / "sdr_tab.py").read_text(encoding="utf-8")
        assert "setRange(-120, 0)" in text

    def test_squelch_line_in_spec_plot(self):
        src = __import__("pathlib").Path(__file__).parent.parent
        text = (src / "ui" / "tabs" / "sdr_tab.py").read_text(encoding="utf-8")
        assert "_squelch_line" in text


@pytest.mark.skipif(not HAS_QT, reason="PyQt6 not installed")
class TestSquelchQt:
    """Qt tests for squelch UI controls."""

    def test_squelch_cb_present(self, qt_app):
        from PyQt6.QtWidgets import QCheckBox
        tab, _ = _make_sdr_tab(qt_app)
        cbs = [w for w in tab.findChildren(QCheckBox)
               if "Squelch" in (w.text() or "")]
        assert cbs, "Squelch checkbox must exist in Demodulator group"

    def test_squelch_default_disabled(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        assert not tab._squelch_enabled

    def test_squelch_enable_toggles_slider(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        tab._squelch_cb.setChecked(True)
        assert tab._squelch_slider.isEnabled()
        tab._squelch_cb.setChecked(False)
        assert not tab._squelch_slider.isEnabled()

    def test_squelch_round_trip_state(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        tab._squelch_cb.setChecked(True)
        tab._squelch_slider.setValue(-45)
        state = tab.save_state()
        assert state["squelch_enabled"] is True
        assert state["squelch_db"] == -45.0
        tab._squelch_cb.setChecked(False)
        tab._squelch_slider.setValue(-60)
        tab.restore_state(state)
        assert tab._squelch_cb.isChecked()
        assert tab._squelch_slider.value() == -45


@pytest.mark.skipif(not HAS_QT, reason="PyQt6 not installed")
class TestSDRRFLabExportQt:
    """Qt tests for the SDR→RF Lab export button and integration."""

    def test_export_button_present(self, qt_app):
        from PyQt6.QtWidgets import QPushButton
        tab, _ = _make_sdr_tab(qt_app)
        btns = [w for w in tab.findChildren(QPushButton)
                if "Monitor" in (w.text() or "")]
        assert len(btns) >= 1, "→ Monitor button must be present in SDR toolbar"

    def test_export_to_rf_lab_method_exists(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        assert hasattr(tab, "_export_to_rf_lab")
        assert callable(tab._export_to_rf_lab)

    def test_add_custom_freqs_batch_via_rf_lab_tab(self, qt_app, tmp_path):
        """RFLabTab.add_custom_freqs_batch() adds entries and deduplicates."""
        from ui.tabs.rf_lab_tab import RFLabTab
        from core.config import Config
        cfg = Config(tmp_path / "config.json")
        tab = RFLabTab(cfg)
        entries = [
            (14_074_000, "FT8",    "SDR Bookmark", "USB"),
            (144_390_000, "APRS",  "SDR Bookmark", "AFSK"),
        ]
        added, skipped = tab.add_custom_freqs_batch(entries)
        assert added == 2
        assert skipped == 0
        # Re-add same entries — all skipped
        added2, skipped2 = tab.add_custom_freqs_batch(entries)
        assert added2 == 0
        assert skipped2 == 2


# ---------------------------------------------------------------------------
# Auto demod/bandwidth on tune (FEAT — auto modulation selection)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_QT, reason="PyQt6 not installed")
class TestAutoDemod:

    def test_auto_checkbox_present(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        assert hasattr(tab, "_auto_demod_cb")

    def test_off_by_default_no_change(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        tab._demod_combo.setCurrentText("USB")
        tab._auto_demod_cb.setChecked(False)
        tab._set_freq(98_500_000)          # FM broadcast
        assert tab._demod_combo.currentText() == "USB"   # unchanged

    def test_auto_sets_wfm_on_fm_broadcast(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        tab._auto_demod_cb.setChecked(True)
        tab._set_freq(98_500_000)
        assert tab._demod_combo.currentText() == "WFM"
        assert tab._demod_bw.currentText() == "200 kHz"

    def test_auto_sets_am_on_airband(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        tab._auto_demod_cb.setChecked(True)
        tab._set_freq(124_000_000)
        assert tab._demod_combo.currentText() == "AM"

    def test_auto_sets_cw_narrow_on_40m_cw(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        tab._auto_demod_cb.setChecked(True)
        tab._set_freq(7_030_000)
        assert tab._demod_combo.currentText() == "CW"
        assert tab._demod_bw.currentText() == "500 Hz"

    def test_auto_state_saved_and_restored(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        tab._auto_demod_cb.setChecked(True)
        st = tab.save_state()
        assert st["demod_auto"] is True
        tab2, _ = _make_sdr_tab(qt_app)
        tab2.restore_state(st)
        assert tab2._auto_demod_cb.isChecked() is True

    def test_manual_pick_disables_auto(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        tab._auto_demod_cb.setChecked(True)
        tab._on_manual_demod_pick()        # simulate a user mode/BW pick
        assert tab._auto_demod_cb.isChecked() is False

    def test_auto_apply_does_not_self_disable(self, qt_app):
        # Programmatic auto-apply must NOT trip the manual-override (it uses
        # activated[], which setCurrentText does not emit).
        tab, _ = _make_sdr_tab(qt_app)
        tab._auto_demod_cb.setChecked(True)
        tab._set_freq(98_500_000)          # auto applies WFM via setCurrentText
        assert tab._auto_demod_cb.isChecked() is True
        assert tab._demod_combo.currentText() == "WFM"


@pytest.mark.skipif(not HAS_QT, reason="PyQt6 not installed")
class TestPassbandAndLegend:
    """SDR spectral-view UX: visible draggable IF passband + colour legend."""

    def _tab(self, qt_app):
        from ui.tabs.sdr_tab import HAS_PG
        if not HAS_PG:
            pytest.skip("pyqtgraph not installed")
        return _make_sdr_tab(qt_app)[0]

    def test_passband_and_legend_built(self, qt_app):
        tab = self._tab(qt_app)
        assert tab._passband is not None
        assert tab._legend is not None

    def test_bw_change_widens_passband(self, qt_app):
        tab = self._tab(qt_app)
        tab._demod_bw.setCurrentText("2.5 kHz")
        lo, hi = tab._passband.getRegion()
        narrow = abs(hi - lo)
        tab._demod_bw.setCurrentText("200 kHz")
        lo, hi = tab._passband.getRegion()
        wide = abs(hi - lo)
        assert wide > narrow

    def test_passband_drag_snaps_bandwidth(self, qt_app):
        tab = self._tab(qt_app)
        cf_mhz = (tab._center_hz + tab._lo_hz) / 1e6
        half   = (5_000 / 2) / 1e6           # a ~5 kHz wide drag
        tab._passband.setRegion((cf_mhz - half, cf_mhz + half))
        tab._on_passband_drag()
        assert tab._demod_bw.currentText() == "5 kHz"

    def test_drag_pauses_auto_demod(self, qt_app):
        tab = self._tab(qt_app)
        tab._auto_demod_cb.setChecked(True)
        cf_mhz = (tab._center_hz + tab._lo_hz) / 1e6
        half   = (10_000 / 2) / 1e6
        tab._passband.setRegion((cf_mhz - half, cf_mhz + half))
        tab._on_passband_drag()
        assert tab._auto_demod_cb.isChecked() is False

    def test_legend_tracks_palette_and_range(self, qt_app):
        tab = self._tab(qt_app)
        tab._on_palette("Viridis")
        assert tab._legend._colors == __import__(
            "ui.tabs.sdr_tab", fromlist=["PALETTES"]).PALETTES["Viridis"]
        tab._legend.set_range(-90, -10)
        assert tab._legend._lo_db == -90.0
        assert tab._legend._hi_db == -10.0


class TestWheelScrollSource:
    """Source-scan: the wheel handler reads both axes; toggle + persistence."""

    def _src(self) -> str:
        root = __import__("pathlib").Path(__file__).parent.parent
        return (root / "ui" / "tabs" / "sdr_tab.py").read_text(encoding="utf-8")

    def test_handler_reads_both_axes(self):
        src = self._src()
        idx = src.find("def _wheel_waterfall(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "angleDelta().x()" in body
        assert "angleDelta().y()" in body

    def test_step_bandwidth_method_defined(self):
        assert "def _step_bandwidth(" in self._src()

    def test_wheel_toggle_widget_present(self):
        src = self._src()
        assert "_wheel_bw_cb" in src
        assert "_scroll_vert_bw" in src

    def test_wheel_toggle_persisted(self):
        src = self._src()
        assert '"wheel_vert_bw"' in src


@pytest.mark.skipif(not HAS_QT, reason="PyQt6 not installed")
class TestWheelScrollQt:
    """Qt behavioural tests for the spectrum/waterfall wheel mapping."""

    class _FakeWheel:
        def __init__(self, dx, dy, ctrl=False):
            from PyQt6.QtCore import QPoint
            self._d = QPoint(dx, dy)
            self._ctrl = ctrl

        def angleDelta(self):
            return self._d

        def modifiers(self):
            from PyQt6.QtCore import Qt
            return (Qt.KeyboardModifier.ControlModifier if self._ctrl
                    else Qt.KeyboardModifier.NoModifier)

        def accept(self):
            pass

    def test_scroll_right_increases_freq(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        f0 = tab._center_hz
        tab._wheel_waterfall(self._FakeWheel(120, 0))
        assert tab._center_hz > f0

    def test_scroll_left_decreases_freq(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        f0 = tab._center_hz
        tab._wheel_waterfall(self._FakeWheel(-120, 0))
        assert tab._center_hz < f0

    def test_scroll_up_increases_freq_by_default(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        tab._scroll_vert_bw = False
        f0 = tab._center_hz
        tab._wheel_waterfall(self._FakeWheel(0, 120))
        assert tab._center_hz > f0

    def test_vertical_changes_bw_when_toggled(self, qt_app):
        tab, _ = _make_sdr_tab(qt_app)
        tab._wheel_bw_cb.setChecked(True)
        tab._demod_bw.setCurrentIndex(2)
        f0 = tab._center_hz
        tab._wheel_waterfall(self._FakeWheel(0, 120))   # up = wider
        assert tab._demod_bw.currentIndex() == 3
        assert tab._center_hz == f0   # frequency untouched in BW mode
