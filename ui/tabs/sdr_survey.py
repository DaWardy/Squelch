# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- ui/tabs/sdr_survey.py

Live wideband survey wiring for the SDR tab (ROADMAP §4.5 I-1 — the founding
"hound" data path).

This mixin connects the running SDR spectrum to
``core.live_analysis.SurveyEngine``. While a survey is active, each spectrum
frame the tab already computes in ``_on_samples`` is offered — throttled, on the
main-thread plot timer so the SDR RX thread is never loaded with occupancy /
baseline / DB work — to the engine, which:

  * detects occupied segments (``core.occupancy``),
  * drops SNOI / tags SOI against the watch-list (``core.soi_snoi``),
  * writes Signal records to the shared store so they surface in the Signal Log
    tab (``core.signal_model`` singleton), and
  * folds the frame into a rolling baseline (``core.rf_baseline``) for later
    snapshot / compare — the anomaly-detection ("what's here now that wasn't at
    location A / an hour ago") workflow.

The rich survey / compare *view* is deliberately NOT built here — this is the
data path only, verifiable headlessly. ``survey_snapshot`` / ``survey_compare``
/ ``survey_reset`` are exposed for that future view (and for tests) to drive.

Host (``SDRTab``) contract — attributes this mixin reads, all set in
``_init_state``: ``_latest_fft`` (the dB spectrum frame), ``_fft_lock``,
``_center_hz``, ``_sample_rate``, ``cfg``, ``location_mgr``, plus the
survey state (``_survey`` / ``_survey_enabled``). The host calls
``_survey_tick()`` from its plot timer.
"""

import logging

log = logging.getLogger(__name__)


class _SDRSurveyMixin:
    """Owns the SurveyEngine lifecycle and the throttled per-frame pump."""

    # Plot-timer ticks between offered frames. The timer runs at 10 Hz, so a
    # stride of 10 offers ~1 frame/second — occupancy + baseline-merge + a
    # handful of store writes per second is negligible on the main thread, and
    # a wideband baseline does not need every frame.
    _SURVEY_STRIDE = 10

    # ── lifecycle ─────────────────────────────────────────────────────────
    def _on_survey_toggle(self, on: bool) -> None:
        """Start/stop the live survey. Engine construction is lazy and safe.

        Toggling off keeps the accumulated baseline so a snapshot/compare still
        works; toggling on again continues the same sweep (use ``survey_reset``
        for a fresh one)."""
        self._survey_enabled = bool(on)
        if on and getattr(self, "_survey", None) is None:
            self._survey = self._build_survey_engine()
        log.info("SDR survey %s", "enabled" if on else "disabled")

    def _build_survey_engine(self):
        """A SurveyEngine bound to the shared Signal store + the cfg watch-list.

        Every sub-lookup is guarded — a missing store or watch-list degrades to
        a still-useful survey (baseline only / no SNOI filtering) rather than
        failing to start."""
        from core.live_analysis import SurveyEngine
        store = None
        try:
            from core.signal_model import get_signal_store
            store = get_signal_store()
        except Exception as exc:                    # pragma: no cover
            log.debug("survey: signal store unavailable: %s", exc)
        watch = None
        try:
            from core.soi_snoi import WatchList
            watch = WatchList.from_cfg(self.cfg)
        except Exception as exc:                    # pragma: no cover
            log.debug("survey: watch-list unavailable: %s", exc)
        return SurveyEngine(store=store, watchlist=watch, ingest=True)

    # ── the pump ──────────────────────────────────────────────────────────
    def _survey_tick(self) -> None:
        """Throttled pump — offer the latest spectrum frame to the engine.

        Called from the main-thread plot timer, so the SDR RX thread is never
        loaded. The frame is copied under the FFT lock, then the lock is
        released before ``offer_frame`` (which never raises)."""
        survey = getattr(self, "_survey", None)
        if survey is None or not getattr(self, "_survey_enabled", False):
            return
        self._survey_tick_n = getattr(self, "_survey_tick_n", 0) + 1
        if self._survey_tick_n % self._SURVEY_STRIDE != 0:
            return
        with self._fft_lock:
            fft = None if self._latest_fft is None else self._latest_fft.copy()
        if fft is None:
            return
        lat, lon = self._survey_latlon()
        # Geometry: fft is FFT_SIZE bins spanning _sample_rate, centred on the
        # tuned _center_hz — exactly what SurveyEngine.frame_geometry expects.
        survey.offer_frame(fft, int(self._center_hz), int(self._sample_rate),
                           lat=lat, lon=lon)

    def _survey_latlon(self):
        """Current RX position for tagging detections; (0.0, 0.0) if unknown."""
        try:
            loc = self.location_mgr.location if self.location_mgr else None
            if loc is not None:
                return float(loc.lat), float(loc.lon)
        except Exception:                           # pragma: no cover
            pass
        return 0.0, 0.0

    # ── exposed for the (future) survey view + tests ──────────────────────
    def survey_snapshot(self, label: str = ""):
        """The accumulated baseline (labelled copy), or None if no survey/data."""
        survey = getattr(self, "_survey", None)
        return None if survey is None else survey.snapshot(label)

    def survey_compare(self, reference):
        """Diff the live baseline against a saved reference → BaselineDiff/None."""
        survey = getattr(self, "_survey", None)
        return None if survey is None else survey.compare_to(reference)

    def survey_reset(self) -> None:
        """Discard the accumulated baseline and start a fresh sweep."""
        survey = getattr(self, "_survey", None)
        if survey is not None:
            survey.reset()
