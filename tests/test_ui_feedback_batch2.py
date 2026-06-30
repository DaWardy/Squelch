"""UI/UX feedback sprint — Batch 2 (label & layout clarity fixes).

Source-level assertions for the small fixes batched together:
  #6  Weak Signal Band/Frequency readout was clipped at small widths.
  Custom-tab Edit/Done toggle (was the inverted 🔓 Rearrange / 🔒 Lock).
  Local RF launch bar marks programming software with a 🛠 icon.
"""
from __future__ import annotations
import pathlib

import pytest

try:
    from PyQt6.QtWidgets import QCheckBox, QComboBox  # noqa: F401
    HAS_QT = True
except Exception:
    HAS_QT = False

ROOT = pathlib.Path(__file__).parent.parent


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class TestWeakSignalFreqLabel:
    def test_freq_label_has_minimum_width(self):
        src = _src("ui/tabs/modes_tab.py")
        # The monospace frequency readout needs a floor width so long
        # readouts (e.g. "1296.074000 MHz") are not clipped (#6).
        assert "_freq_label.setMinimumWidth(" in src

    def test_freq_column_stretches(self):
        src = _src("ui/tabs/modes_tab.py")
        assert "band_gl.setColumnStretch(1, 1)" in src


class TestTabRenameBatch3:
    """Batch 3 — industry-standard tab naming.

    Confusing labels were renamed for clarity; panel_id / internal "ui.mode"
    values ("rf_lab", "localrf", "bandcond", "signals") are kept unchanged
    so saved layouts and configs from prior versions still resolve.
    """

    def test_tabs_list_uses_new_labels(self):
        src = _src("ui/main_window.py")
        assert '"📋  Repeaters"' in src
        assert '"☀️  Propagation"' in src
        assert '"📶  Signal Log"' in src
        assert '"🔬  Monitor"' in src

    def test_panel_ids_unchanged(self):
        src = _src("ui/main_window.py")
        for pid in ('"localrf"', '"bandcond"', '"signals"', '"rf_lab"'):
            assert pid in src, f"panel_id {pid} must be preserved for saved layouts"

    def test_rf_lab_tab_panel_title_renamed(self):
        assert 'panel_title = "Monitor"' in _src("ui/tabs/rf_lab_tab.py")

    def test_localrf_tab_panel_title_renamed(self):
        assert 'panel_title = "Repeaters"' in _src("ui/tabs/localrf_tab.py")

    def test_band_conditions_panel_title_renamed(self):
        assert 'panel_title = "Propagation"' in _src("ui/tabs/band_conditions_tab.py")

    def test_signal_browser_panel_title_renamed(self):
        assert 'panel_title = "Signal Log"' in _src("ui/tabs/signal_browser_tab.py")


class TestRigTuneArrows:
    """#5 — the VFO tuning row mixed ◄►(step) with ▼▲(fine), which gave no
    consistent sense of direction or magnitude. Now a single horizontal axis:
    band-edge (⏮⏭) → step (⏪⏩) → fine 1 Hz (◄►), with a 'Tune:' label.
    """

    def test_no_vertical_fine_tune_arrows(self):
        src = _src("ui/tabs/rig_tab.py")
        # The old vertical fine-tune glyphs must be gone from the tune row.
        assert '"▼", "Fine tune' not in src
        assert '"▲", "Fine tune' not in src

    def test_horizontal_step_glyphs(self):
        src = _src("ui/tabs/rig_tab.py")
        assert '"⏪"' in src and '"⏩"' in src  # coarse step, magnitude-coded

    def test_tune_label_present(self):
        assert 'QLabel("Tune:")' in _src("ui/tabs/rig_tab.py")

    def test_directional_tooltips(self):
        src = _src("ui/tabs/rig_tab.py")
        assert "Fine tune down (− 1 Hz)" in src
        assert "Fine tune up (+ 1 Hz)" in src


class TestMapStatePersistence:
    """#9 — the Map tab never persisted its layer/filter choices, so toggling
    off clutter (ADS-B/APRS) was forgotten every restart. It now implements the
    SquelchPanel save_state/restore_state lifecycle.
    """

    def test_methods_defined(self):
        src = _src("ui/tabs/map_tab.py")
        assert "def save_state(self)" in src
        assert "def restore_state(self, state" in src

    @pytest.mark.skipif(not HAS_QT, reason="PyQt6 not installed")
    def test_roundtrip_with_real_widgets(self):
        # Drive save_state/restore_state against a holder carrying real Qt
        # widgets — avoids constructing MapTab (which needs QtWebEngine).
        from ui.tabs.map_tab import MapTab

        class _Holder:
            _STATE_CHECKS = MapTab._STATE_CHECKS
            _STATE_COMBOS = MapTab._STATE_COMBOS

        src = _Holder()
        src._show_gl = QCheckBox(); src._show_gl.setChecked(True)
        src._show_adsb = QCheckBox(); src._show_adsb.setChecked(True)
        src._qso_filter = QComboBox(); src._qso_filter.addItems(["All", "Last 50"])
        src._qso_filter.setCurrentText("All")

        # User turns ADS-B off and narrows the QSO filter, then we persist.
        src._show_adsb.setChecked(False)
        src._qso_filter.setCurrentText("Last 50")
        state = MapTab.save_state(src)
        assert state["_show_adsb"] is False
        assert state["_qso_filter"] == "Last 50"

        # Fresh widgets (defaults) → restore should reapply the saved view.
        dst = _Holder()
        dst._show_gl = QCheckBox(); dst._show_gl.setChecked(True)
        dst._show_adsb = QCheckBox(); dst._show_adsb.setChecked(True)
        dst._qso_filter = QComboBox(); dst._qso_filter.addItems(["All", "Last 50"])
        MapTab.restore_state(dst, state)
        assert dst._show_adsb.isChecked() is False
        assert dst._qso_filter.currentText() == "Last 50"

    @pytest.mark.skipif(not HAS_QT, reason="PyQt6 not installed")
    def test_restore_tolerates_missing_widgets(self):
        # Fallback toolbar has fewer widgets — restore must not raise.
        from ui.tabs.map_tab import MapTab

        class _Holder:
            _STATE_CHECKS = MapTab._STATE_CHECKS
            _STATE_COMBOS = MapTab._STATE_COMBOS

        dst = _Holder()
        dst._show_gl = QCheckBox()
        MapTab.restore_state(dst, {"_show_gl": False, "_show_adsb": True,
                                   "_qso_filter": "Last 50"})
        assert dst._show_gl.isChecked() is False
