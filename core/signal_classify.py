# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/signal_classify.py

Allocation-based signal classification (ROADMAP Phase 2, ID-CLASSIFY).

Given a frequency (and optional bandwidth), guess *what* a signal likely is by
matching it against data the app already ships:

  1. Known fixed frequencies (RF Lab table) — NOAA WX, aviation guard, marine
     Ch.16, ISS, … → a specific label.
  2. Amateur band segments (core.band_plan) → e.g. "20m DIGITAL", with the
     suggested mode.
  3. Service bands (CB / FRS / GMRS / MURS / ISM) → the band name.

This is the "known-allocation" half of IDENTIFY; it complements the
SigID-wiki DB matching (network/signal_id) and the future modulation
classifier. Pure and unit-tested. `apply_classification()` enriches a Signal
in place when its classification is still generic.
"""

import logging
from dataclasses import dataclass

from core.band_plan import (
    band_at_freq, segment_at_freq, suggested_mode, SERVICE_BANDS,
)

log = logging.getLogger(__name__)

# RF Lab category → a reasonable default modulation for known fixed channels.
_CATEGORY_MOD = {
    "Weather":   "FM",
    "Aviation":  "AM",
    "Marine":    "FM",
    "EMS":       "FM",
    "Space":     "FM",
    "Broadcast": "WFM",
}

# Non-amateur service-band category → default modulation.
_SERVICE_MOD = {
    "CB":             "AM",
    "FRS/GMRS":       "FM",
    "MURS":           "FM",
    "ISM/Unlicensed": "",
}

# Broadcast / airband / utility ranges not in band_plan (checked after
# specific fixed channels and before amateur-band lookup).
# (freq_lo, freq_hi, label, category, modulation)
_BROADCAST_RANGES = [
    (148_000,    530_000,   "LF / MF utilities",   "Utility",    "AM"),
    (530_000,  1_710_000,   "AM Broadcast",        "Broadcast",  "AM"),
    (1_710_000, 2_300_000,  "MF utilities",        "Utility",    "USB"),
    (2_300_000, 2_495_000,  "Shortwave Broadcast", "Broadcast",  "AM"),
    (3_200_000, 3_400_000,  "Shortwave Broadcast", "Broadcast",  "AM"),
    (3_900_000, 4_000_000,  "Shortwave Broadcast", "Broadcast",  "AM"),
    (4_750_000, 5_060_000,  "Shortwave Broadcast", "Broadcast",  "AM"),
    (5_900_000, 6_200_000,  "Shortwave Broadcast", "Broadcast",  "AM"),
    (7_200_000, 7_450_000,  "Shortwave Broadcast", "Broadcast",  "AM"),
    (9_400_000, 9_900_000,  "Shortwave Broadcast", "Broadcast",  "AM"),
    (11_600_000, 12_100_000, "Shortwave Broadcast", "Broadcast", "AM"),
    (13_570_000, 13_870_000, "Shortwave Broadcast", "Broadcast", "AM"),
    (15_100_000, 15_800_000, "Shortwave Broadcast", "Broadcast", "AM"),
    (17_480_000, 17_900_000, "Shortwave Broadcast", "Broadcast", "AM"),
    (18_900_000, 19_020_000, "Shortwave Broadcast", "Broadcast", "AM"),
    (21_450_000, 21_850_000, "Shortwave Broadcast", "Broadcast", "AM"),
    (25_600_000, 26_100_000, "Shortwave Broadcast", "Broadcast", "AM"),
    (108_000_000, 137_000_000, "Airband",           "Aviation",  "AM"),
    (137_000_000, 138_000_000, "Weather satellite", "Utility",   "NFM"),
    (88_000_000, 108_000_000,  "FM Broadcast",      "Broadcast", "WFM"),
    (76_000_000, 88_000_000,   "FM Broadcast (JP)", "Broadcast", "WFM"),
]

# Classifications considered "generic" — safe to overwrite on enrichment.
_GENERIC = {"", "occupied", "bookmark", "DX", "unknown"}

_KNOWN_TOL_HZ = 6_000      # match a fixed channel within ±6 kHz


@dataclass
class Classification:
    label:      str          # "" when unknown
    modulation: str
    category:   str
    confidence: float        # 0..1

    @property
    def is_known(self) -> bool:
        return bool(self.label)


def _nearest_known(freq_hz: int, tol_hz: int):
    """Return the nearest RF Lab fixed-frequency entry within tol, or None.

    Entry tuple: (freq_hz, name, category, description). Imported lazily so
    core does not hard-depend on the ui package at import time.
    """
    try:
        from ui.tabs.rf_lab_data import BUILTIN_FREQS
    except Exception:
        return None
    best = None
    best_d = tol_hz + 1
    for entry in BUILTIN_FREQS:
        d = abs(int(entry[0]) - freq_hz)
        if d <= tol_hz and d < best_d:
            best, best_d = entry, d
    return best


def classify_by_allocation(freq_hz: int, bandwidth_hz: int = 0, *,
                           known_tol_hz: int = _KNOWN_TOL_HZ) -> Classification:
    """Best-effort classification of a frequency by known allocations."""
    freq_hz = int(freq_hz or 0)
    if freq_hz <= 0:
        return Classification("", "", "", 0.0)

    # 1) Known fixed channel (most specific).
    known = _nearest_known(freq_hz, known_tol_hz)
    if known:
        _, name, category, _desc = known
        return Classification(
            label=name, category=category,
            modulation=_CATEGORY_MOD.get(category, ""),
            confidence=0.9)

    # 2) Amateur band segment (band_at_freq is amateur-only by design).
    band = band_at_freq(freq_hz)
    if band is not None:
        seg = segment_at_freq(freq_hz)
        seg_name = (seg.seg_type if seg else "").strip()
        label = f"{band.name} {seg_name}".strip()
        return Classification(
            label=label, category="Amateur",
            modulation=suggested_mode(freq_hz),
            confidence=0.6 if seg else 0.4)

    # 3) Broadcast / airband / utility ranges (FM broadcast, SW broadcast,
    # airband). Checked before SERVICE_BANDS since airband (108-137 MHz)
    # overlaps no service band but FM (88-108 MHz) overlaps nothing amateur.
    for lo, hi, label, category, mod in _BROADCAST_RANGES:
        if lo <= freq_hz <= hi:
            return Classification(
                label=label, category=category,
                modulation=mod, confidence=0.7)

    # 4) Service / unlicensed band (CB / FRS / GMRS / MURS / ISM). First
    # containing match in SERVICE_BANDS order wins (CB before overlapping ISM).
    for sb in SERVICE_BANDS:
        if sb.freq_lo <= freq_hz <= sb.freq_hi:
            return Classification(
                label=sb.name, category=sb.category,
                modulation=_SERVICE_MOD.get(sb.category, ""),
                confidence=0.5)

    return Classification("", "", "", 0.0)


def apply_classification(sig, *, known_tol_hz: int = _KNOWN_TOL_HZ):
    """Enrich a Signal in place when its classification is still generic.

    Sets `classification` (and `modulation` when blank) from the allocation
    match. Returns the same Signal for chaining. Never raises.
    """
    try:
        if (getattr(sig, "classification", "") or "") not in _GENERIC:
            return sig
        c = classify_by_allocation(
            getattr(sig, "freq_hz", 0),
            getattr(sig, "bandwidth_hz", 0),
            known_tol_hz=known_tol_hz)
        if c.is_known:
            sig.classification = c.label
            if not getattr(sig, "modulation", ""):
                sig.modulation = c.modulation
    except Exception as exc:
        log.debug("apply_classification failed on %s: %s",
                  getattr(sig, "freq_hz", "?"), exc)
    return sig
