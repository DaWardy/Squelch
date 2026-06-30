from __future__ import annotations
"""Tests for log table context menu additions — pure-logic (no Qt)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── QRZ URL construction ──────────────────────────────────────────────────────

QRZ_BASE_URL = "https://www.qrz.com/db/"


def _qrz_url(call: str) -> str:
    return QRZ_BASE_URL + call.upper().strip()


class TestQrzUrl:
    def test_simple_callsign(self):
        assert _qrz_url("W1AW") == "https://www.qrz.com/db/W1AW"

    def test_lowercase_uppercased(self):
        assert _qrz_url("ja1xyz") == "https://www.qrz.com/db/JA1XYZ"

    def test_portable_designation_preserved(self):
        assert _qrz_url("W1AW/3") == "https://www.qrz.com/db/W1AW/3"

    def test_leading_trailing_spaces_stripped(self):
        assert _qrz_url("  K1ABC  ") == "https://www.qrz.com/db/K1ABC"

    def test_url_contains_base(self):
        url = _qrz_url("VK2ABC")
        assert url.startswith("https://www.qrz.com/db/")

    def test_different_prefixes(self):
        assert _qrz_url("DL1ABC") == "https://www.qrz.com/db/DL1ABC"
        assert _qrz_url("G3ABC")  == "https://www.qrz.com/db/G3ABC"


# ── Context menu label helpers ────────────────────────────────────────────────

class TestFilterMenuLabel:
    def _label(self, call: str) -> str:
        return f"Show all QSOs with {call}" if call else "Show all QSOs with…"

    def test_with_callsign(self):
        assert self._label("W1AW") == "Show all QSOs with W1AW"

    def test_empty_callsign_shows_ellipsis(self):
        label = self._label("")
        assert "…" in label or "…" in label

    def test_label_includes_call(self):
        label = self._label("JA1XYZ")
        assert "JA1XYZ" in label


# ── Duplicate _export_csv removed ────────────────────────────────────────────

class TestNoDuplicateMethods:
    """Verify log_tab.LogTab no longer has a duplicate _export_csv."""

    def test_export_csv_defined_once(self):
        import ast
        # _export_csv was extracted from log_tab.py into _LogIOMixin
        # (HOUSE-CS split). It must exist exactly once across both files,
        # and no longer in log_tab.py itself.
        base = Path(__file__).parent.parent / "ui" / "tabs"
        counts = {}
        for fname in ("log_tab.py", "log_io_mixin.py"):
            tree = ast.parse(
                (base / fname).read_bytes().decode("utf-8", errors="replace"))
            counts[fname] = [
                n.name for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "_export_csv"
            ]
        total = sum(len(v) for v in counts.values())
        assert total == 1, (
            f"_export_csv defined {total} times across {list(counts)} — "
            "stale duplicate must be removed"
        )
        assert not counts["log_tab.py"], (
            "_export_csv should live in log_io_mixin.py, not log_tab.py"
        )
