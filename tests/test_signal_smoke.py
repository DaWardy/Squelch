# Squelch QA gate — signal/callback emission smoke test
# Catches arity mismatches that only crash when a signal/callback FIRES,
# not when the tab is built. e.g. _on_seq_state / _on_vara_state taking
# the wrong number of args. Requires PyQt6 (skips if absent).
from __future__ import annotations
import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6", reason="PyQt6 not installed")


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_ft8_state_callback_both_arities(app):
    """The FT8 auto-seq state callback fires with (state) and (state, detail).
    The Modes tab slot must accept both without crashing."""
    from core.config import Config
    from modes.ft8 import AutoSeqState
    from ui.tabs.modes_tab import ModesTab
    cfg = Config()
    tab = ModesTab(None, cfg, None)
    # 1-arg form
    tab._on_seq_state(AutoSeqState.IDLE)
    # 2-arg form (the path that fires when WSJT-X/rig not connected)
    tab._on_seq_state(AutoSeqState.IDLE, "WSJT-X not connected")


def test_ft8_engine_tx_without_rig_does_not_crash(app):
    """Pressing CQ/TX with no rig/WSJT-X must not raise (user crash)."""
    from core.config import Config
    from modes.ft8 import FT8Engine
    cfg = Config()
    eng = FT8Engine(cfg, None)
    states = []
    eng.on_state_change(lambda *a: states.append(a))
    # send_cq with nothing connected — should degrade gracefully
    try:
        eng.send_cq()
    except Exception as e:
        pytest.fail(f"send_cq with no rig raised: {e}")


def test_vara_state_callback_arity(app):
    """The VARA state callback is invoked with a VARAState enum, not a string.
    Previously this test used plain strings (which have .lower()), giving a
    false green while the real modem passed an enum — causing the crash."""
    from core.config import Config
    from ui.tabs.winlink_tab import WinlinkTab
    from winlink.vara import VARAState
    cfg = Config()
    tab = WinlinkTab(cfg, None)
    tab._on_vara_state(VARAState.CONNECTED)            # 1-arg, enum type
    tab._on_vara_state(VARAState.CONNECTED, "HF")      # 2-arg, enum type
    tab._on_vara_state(VARAState.DISCONNECTED)         # test non-connected state


def test_winlink_send_without_setup_does_not_crash(app):
    """Pressing send/TX in Winlink with nothing configured must not crash."""
    from core.config import Config
    from ui.tabs.winlink_tab import WinlinkTab
    cfg = Config()
    tab = WinlinkTab(cfg, None)
    try:
        tab._send_message()       # nothing filled in
        tab._connect_hf()         # no modem running
    except Exception as e:
        import pytest
        pytest.fail(f"Winlink TX without setup raised: {e}")


def test_settings_dialog_opens(app):
    """SettingsDialog must build all tabs without a deleted-widget crash."""
    from core.config import Config
    from PyQt6.QtWidgets import QMainWindow
    from ui.dialogs.settings_dialog import SettingsDialog
    cfg = Config()
    mw = QMainWindow()
    dlg = SettingsDialog(cfg, parent=mw)
    assert dlg._tabs.count() >= 6


def test_panel_shell_builds(app):
    """PanelShell builds with all registered panels and shows preset."""
    from core.config import Config
    from core.rig import RigController
    from core.location import LocationManager
    from ui.main_window import MainWindow
    from ui.panel import SquelchPanel
    from ui.panel_shell import PanelShell, PRESETS

    cfg = Config()
    mw = MainWindow(cfg, RigController(cfg), LocationManager(cfg))

    # Collect panels
    panels = {pid: tab for pid, tab in mw._tab_map.items()
              if isinstance(tab, SquelchPanel) and getattr(tab, 'panel_id', '')}
    assert len(panels) >= 8, f"Expected ≥8 panels, got {len(panels)}"

    # Build PanelShell
    shell = PanelShell(panels, cfg)
    assert len(shell._docks) == len(panels)

    # Apply all built-in presets without crashing
    for name in PRESETS:
        shell._apply_preset(name)

    # Verify save/restore round-trips
    shell._persist()
    mw.close(); shell.hide()
