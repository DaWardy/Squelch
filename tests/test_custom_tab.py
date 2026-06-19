"""Tests for CustomLayoutTab — user-created split-panel tab."""
from __future__ import annotations
import sys
import ast
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest


def _src(rel: str) -> str:
    return (pathlib.Path(__file__).parent.parent / rel).read_text(encoding="utf-8")


# ── custom_tab.py source checks ───────────────────────────────────────────

class TestCustomTabSource:
    def test_file_exists(self):
        p = pathlib.Path(__file__).parent.parent / "ui" / "tabs" / "custom_tab.py"
        assert p.exists()

    def test_parses_cleanly(self):
        p = pathlib.Path(__file__).parent.parent / "ui" / "tabs" / "custom_tab.py"
        ast.parse(p.read_text(encoding="utf-8"))

    def test_custom_layout_tab_class(self):
        src = _src("ui/tabs/custom_tab.py")
        assert "class CustomLayoutTab" in src

    def test_panel_slot_frame_class(self):
        src = _src("ui/tabs/custom_tab.py")
        assert "_PanelSlotFrame" in src

    def test_unassign_signal(self):
        src = _src("ui/tabs/custom_tab.py")
        assert "panel_unassign_requested" in src

    def test_assign_unassign_methods(self):
        src = _src("ui/tabs/custom_tab.py")
        assert "def assign_panel(" in src
        assert "def unassign_panel(" in src

    def test_embed_release_methods(self):
        src = _src("ui/tabs/custom_tab.py")
        assert "def embed_panel(" in src
        assert "def release_panel(" in src

    def test_explicit_show_in_embed(self):
        src = _src("ui/tabs/custom_tab.py")
        embed_idx = src.find("def embed_panel(")
        next_def = src.find("\n    def ", embed_idx + 10)
        body = src[embed_idx:next_def]
        assert "panel.show()" in body

    def test_assigned_keys_property(self):
        src = _src("ui/tabs/custom_tab.py")
        assert "def assigned_keys" in src

    def test_save_restore_state(self):
        src = _src("ui/tabs/custom_tab.py")
        assert "def save_state(" in src
        assert "def restore_state(" in src

    def test_save_state_uses_assigned_not_slot(self):
        src = _src("ui/tabs/custom_tab.py")
        save_idx = src.find("def save_state(")
        next_def = src.find("\n    def ", save_idx + 10)
        body = src[save_idx:next_def]
        assert "assigned" in body
        assert "_slot_keys" not in body

    def test_no_hardcoded_dark_hex(self):
        src = _src("ui/tabs/custom_tab.py")
        for bad in ("#141414", "#0a0a0a", "#1a1a1a", "#111111"):
            assert bad not in src, f"hardcoded dark hex {bad} found"


# ── main_window.py wiring checks ──────────────────────────────────────────

class TestMainWindowCustomTabWiring:
    def test_add_custom_tab_method(self):
        src = _src("ui/main_window.py")
        assert "def _add_custom_tab(" in src

    def test_remove_custom_tab_method(self):
        src = _src("ui/main_window.py")
        assert "def _remove_custom_tab(" in src

    def test_assign_panel_method(self):
        src = _src("ui/main_window.py")
        assert "def _assign_panel_to_custom_tab(" in src

    def test_unassign_panel_method(self):
        src = _src("ui/main_window.py")
        assert "def _unassign_panel_from_custom_tab(" in src

    def test_on_tab_switched_handler(self):
        src = _src("ui/main_window.py")
        assert "def _on_tab_switched(" in src

    def test_auto_swap_connected_to_current_changed(self):
        src = _src("ui/main_window.py")
        assert "_on_tab_switched" in src
        assert "currentChanged.connect(self._on_tab_switched)" in src

    def test_restore_called_at_startup(self):
        src = _src("ui/main_window.py")
        assert "_restore_custom_tabs()" in src

    def test_save_called_on_close(self):
        src = _src("ui/main_window.py")
        close_idx = src.find("\n    def closeEvent(self, event):")
        body = src[close_idx:close_idx + 2000]
        assert "_save_custom_tabs_state()" in body

    def test_corner_widget_new_tab_button(self):
        src = _src("ui/main_window.py")
        assert "New Tab" in src
        assert "setCornerWidget" in src

    def test_context_menu_remove_and_rename(self):
        src = _src("ui/main_window.py")
        assert "_remove_custom_tab" in src
        assert "_rename_custom_tab" in src

    def test_insert_position_helper(self):
        # helper lives in ui/tab_utils.py; main_window imports it
        src = _src("ui/tab_utils.py")
        assert "def tab_insert_position(" in src

    def test_main_window_parses_cleanly(self):
        p = pathlib.Path(__file__).parent.parent / "ui" / "main_window.py"
        ast.parse(p.read_text(encoding="utf-8"))


# ── _tab_insert_position pure logic ───────────────────────────────────────

class TestTabInsertPosition:
    def _pos(self, key, existing_ids, tabs):
        """Simulate _tab_insert_position with a mock tab widget."""
        class _FakeWidget:
            def __init__(self, pid): self.panel_id = pid
        class _FakeTabs:
            def __init__(self, ids):
                self._ws = [_FakeWidget(i) for i in ids]
            def count(self): return len(self._ws)
            def widget(self, i): return self._ws[i]
        from ui.tab_utils import tab_insert_position
        return tab_insert_position(key, _FakeTabs(existing_ids), tabs)

    def test_insert_before_all(self):
        tabs = [("a", "", True), ("b", "", True), ("c", "", True)]
        assert self._pos("a", ["b", "c"], tabs) == 0

    def test_insert_after_first(self):
        tabs = [("a", "", True), ("b", "", True), ("c", "", True)]
        assert self._pos("b", ["a", "c"], tabs) == 1

    def test_insert_at_end(self):
        tabs = [("a", "", True), ("b", "", True), ("c", "", True)]
        assert self._pos("c", ["a", "b"], tabs) == 2

    def test_unknown_key_appends(self):
        tabs = [("a", "", True), ("b", "", True)]
        assert self._pos("z", ["a", "b"], tabs) == 2
