# Squelch QA gate — headless tab smoke test (DevSecOps QA/QC)
# Licensed under GNU GPL v3
"""
Instantiates the MainWindow and every tab under an offscreen Qt platform and
fails if any tab raises. This is the feature test that should run before
packaging — it would have caught the modes/_hold_tx_cb, sdr/_sep, and
winlink/_vsep crashes that reached the user.

Skips automatically where PyQt6 is unavailable (e.g. a headless CI image
without Qt); CI installs PyQt6 so it runs there and locally on the dev box.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6", reason="PyQt6 not installed in this environment")


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    a = QApplication.instance() or QApplication([])
    yield a


def test_main_window_builds(app):
    """The whole window — every tab — must build without raising."""
    from core.config import Config
    from core.rig import RigController
    from core.location import LocationManager
    from ui.main_window import MainWindow
    cfg = Config()
    rig = RigController(cfg)
    location = LocationManager(cfg)
    win = MainWindow(cfg, rig, location)
    assert win is not None
    assert win.tabs.count() > 0
    # Assert that NO tab failed to load (each should be a real widget,
    # not the error-stub). This catches signal/slot arg mismatches and
    # any exception raised during a tab's construction.
    from ui.main_window import TABS
    failed = []
    for key, label, _ in TABS:
        w = win._tab_map.get(key)
        if w is None:
            failed.append(f"{key} (None)")
        elif w.objectName() == "tab_load_error":
            failed.append(f"{key} (error stub — exception during build)")
    assert not failed, f"Tabs failed to build: {failed}"
    win.close()


def test_each_tab_builds_individually(app):
    """Build each tab in isolation so a failure names the exact tab."""
    from core.config import Config
    from core.rig import RigController
    from core.location import LocationManager
    from ui.main_window import MainWindow, TABS
    cfg = Config()
    rig = RigController(cfg)
    location = LocationManager(cfg)
    win = MainWindow(cfg, rig, location)
    failures = []
    for key, label, _ in TABS:
        w = win._tab_map.get(key)
        if w is None:
            failures.append(f"{key}: tab not created")
        elif w.objectName() == "tab_load_error":
            failures.append(f"{key}: exception during build (error stub)")
    win.close()
    assert not failures, "Tabs failed to build:\n" + "\n".join(failures)
