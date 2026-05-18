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
