# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/signal_history.py

Signal History (ROADMAP §14.3, SDR-Console parity) — a continuous record of
band-power over time so you can scroll BACK and see *when* a signal came and
went. SDR Console samples the strength of a bandwidth every 50 ms and lets you
review/export it; this is Squelch's version, and it's on-brand with the hound
workflow: an alert fires → look at the history to see the onset, or leave it
running overnight and review what appeared.

A `SignalHistory` tracks one or more frequency **channels** (plus an implicit
`wideband` channel spanning the whole frame). Each offered spectrum frame appends
one timestamped `HistorySample` per channel holding the peak and mean power in
that band. The store is rolling — capped by sample count and/or age — so a long
run stays bounded. `series()` / `window()` read it back for a plot, and
`to_csv()` / `export_csv()` write it out (formula-injection-safe).

Pure Python + numpy for the band reduction; no Qt. Never raises on a bad frame —
a monitoring recorder must not die on one glitch. Frame geometry matches the
survey pump (`start_hz = center - rate/2`, `bin_hz = rate/len`).
"""

import logging
from collections import deque
from dataclasses import dataclass

import numpy as np

log = logging.getLogger(__name__)

WIDEBAND = "wideband"
DEFAULT_MAX_SAMPLES = 200_000       # ~ a few hours at 1 Hz across a few channels
DEFAULT_MAX_AGE_S = 0.0             # 0 = no age cap (count cap only)


@dataclass
class HistoryChannel:
    """A frequency window whose strength is tracked over time."""
    label: str
    lo_hz: int
    hi_hz: int


@dataclass
class HistorySample:
    """One strength reading for one channel at one instant."""
    t:       float
    channel: str
    peak_db: float
    mean_db: float


class SignalHistory:
    """Rolling band-power-over-time recorder for one or more channels."""

    def __init__(self, *, max_samples: int = DEFAULT_MAX_SAMPLES,
                 max_age_s: float = DEFAULT_MAX_AGE_S, track_wideband: bool = True):
        self.max_samples = max(1, int(max_samples))
        self.max_age_s   = max(0.0, float(max_age_s))
        self.track_wideband = bool(track_wideband)
        self.channels: list[HistoryChannel] = []
        self._samples: deque = deque(maxlen=self.max_samples)

    # ── channels ──────────────────────────────────────────────────────────
    def add_channel(self, label: str, lo_hz: int, hi_hz: int) -> None:
        """Track a frequency window. Re-adding a label updates its range."""
        lo, hi = int(min(lo_hz, hi_hz)), int(max(lo_hz, hi_hz))
        for c in self.channels:
            if c.label == label:
                c.lo_hz, c.hi_hz = lo, hi
                return
        self.channels.append(HistoryChannel(str(label), lo, hi))

    def clear_channels(self) -> None:
        self.channels = []

    # ── ingest ────────────────────────────────────────────────────────────
    def offer_frame(self, powers_db, start_hz: int, bin_hz: float,
                    *, t: float) -> int:
        """Append a strength sample per channel from one spectrum frame.

        Returns the number of samples appended. Never raises."""
        try:
            powers = np.asarray(powers_db, dtype=float)
            n = powers.size
            if n < 2 or bin_hz <= 0:
                return 0
            added = 0
            if self.track_wideband:
                added += self._append(WIDEBAND, powers, float(t))
            for c in self.channels:
                lo_bin = int((c.lo_hz - start_hz) / bin_hz)
                hi_bin = int((c.hi_hz - start_hz) / bin_hz)
                if hi_bin < 0 or lo_bin > n - 1:
                    continue                        # no overlap with this frame
                lo_bin = max(0, lo_bin)
                hi_bin = min(n - 1, hi_bin)
                if hi_bin < lo_bin:
                    continue
                added += self._append(c.label, powers[lo_bin:hi_bin + 1],
                                      float(t))
            self._prune(float(t))
            return added
        except Exception as exc:                    # pragma: no cover
            log.debug("signal_history offer_frame failed: %s", exc)
            return 0

    def _append(self, channel: str, seg: np.ndarray, t: float) -> int:
        if seg.size == 0:
            return 0
        self._samples.append(HistorySample(
            t=t, channel=channel,
            peak_db=round(float(np.max(seg)), 2),
            mean_db=round(float(np.mean(seg)), 2)))
        return 1

    def _prune(self, now: float) -> None:
        # deque(maxlen) already bounds count; apply the age cap if set.
        if self.max_age_s <= 0:
            return
        cutoff = now - self.max_age_s
        while self._samples and self._samples[0].t < cutoff:
            self._samples.popleft()

    # ── read ──────────────────────────────────────────────────────────────
    def series(self, channel: str = WIDEBAND) -> list:
        """[(t, peak_db, mean_db), …] for one channel, chronological."""
        return [(s.t, s.peak_db, s.mean_db)
                for s in self._samples if s.channel == channel]

    def window(self, t0: float, t1: float) -> list:
        """All samples whose timestamp is in [t0, t1] (any channel)."""
        lo, hi = (t0, t1) if t0 <= t1 else (t1, t0)
        return [s for s in self._samples if lo <= s.t <= hi]

    def channel_labels(self) -> list:
        seen, out = set(), []
        for s in self._samples:
            if s.channel not in seen:
                seen.add(s.channel)
                out.append(s.channel)
        return out

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    def reset(self) -> None:
        self._samples.clear()

    # ── export ────────────────────────────────────────────────────────────
    def to_csv(self) -> str:
        """The full history as CSV text (formula-injection-safe channel names)."""
        from core.sanitize import csv_safe
        rows = ["time_s,channel,peak_db,mean_db"]
        for s in self._samples:
            rows.append(f"{s.t:.3f},{csv_safe(s.channel)},"
                        f"{s.peak_db:.2f},{s.mean_db:.2f}")
        return "\n".join(rows) + "\n"

    def export_csv(self, path) -> bool:
        """Write the history to `path`. Returns True on success (never raises)."""
        try:
            from pathlib import Path
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(self.to_csv(), encoding="utf-8")
            return True
        except Exception as exc:                    # pragma: no cover
            log.debug("signal_history export failed: %s", exc)
            return False
