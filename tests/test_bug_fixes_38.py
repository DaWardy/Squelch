"""Sprint 38 bug-fix tests — BUG-04 sideview labels, BUG-11 lock label; tab presets."""
from __future__ import annotations
import sys
import ast
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest


def _src(rel: str) -> str:
    return (pathlib.Path(__file__).parent.parent / rel).read_text(encoding="utf-8")


def _src_mw() -> str:
    """main_window.py + its menu mixin — the menu bar (View menu, tab presets,
    lock action, save-layout) was extracted to main_window_menu.py (HOUSE-CS)."""
    return _src("ui/main_window.py") + "\n" + _src("ui/main_window_menu.py")


# ── Tab presets — workspace mode removed; presets now native to tab UI ────────

class TestTabPresets:
    def test_tab_presets_dict_defined(self):
        src = _src("ui/main_window.py")
        assert "TAB_PRESETS" in src

    def test_hf_ops_preset_defined(self):
        src = _src("ui/main_window.py")
        assert "HF Ops" in src

    def test_apply_tab_preset_method_exists(self):
        src = _src_mw()
        assert "def _apply_tab_preset(" in src

    def test_save_tab_layout_method_exists(self):
        src = _src_mw()
        assert "def _save_tab_layout(" in src

    def test_no_workspace_mode_entry_point(self):
        src = _src("ui/main_window.py")
        assert "_enter_workspace_mode" not in src
        assert "exit_workspace_mode" not in src

    def test_main_window_parses_cleanly(self):
        p = pathlib.Path(__file__).parent.parent / "ui" / "main_window.py"
        ast.parse(p.read_text(encoding="utf-8"))


# ── BUG-11 — Lock action label must clarify scope (tab order only) ────────────

class TestLockActionLabel:
    def test_lock_tooltip_mentions_tab_order(self):
        src = _src_mw()
        assert "tab bar order" in src.lower() or "tab order" in src.lower()

    def test_lock_tooltip_clarifies_not_section_order(self):
        src = _src_mw()
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
        # Redesigned: layers use h_px height guard before drawing label
        assert "h_px" in src or "band_h" in src or "h_px >= " in src

    def test_signal_bar_labels_on_different_y(self):
        src = self._sideview_src()
        # Redesigned: signal meter has separate bar_y and text lines
        assert "bar_y" in src
        assert "_draw_signal_meter" in src

    def test_sideview_parses_cleanly(self):
        p = pathlib.Path(__file__).parent.parent / "ui" / "widgets" / "propagation_sideview.py"
        ast.parse(p.read_text(encoding="utf-8"))
