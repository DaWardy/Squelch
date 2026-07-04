# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/soi_snoi.py

Signals-of-interest / signals-not-of-interest (SOI / SNOI) rules — the founding
"signals of interest recorded; signals not of interest silently ignored"
concept.

A `WatchList` is a persistent, user-editable set of frequency rules that lets
the operator tune what the RF-baseline compare, the occupancy survey, and the
anomaly alerts pay attention to:

  * **SOI** — a band you care about; matches are flagged / prioritised / alerted.
  * **SNOI** — a band you want ignored (local broadcast, pagers, your own
    repeater); matches are suppressed so they never raise an anomaly.

On overlap, **SOI wins** (an explicit interest overrides an ignore). The list
feeds `core/rf_baseline.compare_baselines(ignore_ranges=...)` via
`snoi_ranges()`, and can partition any freq-bearing objects (Signal records,
occupancy segments) into interest / ignore / neutral buckets.

Pure Python, no Qt, never raises. JSON + cfg persistence.
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict

log = logging.getLogger(__name__)

SOI  = "soi"
SNOI = "snoi"

_CFG_KEY = "watchlist.rules"


@dataclass
class WatchRule:
    """One frequency rule. An optional `modulation` narrows the match to a
    modulation family (AFSK matches FSK, etc.)."""
    freq_lo_hz: int
    freq_hi_hz: int
    kind:       str  = SOI          # SOI | SNOI
    label:      str  = ""
    modulation: str  = ""
    enabled:    bool = True
    note:       str  = ""

    def matches(self, freq_hz: int, modulation: str = "") -> bool:
        if not self.enabled:
            return False
        lo, hi = sorted((int(self.freq_lo_hz), int(self.freq_hi_hz)))
        if not (lo <= int(freq_hz or 0) <= hi):
            return False
        if self.modulation and modulation:
            return _same_family(self.modulation, modulation)
        return True


def _same_family(a: str, b: str) -> bool:
    try:
        from core.sigid_db import _family
        return _family(a) == _family(b)
    except Exception:                          # pragma: no cover
        return a.strip().upper() == b.strip().upper()


class WatchList:
    """An ordered set of SOI/SNOI rules."""

    def __init__(self, rules=None):
        self._rules: list = list(rules or [])

    def __len__(self) -> int:
        return len(self._rules)

    @property
    def rules(self) -> list:
        return list(self._rules)

    # ── mutate ────────────────────────────────────────────────────────────
    def add(self, rule: WatchRule) -> WatchRule:
        self._rules.append(rule)
        return rule

    def add_range(self, freq_lo_hz: int, freq_hi_hz: int, kind: str = SOI,
                  label: str = "", modulation: str = "") -> WatchRule:
        return self.add(WatchRule(int(freq_lo_hz), int(freq_hi_hz),
                                  kind=kind, label=label, modulation=modulation))

    def remove(self, index: int) -> bool:
        if 0 <= index < len(self._rules):
            del self._rules[index]
            return True
        return False

    def clear(self) -> None:
        self._rules.clear()

    # ── classify ──────────────────────────────────────────────────────────
    def classify(self, freq_hz: int, modulation: str = ""):
        """Return SOI, SNOI, or None for a frequency. SOI takes precedence."""
        snoi_hit = False
        for r in self._rules:
            if r.matches(freq_hz, modulation):
                if r.kind == SOI:
                    return SOI
                snoi_hit = True
        return SNOI if snoi_hit else None

    def is_soi(self, freq_hz: int, modulation: str = "") -> bool:
        return self.classify(freq_hz, modulation) == SOI

    def is_snoi(self, freq_hz: int, modulation: str = "") -> bool:
        return self.classify(freq_hz, modulation) == SNOI

    def snoi_ranges(self) -> list:
        """(lo, hi) tuples for enabled SNOI rules — ready for
        rf_baseline.compare_baselines(ignore_ranges=...)."""
        return [(min(r.freq_lo_hz, r.freq_hi_hz), max(r.freq_lo_hz, r.freq_hi_hz))
                for r in self._rules if r.enabled and r.kind == SNOI]

    def soi_ranges(self) -> list:
        return [(min(r.freq_lo_hz, r.freq_hi_hz), max(r.freq_lo_hz, r.freq_hi_hz))
                for r in self._rules if r.enabled and r.kind == SOI]

    # ── partition / filter ────────────────────────────────────────────────
    def partition(self, items, freq_attr: str = "freq_hz",
                  mod_attr: str = "modulation") -> dict:
        """Split freq-bearing objects into {soi, snoi, other} by their rules."""
        out = {SOI: [], SNOI: [], "other": []}
        for it in items:
            f = _get(it, freq_attr)
            m = _get(it, mod_attr, "")
            out[self.classify(int(f or 0), m or "") or "other"].append(it)
        return out

    def filter_out_snoi(self, items, freq_attr: str = "freq_hz",
                        mod_attr: str = "modulation") -> list:
        """Drop SNOI matches (the 'silently ignore' behaviour); keep the rest."""
        keep = []
        for it in items:
            f = _get(it, freq_attr)
            m = _get(it, mod_attr, "")
            if self.classify(int(f or 0), m or "") != SNOI:
                keep.append(it)
        return keep

    # ── persistence ───────────────────────────────────────────────────────
    def to_dicts(self) -> list:
        return [asdict(r) for r in self._rules]

    @classmethod
    def from_dicts(cls, dicts) -> "WatchList":
        wl = cls()
        for d in dicts or []:
            try:
                wl._rules.append(_rule_from_dict(d))
            except Exception:
                continue
        return wl

    def save(self, path: Path | str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dicts(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str) -> "WatchList":
        return cls.from_dicts(json.loads(Path(path).read_text(encoding="utf-8")))

    @classmethod
    def from_cfg(cls, cfg) -> "WatchList":
        try:
            return cls.from_dicts(cfg.get(_CFG_KEY, []) or [])
        except Exception:                      # pragma: no cover
            return cls()

    def save_to_cfg(self, cfg) -> None:
        try:
            cfg.set(_CFG_KEY, self.to_dicts())
            cfg.save()
        except Exception as exc:               # pragma: no cover
            log.debug("watchlist save failed: %s", exc)

    # ── suggested defaults ────────────────────────────────────────────────
    @classmethod
    def with_common_snoi(cls) -> "WatchList":
        """A starting set of SNOI rules for common high-energy 'boring' bands
        so a fresh survey isn't swamped by broadcast/paging."""
        wl = cls()
        wl.add_range(530_000, 1_710_000, SNOI, "AM broadcast")
        wl.add_range(88_000_000, 108_000_000, SNOI, "FM broadcast")
        wl.add_range(162_400_000, 162_550_000, SNOI, "NOAA weather")
        wl.add_range(929_000_000, 932_000_000, SNOI, "Paging")
        return wl


# ── helpers ───────────────────────────────────────────────────────────────

def _get(obj, attr, default=0):
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def _rule_from_dict(d: dict) -> WatchRule:
    return WatchRule(
        freq_lo_hz=int(d.get("freq_lo_hz", 0) or 0),
        freq_hi_hz=int(d.get("freq_hi_hz", 0) or 0),
        kind=(d.get("kind") or SOI),
        label=str(d.get("label") or ""),
        modulation=str(d.get("modulation") or ""),
        enabled=bool(d.get("enabled", True)),
        note=str(d.get("note") or ""))
