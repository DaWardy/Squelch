# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/sigid_db.py

Offline signal-identification lookup (the founding "identify probable signal
types, no cloud required" concept).

A `SigIdDatabase` matches an observed signal's fingerprint — frequency,
bandwidth, modulation — against a table of known signal descriptions and
returns ranked candidate identities. It ties together the frequency-allocation
classifier (core/signal_classify) and the modulation classifier
(core/modulation_classify): feed their outputs in, get human-readable "this is
probably X" candidates out.

LICENSING — important, by design:
  * The built-in table (`SigIdDatabase.builtin()`) contains ONLY original,
    factual reference data — public frequency allocations and well-known
    signal characteristics. Facts are not copyrightable; this ships freely.
  * Third-party catalogues (SigIDWiki — CC BY-SA; Artemis — CC BY-NC-SA) are
    NOT bundled or redistributed. The engine is data-source-agnostic:
    `import_entries()` / `from_json()` load a database the *user* supplies or
    downloads themselves, and each entry keeps a `source` + `url` for
    attribution. This keeps Squelch clear of the NonCommercial / redistribution
    terms those catalogues carry.

Pure Python, no Qt, never raises on sparse input.
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict

log = logging.getLogger(__name__)


# ── model ─────────────────────────────────────────────────────────────────────

@dataclass
class SigIdEntry:
    """One known-signal description. freq_lo=freq_hi=0 ⇒ a mode-only entry
    (matches on modulation regardless of frequency)."""
    name:         str
    freq_lo_hz:   int   = 0
    freq_hi_hz:   int   = 0
    bandwidth_hz: int   = 0
    modulation:   str   = ""
    category:     str   = ""
    description:  str   = ""
    source:       str   = "builtin"     # attribution: builtin/user/sigidwiki/artemis
    url:          str   = ""


@dataclass
class SigIdMatch:
    entry:   SigIdEntry
    score:   float
    reasons: list = field(default_factory=list)


# ── modulation family matching ────────────────────────────────────────────────

# Map many labels to a coarse family so "AFSK"/"MFSK"/"4FSK" all match "FSK".
_MOD_FAMILY = {
    "OOK": "OOK", "ASK": "OOK", "OOK/ASK": "OOK",
    "FSK": "FSK", "AFSK": "FSK", "MFSK": "FSK", "GFSK": "FSK", "4FSK": "FSK",
    "PSK": "PSK", "BPSK": "PSK", "QPSK": "PSK", "DPSK": "PSK", "DBPSK": "PSK",
    "AM": "AM", "SSB": "SSB", "USB": "SSB", "LSB": "SSB",
    "FM": "FM", "NFM": "FM", "WFM": "FM", "NBFM": "FM",
    "CW": "CW", "OFDM": "OFDM", "OFDM/DIGITAL": "OFDM", "CSS": "CSS",
}


def _family(mod: str) -> str:
    m = (mod or "").strip().upper()
    return _MOD_FAMILY.get(m, m)


def _mod_match(a: str, b: str) -> bool:
    return bool(a) and bool(b) and _family(a) == _family(b)


# ── database ──────────────────────────────────────────────────────────────────

class SigIdDatabase:
    """Ranked offline signal-identity lookup over a table of SigIdEntry."""

    def __init__(self, entries=None):
        self._entries: list = list(entries or [])

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def entries(self) -> list:
        return list(self._entries)

    def add(self, entry: SigIdEntry) -> None:
        self._entries.append(entry)

    def import_entries(self, dicts, source: str = "user") -> int:
        """Load user/third-party entries (list of dicts). Missing `source` is
        stamped with `source` for attribution. Returns how many were added."""
        n = 0
        for d in dicts or []:
            try:
                e = _entry_from_dict(d, default_source=source)
            except Exception:
                continue
            self._entries.append(e)
            n += 1
        return n

    @classmethod
    def from_json(cls, path, source: str = "user") -> "SigIdDatabase":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("signals") or data.get("entries") or []
        db = cls()
        db.import_entries(data, source=source)
        return db

    @classmethod
    def builtin(cls) -> "SigIdDatabase":
        """Original, factual reference table (public allocations / well-known
        signal traits). No third-party catalogue content."""
        return cls([SigIdEntry(*row) for row in _BUILTIN_ROWS])

    # ── lookup ────────────────────────────────────────────────────────────
    def identify(self, freq_hz: int = 0, bandwidth_hz: int = 0,
                 modulation: str = "", *, limit: int = 5,
                 freq_tol_hz: int = 5_000) -> list:
        """Rank candidate identities for an observed signal (best first)."""
        out = []
        for e in self._entries:
            score, reasons = _score(e, int(freq_hz or 0), int(bandwidth_hz or 0),
                                    modulation, freq_tol_hz)
            if score > 0:
                out.append(SigIdMatch(e, round(score, 3), reasons))
        out.sort(key=lambda m: m.score, reverse=True)
        return out[:limit]

    def best_match(self, freq_hz: int = 0, bandwidth_hz: int = 0,
                   modulation: str = "", **kw):
        hits = self.identify(freq_hz, bandwidth_hz, modulation, limit=1, **kw)
        return hits[0] if hits else None


def _score(e: SigIdEntry, freq_hz: int, bw: int, mod: str, tol: int):
    """(score, reasons). A frequency given but outside the entry's range is a
    hard exclusion (it is not that signal); everything else is additive."""
    score, reasons = 0.0, []
    has_freq = e.freq_lo_hz or e.freq_hi_hz
    if has_freq and freq_hz:
        lo = e.freq_lo_hz
        hi = e.freq_hi_hz or e.freq_lo_hz
        if lo - tol <= freq_hz <= hi + tol:
            in_core = lo <= freq_hz <= hi
            score += 0.55 if in_core else 0.35
            reasons.append("frequency")
        else:
            return 0.0, []
    if mod and e.modulation and _mod_match(mod, e.modulation):
        score += 0.3
        reasons.append("modulation")
    if bw and e.bandwidth_hz:
        ratio = min(bw, e.bandwidth_hz) / max(bw, e.bandwidth_hz)
        if ratio > 0.5:
            score += 0.15 * ratio
            reasons.append("bandwidth")
    return score, reasons


def _entry_from_dict(d: dict, default_source: str = "user") -> SigIdEntry:
    def _i(*keys):
        for k in keys:
            if d.get(k) is not None:
                return int(float(d[k]))
        return 0
    return SigIdEntry(
        name=str(d.get("name") or d.get("label") or "unknown"),
        freq_lo_hz=_i("freq_lo_hz", "freq_lo", "f_lo"),
        freq_hi_hz=_i("freq_hi_hz", "freq_hi", "f_hi"),
        bandwidth_hz=_i("bandwidth_hz", "bandwidth", "bw"),
        modulation=str(d.get("modulation") or d.get("mode") or ""),
        category=str(d.get("category") or ""),
        description=str(d.get("description") or d.get("desc") or ""),
        source=str(d.get("source") or default_source),
        url=str(d.get("url") or ""))


# ── built-in factual reference table ──────────────────────────────────────────
# (name, freq_lo, freq_hi, bandwidth, modulation, category, description, source, url)
# Public frequency allocations / well-known signal traits — original wording.
_BUILTIN_ROWS = [
    ("AM broadcast",       530_000,      1_710_000,    10_000,  "AM",  "Broadcast",
     "Medium-wave AM broadcast band", "builtin", ""),
    ("Shortwave broadcast",3_900_000,    26_100_000,   10_000,  "AM",  "Broadcast",
     "HF international AM broadcast", "builtin", ""),
    ("Aircraft VHF voice", 108_000_000,  137_000_000,  8_000,   "AM",  "Aviation",
     "VHF airband AM voice", "builtin", ""),
    ("FM broadcast",       88_000_000,   108_000_000,  200_000, "FM",  "Broadcast",
     "VHF wideband FM broadcast", "builtin", ""),
    ("NOAA weather radio", 162_400_000,  162_550_000,  16_000,  "FM",  "Weather",
     "VHF weather broadcast (WX1-WX7)", "builtin", ""),
    ("Marine VHF",         156_000_000,  162_025_000,  16_000,  "FM",  "Marine",
     "VHF marine FM voice", "builtin", ""),
    ("APRS",               144_390_000,  144_390_000,  12_000,  "AFSK","Amateur",
     "1200-baud AFSK packet position reporting", "builtin", ""),
    ("FRS / GMRS",         462_000_000,  468_000_000,  12_500,  "FM",  "PMR",
     "Licence-free / GMRS FM voice", "builtin", ""),
    ("DMR",                136_000_000,  480_000_000,  12_500,  "4FSK","Digital voice",
     "Two-slot TDMA 4FSK digital voice", "builtin", ""),
    ("ADS-B (Mode S)",     1_090_000_000,1_090_000_000,2_000_000,"PSK","Aviation",
     "1090 MHz extended squitter", "builtin", ""),
    ("LoRa",               902_000_000,  928_000_000,  125_000, "CSS", "ISM/IoT",
     "Chirp spread-spectrum IoT telemetry", "builtin", ""),
    ("POCSAG paging",      929_000_000,  932_000_000,  12_500,  "FSK", "Paging",
     "POCSAG pager FSK", "builtin", ""),
    ("Morse (CW)",         0,            0,            200,     "CW",  "Amateur",
     "On/off keyed continuous-wave Morse", "builtin", ""),
    ("RTTY",               0,            0,            300,     "FSK", "Data",
     "Radioteletype frequency-shift keying", "builtin", ""),
]
