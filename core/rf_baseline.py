# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/rf_baseline.py

RF Baseline & Compare — the "hound" core (the project's founding feature).

Snapshot the RF environment (noise floor + occupied channels), store it, then
compare two snapshots taken at different times or locations to surface what
CHANGED: signals that APPEARED (a new emitter — a potential bug / tracker /
unauthorized transmitter), signals that vanished, signals whose power shifted,
and how the overall noise floor moved.

A `Baseline` is built from one power spectrum via core/occupancy (robust noise
floor + occupied-segment detection); `merge()` folds repeated sweeps into a
steadier baseline. `compare_baselines()` diffs a reference against a current
baseline, labels each anomaly with core/signal_classify, and honours a set of
SNOI (signals-not-of-interest) frequency ranges to ignore (broadcast, pagers…).

Pure Python (no numpy needed at this layer — it consumes already-computed
segments), no Qt. JSON save/load so snapshots persist across sessions. Never
raises on sparse input.
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict

from core.occupancy import (
    OccupancySegment, estimate_noise_floor, detect_segments)

log = logging.getLogger(__name__)

DEFAULT_FREQ_TOL_HZ = 5_000     # two segments this close in centre = "same"
DEFAULT_POWER_TOL_DB = 6.0      # peak change beyond this = "changed"


# ── baseline ──────────────────────────────────────────────────────────────────

@dataclass
class Baseline:
    """A snapshot of an RF environment."""
    label:      str   = ""
    freq_lo_hz: int   = 0
    freq_hi_hz: int   = 0
    bin_hz:     float = 0.0
    floor_db:   float = 0.0
    created:    str   = ""
    lat:        float = 0.0
    lon:        float = 0.0
    n_sweeps:   int   = 1
    segments:   list  = field(default_factory=list)   # OccupancySegment

    def __post_init__(self):
        if not self.created:
            self.created = _utcnow()

    # ── persistence ───────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Baseline":
        raw = dict(d)
        segs = [OccupancySegment(**{k: v for k, v in s.items()
                                    if k in OccupancySegment.__dataclass_fields__})
                for s in raw.pop("segments", []) or []]
        b = cls(**{k: v for k, v in raw.items()
                   if k in cls.__dataclass_fields__ and k != "segments"})
        b.segments = segs
        return b

    def save(self, path: Path | str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str) -> "Baseline":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    # ── accumulate ────────────────────────────────────────────────────────
    def merge(self, other: "Baseline",
              freq_tol_hz: int = DEFAULT_FREQ_TOL_HZ) -> "Baseline":
        """Fold another sweep/scan into this baseline in place: sweep-weighted
        mean floor, and a union of segments (near-duplicates keep the stronger
        peak). Returns self."""
        ns, no = max(1, self.n_sweeps), max(1, other.n_sweeps)
        self.floor_db = (self.floor_db * ns + other.floor_db * no) / (ns + no)
        for seg in other.segments:
            match = _nearest_segment(seg.center_hz, self.segments, freq_tol_hz)
            if match is None:
                self.segments.append(seg)
            elif seg.peak_db > match.peak_db:
                self.segments[self.segments.index(match)] = seg
        self.segments.sort(key=lambda s: s.center_hz)
        self.n_sweeps = ns + no
        self.freq_lo_hz = min(self.freq_lo_hz or other.freq_lo_hz,
                              other.freq_lo_hz or self.freq_lo_hz)
        self.freq_hi_hz = max(self.freq_hi_hz, other.freq_hi_hz)
        return self


def baseline_from_spectrum(powers_db, start_hz: int, bin_hz: float, *,
                           label: str = "", threshold_db: float = 6.0,
                           min_width_bins: int = 1,
                           lat: float = 0.0, lon: float = 0.0) -> Baseline:
    """Build a Baseline from one power spectrum (dB per bin)."""
    powers = list(powers_db)
    floor = estimate_noise_floor(powers)
    segs = detect_segments(powers, start_hz, bin_hz,
                           threshold_db=threshold_db,
                           min_width_bins=min_width_bins, floor_db=floor)
    hi = int(start_hz + (len(powers) - 1) * bin_hz) if powers else int(start_hz)
    return Baseline(label=label, freq_lo_hz=int(start_hz), freq_hi_hz=hi,
                    bin_hz=float(bin_hz), floor_db=float(floor),
                    lat=lat, lon=lon, segments=segs)


# ── comparison ────────────────────────────────────────────────────────────────

@dataclass
class SignalDelta:
    """One change between two baselines."""
    kind:         str          # 'new' | 'missing' | 'changed'
    center_hz:    int
    bandwidth_hz: int
    peak_db:      float
    ref_peak_db:  float
    delta_db:     float
    label:        str = ""
    category:     str = ""


@dataclass
class BaselineDiff:
    ref_label:      str = ""
    cur_label:      str = ""
    floor_delta_db: float = 0.0
    new:            list = field(default_factory=list)   # appeared (anomalies)
    missing:        list = field(default_factory=list)   # vanished
    changed:        list = field(default_factory=list)   # power shifted

    @property
    def anomaly_count(self) -> int:
        return len(self.new) + len(self.changed)


def compare_baselines(ref: Baseline, cur: Baseline, *,
                      freq_tol_hz: int = DEFAULT_FREQ_TOL_HZ,
                      power_tol_db: float = DEFAULT_POWER_TOL_DB,
                      ignore_ranges=None) -> BaselineDiff:
    """Diff `cur` against reference `ref`. `ignore_ranges` is a list of
    (lo_hz, hi_hz) SNOI bands whose signals are excluded from the report."""
    ignore_ranges = ignore_ranges or []
    diff = BaselineDiff(ref_label=ref.label, cur_label=cur.label,
                        floor_delta_db=round(cur.floor_db - ref.floor_db, 2))
    ref_pool = list(ref.segments)
    for seg in cur.segments:
        if _in_ranges(seg.center_hz, ignore_ranges):
            continue
        match = _nearest_segment(seg.center_hz, ref_pool, freq_tol_hz)
        if match is None:
            diff.new.append(_delta("new", seg, None))
        else:
            ref_pool.remove(match)
            if abs(seg.peak_db - match.peak_db) > power_tol_db:
                diff.changed.append(_delta("changed", seg, match))
    for seg in ref_pool:                       # unmatched reference = vanished
        if not _in_ranges(seg.center_hz, ignore_ranges):
            diff.missing.append(_delta("missing", seg, seg))
    return diff


def anomalies_to_signals(diff: BaselineDiff):
    """Turn the appeared/changed anomalies into unified Signal records
    (source='anomaly') for the store / map / browser."""
    from core.signal_model import Signal
    out = []
    for d in diff.new + diff.changed:
        out.append(Signal(
            freq_hz=int(d.center_hz), bandwidth_hz=int(d.bandwidth_hz),
            rssi_dbm=float(d.peak_db), source="anomaly",
            classification=(d.label or f"anomaly ({d.kind})"),
            confidence=0.5,
            tags=f"baseline-compare,{d.kind}"))
    return out


# ── helpers ───────────────────────────────────────────────────────────────────

def _delta(kind: str, seg: OccupancySegment,
           ref: OccupancySegment | None) -> SignalDelta:
    ref_peak = float(ref.peak_db) if ref is not None else 0.0
    label, category = _classify(seg.center_hz, seg.bandwidth_hz)
    return SignalDelta(
        kind=kind, center_hz=int(seg.center_hz),
        bandwidth_hz=int(seg.bandwidth_hz), peak_db=float(seg.peak_db),
        ref_peak_db=ref_peak,
        delta_db=round(float(seg.peak_db) - ref_peak, 2),
        label=label, category=category)


def _classify(freq_hz: int, bandwidth_hz: int):
    try:
        from core.signal_classify import classify_by_allocation
        c = classify_by_allocation(int(freq_hz), int(bandwidth_hz))
        return c.label, c.category
    except Exception:                          # pragma: no cover
        return "", ""


def _nearest_segment(center_hz: int, pool, tol_hz: int):
    best, best_d = None, tol_hz + 1
    for seg in pool:
        d = abs(int(seg.center_hz) - int(center_hz))
        if d <= tol_hz and d < best_d:
            best, best_d = seg, d
    return best


def _in_ranges(freq_hz: int, ranges) -> bool:
    return any(lo <= freq_hz <= hi for lo, hi in ranges)


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
