# Squelch — core/sanitize.py
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Pure-Python sanitization and redaction helpers.
No GUI or network imports — safe to unit-test in isolation.

These implement security rules from docs/DESIGN_REVIEW.md:
  S4 — credentials never logged (redact_url)
  S6 — CSV/XLSX formula-injection prevention (csv_safe)
"""
from __future__ import annotations
import re

_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value) -> str:
    """Neutralize CSV/Excel formula injection (rule S6).

    A spreadsheet cell beginning with = + - @ (or tab/CR) can execute as a
    formula in Excel/LibreOffice. Ham log fields like callsign, name, and
    comment may contain attacker-influenced text (e.g. from an over-the-air
    exchange or imported ADIF), so any value starting with a trigger char is
    prefixed with a single quote to force text interpretation.
    """
    if value is None:
        return ""
    s = str(value)
    if s and s[0] in _FORMULA_TRIGGERS:
        return "'" + s
    return s


def redact_url(url: str) -> str:
    """Strip credentials from a URL before logging or display (rule S4).

    ARRL's LoTW API requires login and password in the query string; there is
    no token alternative. This MUST be applied anywhere such a URL could be
    logged, shown in an error dialog, or written to disk.
    """
    return re.sub(r"(login|password|pass|key|token)=[^&]*",
                  r"\1=***", url, flags=re.IGNORECASE)
