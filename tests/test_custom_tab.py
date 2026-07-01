"""Tests for CustomLayoutTab — redesigned coexistence card approach.

Sprint 41: panels are NEVER reparented.  The custom tab shows navigation
cards — clicking 'Open tab' navigates to the original panel, which remains
fully functional in its own tab slot at all times.
"""
from __future__ import annotations
import sys
import ast
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest


def _src(rel: str) -> str:
    return (pathlib.Path(__file__).parent.parent / rel).read_text(encoding="utf-8")


def _src_ct() -> str:
    """main_window.py + its custom-tabs mixin — the add/remove/rename/assign/
    navigate methods were extracted to main_window_customtabs.py (HOUSE-CS)."""
    return _src("ui/main_window.py") + "\n" + _src("ui/main_window_customtabs.py")


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

    def test_panel_card_class(self):
        src = _src("ui/tabs/custom_tab.py")
        assert "_PanelCard" in src

    def test_no_reparenting_methods(self):
        src = _src("ui/tabs/custom_tab.py")
        assert "def embed_panel(" not in src, \
            "embed_panel must not exist — panels are never reparented"
        assert "def release_panel(" not in src, \
            "release_panel must not exist — panels are never reparented"

    def test_unassign_signal(self):
        src = _src("ui/tabs/custom_tab.py")
        assert "panel_unassign_requested" in src

    def test_navigate_signal(self):
        src = _src("ui/tabs/custom_tab.py")
        assert "panel_navigate_requested" in src

    def test_assign_unassign_methods(self):
        src = _src("ui/tabs/custom_tab.py")
        assert "def assign_panel(" in src
        assert "def unassign_panel(" in src

    def test_assigned_keys_property(self):
        src = _src("ui/tabs/custom_tab.py")
        assert "def assigned_keys" in src

    def test_save_restore_state(self):
        src = _src("ui/tabs/custom_tab.py")
        assert "def save_state(" in src
        assert "def restore_state(" in src

    def test_save_state_uses_assigned(self):
        src = _src("ui/tabs/custom_tab.py")
        save_idx = src.find("def save_state(")
        next_def = src.find("\n    def ", save_idx + 10)
        body = src[save_idx:next_def]
        assert "assigned" in body

    def test_no_hardcoded_dark_hex(self):
        src = _src("ui/tabs/custom_tab.py")
        for bad in ("#141414", "#0a0a0a", "#1a1a1a", "#111111"):
            assert bad not in src, f"hardcoded dark hex {bad} found"

    def test_unlock_rearrange_button(self):
        src = _src("ui/tabs/custom_tab.py")
        assert "_unlock_btn" in src, \
            "Rearrange/unlock button must be present in toolbar"

    def test_lock_toggle_labels(self):
        # The toolbar toggle now locks/unlocks the widget windows (freeze
        # move + resize) with clear, non-inverted action labels — the button
        # shows what a click will do.
        src = _src("ui/tabs/custom_tab.py")
        assert "Lock windows" in src
        assert "Unlock windows" in src
        # set_locked drives the per-window freeze.
        assert "def set_locked(" in src


# ── main_window.py wiring checks ──────────────────────────────────────────

class TestMainWindowCustomTabWiring:
    def test_add_custom_tab_method(self):
        src = _src_ct()
        assert "def _add_custom_tab(" in src

    def test_remove_custom_tab_method(self):
        src = _src_ct()
        assert "def _remove_custom_tab(" in src

    def test_assign_panel_method(self):
        src = _src_ct()
        assert "def _assign_panel_to_custom_tab(" in src

    def test_unassign_panel_method(self):
        src = _src_ct()
        assert "def _unassign_panel_from_custom_tab(" in src

    def test_no_borrowed_panels_infrastructure(self):
        src = _src("ui/main_window.py")
        assert "_borrowed_panels: dict" not in src, \
            "_borrowed_panels must be removed (no reparenting)"
        assert "def _do_embed_panel(" not in src, \
            "_do_embed_panel must be removed (no reparenting)"
        assert "def _do_release_panel(" not in src, \
            "_do_release_panel must be removed (no reparenting)"

    def test_navigate_to_panel_wired(self):
        src = _src_ct()
        assert "def _navigate_to_panel(" in src

    def test_panel_navigate_signal_connected(self):
        src = _src_ct()
        assert "panel_navigate_requested.connect" in src

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


# ── Pure-logic tests: assign / unassign / reorder ─────────────────────────

_HAS_QT = False
try:
    import PyQt6  # noqa: F401
    _HAS_QT = True
except ImportError:
    pass

_needs_qt = pytest.mark.skipif(not _HAS_QT, reason="PyQt6 not installed")


class _FakeCfg:
    def get(self, key, default=None):
        return default


@_needs_qt
class TestCustomTabLogic:

    def _make(self, *keys):
        from ui.tabs.custom_tab import CustomLayoutTab
        ct = CustomLayoutTab("_t1", "My Tab", _FakeCfg())
        for key in keys:
            ct.assign_panel(key, key.title())
        return ct

    def test_assign_adds_key(self):
        ct = self._make("rig")
        assert "rig" in ct.assigned_keys

    def test_assign_idempotent(self):
        ct = self._make("rig", "rig")
        assert ct.assigned_keys.count("rig") == 1

    def test_unassign_removes_key(self):
        ct = self._make("rig", "log")
        ct.unassign_panel("rig")
        assert "rig" not in ct.assigned_keys
        assert "log" in ct.assigned_keys

    def test_save_state_round_trip(self):
        ct = self._make("rig", "log", "map")
        state = ct.save_state()
        assert state["assigned"] == ["rig", "log", "map"]
        assert state["title"] == "My Tab"

    def test_restore_state_populates_keys(self):
        from ui.tabs.custom_tab import CustomLayoutTab
        ct = CustomLayoutTab("_t2", "T", _FakeCfg())
        ct.restore_state({"title": "T", "assigned": ["sdr", "map"]})
        assert "sdr" in ct.assigned_keys
        assert "map" in ct.assigned_keys

    def test_move_right_shifts_key(self):
        ct = self._make("rig", "log", "map")
        ct._on_move_right("rig")
        assert ct.assigned_keys == ["log", "rig", "map"]

    def test_move_left_shifts_key(self):
        ct = self._make("rig", "log", "map")
        ct._on_move_left("map")
        assert ct.assigned_keys == ["rig", "map", "log"]

    def test_move_left_at_boundary_no_change(self):
        ct = self._make("rig", "log")
        ct._on_move_left("rig")
        assert ct.assigned_keys[0] == "rig"

    def test_move_right_at_boundary_no_change(self):
        ct = self._make("rig", "log")
        ct._on_move_right("log")
        assert ct.assigned_keys[-1] == "log"
