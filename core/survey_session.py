# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/survey_session.py

Saved-baseline library for the survey / "hound" workflow (ROADMAP §4.5 I-1,
§13.1). The RF Baseline & Compare core (`core/rf_baseline`) already snapshots an
environment and diffs two snapshots; what it lacked was a *place to keep them* so
the comparison can span sessions and locations — snapshot a clean environment at
location A, come back later / go elsewhere, and compare **live vs the saved
reference** to surface what appeared (a new emitter — a potential bug / tracker /
unauthorized transmitter).

`SurveyStore` is a folder of saved `Baseline` JSON files with:
  * `save(baseline, label)`   → a `SurveyEntry` (unique, filesystem-safe id),
  * `list()`                  → lightweight `SurveyEntry` rows for a picker,
  * `load(id)` / `delete(id)` → the full `Baseline` / removal,
  * `compare(ref_id, cur)` / `compare_ids(a, b)` → `BaselineDiff`
    (live-vs-saved and saved-vs-saved).

Pure Python over `core/rf_baseline`; no numpy, no Qt. Never raises — a bad file
is skipped, a bad id returns None. Ids are validated against path traversal.
"""

import re
import logging
from pathlib import Path
from dataclasses import dataclass

from core.rf_baseline import Baseline, compare_baselines

log = logging.getLogger(__name__)

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_SAFE_ID    = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass
class SurveyEntry:
    """Lightweight metadata for one saved baseline (for a picker list)."""
    id:         str
    label:      str
    created:    str
    freq_lo_hz: int
    freq_hi_hz: int
    floor_db:   float
    n_segments: int
    lat:        float
    lon:        float
    path:       str


class SurveyStore:
    """A directory of saved survey baselines (JSON) for snapshot / compare."""

    def __init__(self, base_dir):
        self.dir = Path(base_dir)

    # ── write ─────────────────────────────────────────────────────────────
    def save(self, baseline: Baseline, label: str = "") -> SurveyEntry | None:
        """Persist a baseline (from `SurveyEngine.snapshot()`), returning its
        entry — or None if it could not be written."""
        try:
            if baseline is None:
                return None
            if label:
                baseline.label = label
            self.dir.mkdir(parents=True, exist_ok=True)
            stem = self._unique_stem(baseline)
            path = self.dir / f"{stem}.json"
            baseline.save(path)
            return self._entry(baseline, stem, path)
        except Exception as exc:                    # pragma: no cover
            log.debug("survey save failed: %s", exc)
            return None

    # ── read ──────────────────────────────────────────────────────────────
    def list(self) -> list[SurveyEntry]:
        """All saved baselines as metadata rows, newest first. Bad files skipped."""
        out: list[SurveyEntry] = []
        if not self.dir.exists():
            return out
        for p in sorted(self.dir.glob("*.json")):
            try:
                out.append(self._entry(Baseline.load(p), p.stem, p))
            except Exception as exc:                # pragma: no cover
                log.debug("survey list: skip bad baseline %s: %s", p, exc)
        out.sort(key=lambda e: e.created, reverse=True)
        return out

    def load(self, entry_id: str) -> Baseline | None:
        """The full Baseline for an id, or None (unknown / bad / unsafe id)."""
        p = self._path_for(entry_id)
        if p is None or not p.exists():
            return None
        try:
            return Baseline.load(p)
        except Exception as exc:                    # pragma: no cover
            log.debug("survey load failed: %s", exc)
            return None

    def delete(self, entry_id: str) -> bool:
        p = self._path_for(entry_id)
        if p is None or not p.exists():
            return False
        try:
            p.unlink()
            return True
        except Exception as exc:                    # pragma: no cover
            log.debug("survey delete failed: %s", exc)
            return False

    # ── compare ───────────────────────────────────────────────────────────
    def compare(self, ref_id: str, cur: Baseline, **kw):
        """Diff a live/current baseline against a saved reference → BaselineDiff.

        Direction matches the hound workflow: `ref` = the saved (earlier / other
        location) snapshot, `cur` = now → `diff.new` are signals present now that
        were not in the reference (the anomalies). None if either is missing."""
        ref = self.load(ref_id)
        if ref is None or cur is None:
            return None
        try:
            return compare_baselines(ref, cur, **kw)
        except Exception as exc:                    # pragma: no cover
            log.debug("survey compare failed: %s", exc)
            return None

    def compare_ids(self, ref_id: str, cur_id: str, **kw):
        """Diff two saved baselines (e.g. location A reference vs location B)."""
        return self.compare(ref_id, self.load(cur_id), **kw)

    # ── helpers ───────────────────────────────────────────────────────────
    def _unique_stem(self, baseline: Baseline) -> str:
        base = f"{_compact(baseline.created)}_{_slug(baseline.label)}"
        stem, n = base, 2
        while (self.dir / f"{stem}.json").exists():
            stem, n = f"{base}-{n}", n + 1
        return stem

    def _path_for(self, entry_id) -> Path | None:
        """A safe path inside the store for an id, or None if the id is unsafe.

        Rejects anything with path separators or `..` so a picker value can
        never escape the store directory."""
        eid = str(entry_id or "")
        if not _SAFE_ID.match(eid) or ".." in eid:
            return None
        return self.dir / f"{eid}.json"

    @staticmethod
    def _entry(bl: Baseline, stem: str, path) -> SurveyEntry:
        return SurveyEntry(
            id=stem, label=bl.label, created=bl.created,
            freq_lo_hz=int(bl.freq_lo_hz), freq_hi_hz=int(bl.freq_hi_hz),
            floor_db=float(bl.floor_db), n_segments=len(bl.segments),
            lat=float(bl.lat), lon=float(bl.lon), path=str(path))


def _slug(text: str, fallback: str = "baseline") -> str:
    s = _SLUG_STRIP.sub("-", (text or "").strip().lower()).strip("-")
    return s[:40] or fallback


def _compact(created: str) -> str:
    """'2026-07-18T12:34:56Z' → '20260718-123456' for a sortable filename."""
    digits = re.sub(r"[^0-9]", "", created or "")
    return f"{digits[:8]}-{digits[8:14]}" if len(digits) >= 14 else (
        digits or "baseline")
