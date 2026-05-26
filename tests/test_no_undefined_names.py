# Squelch QA gate — static undefined-name check (DevSecOps QA/QC)
# Licensed under GNU GPL v3
"""
Catches the #1 recurring bug class: a NameError from a missing import or a
'self.' that was dropped (e.g. _hold_tx_cb, _sep, _vsep). Runs pyflakes over
the source and fails if any 'undefined name' is reported. This gate must pass
before packaging.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PKGS = ["ui", "core", "modes", "network"]


def test_no_undefined_names():
    try:
        import pyflakes  # noqa
    except ImportError:
        import pytest
        pytest.skip("pyflakes not installed")
    targets = [str(ROOT / p) for p in PKGS if (ROOT / p).exists()]
    result = subprocess.run(
        [sys.executable, "-m", "pyflakes", *targets],
        capture_output=True, text=True)
    undefined = [ln for ln in result.stdout.splitlines()
                 if "undefined name" in ln]
    assert not undefined, (
        "Undefined names found (would crash at runtime):\n"
        + "\n".join(undefined))
