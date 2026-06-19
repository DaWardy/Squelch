"""HOUSE-02 — QSS widget coverage regression test.

Ensures that any date/time/spinbox widget type introduced in a _Settings*Tab
file has a corresponding selector in core/themes.py.  Prevents BUG-01/BUG-02
class regressions (white date pickers, invisible dropdown text in dark mode).
"""
from __future__ import annotations
import re
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent

# Widget types that MUST have a QSS selector in themes.py when they appear
# in any _Settings*Tab source file.
_REQUIRE_QSS = {
    "QDateEdit",
    "QTimeEdit",
    "QDateTimeEdit",
    "QSpinBox",
    "QDoubleSpinBox",
    "QSlider",
    "QProgressBar",
    "QComboBox",
    "QCheckBox",
    "QLineEdit",
}


def _settings_tab_files():
    return sorted((ROOT / "ui" / "dialogs").glob("settings_*tab.py"))


def _themes_src() -> str:
    return (ROOT / "core" / "themes.py").read_text(encoding="utf-8")


def _widget_types_in_file(path: pathlib.Path) -> set:
    src = path.read_text(encoding="utf-8")
    return set(re.findall(r'\b(Q\w+)\b', src)) & _REQUIRE_QSS


def _qss_selectors_in_themes(themes_src: str) -> set:
    return set(re.findall(r'\b(Q\w+)\b', themes_src))


class TestSettingsQSSCoverage:
    """Every widget type in _REQUIRE_QSS that appears in a settings tab
    must have a matching selector in core/themes.py."""

    def test_no_uncovered_widget_types(self):
        themes_src = _themes_src()
        qss_selectors = _qss_selectors_in_themes(themes_src)
        missing = []
        for f in _settings_tab_files():
            used = _widget_types_in_file(f)
            uncovered = used - qss_selectors
            for w in sorted(uncovered):
                missing.append(f"{f.name}: {w} has no QSS selector in themes.py")
        assert not missing, "\n".join(missing)

    def test_qdateedit_covered(self):
        themes_src = _themes_src()
        assert "QDateEdit" in themes_src, \
            "QDateEdit must have a QSS selector in themes.py (BUG-01 regression)"

    def test_qdatetimeedit_covered(self):
        themes_src = _themes_src()
        assert "QDateTimeEdit" in themes_src, \
            "QDateTimeEdit must have a QSS selector in themes.py (BUG-01 regression)"

    def test_qtimeedit_covered(self):
        themes_src = _themes_src()
        assert "QTimeEdit" in themes_src, \
            "QTimeEdit must have a QSS selector in themes.py (BUG-01 regression)"

    def test_qcombobox_dropdown_covered(self):
        themes_src = _themes_src()
        assert "QAbstractItemView" in themes_src, \
            "QAbstractItemView must be in themes.py (BUG-02: invisible dropdown items)"

    def test_settings_tab_files_found(self):
        files = _settings_tab_files()
        assert len(files) >= 6, f"Expected at least 6 settings tab files, found {len(files)}"

    def test_require_qss_list_non_empty(self):
        assert len(_REQUIRE_QSS) >= 8


class TestNoHardcodedDarkHexInSettingsTabs:
    """Settings tab files must not introduce new hardcoded dark hex colors."""

    BANNED = {"#141414", "#0a0a0a", "#1a1a1a", "#111111", "#0d0d0d", "#080808"}

    def _check_file(self, path: pathlib.Path) -> list[str]:
        lines = path.read_text(encoding="utf-8").splitlines()
        hits = []
        for bad in self.BANNED:
            for line in lines:
                stripped = line.strip()
                # Skip comment lines and color-data tuples (e.g. _CUSTOM_COLORS entries).
                # Those are legitimate default values, not hardcoded display styles.
                if stripped.startswith("#") or (stripped.startswith("(") and "setStyleSheet" not in stripped):
                    continue
                if bad in line:
                    hits.append(f"{path.name}: contains {bad!r} in stylesheet context")
                    break
        return hits

    def test_no_banned_hex_in_settings_tabs(self):
        violations = []
        for f in _settings_tab_files():
            violations.extend(self._check_file(f))
        assert not violations, "\n".join(violations)
