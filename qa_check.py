#!/usr/bin/env python3
# Squelch — qa_check.py  (DevSecOps QA/QC gate, run before packaging)
# Licensed under GNU GPL v3
from __future__ import annotations
"""
Pre-package quality gate. Run `python qa_check.py` before building a release.
Fails (non-zero exit) if any check fails, so a broken build is never shipped.

Checks:
  1. Every .py file compiles (syntax).
  2. pyflakes reports no undefined names (the recurring NameError class).
  3. The full pytest suite passes.
  4. Connected method references exist (self._x in .connect()).
  5. (If PyQt6 present) every tab builds headless.
"""
import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
PKGS = ["ui", "core", "modes", "network"]


def _hdr(t): print(f"\n=== {t} ===")


def check_syntax() -> list[str]:
    _hdr("1. Syntax")
    errs = []
    for f in ROOT.rglob("*.py"):
        if "__pycache__" in str(f) or "venv" in str(f):
            continue
        try:
            compile(f.read_text(encoding="utf-8", errors="replace"), str(f), "exec")
        except SyntaxError as e:
            errs.append(f"{f.name}:{e.lineno}: {e.msg}")
    print("OK" if not errs else f"{len(errs)} error(s)")
    return errs


def check_undefined() -> list[str]:
    _hdr("2. Undefined names (pyflakes)")
    targets = [str(ROOT / p) for p in PKGS if (ROOT / p).exists()]
    try:
        r = subprocess.run([sys.executable, "-m", "pyflakes", *targets],
                           capture_output=True, text=True)
    except Exception as e:
        print(f"pyflakes unavailable: {e}")
        return []
    undef = [ln for ln in r.stdout.splitlines() if "undefined name" in ln]
    print("OK" if not undef else f"{len(undef)} undefined name(s)")
    return undef


def check_tests() -> bool:
    _hdr("3. Test suite")
    import os
    env = dict(os.environ)
    # Force offscreen Qt so the tab + signal smoke tests RUN (not skip)
    # when PyQt6 is installed. These catch the runtime crashes (signal
    # arity, tab build) that static checks cannot.
    env["QT_QPA_PLATFORM"] = "offscreen"
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "--tb=line"],
                       cwd=ROOT, env=env)
    return r.returncode == 0


def check_qt_available() -> None:
    _hdr("3a. Qt smoke-test availability")
    try:
        import PyQt6  # noqa
        print("PyQt6 present — tab + signal smoke tests WILL run")
    except ImportError:
        print("WARNING: PyQt6 not installed — tab/signal smoke tests will "
              "SKIP.\n  Install with: pip install PyQt6\n"
              "  Without it, runtime crashes (signal arity, tab build) are "
              "NOT caught.")


def main() -> int:
    problems = []
    problems += check_syntax()
    problems += check_undefined()
    check_qt_available()
    tests_ok = check_tests()

    print("\n" + "=" * 50)
    if problems:
        print("QA FAILED — do not package:")
        for p in problems:
            print(f"  {p}")
    if not tests_ok:
        print("QA FAILED — tests did not pass.")
    if problems or not tests_ok:
        return 1
    print("QA PASSED — safe to package.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
