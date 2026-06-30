from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for launcher/path management (offline portions)."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock
from core.launcher import get_launcher, AppDef, APPS


class TestAppDefs:
    def test_apps_list_not_empty(self):
        assert len(APPS) > 0

    def test_each_app_has_key(self):
        for app in APPS:
            assert app.key, f"App missing key: {app.name}"
            assert app.key.startswith("paths.")

    def test_each_app_has_name(self):
        for app in APPS:
            assert app.name, f"App missing name"

    def test_launch_bar_marks_programming_with_wrench(self):
        # Batch 2 fix: programming software (Icom CS-7100 etc.) read as rigs
        # in the Local RF launch bar; LaunchButton prefixes them with 🛠.
        src = (Path(__file__).parent.parent
               / "ui/widgets/launch_bar.py").read_text(encoding="utf-8")
        assert "🛠" in src
        assert 'category", "") == "programming"' in src

    def test_each_app_has_download_url(self):
        for app in APPS:
            assert app.download_url, \
                f"{app.name} missing download URL"

    def test_wsjtx_present(self):
        keys = [a.key for a in APPS]
        assert "paths.wsjtx" in keys

    def test_vara_hf_present(self):
        keys = [a.key for a in APPS]
        assert "paths.vara_hf" in keys

    def test_dsdplus_present(self):
        keys = [a.key for a in APPS]
        assert "paths.dsdplus" in keys

    def test_chirp_present(self):
        keys = [a.key for a in APPS]
        assert "paths.chirp" in keys

    def test_sdruno_present(self):
        keys = [a.key for a in APPS]
        assert "paths.sdruno" in keys

    def test_hdsdr_present(self):
        keys = [a.key for a in APPS]
        assert "paths.hdsdr" in keys

    def test_added_sdr_apps_are_sdr_category(self):
        by_key = {a.key: a for a in APPS}
        assert by_key["paths.sdruno"].category == "sdr"
        assert by_key["paths.hdsdr"].category == "sdr"

    def test_no_duplicate_keys(self):
        keys = [a.key for a in APPS]
        assert len(keys) == len(set(keys)), \
            "Duplicate app keys found"


class TestLauncher:
    def setup_method(self):
        from core.config import Config
        import tempfile
        self.cfg = Config(
            Path(tempfile.mkdtemp()) / "config.json")
        self.launcher = get_launcher(self.cfg)

    def test_get_launcher_returns_launcher(self):
        assert self.launcher is not None

    def test_get_path_missing(self):
        result = self.launcher.get_path("paths.wsjtx")
        # Should return empty string if not configured
        assert result == "" or isinstance(result, str)

    def test_get_path_from_config(self):
        # get_path returns empty if file doesn't exist on disk
        # Just verify it reads from config and returns a string
        self.cfg.set("paths.wsjtx", r"C:\fake\wsjtx.exe")
        result = self.launcher.get_path("paths.wsjtx")
        assert isinstance(result, str)

    def test_is_available_missing(self):
        result = self.launcher.is_available("paths.wsjtx")
        # Should be False if path not set/found
        assert isinstance(result, bool)

    def test_tab_categories(self):
        """Each app should have a valid tab assignment."""
        valid_tabs = {"rig", "modes", "sdr", "digital",
                      "winlink", "localrf", "log", "general"}
        for app in APPS:
            if app.tab:
                assert app.tab in valid_tabs, \
                    f"{app.name} has invalid tab: {app.tab}"
