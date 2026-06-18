"""Sprint 37 bug-fix tests — BUG-07 font-size labels + BUG-08 paths dialog."""
from __future__ import annotations
import sys
import ast
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest


# ── BUG-07 — Settings dialogs must not hardcode font-size on hint labels ─────

def _src(rel: str) -> str:
    return (pathlib.Path(__file__).parent.parent / rel).read_text(encoding="utf-8")


class TestNoHardcodedFontSizeInSettingsHints:
    def test_appearance_tab_theme_note_no_font_size(self):
        src = _src("ui/dialogs/settings_appearance_tab.py")
        # theme_note and hint labels must not hardcode font-size
        lines = [l for l in src.splitlines()
                 if "theme_note" in l or ("hint" in l and "setStyleSheet" in l)]
        for line in lines:
            assert "font-size" not in line, (
                f"Hardcoded font-size found in appearance tab hint: {line!r}")

    def test_apis_tab_ha_note_no_font_size(self):
        src = _src("ui/dialogs/settings_apis_tab.py")
        # ha_note must not hardcode font-size
        lines = [l for l in src.splitlines()
                 if "ha_note" in l and "setStyleSheet" in l]
        for line in lines:
            assert "font-size" not in line, (
                f"Hardcoded font-size found in apis tab ha_note: {line!r}")

    def test_audio_status_label_no_font_size(self):
        src = _src("ui/dialogs/settings_audio_tab.py")
        lines = [l for l in src.splitlines()
                 if "_audio_status_lbl" in l and "setStyleSheet" in l]
        for line in lines:
            assert "font-size" not in line

    def test_settings_dialog_audio_restore_no_font_size(self):
        src = _src("ui/dialogs/settings_dialog.py")
        # _restore_audio_config_values sets _audio_status_lbl style
        in_block = False
        for line in src.splitlines():
            if "_restore_audio_config_values" in line:
                in_block = True
            if in_block and "_audio_status_lbl.setStyleSheet" in line:
                assert "font-size" not in line, (
                    f"font-size in _restore_audio_config_values: {line!r}")

    def test_appearance_tab_parses_cleanly(self):
        p = pathlib.Path(__file__).parent.parent / "ui" / "dialogs" / "settings_appearance_tab.py"
        ast.parse(p.read_text(encoding="utf-8"))

    def test_apis_tab_parses_cleanly(self):
        p = pathlib.Path(__file__).parent.parent / "ui" / "dialogs" / "settings_apis_tab.py"
        ast.parse(p.read_text(encoding="utf-8"))


# ── BUG-08 — Paths dialog: horizontal scroll + reasonable default size ────────

class TestPathsDialogLayout:
    def _paths_src(self) -> str:
        return _src("ui/dialogs/paths_dialog.py")

    def test_horizontal_scroll_enabled(self):
        src = self._paths_src()
        assert "ScrollBarAsNeeded" in src

    def test_horizontal_scrollbar_policy_set(self):
        src = self._paths_src()
        assert "setHorizontalScrollBarPolicy" in src

    def test_resize_called_with_larger_dimensions(self):
        import re
        src = self._paths_src()
        m = re.search(r'self\.resize\((\d+),\s*(\d+)\)', src)
        assert m is not None, "PathsDialog.resize() not found"
        w, h = int(m.group(1)), int(m.group(2))
        assert w >= 800, f"Default width {w} too small"
        assert h >= 600, f"Default height {h} too small"

    def test_paths_dialog_parses_cleanly(self):
        p = pathlib.Path(__file__).parent.parent / "ui" / "dialogs" / "paths_dialog.py"
        ast.parse(p.read_text(encoding="utf-8"))
