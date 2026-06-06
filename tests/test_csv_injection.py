# Squelch tests — CSV formula-injection sanitizer (security rule S6)
# Licensed under GNU GPL v3
from __future__ import annotations
"""Verify CSV export sanitizes formula-injection vectors."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_csv_safe_prefixes_formula_chars():
    from core.sanitize import csv_safe as _csv_safe
    # Each dangerous leading char must be neutralized
    for bad in ("=cmd", "+1+1", "-2+3", "@SUM(A1)"):
        out = _csv_safe(bad)
        assert out.startswith("'"), f"{bad!r} not sanitized"

def test_csv_safe_passes_normal_values():
    from core.sanitize import csv_safe as _csv_safe
    for ok in ("W1AW", "FT8", "14.074000", "Hiram Percy Maxim"):
        assert _csv_safe(ok) == ok

def test_csv_safe_handles_none_and_numbers():
    from core.sanitize import csv_safe as _csv_safe
    assert _csv_safe(None) == ""
    assert _csv_safe(599) == "599"

def test_redact_url_strips_lotw_credentials():
    from core.sanitize import redact_url as _redact_url
    url = ("https://lotw.arrl.org/lotwuser/lotwreport.adi"
           "?login=W1AW&password=secret123&qso_query=1")
    red = _redact_url(url)
    assert "secret123" not in red
    assert "W1AW" not in red
    assert "***" in red
