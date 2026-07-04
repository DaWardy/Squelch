# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/emitter_correlate.py

Emitter fingerprint correlation (ROADMAP Phase 3, DF-EMITTER).

The "correlate" half of correlate→geolocate: collapse many `Signal`
observations of the *same emitter* — scattered across frequencies, sources
(APRS / DF / survey / SDR bookmark), and time — into one `Emitter` record,
then estimate where it is from whatever positioned observations it has.

Fingerprint rule:

  * A non-empty `emitter_id` (callsign / radio id / talkgroup / MAC) is the
    strongest identity — it names the *physical* emitter across every
    frequency it was heard on, so those observations group together (more
    points ⇒ a better location fix).
  * With no emitter id, an observation is an anonymous channel occupant; it
    groups by (source, classification, frequency bucket) so repeat hits on the
    same channel still coalesce.

Location is estimated with the same DF math the foxhunt uses
(`digital/rfdf.estimate_location_rssi`) when RSSI is present, else a plain
centroid of the positioned observations. Pure, Qt-free, headlessly tested;
the persistent emitter *map overlay* is the GUI layer on top of this.
"""

import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

# Frequency bucket width for grouping *anonymous* (no emitter-id) observations.
DEFAULT_FREQ_BUCKET_HZ = 12_500          # one NBFM channel


@dataclass
class Emitter:
    """A correlated group of Signal observations of one emitter."""
    key:                 str                       # fingerprint group key
    emitter_id:          str          = ""         # '' when freq-only
    freq_hz:             int          = 0          # representative frequency
    freq_lo:             int          = 0
    freq_hi:             int          = 0
    classifications:     list[str]    = field(default_factory=list)
    sources:             list[str]    = field(default_factory=list)
    modulations:         list[str]    = field(default_factory=list)
    n_signals:           int          = 0          # Signal rows in this group
    n_observations:      int          = 0          # Σ their merge counts
    first_seen:          str          = ""
    last_seen:           str          = ""
    lat:                 float        = 0.0        # estimated location
    lon:                 float        = 0.0
    location_confidence: float        = 0.0        # 0..1
    location_method:     str          = "none"     # rssi-centroid|centroid|none
    signal_ids:          list[int]    = field(default_factory=list)

    @property
    def located(self) -> bool:
        return self.location_method != "none"


# ── fingerprint ───────────────────────────────────────────────────────────────

def fingerprint(sig, freq_bucket_hz: int = DEFAULT_FREQ_BUCKET_HZ) -> str:
    """Group key for one Signal. `emitter_id` (identity) dominates; otherwise
    key by source + classification + a coarse frequency bucket."""
    eid = (getattr(sig, "emitter_id", "") or "").strip().upper()
    if eid:
        return "id:" + eid
    bucket = int(getattr(sig, "freq_hz", 0) or 0) // max(1, freq_bucket_hz)
    src = (getattr(sig, "source", "") or "?")
    cls = (getattr(sig, "classification", "") or "?")
    return f"ch:{src}:{cls}:{bucket}"


# ── correlation ───────────────────────────────────────────────────────────────

def correlate_emitters(signals, *,
                       freq_bucket_hz: int = DEFAULT_FREQ_BUCKET_HZ,
                       min_signals: int = 1) -> list[Emitter]:
    """Group Signal records into Emitters and estimate each location.

    Returns emitters with at least `min_signals` grouped rows, most-active
    first (by observation count, then recency).
    """
    groups: dict[str, list] = {}
    for sig in signals:
        groups.setdefault(fingerprint(sig, freq_bucket_hz), []).append(sig)
    emitters = [_build_emitter(key, grp) for key, grp in groups.items()]
    emitters = [e for e in emitters if e.n_signals >= max(1, min_signals)]
    emitters.sort(key=lambda e: (e.n_observations, e.last_seen), reverse=True)
    return emitters


def correlate_from_store(store=None, *, limit: int = 5000,
                         freq_bucket_hz: int = DEFAULT_FREQ_BUCKET_HZ,
                         min_signals: int = 1) -> list[Emitter]:
    """Convenience: pull recent Signals from the shared store and correlate."""
    try:
        from core.signal_model import get_signal_store
        st = store if store is not None else get_signal_store()
        signals = st.recent(limit=limit)
    except Exception as exc:                       # pragma: no cover
        log.debug("emitter correlate: store read failed: %s", exc)
        return []
    return correlate_emitters(signals, freq_bucket_hz=freq_bucket_hz,
                              min_signals=min_signals)


# ── group builders ────────────────────────────────────────────────────────────

def _uniq(values) -> list[str]:
    """Distinct, non-empty, order-preserving."""
    out: list[str] = []
    for v in values:
        v = (v or "").strip()
        if v and v not in out:
            out.append(v)
    return out


def _build_emitter(key: str, grp: list) -> Emitter:
    freqs = [int(getattr(s, "freq_hz", 0) or 0) for s in grp]
    freqs_nz = [f for f in freqs if f] or [0]
    seens_first = [getattr(s, "first_seen", "") or "" for s in grp]
    seens_last  = [getattr(s, "last_seen", "") or "" for s in grp]
    eid = (getattr(grp[0], "emitter_id", "") or "").strip()
    lat, lon, conf, method = _estimate_group_location(grp)
    return Emitter(
        key=key,
        emitter_id=eid,
        freq_hz=freqs_nz[len(freqs_nz) // 2],       # median-ish representative
        freq_lo=min(freqs_nz),
        freq_hi=max(freqs_nz),
        classifications=_uniq(getattr(s, "classification", "") for s in grp),
        sources=_uniq(getattr(s, "source", "") for s in grp),
        modulations=_uniq(getattr(s, "modulation", "") for s in grp),
        n_signals=len(grp),
        n_observations=sum(int(getattr(s, "count", 1) or 1) for s in grp),
        first_seen=min((s for s in seens_first if s), default=""),
        last_seen=max(seens_last) if seens_last else "",
        lat=lat, lon=lon, location_confidence=conf, location_method=method,
        signal_ids=[int(getattr(s, "id", 0) or 0)
                    for s in grp if getattr(s, "id", 0)],
    )


def _estimate_group_location(grp: list):
    """(lat, lon, confidence, method) for a correlated group.

    Uses the power-weighted DF centroid when ≥2 positioned samples carry RSSI;
    otherwise a plain centroid of the positioned samples; ``none`` if the
    group has no position at all.
    """
    positioned = [s for s in grp
                  if (getattr(s, "lat", 0.0) or getattr(s, "lon", 0.0))]
    if not positioned:
        return 0.0, 0.0, 0.0, "none"
    rssi_pts = [(s.lat, s.lon, s.rssi_dbm) for s in positioned
                if getattr(s, "rssi_dbm", 0.0)]
    if len(rssi_pts) >= 2:
        from digital.rfdf import estimate_location_rssi
        est = estimate_location_rssi(rssi_pts)
        if est is not None:
            return est.lat, est.lon, est.confidence, "rssi-centroid"
    n = len(positioned)
    lat = round(sum(s.lat for s in positioned) / n, 6)
    lon = round(sum(s.lon for s in positioned) / n, 6)
    conf = round(min(1.0, n / 6.0), 3)
    return lat, lon, conf, "centroid"
