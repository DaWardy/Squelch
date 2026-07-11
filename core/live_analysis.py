# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/live_analysis.py

The live-analysis pump: feed SDR spectrum frames in, get occupancy detections,
an accumulating RF baseline, and unified Signal records out. This is the
connective tissue between the SDR stream and the analysis cores — the "live
wideband survey loop" the rest of Phase 1 / the founding hound feature depends
on.

Frame contract matches `ui/tabs/sdr_tab._on_samples`: each frame is a
power-in-dB spectrum array (one FFT frame) centred on `center_hz` and spanning
`sample_rate` Hz. From that, bin geometry is:

    start_hz = center_hz - sample_rate / 2
    bin_hz   = sample_rate / len(powers_db)

`SurveyEngine.offer_frame()` then:
  1. detects occupied segments (core/occupancy),
  2. drops SNOI matches and tags SOI (core/soi_snoi),
  3. turns the rest into Signal records (core/signal_ingest) and — optionally —
     records them in the shared store,
  4. folds the frame into a rolling `Baseline` (core/rf_baseline) so a sweep
     across a band builds one wideband snapshot to compare against later.

Pure Python + the analysis cores; no Qt, no hardware. The GUI/HW layer only has
to call `offer_frame()` from its sample callback. Tested with synthetic frames.
Never raises on a bad frame — a survey loop must not die on one glitch.
"""

import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

from core.soi_snoi import SOI, SNOI


@dataclass
class Detection:
    """One occupied segment surfaced by a frame, with its watch-list verdict."""
    signal:   object            # core.signal_model.Signal
    interest: str = "other"     # soi | other  (snoi are dropped, never surfaced)


class SurveyEngine:
    """Accumulates live spectrum frames into detections + a rolling baseline."""

    def __init__(self, *, store=None, watchlist=None,
                 threshold_db: float = 6.0, min_width_bins: int = 2,
                 ingest: bool = True, sigid_db=None, freq_db=None,
                 utc_hhmm=None):
        self._store = store
        self._watchlist = watchlist
        self._threshold_db = float(threshold_db)
        self._min_width_bins = int(min_width_bins)
        self._ingest = bool(ingest)
        self._sigid_db = sigid_db      # optional SigIdDatabase for identity
        self._freq_db = freq_db        # optional FreqDatabase for station name
        self._utc_hhmm = utc_hhmm
        self.baseline = None                # accumulating core.rf_baseline.Baseline
        self.frames_seen = 0
        self.last_detections: list = []

    # ── geometry ──────────────────────────────────────────────────────────
    @staticmethod
    def frame_geometry(n_bins: int, center_hz: int, sample_rate: int):
        """(start_hz, bin_hz) for a spectrum frame — matches sdr_tab's FFT."""
        n = max(1, int(n_bins))
        bin_hz = float(sample_rate) / n
        start_hz = int(center_hz) - int(sample_rate) // 2
        return start_hz, bin_hz

    # ── main entry ────────────────────────────────────────────────────────
    def offer_frame(self, powers_db, center_hz: int, sample_rate: int,
                    *, lat: float = 0.0, lon: float = 0.0) -> list:
        """Process one spectrum frame → list[Detection]. Never raises."""
        try:
            powers = list(powers_db)
            if len(powers) < 4 or sample_rate <= 0:
                return []
            start_hz, bin_hz = self.frame_geometry(len(powers), center_hz,
                                                   sample_rate)
            dets = self._detect(powers, start_hz, bin_hz)
            self._accumulate(powers, start_hz, bin_hz, lat, lon)
            self.frames_seen += 1
            self.last_detections = dets
            return dets
        except Exception as exc:                # pragma: no cover
            log.debug("offer_frame failed: %s", exc)
            return []

    def _detect(self, powers, start_hz, bin_hz) -> list:
        from core.occupancy import detect_segments
        from core.signal_ingest import signal_from_occupancy, ingest
        segs = detect_segments(powers, start_hz, bin_hz,
                               threshold_db=self._threshold_db,
                               min_width_bins=self._min_width_bins)
        dets = []
        for seg in segs:
            verdict = (self._watchlist.classify(seg.center_hz)
                       if self._watchlist else None)
            if verdict == SNOI:
                continue                        # signals-not-of-interest: ignore
            sig = signal_from_occupancy(seg)
            self._enrich(sig)
            if self._ingest and self._store is not None:
                ingest(sig, self._store)
            dets.append(Detection(sig, SOI if verdict == SOI else "other"))
        return dets

    def _enrich(self, sig) -> None:
        """Attach an offline signal-ID identity + frequency-database station
        name to a fresh detection, when those catalogues are provided."""
        if self._sigid_db is not None:
            from core.sigid_db import apply_sigid
            apply_sigid(sig, self._sigid_db)
        if self._freq_db is not None:
            from core.freq_database import apply_freq_database
            apply_freq_database(sig, self._freq_db, utc_hhmm=self._utc_hhmm)

    def _accumulate(self, powers, start_hz, bin_hz, lat, lon) -> None:
        from core.rf_baseline import baseline_from_spectrum
        frame_bl = baseline_from_spectrum(
            powers, start_hz, bin_hz, threshold_db=self._threshold_db,
            min_width_bins=self._min_width_bins, lat=lat, lon=lon)
        if self.baseline is None:
            self.baseline = frame_bl
        else:
            self.baseline.merge(frame_bl)

    # ── snapshot / compare ────────────────────────────────────────────────
    def snapshot(self, label: str = ""):
        """Return the accumulated baseline (labelled copy), or None if empty."""
        if self.baseline is None:
            return None
        from core.rf_baseline import Baseline
        snap = Baseline.from_dict(self.baseline.to_dict())
        snap.label = label or self.baseline.label
        return snap

    def compare_to(self, reference, **kw):
        """Diff the accumulated baseline against a saved reference, honouring the
        watch-list's SNOI ranges. Returns a BaselineDiff, or None if no data."""
        if self.baseline is None or reference is None:
            return None
        from core.rf_baseline import compare_baselines
        ignore = self._watchlist.snoi_ranges() if self._watchlist else None
        return compare_baselines(reference, self.baseline,
                                 ignore_ranges=ignore, **kw)

    def reset(self) -> None:
        """Start a fresh sweep/baseline."""
        self.baseline = None
        self.frames_seen = 0
        self.last_detections = []
