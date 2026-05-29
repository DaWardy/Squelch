"""Tests for the side-view propagation mode classifier."""
from __future__ import annotations
import os, sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6", reason="PyQt6 not installed")


@pytest.fixture
def widget():
    from PyQt6.QtWidgets import QApplication, QWidget
    app = QApplication.instance() or QApplication([])
    from ui.widgets.propagation_sideview import PropagationSideView
    holder = QWidget()
    w = PropagationSideView(parent=holder)
    yield w
    # Keep holder reference alive until teardown
    del w
    del holder


def test_above_muf_is_beyond(widget):
    widget.update_state(path_km=3000, muf_mhz=14, freq_mhz=28)
    assert widget._propagation_mode() == "beyond"


def test_below_luf_is_absorbed(widget):
    widget.update_state(path_km=3000, muf_mhz=14, luf_mhz=5, freq_mhz=1.8)
    assert widget._propagation_mode() == "absorbed"


def test_long_path_in_band_is_skywave(widget):
    widget.update_state(path_km=3000, muf_mhz=14, luf_mhz=3, freq_mhz=10)
    assert widget._propagation_mode() == "skywave"


def test_short_low_freq_is_nvis(widget):
    # < 400 km path, < 10 MHz → near-vertical-incidence skywave
    widget.update_state(path_km=200, muf_mhz=14, luf_mhz=3, freq_mhz=7)
    assert widget._propagation_mode() == "nvis"


def test_short_high_freq_is_groundwave(widget):
    # Short path on 2m/440 is groundwave/line-of-sight territory
    widget.update_state(path_km=200, muf_mhz=14, luf_mhz=3, freq_mhz=14)
    # 14 MHz is at MUF (not above), short path, freq >= 10 → groundwave path
    assert widget._propagation_mode() == "groundwave"


def test_no_freq_returns_empty(widget):
    widget.update_state(path_km=3000, muf_mhz=14, freq_mhz=0)
    assert widget._propagation_mode() == ""


def test_paints_without_crash(widget):
    """The widget should be paintable with no path set and not crash."""
    from PyQt6.QtGui import QPixmap
    widget.update_state(path_km=0, muf_mhz=0)
    pm = QPixmap(400, 200)
    widget.resize(400, 200)
    widget.render(pm)
    # If we got here, paintEvent didn't raise
