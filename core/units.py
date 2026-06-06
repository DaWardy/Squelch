# Squelch — core/units.py
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
from __future__ import annotations
"""
UI-wide unit handling (metric vs imperial).

A single source of truth so distances/speeds render consistently everywhere.
The preference lives in config under "ui.units" ("metric" or "imperial").
Internally Squelch always stores SI (km, meters); these helpers format for
display only.
"""

KM_PER_MILE = 1.609344
M_PER_FOOT  = 0.3048


def units_pref(cfg) -> str:
    """Return 'metric' or 'imperial' from config (default metric)."""
    try:
        u = (cfg.get("ui.units", "metric") or "metric").lower()
        return "imperial" if u.startswith("imp") else "metric"
    except Exception:
        return "metric"


def format_distance(km: float, cfg, decimals: int = 1) -> str:
    """Format a distance given in km for display, honoring the unit pref."""
    try:
        km = float(km)
    except (TypeError, ValueError):
        return "—"
    if units_pref(cfg) == "imperial":
        miles = km / KM_PER_MILE
        return f"{miles:.{decimals}f} mi"
    return f"{km:.{decimals}f} km"


def format_altitude(meters: float, cfg) -> str:
    """Format an altitude given in meters (e.g. satellite alt) for display."""
    try:
        meters = float(meters)
    except (TypeError, ValueError):
        return "—"
    if units_pref(cfg) == "imperial":
        feet = meters / M_PER_FOOT
        return f"{feet:,.0f} ft"
    return f"{meters:,.0f} m"


def distance_suffix(cfg) -> str:
    """Just the unit label, e.g. for a spinbox suffix."""
    return " mi" if units_pref(cfg) == "imperial" else " km"
