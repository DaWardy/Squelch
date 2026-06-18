"""Sprint 36 bug-fix tests — BUG-05 (audio status label) and BUG-06 (spinbox typing)."""
from __future__ import annotations
import sys
import ast
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest


# ── BUG-06 — QSO goal spinbox must remain editable ───────────────────────────

class TestSpinBoxEditable:
    def _station_src(self) -> str:
        p = pathlib.Path(__file__).parent.parent / "ui" / "dialogs" / "settings_station_tab.py"
        return p.read_text(encoding="utf-8")

    def test_lineedit_readonly_false_called(self):
        src = self._station_src()
        assert "lineEdit().setReadOnly(False)" in src

    def test_special_value_text_still_present(self):
        src = self._station_src()
        assert "setSpecialValueText" in src

    def test_daily_goal_spinbox_present(self):
        src = self._station_src()
        assert "_daily_goal" in src

    def test_file_parses_cleanly(self):
        p = pathlib.Path(__file__).parent.parent / "ui" / "dialogs" / "settings_station_tab.py"
        ast.parse(p.read_text(encoding="utf-8"))


# ── BUG-05 — Audio tab must surface status info to user ──────────────────────

class TestAudioStatusLabel:
    def _audio_tab_src(self) -> str:
        p = pathlib.Path(__file__).parent.parent / "ui" / "dialogs" / "settings_audio_tab.py"
        return p.read_text(encoding="utf-8")

    def _dialog_src(self) -> str:
        p = pathlib.Path(__file__).parent.parent / "ui" / "dialogs" / "settings_dialog.py"
        return p.read_text(encoding="utf-8")

    def test_status_label_widget_in_tab(self):
        assert "_audio_status_lbl" in self._audio_tab_src()

    def test_status_label_has_wordwrap(self):
        assert "setWordWrap(True)" in self._audio_tab_src()

    def test_dialog_updates_status_label_on_no_sounddevice(self):
        src = self._dialog_src()
        assert "sounddevice not installed" in src

    def test_dialog_updates_status_label_on_success(self):
        src = self._dialog_src()
        assert "input device" in src.lower()

    def test_audio_tab_parses_cleanly(self):
        p = pathlib.Path(__file__).parent.parent / "ui" / "dialogs" / "settings_audio_tab.py"
        ast.parse(p.read_text(encoding="utf-8"))

    def test_dialog_parses_cleanly(self):
        p = pathlib.Path(__file__).parent.parent / "ui" / "dialogs" / "settings_dialog.py"
        ast.parse(p.read_text(encoding="utf-8"))
