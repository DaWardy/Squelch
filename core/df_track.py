# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/df_track.py

Direction-finding capture / logging (ROADMAP Phase 3, DF-RSSI-GPS).

The layer between the *live* feeds (a GPS position source + an SDR RSSI
reading + an optional antenna/compass heading) and the pure DF *math*
(`digital/rfdf.py`). A foxhunt / drive-test is a stream of observations; this
module decides which of them to keep and stores them as a `DFTrack` — an
ordered list of `DFSample` points that can then be turned into a location fix,
a bearing, a heatmap overlay, or a unified `Signal` record.

Four capture triggers gate the incoming stream:

  * MANUAL      — the stream is ignored; the operator logs points explicitly
                  via `add()` ("Log sample now" button).
  * CONTINUOUS  — every offered observation is logged.
  * TIMED       — log at most one point every `interval_s` seconds.
  * DISTANCE    — log a point once the receiver has moved `min_dist_m` metres
                  from the last logged point.

Pure Python, no numpy, no Qt — deterministic (all timestamps are passed in as
epoch seconds, only deltas matter) and fully unit-tested headlessly. The live
GUI wiring (feed GPS+RSSI in, draw the track/heatmap) sits on top of this.
"""

import json
import math
import logging
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict

log = logging.getLogger(__name__)

_EARTH_R_M = 6_371_000.0        # mean Earth radius, metres


class TriggerMode:
    """Capture-trigger identifiers (str values so they persist cleanly)."""
    MANUAL     = "manual"
    CONTINUOUS = "continuous"
    TIMED      = "timed"
    DISTANCE   = "distance"
    ALL = (MANUAL, CONTINUOUS, TIMED, DISTANCE)


# Sensible defaults for the automatic triggers.
DEFAULT_INTERVAL_S = 5.0
DEFAULT_MIN_DIST_M = 25.0


@dataclass
class DFSample:
    """One logged direction-finding observation."""
    t:           float                 # epoch seconds (only deltas matter)
    lat:         float
    lon:         float
    rssi_dbm:    float
    heading_deg: float | None = None   # antenna/travel heading, if known
    freq_hz:     int          = 0
    alt_m:       float        = 0.0

    def has_pos(self) -> bool:
        return bool(self.lat or self.lon)


# ── geo helper ────────────────────────────────────────────────────────────────

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 points, in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * _EARTH_R_M * math.asin(min(1.0, math.sqrt(a)))


# ── trigger decision (pure) ───────────────────────────────────────────────────

def should_log(mode: str, last: DFSample | None, cand: DFSample, *,
               interval_s: float = DEFAULT_INTERVAL_S,
               min_dist_m: float = DEFAULT_MIN_DIST_M) -> bool:
    """Should `cand` be logged, given the last-logged sample `last`?

    Pure function of the two samples + the mode's threshold — no wall clock,
    so it is fully deterministic under test. The first point of any automatic
    track always logs (`last is None`).
    """
    if mode == TriggerMode.MANUAL:
        return False                       # stream suppressed; add() only
    if mode == TriggerMode.CONTINUOUS:
        return True
    if mode == TriggerMode.TIMED:
        if last is None:
            return True                    # first point of an auto track
        return (cand.t - last.t) >= max(0.0, interval_s)
    if mode == TriggerMode.DISTANCE:
        if last is None:
            return True
        moved = haversine_m(last.lat, last.lon, cand.lat, cand.lon)
        return moved >= max(0.0, min_dist_m)
    return False                           # unknown mode → log nothing


# ── the track ─────────────────────────────────────────────────────────────────

@dataclass
class DFTrack:
    """An accumulating direction-finding track (one foxhunt / drive-test)."""
    freq_hz:     int    = 0
    emitter_id:  str    = ""
    label:       str    = ""
    mode:        str    = TriggerMode.TIMED
    interval_s:  float  = DEFAULT_INTERVAL_S
    min_dist_m:  float  = DEFAULT_MIN_DIST_M
    created:     str    = ""
    samples:     list[DFSample] = field(default_factory=list)

    def __post_init__(self):
        if not self.created:
            self.created = _utcnow()
        if self.mode not in TriggerMode.ALL:
            self.mode = TriggerMode.TIMED

    # ── capture ───────────────────────────────────────────────────────────
    def add(self, sample: DFSample) -> DFSample:
        """Unconditionally log a sample (on-demand / MANUAL path)."""
        self.samples.append(sample)
        return sample

    def offer(self, sample: DFSample) -> bool:
        """Offer a streamed observation to the active trigger.

        Returns True if it was logged. Uses the track's own `mode`,
        `interval_s`, `min_dist_m`.
        """
        last = self.samples[-1] if self.samples else None
        if should_log(self.mode, last, sample,
                      interval_s=self.interval_s, min_dist_m=self.min_dist_m):
            self.samples.append(sample)
            return True
        return False

    def clear(self) -> None:
        self.samples.clear()

    def __len__(self) -> int:
        return len(self.samples)

    # ── estimates (delegate to the DF math core) ──────────────────────────
    def location_estimate(self):
        """Power-weighted centroid fix from the logged track, or None."""
        from digital.rfdf import estimate_location_rssi
        pts = [(s.lat, s.lon, s.rssi_dbm) for s in self.samples if s.has_pos()]
        return estimate_location_rssi(pts) if pts else None

    def bearing(self):
        """Gradient bearing from heading+RSSI (rotating-antenna sweep), or None."""
        from digital.rfdf import bearing_from_rssi_sweep
        sweep = [(s.heading_deg, s.rssi_dbm)
                 for s in self.samples if s.heading_deg is not None]
        return bearing_from_rssi_sweep(sweep) if sweep else None

    def to_signal(self, est=None):
        """Turn the current fix into a unified Signal record (source='df'), or
        None if no fix can be formed."""
        from core.signal_ingest import signal_from_df_estimate
        est = est if est is not None else self.location_estimate()
        if est is None:
            return None
        return signal_from_df_estimate(
            est, freq_hz=self.freq_hz, emitter_id=self.emitter_id)

    # ── map / analysis helpers ────────────────────────────────────────────
    def heatmap_points(self) -> list[tuple[float, float, float]]:
        """(lat, lon, weight 0..1) for a strength heatmap overlay.

        Weight is the sample's RSSI scaled linearly between the track's
        weakest (0.0) and strongest (1.0) readings — a flat track yields all
        1.0 (nothing to differentiate)."""
        ss = [s for s in self.samples if s.has_pos()]
        if not ss:
            return []
        rs = [s.rssi_dbm for s in ss]
        lo, hi = min(rs), max(rs)
        if hi == lo:                       # flat track — uniform full weight
            return [(s.lat, s.lon, 1.0) for s in ss]
        span = hi - lo
        return [(s.lat, s.lon, round((s.rssi_dbm - lo) / span, 4)) for s in ss]

    def strongest(self) -> DFSample | None:
        """The single strongest logged sample (closest-approach hint)."""
        pos = [s for s in self.samples if s.has_pos()]
        return max(pos, key=lambda s: s.rssi_dbm) if pos else None

    def bbox(self) -> tuple[float, float, float, float] | None:
        """(min_lat, min_lon, max_lat, max_lon) of the positioned samples."""
        pos = [s for s in self.samples if s.has_pos()]
        if not pos:
            return None
        lats = [s.lat for s in pos]
        lons = [s.lon for s in pos]
        return (min(lats), min(lons), max(lats), max(lons))

    def path_length_m(self) -> float:
        """Total distance walked/driven along the logged track, in metres."""
        pos = [s for s in self.samples if s.has_pos()]
        return sum(
            haversine_m(a.lat, a.lon, b.lat, b.lon)
            for a, b in zip(pos, pos[1:])
        )

    def duration_s(self) -> float:
        """Elapsed time between first and last logged sample, in seconds."""
        if len(self.samples) < 2:
            return 0.0
        return self.samples[-1].t - self.samples[0].t

    # ── persistence ───────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "DFTrack":
        raw = dict(d)
        samples = [DFSample(**{k: v for k, v in s.items()
                               if k in DFSample.__dataclass_fields__})
                   for s in raw.pop("samples", []) or []]
        trk = cls(**{k: v for k, v in raw.items()
                     if k in cls.__dataclass_fields__ and k != "samples"})
        trk.samples = samples
        return trk

    def save(self, path: Path | str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str) -> "DFTrack":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


# ── module helpers ────────────────────────────────────────────────────────────

def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_s() -> float:
    """Wall-clock epoch seconds — the live feed stamps samples with this; tests
    pass explicit `t` for determinism."""
    return datetime.now(timezone.utc).timestamp()
