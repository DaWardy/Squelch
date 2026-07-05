from __future__ import annotations
# Squelch — RF / SDR signal platform
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for SDR Console in the launcher + the download-link menu for
undetected external software (launch_bar)."""
import ast
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
ROOT = Path(__file__).parent.parent
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ── SDR Console registry entry ────────────────────────────────────────────────

class TestSdrConsoleRegistered:
    def _apps(self):
        from core.launcher import APPS
        return {a.key: a for a in APPS}

    def test_sdr_console_present(self):
        apps = self._apps()
        assert "paths.sdrconsole" in apps
        a = apps["paths.sdrconsole"]
        assert a.name == "SDR Console"
        assert a.category == "sdr"
        assert a.tab == "sdr"
        assert a.download_url.startswith("https://www.sdr-radio.com")

    def test_shows_in_sdr_launch_bar(self):
        from core.launcher import _BY_TAB
        names = [a.name for a in _BY_TAB.get("sdr", [])]
        assert "SDR Console" in names

    def test_every_sdr_app_has_download_url(self):
        from core.launcher import _BY_TAB
        for a in _BY_TAB.get("sdr", []):
            assert a.download_url, f"{a.key} missing download_url"


# ── download-menu wiring (source-level) ───────────────────────────────────────

class TestDownloadMenuSource:
    def _src(self):
        return (ROOT / "ui/widgets/launch_bar.py").read_text(encoding="utf-8")

    def test_unavailable_click_opens_menu_not_paths_dialog(self):
        src = self._src()
        tree = ast.parse(src)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "_launch")
        body = ast.get_source_segment(src, fn)
        assert "_show_unavailable_menu" in body

    def test_menu_offers_download_and_path(self):
        src = self._src()
        assert "_show_unavailable_menu" in src
        assert "_configure_path" in src
        assert "QDesktopServices.openUrl" in src
        assert "download_url" in src


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


class TestLaunchButtonQt:
    def _unavailable_app(self):
        from core.launcher import APPS
        # SDR Console won't be installed in CI → an unavailable button
        return next(a for a in APPS if a.key == "paths.sdrconsole")

    def test_button_builds_for_unavailable_app(self, app):
        from ui.widgets.launch_bar import LaunchButton
        btn = LaunchButton(self._unavailable_app(), _Cfg())
        assert btn._avail is False
        assert "SDR Console" in btn.text()
        assert hasattr(btn, "_show_unavailable_menu")
        assert hasattr(btn, "_configure_path")

    def test_sdr_launch_bar_includes_sdr_console(self, app):
        from ui.widgets.launch_bar import LaunchBar
        bar = LaunchBar("sdr", _Cfg())
        labels = [b.text() for b in bar._btns]
        assert any("SDR Console" in t for t in labels)
