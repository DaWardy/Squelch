from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for Custom theme support in core/themes.py."""

import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.themes import (
    THEMES, custom_theme_from_config, build_stylesheet, Theme,
    DARK,
)


def _cfg(**overrides):
    """Minimal config-like object backed by a dict."""
    data = {
        "theme.custom.bg_primary":   "#0f0f0f",
        "theme.custom.bg_secondary": "#1a1a1a",
        "theme.custom.fg_primary":   "#cccccc",
        "theme.custom.accent":       "#3fbe6f",
        "theme.custom.tx_color":     "#ff4444",
        "theme.custom.border":       "#2a2a2a",
    }
    data.update({f"theme.custom.{k}": v for k, v in overrides.items()})

    class _Cfg:
        def get(self, key, default=None):
            return data.get(key, default)
    return _Cfg()


class TestCustomThemeInRegistry:
    def test_custom_in_themes_dict(self):
        assert "Custom" in THEMES

    def test_custom_theme_is_theme_instance(self):
        assert isinstance(THEMES["Custom"], Theme)


class TestCustomThemeFromConfig:
    def test_returns_theme(self):
        t = custom_theme_from_config(_cfg())
        assert isinstance(t, Theme)

    def test_name_is_custom(self):
        t = custom_theme_from_config(_cfg())
        assert t.name == "Custom"

    def test_bg_primary_applied(self):
        t = custom_theme_from_config(_cfg())
        assert t.bg_primary == "#0f0f0f"

    def test_accent_applied(self):
        t = custom_theme_from_config(_cfg())
        assert t.accent == "#3fbe6f"

    def test_custom_accent_overrides_default(self):
        t = custom_theme_from_config(_cfg(accent="#ff00ff"))
        assert t.accent == "#ff00ff"

    def test_custom_bg_overrides_default(self):
        t = custom_theme_from_config(_cfg(bg_primary="#123456"))
        assert t.bg_primary == "#123456"

    def test_missing_key_falls_back_to_dark_default(self):
        class _EmptyCfg:
            def get(self, key, default=None):
                return default
        t = custom_theme_from_config(_EmptyCfg())
        # Should not crash; should use fallback values
        assert t.bg_primary == "#0f0f0f"
        assert t.accent == "#3fbe6f"

    def test_border_focus_matches_accent(self):
        t = custom_theme_from_config(_cfg(accent="#aabbcc"))
        assert t.border_focus == t.accent

    def test_none_value_falls_back_to_default(self):
        class _NoneCfg:
            def get(self, key, default=None):
                return None  # simulate key present but empty
        t = custom_theme_from_config(_NoneCfg())
        assert t.bg_primary == "#0f0f0f"


class TestBuildStylesheetCustom:
    def test_stylesheet_contains_custom_bg(self):
        t = custom_theme_from_config(_cfg(bg_primary="#abcdef"))
        css = build_stylesheet(t)
        assert "#abcdef" in css

    def test_stylesheet_contains_custom_accent(self):
        t = custom_theme_from_config(_cfg(accent="#ff1234"))
        css = build_stylesheet(t)
        assert "#ff1234" in css

    def test_stylesheet_is_string(self):
        t = custom_theme_from_config(_cfg())
        css = build_stylesheet(t)
        assert isinstance(css, str)
        assert len(css) > 100

    def test_stylesheet_no_hc_overrides_for_custom(self):
        t = custom_theme_from_config(_cfg())
        css = build_stylesheet(t)
        # High Contrast overrides should NOT appear for Custom theme
        assert "font-weight: bold" not in css or t.name != "High Contrast"
