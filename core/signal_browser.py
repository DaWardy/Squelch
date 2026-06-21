# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/signal_browser.py

Pure (Qt-free) presenter for the Signal Browser (ROADMAP Phase 1, SIG-BROWSER).

The browser tab will be a thin QTableWidget that calls `SignalStore.search()`
and renders rows via `format_row()`. Keeping column layout, row formatting,
in-memory text filtering, and the summary line here means they are unit-tested
without PyQt6, and the eventual tab is a trivial shell.
"""

from core.signal_model import Signal
from core.freq_format import format_freq

# Display columns, in order. (header, fixed?) — the Qt tab maps these 1:1.
COLUMNS: list[str] = [
    "Last seen", "Freq", "Source", "Class", "Emitter",
    "SNR", "RSSI", "Count", "Decoded",
]


def format_freq_mhz(hz: int) -> str:
    """Frequency as MHz for display (reuses core.freq_format)."""
    try:
        return format_freq(int(hz or 0), "MHz")
    except Exception:
        return f"{(hz or 0) / 1e6:.6f} MHz"


def _short_time(iso: str) -> str:
    """'2026-06-21T14:32:00Z' → '06-21 14:32'. Pass through on odd input."""
    if not iso or "T" not in iso:
        return iso or ""
    date, _, rest = iso.partition("T")
    hhmm = rest[:5]
    md = date[5:] if len(date) >= 10 else date
    return f"{md} {hhmm}".strip()


def _num(v, fmt: str) -> str:
    """Format a measurement, blank when zero/unknown."""
    try:
        return format(v, fmt) if v else ""
    except Exception:
        return ""


def format_row(sig: Signal) -> list[str]:
    """One Signal → a list of display strings aligned to COLUMNS."""
    return [
        _short_time(sig.last_seen),
        format_freq_mhz(sig.freq_hz),
        sig.source or "",
        sig.classification or "",
        sig.emitter_id or "",
        _num(sig.snr_db, "+.0f") if sig.snr_db else "",
        _num(sig.rssi_dbm, ".0f"),
        str(sig.count or 1),
        (sig.decoded or "")[:80],
    ]


def text_match(sig: Signal, query: str) -> bool:
    """Case-insensitive substring match across the user-visible text fields.

    Empty query matches everything. Used for in-memory filtering on top of the
    store's DB-level `search()`.
    """
    q = (query or "").strip().lower()
    if not q:
        return True
    hay = " ".join((
        sig.emitter_id or "", sig.classification or "", sig.source or "",
        sig.decoded or "", sig.modulation or "", sig.tags or "",
        format_freq_mhz(sig.freq_hz),
    )).lower()
    return q in hay


def filter_signals(signals: list[Signal], query: str) -> list[Signal]:
    """Return signals matching the text query (in display order preserved)."""
    return [s for s in signals if text_match(s, query)]


def summarize(signals: list[Signal]) -> dict:
    """Stats line for the browser: totals, by-source counts, distinct emitters."""
    by_source: dict[str, int] = {}
    emitters: set[str] = set()
    for s in signals:
        if s.source:
            by_source[s.source] = by_source.get(s.source, 0) + 1
        if s.emitter_id:
            emitters.add(s.emitter_id)
    return {
        "total":            len(signals),
        "by_source":        dict(sorted(by_source.items(),
                                        key=lambda x: -x[1])),
        "distinct_emitters": len(emitters),
    }


def summary_line(signals: list[Signal]) -> str:
    """Human-readable one-liner, e.g. 'Signals: 42  ·  aprs 20, ft8 15, sdr 7  ·  emitters: 31'."""
    s = summarize(signals)
    src = ", ".join(f"{k} {v}" for k, v in s["by_source"].items()) or "—"
    return (f"Signals: {s['total']}  ·  {src}  ·  "
            f"emitters: {s['distinct_emitters']}")
