# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/survey_alert.py

Live-alert policy for the survey / "hound" workflow (ROADMAP §13.3). The
monitoring and counter-surveillance use cases want to be *told* when something
changes, not to stare at a waterfall. This is the decision layer — given the
detections a survey frame produces (or a baseline-compare's appeared-signals), it
decides which ones warrant an operator alert, and debounces so the same emitter
doesn't fire every second.

Triggers (each independently toggleable):
  * **SOI active** — a detection the watch-list flagged as a signal-of-interest
    (`Detection.interest == 'soi'`),
  * **novel** — a detection on a frequency not seen before this session
    (off by default — noisy in a busy band),
  * **anomaly** — a signal that appeared vs a saved reference baseline
    (`BaselineDiff.new`).

Debounce is per (kind, frequency-bucket) with a cooldown, and an optional
minimum peak gate keeps weak noise from alerting. Pure Python, no Qt; the
notification surface (banner / sound) is the caller's. Never raises — a
monitoring loop must not die on one bad detection.
"""

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

SOI = "soi"                 # mirrors core.soi_snoi.SOI (a plain str constant)
DEFAULT_COOLDOWN_S = 60.0
DEFAULT_BUCKET_HZ  = 12_500


@dataclass
class Alert:
    """One operator-facing alert."""
    kind:    str            # 'soi' | 'novel' | 'anomaly'
    freq_hz: int
    peak_db: float
    label:   str
    message: str
    t:       float = 0.0

    @property
    def freq_mhz(self) -> float:
        return round(self.freq_hz / 1e6, 6)


class AlertMonitor:
    """Decides when a survey detection warrants alerting — debounced."""

    def __init__(self, *, on_soi: bool = True, on_novel: bool = False,
                 on_anomaly: bool = True, cooldown_s: float = DEFAULT_COOLDOWN_S,
                 min_peak_db=None, bucket_hz: int = DEFAULT_BUCKET_HZ):
        self.on_soi     = bool(on_soi)
        self.on_novel   = bool(on_novel)
        self.on_anomaly = bool(on_anomaly)
        self.cooldown_s = float(cooldown_s)
        self.min_peak_db = None if min_peak_db is None else float(min_peak_db)
        self.bucket_hz  = max(1, int(bucket_hz))
        self._last: dict = {}       # (kind, bucket) -> last alert time
        self._seen: set = set()     # frequency buckets seen (novelty)

    # ── live detections (each survey frame) ───────────────────────────────
    def offer_detections(self, detections, *, t: float = 0.0) -> list[Alert]:
        """SOI-active + novel-emitter alerts from a frame's detections."""
        out: list[Alert] = []
        try:
            for d in detections or []:
                sig = getattr(d, "signal", d)
                interest = getattr(d, "interest", "other")
                freq = int(getattr(sig, "freq_hz", 0) or 0)
                peak = float(getattr(sig, "rssi_dbm", 0.0) or 0.0)
                label = str(getattr(sig, "classification", "") or "")
                if not freq or self._below(peak):
                    continue
                bkt = self._bucket(freq)
                fresh = bkt not in self._seen
                self._seen.add(bkt)
                if self.on_soi and interest == SOI:
                    a = self._fire("soi", freq, peak, label, t,
                                   f"SOI active: {label or 'signal'}")
                elif self.on_novel and fresh:
                    a = self._fire("novel", freq, peak, label, t,
                                   f"New signal: {label or 'unclassified'}")
                else:
                    a = None
                if a is not None:
                    out.append(a)
        except Exception as exc:                    # pragma: no cover
            log.debug("offer_detections failed: %s", exc)
        return out

    # ── anomalies (a baseline compare) ────────────────────────────────────
    def offer_diff(self, diff, *, t: float = 0.0) -> list[Alert]:
        """Anomaly alerts from a baseline compare's appeared-signals."""
        out: list[Alert] = []
        if not self.on_anomaly or diff is None:
            return out
        try:
            for d in getattr(diff, "new", []) or []:
                freq = int(getattr(d, "center_hz", 0) or 0)
                peak = float(getattr(d, "peak_db", 0.0) or 0.0)
                label = str(getattr(d, "label", "") or "")
                if not freq or self._below(peak):
                    continue
                a = self._fire("anomaly", freq, peak, label, t,
                               f"Anomaly vs baseline: {label or 'new signal'}")
                if a is not None:
                    out.append(a)
        except Exception as exc:                    # pragma: no cover
            log.debug("offer_diff failed: %s", exc)
        return out

    def reset(self) -> None:
        """Forget debounce + novelty history (new sweep / new reference)."""
        self._last.clear()
        self._seen.clear()

    # ── helpers ───────────────────────────────────────────────────────────
    def _below(self, peak: float) -> bool:
        return self.min_peak_db is not None and peak < self.min_peak_db

    def _bucket(self, freq: int) -> int:
        return int(freq) // self.bucket_hz

    def _fire(self, kind, freq, peak, label, t, message):
        """Return an Alert unless this (kind, bucket) is still within cooldown."""
        key = (kind, self._bucket(freq))
        last = self._last.get(key)
        if last is not None and (t - last) < self.cooldown_s:
            return None
        self._last[key] = t
        return Alert(kind=kind, freq_hz=int(freq), peak_db=round(peak, 1),
                     label=label, message=message, t=t)

    # ── config ────────────────────────────────────────────────────────────
    @classmethod
    def from_cfg(cls, cfg) -> "AlertMonitor":
        """Build from cfg 'survey.alert.*' keys (safe defaults on any error)."""
        try:
            def g(k, d):
                return cfg.get(f"survey.alert.{k}", d)
            mp = g("min_peak_db", None)
            return cls(
                on_soi=bool(g("on_soi", True)),
                on_novel=bool(g("on_novel", False)),
                on_anomaly=bool(g("on_anomaly", True)),
                cooldown_s=float(g("cooldown_s", DEFAULT_COOLDOWN_S)),
                min_peak_db=(None if mp in (None, "") else float(mp)),
                bucket_hz=int(g("bucket_hz", DEFAULT_BUCKET_HZ)))
        except Exception:                           # pragma: no cover
            return cls()
