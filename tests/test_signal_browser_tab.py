"""Tests for the Signal Browser tab (SIG-BROWSER).

Pure source/registration checks run everywhere; Qt round-trip tests skip when
PyQt6 is absent from the runner.
"""
from __future__ import annotations
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

ROOT = Path(__file__).parent.parent


# ── Registration / contract (no Qt) ─────────────────────────────────────────


class TestRegistration:
    def _mw_src(self) -> str:
        return (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")

    def test_tab_in_TABS(self):
        assert '("signals",' in self._mw_src()

    def test_tab_in_registry(self):
        src = self._mw_src()
        assert "ui.tabs.signal_browser_tab" in src
        assert "SignalBrowserTab" in src

    def test_tab_shown_in_rf_lab_mode(self):
        # signals tab should appear in RF Lab / Education layout
        src = self._mw_src()
        i = src.index("_RF_LAB_SHOWN")
        assert '"signals"' in src[i:i + 200]

    def test_tune_cb_wired(self):
        assert "signals.set_sdr_tune_cb" in self._mw_src()


class TestModuleContract:
    def _src(self) -> str:
        return (ROOT / "ui" / "tabs" / "signal_browser_tab.py").read_text(
            encoding="utf-8")

    def test_panel_id(self):
        assert 'panel_id    = "signals"' in self._src()

    def test_uses_presenter(self):
        src = self._src()
        assert "from core.signal_browser import" in src
        assert "format_row" in src and "filter_signals" in src

    def test_uses_store(self):
        assert "get_signal_store" in self._src()

    def test_no_sorting_enabled_at_init(self):
        # setSortingEnabled(True) during init hangs offscreen Qt — must be absent
        assert "setSortingEnabled(True)" not in self._src()

    def test_compiles(self):
        import py_compile
        py_compile.compile(
            str(ROOT / "ui" / "tabs" / "signal_browser_tab.py"), doraise=True)


# ── Qt round-trip (skips without PyQt6) ──────────────────────────────────────

try:
    import PyQt6  # noqa: F401
    HAS_QT = True
except ImportError:
    HAS_QT = False


@pytest.fixture(scope="module")
def qt_app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


def _make_tab(qt_app, monkeypatch):
    from core.config import Config
    from core.signal_model import SignalStore, Signal
    import ui.tabs.signal_browser_tab as mod

    store = SignalStore(":memory:")
    store.add(Signal(freq_hz=144_390_000, source="aprs", emitter_id="K1ABC",
                     classification="APRS", decoded="hello"))
    store.add(Signal(freq_hz=14_074_000, source="ft8", emitter_id="W1AW",
                     classification="FT8", snr_db=-12.0))
    monkeypatch.setattr(mod, "get_signal_store", lambda: store)

    cfg = Config(Path(tempfile.mkdtemp()) / "config.json")
    return mod.SignalBrowserTab(cfg), store


@pytest.mark.skipif(not HAS_QT, reason="PyQt6 not installed")
class TestQtTab:
    def test_builds_and_populates(self, qt_app, monkeypatch):
        tab, _ = _make_tab(qt_app, monkeypatch)
        assert tab._table.rowCount() == 2

    def test_source_filter(self, qt_app, monkeypatch):
        tab, _ = _make_tab(qt_app, monkeypatch)
        tab._source.setCurrentText("ft8")
        assert tab._table.rowCount() == 1

    def test_text_filter(self, qt_app, monkeypatch):
        tab, _ = _make_tab(qt_app, monkeypatch)
        tab._search.setText("k1abc")
        assert tab._table.rowCount() == 1

    def test_save_restore(self, qt_app, monkeypatch):
        tab, _ = _make_tab(qt_app, monkeypatch)
        tab._search.setText("cq")
        st = tab.save_state()
        assert st["search"] == "cq"
        tab2, _ = _make_tab(qt_app, monkeypatch)
        tab2.restore_state(st)
        assert tab2._search.text() == "cq"

    def test_double_click_emits_tune(self, qt_app, monkeypatch):
        tab, _ = _make_tab(qt_app, monkeypatch)
        from PyQt6.QtCore import QModelIndex
        captured = []
        tab.tune_requested.connect(lambda hz: captured.append(hz))
        # row 0 is the most-recent (ft8 @ 14.074 or aprs) — just take row 0's freq
        idx = tab._table.model().index(0, 0)
        tab._on_double_click(idx)
        assert captured and captured[0] > 0
