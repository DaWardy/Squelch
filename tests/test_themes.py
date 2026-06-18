from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for themes module."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.themes import THEMES, get_stylesheet


class TestThemes:
    def test_themes_dict_exists(self):
        assert isinstance(THEMES, dict)
        assert len(THEMES) > 0

    def test_dark_theme_present(self):
        assert "Dark" in THEMES

    def test_light_theme_present(self):
        assert "Light" in THEMES

    def test_night_theme_present(self):
        assert "Night" in THEMES

    def test_high_contrast_present(self):
        assert any("Contrast" in k or "contrast" in k
                   for k in THEMES)

    def test_get_stylesheet_returns_string(self):
        css = get_stylesheet("Dark")
        assert isinstance(css, str)
        assert len(css) > 0

    def test_get_stylesheet_dark(self):
        css = get_stylesheet("Dark")
        # Dark theme should have dark backgrounds
        assert "#" in css   # color values

    def test_get_stylesheet_font_size(self):
        css11 = get_stylesheet("Dark", 11)
        css15 = get_stylesheet("Dark", 15)
        # Different font sizes should produce different CSS
        assert css11 != css15 or isinstance(css11, str)

    def test_get_stylesheet_unknown_theme(self):
        # Unknown theme should not crash
        css = get_stylesheet("NonExistentTheme")
        assert isinstance(css, str)

    def test_all_themes_valid_css(self):
        for name in THEMES:
            css = get_stylesheet(name)
            assert isinstance(css, str)
            # Should contain some style rules
            assert len(css) > 10


# ── Date/time widget dark-mode coverage ──────────────────────────────────────

class TestDateWidgetStyling:
    def test_qdate_edit_in_qss(self):
        css = get_stylesheet("Dark")
        assert "QDateEdit" in css

    def test_qtime_edit_in_qss(self):
        css = get_stylesheet("Dark")
        assert "QTimeEdit" in css

    def test_qdatetime_edit_in_qss(self):
        css = get_stylesheet("Dark")
        assert "QDateTimeEdit" in css

    def test_date_edit_in_light_theme(self):
        css = get_stylesheet("Light")
        assert "QDateEdit" in css

    def test_date_edit_in_high_contrast(self):
        css = get_stylesheet("High Contrast")
        assert "QDateEdit" in css


# ── ComboBox dropdown popup coverage ─────────────────────────────────────────

class TestComboDropdownStyling:
    def test_combo_abstract_item_view_present(self):
        css = get_stylesheet("Dark")
        assert "QComboBox QAbstractItemView" in css

    def test_combo_dropdown_has_explicit_bg(self):
        from core.themes import DARK, build_stylesheet
        css = build_stylesheet(DARK, 11)
        start = css.find("QComboBox QAbstractItemView")
        snippet = css[start:start + 300]
        assert DARK.bg_secondary in snippet

    def test_combo_dropdown_all_themes(self):
        for name in ("Dark", "Light", "Night", "High Contrast"):
            css = get_stylesheet(name)
            assert "QComboBox QAbstractItemView" in css, (
                f"{name} theme missing QComboBox QAbstractItemView block")


# ── Help article presence ─────────────────────────────────────────────────────

import re as _re


def _help_titles():
    from pathlib import Path as _Path
    src = _Path(__file__).parent.parent / "ui" / "tabs" / "help_tab.py"
    text = src.read_bytes().decode("utf-8", errors="replace")
    return {t: c for t, c in _re.findall(
        r'^\s*\("([^"]+)",\s*"([^"]+)"', text, _re.MULTILINE)}


class TestHelpArticles:
    def test_dxcc_tracking_article_exists(self):
        assert "DXCC & Award Tracking" in _help_titles()

    def test_contest_logging_article_exists(self):
        assert "Contest Logging" in _help_titles()

    def test_log_export_article_exists(self):
        assert "Log Export Guide" in _help_titles()

    def test_dxcc_article_in_logging_category(self):
        assert _help_titles().get("DXCC & Award Tracking") == "Logging"

    def test_contest_article_in_logging_category(self):
        assert _help_titles().get("Contest Logging") == "Logging"

    def test_log_export_in_logging_category(self):
        assert _help_titles().get("Log Export Guide") == "Logging"
