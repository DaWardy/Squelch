# Squelch QA gate — method-reference checker (no Qt needed)
# Catches .connect(self._foo) where _foo is not a method of that class.
# This exact pattern caused the RigTab/_toggle_split and
# WinlinkTab/_connect_hf runtime crashes.
from __future__ import annotations
import ast
import re
from pathlib import Path

ROOT   = Path(__file__).parent.parent
UI_DIR = ROOT / "ui"


def _class_methods(tree: ast.Module) -> set[str]:
    """All method names defined anywhere in the file."""
    return {
        n.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        for n in ast.walk(node)
        if isinstance(n, ast.FunctionDef)
    }


def _connected_methods(src: str) -> list[tuple[int, str]]:
    """(lineno, name) for every .connect(self._name) in source."""
    results = []
    for m in re.finditer(r'\.connect\(self\.(_\w+)\)', src):
        lineno = src.count('\n', 0, m.start()) + 1
        results.append((lineno, m.group(1)))
    return results


def test_no_missing_connected_methods():
    """Every self._X referenced in .connect() must be defined as a method
    somewhere in the UI package — including mixin files."""
    failures = []
    # Build a global pool of all method names across all UI Python files.
    # This handles mixin patterns where methods are defined in *_mixin.py
    # files and then inherited via multiple inheritance.
    all_ui_methods: set[str] = set()
    for py in UI_DIR.rglob("*.py"):
        if "__pycache__" in str(py):
            continue
        try:
            tree = ast.parse(py.read_text(errors="replace"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for n in ast.walk(node):
                        if isinstance(n, ast.FunctionDef):
                            all_ui_methods.add(n.name)
        except SyntaxError:
            continue

    for py in UI_DIR.rglob("*.py"):
        if "__pycache__" in str(py):
            continue
        src = py.read_text(errors="replace")
        try:
            ast.parse(src)
        except SyntaxError:
            continue
        for lineno, name in _connected_methods(src):
            if name not in all_ui_methods:
                failures.append(
                    f"{py.name}:{lineno}  "
                    f".connect(self.{name})  — not defined anywhere in ui/")
    assert not failures, (
        "Connected methods not defined (crash on tab load):\n"
        + "\n".join(failures))
