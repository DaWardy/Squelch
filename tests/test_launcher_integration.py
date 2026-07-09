from __future__ import annotations
# Squelch — RF / SDR signal platform
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for external-software integration labelling + the console launch
script (both from live user feedback)."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
ROOT = Path(__file__).parent.parent
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ── integrated vs launch-only classification ──────────────────────────────────

class TestIntegrationClassification:
    def test_decoders_and_control_are_integrated(self):
        from core.launcher import app_is_integrated, APPS
        by_key = {a.key: a for a in APPS}
        for k in ("paths.wsjtx", "paths.fldigi", "paths.dump1090",
                  "paths.rigctld", "paths.dsdplus", "paths.pat"):
            assert app_is_integrated(by_key[k]), k

    def test_standalone_sdr_apps_are_launch_only(self):
        from core.launcher import app_is_integrated, APPS
        by_key = {a.key: a for a in APPS}
        for k in ("paths.sdrsharp", "paths.sdruno", "paths.hdsdr",
                  "paths.sdrconsole", "paths.gnuradio"):
            assert not app_is_integrated(by_key[k]), k

    def test_unknown_app_not_integrated(self):
        from core.launcher import app_is_integrated
        assert app_is_integrated(object()) is False


# ── tooltip wiring (source-level) ─────────────────────────────────────────────

class TestTooltipWiring:
    def test_launch_button_uses_integration_note(self):
        src = (ROOT / "ui/widgets/launch_bar.py").read_text(encoding="utf-8")
        assert "_integration_note" in src
        assert "app_is_integrated" in src
        assert "runs independently" in src


# ── Qt behaviour ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
    pytest.importorskip("PyQt6", reason="PyQt6 not installed")
    from PyQt6.QtWidgets import QApplication
    a = QApplication.instance() or QApplication([])
    yield a


class _Cfg:
    def get(self, k, d=None):
        return d


class TestTooltipQt:
    def _btn(self, key):
        from core.launcher import APPS
        from ui.widgets.launch_bar import LaunchButton
        app_def = next(a for a in APPS if a.key == key)
        return LaunchButton(app_def, _Cfg())

    def test_integrated_tooltip(self, app):
        note = self._btn("paths.dump1090")._integration_note()
        assert "Integrated" in note

    def test_launch_only_tooltip(self, app):
        note = self._btn("paths.sdrconsole")._integration_note()
        assert "independently" in note


# ── run_squelch.bat console + keep-open warning ───────────────────────────────

class TestLaunchScript:
    def test_run_bat_is_console_with_warning(self):
        bat = (ROOT / "run_squelch.bat").read_text(encoding="utf-8")
        assert "python main.py" in bat
        assert "pythonw" not in bat            # console, not windowless
        assert "KEEP THIS WINDOW OPEN" in bat
        assert "Ctrl+C" in bat

    def test_installer_generates_console_run_bat(self):
        src = (ROOT / "setup/installer.py").read_text(encoding="utf-8")
        # the installer must not regenerate the windowless pythonw version
        import re
        m = re.search(r'_write\("run_squelch\.bat",(.+?)\)\n\s*ok\(',
                      src, re.DOTALL)
        assert m, "run_squelch.bat writer not found"
        block = m.group(1)
        assert "python main.py" in block
        assert "pythonw main.py" not in block
        assert "KEEP THIS WINDOW OPEN" in block
