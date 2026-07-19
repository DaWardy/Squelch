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
import time
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_MAX_ALERTS = 200        # cap the in-memory alert ring the view reads


def _utc_now_str() -> str:
    """UTC timestamp for report headers, e.g. '2026-07-18 14:22:05 UTC'."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


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
        if on and getattr(self, "_alert_monitor", None) is None:
            self._alert_monitor = self._build_alert_monitor()
        if on and getattr(self, "_signal_history", None) is None:
            self._signal_history = self._build_signal_history()
        log.info("SDR survey %s", "enabled" if on else "disabled")

    def _build_signal_history(self):
        """Signal History recorder (§14.3), seeded with the watch-list's SOI
        windows as tracked channels (plus the implicit wideband channel)."""
        try:
            from core.signal_history import SignalHistory
            hist = SignalHistory()
            try:
                from core.soi_snoi import WatchList, SOI
                for r in WatchList.from_cfg(self.cfg).rules:
                    if getattr(r, "kind", None) == SOI:
                        hist.add_channel(getattr(r, "label", "") or "SOI",
                                         int(r.freq_lo_hz), int(r.freq_hi_hz))
            except Exception as exc:                # pragma: no cover
                log.debug("survey: history channels unavailable: %s", exc)
            return hist
        except Exception as exc:                    # pragma: no cover
            log.debug("survey: signal history unavailable: %s", exc)
            return None

    def _build_alert_monitor(self):
        """Live-alert policy from cfg 'survey.alert.*' (safe defaults)."""
        try:
            from core.survey_alert import AlertMonitor
            return AlertMonitor.from_cfg(self.cfg)
        except Exception as exc:                    # pragma: no cover
            log.debug("survey: alert monitor unavailable: %s", exc)
            return None

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
        return SurveyEngine(store=store, watchlist=watch, ingest=True,
                            sigid_db=self._build_sigid_db())

    def _build_sigid_db(self):
        """Signal-ID database for enriching detections with an identity: the
        built-in factual allocations, plus a user-supplied SigIDWiki/Artemis
        export if one is configured (cfg 'sdr.sigid_db_path' → a JSON list of
        {freq_hz, bandwidth_hz, modulation, name, …} entries). None on failure."""
        try:
            from core.sigid_db import SigIdDatabase
            db = SigIdDatabase.builtin()
            path = self.cfg.get("sdr.sigid_db_path", "") if self.cfg else ""
            if path:
                import json
                from pathlib import Path
                entries = json.loads(Path(path).read_text(encoding="utf-8"))
                db.import_entries(entries, source="user")
            return db
        except Exception as exc:                    # pragma: no cover
            log.debug("survey: sigid db unavailable: %s", exc)
            return None

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
        dets = survey.offer_frame(fft, int(self._center_hz),
                                  int(self._sample_rate), lat=lat, lon=lon)
        self._survey_run_alerts(dets)
        self._survey_feed_history(fft)

    def _survey_feed_history(self, fft) -> None:
        """Feed the same frame to the Signal History recorder (band-power over
        time). Geometry matches the survey engine's frame_geometry."""
        hist = getattr(self, "_signal_history", None)
        if hist is None:
            return
        rate = int(self._sample_rate)
        start_hz = int(self._center_hz) - rate // 2
        bin_hz = rate / len(fft) if len(fft) else 0.0
        hist.offer_frame(fft, start_hz, bin_hz, t=time.monotonic())

    def _survey_run_alerts(self, detections) -> None:
        """Feed a frame's detections to the alert policy; collect + log fires."""
        mon = getattr(self, "_alert_monitor", None)
        if mon is None or not detections:
            return
        for a in mon.offer_detections(detections, t=time.monotonic()):
            log.info("Survey alert: %s @ %.4f MHz (%.1f dB)",
                     a.message, a.freq_mhz, a.peak_db)
            self._survey_alerts.append(a)
        if len(self._survey_alerts) > _MAX_ALERTS:
            del self._survey_alerts[:-_MAX_ALERTS]

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
        mon = getattr(self, "_alert_monitor", None)
        if mon is not None:
            mon.reset()
        hist = getattr(self, "_signal_history", None)
        if hist is not None:
            hist.reset()
        self._survey_alerts = []

    def survey_recent_alerts(self, limit: int = 50) -> list:
        """The most recent live-survey alerts (newest last), for the view."""
        return list(getattr(self, "_survey_alerts", []))[-int(limit):]

    # ── signal history (§14.3) ────────────────────────────────────────────
    def survey_history_series(self, channel: str = "wideband") -> list:
        """Strength-over-time [(t, peak_db, mean_db), …] for one channel."""
        hist = getattr(self, "_signal_history", None)
        return [] if hist is None else hist.series(channel)

    def survey_history_channels(self) -> list:
        """Channel labels present in the history (for a plot's series picker)."""
        hist = getattr(self, "_signal_history", None)
        return [] if hist is None else hist.channel_labels()

    def survey_history_export_csv(self, path) -> bool:
        """Export the signal history to CSV. False if no history / write fails."""
        hist = getattr(self, "_signal_history", None)
        return False if hist is None else hist.export_csv(path)

    # ── saved-baseline library (cross-session/location compare) ───────────
    def _survey_store(self):
        """The on-disk baseline library — default %APPDATA%/Squelch/baselines,
        overridable via cfg 'paths.baselines'."""
        from core.survey_session import SurveyStore
        base = self.cfg.get("paths.baselines", "") if self.cfg else ""
        if not base:
            from core.config import USER_DIR
            base = USER_DIR / "baselines"
        return SurveyStore(base)

    def survey_save_baseline(self, label: str = ""):
        """Save the current accumulated baseline to the library for later
        compare. Returns a SurveyEntry, or None if no survey data yet."""
        snap = self.survey_snapshot(label)
        if snap is None:
            return None
        return self._survey_store().save(snap, label)

    def survey_saved_baselines(self):
        """List saved baselines (metadata rows, newest first) for a picker."""
        return self._survey_store().list()

    def survey_compare_saved(self, entry_id):
        """Compare the LIVE baseline against a SAVED reference → BaselineDiff.

        Routed through the engine so the watch-list's SNOI ranges are honoured;
        `diff.new` are signals present now that the saved reference lacked."""
        ref = self._survey_store().load(entry_id)
        if ref is None:
            return None
        return self.survey_compare(ref)

    def survey_export_report(self, path, diff=None, *, fmt: str = "html",
                             location: str = ""):
        """Write a shareable report of a baseline comparison to `path`.

        `diff` defaults to the last-computed compare; pass a BaselineDiff (e.g.
        from `survey_compare_saved`) to report a specific one. Returns the
        written Path or None."""
        if diff is None:
            return None
        from core.survey_report import write_report
        loc = location or self._survey_location_str()
        return write_report(diff, path, fmt=fmt, location=loc,
                            when=_utc_now_str())

    def _survey_location_str(self) -> str:
        """Human-readable current location for a report header (grid/lat-lon)."""
        try:
            loc = self.location_mgr.location if self.location_mgr else None
            if loc is not None:
                if getattr(loc, "grid", ""):
                    return str(loc.grid)
                if loc.lat or loc.lon:
                    return f"{loc.lat:.4f}, {loc.lon:.4f}"
        except Exception:                           # pragma: no cover
            pass
        return ""
