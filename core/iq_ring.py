# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/iq_ring.py

Rolling raw-IQ buffer — the enabler for the right-click signal workbench. The
waterfall shows a history of *computed* spectrum rows, but the raw IQ behind it
is thrown away, so a past signal can be seen but not re-analysed or saved. This
keeps the last N seconds of raw samples so a waterfall time-selection can be
pulled back out and fed to the decode workbench (`core/decode_workbench`) or
written to a SigMF clip (`core/sigmf_io.write_iq`).

Fed from the SDR sample callback: `add(iq, sample_rate, center_hz, t=…)` each
frame; `extract(t0, t1)` returns the concatenated IQ for a time window;
`extract_recent(seconds)` grabs the tail. Bounded by wall-time so memory stays
flat on a long run. Pure numpy, never raises — a capture buffer must not crash
the receiver.
"""

import logging
from collections import deque
from dataclasses import dataclass

import numpy as np

log = logging.getLogger(__name__)

DEFAULT_MAX_SECONDS = 20.0


@dataclass
class IQFrame:
    """One received chunk of raw IQ, timestamped when it arrived."""
    t:           float
    iq:          np.ndarray      # complex64
    sample_rate: int
    center_hz:   int


class IQRing:
    """A time-bounded rolling buffer of recent raw IQ frames."""

    def __init__(self, max_seconds: float = DEFAULT_MAX_SECONDS):
        self.max_seconds = max(0.1, float(max_seconds))
        self._frames: deque = deque()

    # ── ingest ────────────────────────────────────────────────────────────
    def add(self, iq, sample_rate: int, center_hz: int, *, t: float) -> None:
        """Append a frame and drop anything older than `max_seconds`."""
        try:
            a = np.asarray(iq, dtype=np.complex64)
            if a.size == 0 or sample_rate <= 0:
                return
            self._frames.append(IQFrame(float(t), a, int(sample_rate),
                                        int(center_hz)))
            newest = self._frames[-1].t
            while self._frames and (newest - self._frames[0].t) > self.max_seconds:
                self._frames.popleft()
        except Exception as exc:                    # pragma: no cover
            log.debug("iq_ring add failed: %s", exc)

    # ── read ──────────────────────────────────────────────────────────────
    def extract(self, t0: float, t1: float):
        """Concatenated IQ for frames whose timestamp is in [t0, t1].

        Returns (iq complex64, sample_rate, center_hz), or None if the window
        holds no frames. sample_rate/center are taken from the selected frames
        (assumed ~constant across a short selection)."""
        lo, hi = (t0, t1) if t0 <= t1 else (t1, t0)
        sel = [f for f in self._frames if lo <= f.t <= hi]
        if not sel:
            return None
        iq = np.concatenate([f.iq for f in sel]).astype(np.complex64)
        return iq, sel[0].sample_rate, sel[0].center_hz

    def extract_recent(self, seconds: float):
        """The most recent `seconds` of IQ, or None if empty."""
        if not self._frames:
            return None
        t1 = self._frames[-1].t
        return self.extract(t1 - float(seconds), t1 + 1e-9)

    # ── info ──────────────────────────────────────────────────────────────
    @property
    def frame_count(self) -> int:
        return len(self._frames)

    @property
    def duration_s(self) -> float:
        if not self._frames:
            return 0.0
        last = self._frames[-1]
        tail = len(last.iq) / last.sample_rate if last.sample_rate else 0.0
        return (last.t - self._frames[0].t) + tail

    def span(self):
        """(t_start, t_end) of retained frames, or None if empty."""
        if not self._frames:
            return None
        return self._frames[0].t, self._frames[-1].t

    def reset(self) -> None:
        self._frames.clear()
