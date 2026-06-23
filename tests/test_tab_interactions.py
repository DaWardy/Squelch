# Squelch QA gate — tab interaction smoke tests (DevSecOps QA/QC)
# Licensed under GNU GPL v3
from __future__ import annotations
"""
Goes beyond test_tab_smoke (which only builds tabs): this drives each tab's
*behaviour* under offscreen Qt, to catch runtime bugs in handlers that
construction alone misses —
  * save_state() / restore_state() round-trip
  * showEvent (tabs that defer building until first shown)
  * tab-switch handlers (currentChanged) for every tab, including hidden ones
  * the SDR live-sample pipeline (NB + NR + FFT) on a synthetic IQ frame

Only side-effect-free interactions are exercised; it never clicks buttons that
open file dialogs, hit the network, or launch external programs.

Skips where PyQt6 / numpy are unavailable. Run via the venv (qa_check does this
automatically).
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6", reason="PyQt6 not installed")


@pytest.fixture(scope="module")
def window():
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from core.config import Config
    from core.rig import RigController
    from core.location import LocationManager
    from ui.main_window import MainWindow
    cfg = Config()
    win = MainWindow(cfg, RigController(cfg), LocationManager(cfg))
    yield win
    win.close()


def _tabs(win):
    from ui.main_window import TABS
    for key, _label, _ in TABS:
        w = win._tab_map.get(key)
        if w is not None and w.objectName() != "tab_load_error":
            yield key, w


# ── save_state / restore_state round-trip ────────────────────────────────────

def test_save_state_returns_dict(window):
    bad = []
    for key, w in _tabs(window):
        if hasattr(w, "save_state"):
            try:
                st = w.save_state()
                if not isinstance(st, dict):
                    bad.append(f"{key}: save_state returned {type(st).__name__}")
            except Exception as e:
                bad.append(f"{key}: save_state raised {type(e).__name__}: {e}")
    assert not bad, "save_state problems:\n" + "\n".join(bad)


def test_restore_state_roundtrip(window):
    bad = []
    for key, w in _tabs(window):
        if hasattr(w, "save_state") and hasattr(w, "restore_state"):
            try:
                w.restore_state(w.save_state())
            except Exception as e:
                bad.append(f"{key}: restore_state raised {type(e).__name__}: {e}")
    assert not bad, "restore_state problems:\n" + "\n".join(bad)


def test_restore_empty_state_safe(window):
    """A tab must tolerate an empty/foreign state dict (older config, etc.)."""
    bad = []
    for key, w in _tabs(window):
        if hasattr(w, "restore_state"):
            try:
                w.restore_state({})
            except Exception as e:
                bad.append(f"{key}: restore_state({{}}) raised "
                           f"{type(e).__name__}: {e}")
    assert not bad, "empty-state problems:\n" + "\n".join(bad)


# ── showEvent / tab switching ────────────────────────────────────────────────

def test_switch_through_every_tab(window):
    """Make each tab current (fires showEvent + currentChanged), including
    tabs hidden by default — that's where deferred builds blow up."""
    from PyQt6.QtWidgets import QApplication
    tabs = window.tabs
    errors = []
    for i in range(tabs.count()):
        try:
            tabs.setTabVisible(i, True)
            tabs.setCurrentIndex(i)
            QApplication.processEvents()
        except Exception as e:
            errors.append(f"tab index {i}: {type(e).__name__}: {e}")
    assert not errors, "tab-switch problems:\n" + "\n".join(errors)


# ── SDR live-sample pipeline ─────────────────────────────────────────────────

def test_sdr_sample_pipeline(window):
    """Feed a synthetic IQ frame through the SDR tab with NB + NR enabled —
    exercises the hot path (noise blank → window → FFT → waterfall)."""
    np = pytest.importorskip("numpy")
    sdr = window._tab_map.get("sdr")
    if sdr is None or sdr.objectName() == "tab_load_error":
        pytest.skip("SDR tab unavailable")
    rng = np.random.default_rng(0)
    iq = (rng.standard_normal(2048) + 1j * rng.standard_normal(2048)).astype("complex64")
    iq[500] = 40.0          # an impulse for the noise blanker to clamp
    sdr._nb_enabled = True
    sdr._nr_enabled = True
    sdr._on_samples(iq, 2_400_000, 100_000_000)   # must not raise
    assert sdr._latest_fft is not None


def test_sdr_auto_demod_follows_tuning(window):
    """With Auto on, tuning the SDR sets a sensible demod mode (integration)."""
    sdr = window._tab_map.get("sdr")
    if sdr is None or sdr.objectName() == "tab_load_error":
        pytest.skip("SDR tab unavailable")
    sdr._auto_demod_cb.setChecked(True)
    sdr._set_freq(98_500_000)
    assert sdr._demod_combo.currentText() == "WFM"
    sdr._set_freq(14_074_000)
    assert sdr._demod_combo.currentText() == "USB"
