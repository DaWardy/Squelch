"""Sprint 35 tests — telemetry removal, tab names, privacy article."""
from __future__ import annotations
import sys
import ast
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest


# ── Telemetry checkbox removed ────────────────────────────────────────────────

class TestNoTelemetryCheckbox:
    """Verify the dead _anon_telemetry checkbox has been removed."""

    def _adv_source(self) -> str:
        p = pathlib.Path(__file__).parent.parent / "ui" / "dialogs" / "settings_advanced_tab.py"
        return p.read_text(encoding="utf-8")

    def test_anon_telemetry_attribute_gone(self):
        assert "_anon_telemetry" not in self._adv_source()

    def test_crash_report_text_gone(self):
        assert "Send anonymous crash reports" not in self._adv_source()

    def test_privacy_section_still_present(self):
        assert "_share_spotting" in self._adv_source()

    def test_file_parses_cleanly(self):
        p = pathlib.Path(__file__).parent.parent / "ui" / "dialogs" / "settings_advanced_tab.py"
        ast.parse(p.read_text(encoding="utf-8"))


# ── Tab names and order ───────────────────────────────────────────────────────

def _tabs_constant() -> list[tuple[str, str, bool]]:
    """Load the TABS list from main_window.py via regex (no Qt import needed)."""
    import re
    src = (pathlib.Path(__file__).parent.parent / "ui" / "main_window.py"
           ).read_text(encoding="utf-8")
    rows = re.findall(
        r'^\s*\("(\w+)",\s*"([^"]+)",\s*(True|False)\)', src, re.MULTILINE)
    return [(key, label, visible == "True") for key, label, visible in rows]


class TestTabNames:
    def test_weak_signal_label(self):
        tabs = {k: lbl for k, lbl, _ in _tabs_constant()}
        assert "Weak Signal" in tabs["modes"]

    def test_voice_digital_label(self):
        tabs = {k: lbl for k, lbl, _ in _tabs_constant()}
        assert "Digital Voice" in tabs["digital"]

    def test_modes_not_bare_label(self):
        tabs = {k: lbl for k, lbl, _ in _tabs_constant()}
        assert tabs["modes"].strip().rstrip() != "Modes"

    def test_digital_not_bare_label(self):
        tabs = {k: lbl for k, lbl, _ in _tabs_constant()}
        assert "Digital Voice" in tabs["digital"]

    def test_rig_is_first(self):
        keys = [k for k, _, _ in _tabs_constant()]
        assert keys[0] == "rig"

    def test_sdr_before_weak_signal(self):
        keys = [k for k, _, _ in _tabs_constant()]
        assert keys.index("sdr") < keys.index("modes")

    def test_help_is_last(self):
        keys = [k for k, _, _ in _tabs_constant()]
        assert keys[-1] == "help"

    def test_rf_lab_hidden_by_default(self):
        tabs = {k: v for k, _, v in _tabs_constant()}
        assert tabs["rf_lab"] is False

    def test_core_tabs_present(self):
        # "signals" (SIG-BROWSER) added in Phase 1 — assert the core set is a
        # subset rather than pinning an exact count as new pillars land.
        keys = set(k for k, _, _ in _tabs_constant())
        expected = {"rig", "sdr", "modes", "digital", "winlink",
                    "log", "localrf", "map", "bandcond", "rf_lab", "help"}
        assert expected <= keys
        assert "signals" in keys


# ── Privacy & Crash Logs help article ────────────────────────────────────────

def _help_titles_cats() -> dict[str, str]:
    import re
    src = (pathlib.Path(__file__).parent.parent / "ui" / "tabs" / "help_tab.py"
           ).read_text(encoding="utf-8")
    return {t: c for t, c in re.findall(
        r'^\s*\("([^"]+)",\s*"([^"]+)"', src, re.MULTILINE)}


class TestPrivacyArticle:
    def test_article_exists(self):
        assert "Privacy & Crash Logs" in _help_titles_cats()

    def test_article_in_reference_category(self):
        assert _help_titles_cats().get("Privacy & Crash Logs") == "Reference"

    def test_article_mentions_log_path(self):
        src = (pathlib.Path(__file__).parent.parent / "ui" / "tabs" / "help_tab.py"
               ).read_text(encoding="utf-8")
        assert "logs/squelch.log" in src

    def test_article_says_no_crash_reports_sent(self):
        src = (pathlib.Path(__file__).parent.parent / "ui" / "tabs" / "help_tab.py"
               ).read_text(encoding="utf-8")
        assert "never" in src.lower() or "No." in src

    def test_article_mentions_network_activity(self):
        src = (pathlib.Path(__file__).parent.parent / "ui" / "tabs" / "help_tab.py"
               ).read_text(encoding="utf-8")
        assert "Network Activity" in src
