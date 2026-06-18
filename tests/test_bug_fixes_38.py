"""Sprint 38 bug-fix tests — BUG-04 sideview labels, BUG-10 workspace, BUG-11 lock label."""
from __future__ import annotations
import sys
import ast
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest


def _src(rel: str) -> str:
    return (pathlib.Path(__file__).parent.parent / rel).read_text(encoding="utf-8")


# ── BUG-10 — Entering workspace mode must hide the main window ────────────────

class TestWorkspaceModeHidesMainWindow:
    def test_hide_called_after_panel_shell_show(self):
        src = _src("ui/main_window.py")
        enter_idx = src.find("def _enter_workspace_mode(")
        # find next method boundary to bound the search
        next_def = src.find("\n    def ", enter_idx + 10)
        body = src[enter_idx: next_def if next_def > 0 else enter_idx + 1500]
        shell_show = body.find("_panel_shell.show()")
        hide_call  = body.find("self.hide()")
        assert shell_show >= 0, "_panel_shell.show() not found in _enter_workspace_mode"
        assert hide_call  >= 0, "self.hide() not found in _enter_workspace_mode"
        assert hide_call > shell_show, "self.hide() must come AFTER _panel_shell.show()"

    def test_exit_workspace_still_shows_main_window(self):
        src = _src("ui/main_window.py")
        exit_idx = src.find("def exit_workspace_mode(")
        next_def = src.find("\n    def ", exit_idx + 10)
        body = src[exit_idx: next_def if next_def > 0 else exit_idx + 800]
        assert "self.show()" in body

    def test_main_window_parses_cleanly(self):
        p = pathlib.Path(__file__).parent.parent / "ui" / "main_window.py"
        ast.parse(p.read_text(encoding="utf-8"))


# ── BUG-11 — Lock action label must clarify scope (tab order only) ────────────

class TestLockActionLabel:
    def test_lock_tooltip_mentions_tab_order(self):
        src = _src("ui/main_window.py")
        assert "tab bar order" in src.lower() or "tab order" in src.lower()

    def test_lock_tooltip_clarifies_not_section_order(self):
        src = _src("ui/main_window.py")
        assert "NOT affect section order" in src or "not affect section" in src.lower()

    def test_context_menu_uses_tab_order_label(self):
        src = _src("ui/main_window.py")
        assert "Lock tab order" in src or "Unlock tab order" in src


# ── BUG-04 — Propagation sideview label positions must not collide ────────────

class TestPropagationSideviewLabelPositions:
    def _sideview_src(self) -> str:
        return _src("ui/widgets/propagation_sideview.py")

    def test_f_layer_label_drawn_inside_band(self):
        src = self._sideview_src()
        # label_y must be computed from band centre, not f_top - 2
        assert "f_top - 2" not in src

    def test_f_layer_label_guarded_by_band_height(self):
        src = self._sideview_src()
        # should only draw if band is tall enough
        assert "band_h >= 12" in src or "band_h > " in src

    def test_signal_bar_labels_on_different_y(self):
        src = self._sideview_src()
        # EIRP text above bar (sig_y - 2) and Prx below (sig_y + 8)
        assert "sig_y - 2" in src
        assert "sig_y + 8" in src

    def test_sideview_parses_cleanly(self):
        p = pathlib.Path(__file__).parent.parent / "ui" / "widgets" / "propagation_sideview.py"
        ast.parse(p.read_text(encoding="utf-8"))
