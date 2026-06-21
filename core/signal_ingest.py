# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/signal_ingest.py

Adapters that turn each finding source's native object into a unified
`Signal` record (ROADMAP Phase 1, SIG-MIGRATE). Keeping the conversion here —
pure, Qt-free, and unit-tested — means the UI handlers only need a one-line
bridge: `ingest(signal_from_aprs(packet))`.

Converters never raise on sparse input; they return a best-effort Signal.
`ingest()` records into the shared SignalStore (or a supplied one for tests).
"""

import logging

from core.signal_model import Signal, get_signal_store

log = logging.getLogger(__name__)

# North-American APRS calling frequency.
APRS_FREQ_HZ = 144_390_000


def _latlon_from_grid(grid: str) -> tuple[float, float]:
    """Best-effort Maidenhead grid → (lat, lon); (0, 0) on failure."""
    if not grid:
        return 0.0, 0.0
    try:
        from core.location import _grid_to_latlon
        lat, lon = _grid_to_latlon(grid)
        return float(lat or 0.0), float(lon or 0.0)
    except Exception:
        return 0.0, 0.0


# ── converters ──────────────────────────────────────────────────────────────

def signal_from_aprs(pkt) -> Signal:
    """APRS packet → Signal. Emitter is the station callsign; comment is the
    decoded payload; position is used when present."""
    return Signal(
        freq_hz=APRS_FREQ_HZ,
        source="aprs",
        classification="APRS",
        modulation="AFSK",
        emitter_id=(getattr(pkt, "callsign", "") or ""),
        decoded=(getattr(pkt, "comment", "") or "")[:200],
        lat=float(getattr(pkt, "lat", 0.0) or 0.0),
        lon=float(getattr(pkt, "lon", 0.0) or 0.0),
    )


def signal_from_ft8(dec) -> Signal:
    """FT8/FT4 DecodedSignal → Signal."""
    lat, lon = _latlon_from_grid(getattr(dec, "grid", "") or "")
    return Signal(
        freq_hz=int(getattr(dec, "freq_hz", 0) or 0),
        source="ft8",
        classification="FT8",
        modulation="MFSK",
        emitter_id=(getattr(dec, "callsign", "") or ""),
        snr_db=float(getattr(dec, "snr", 0) or 0),
        decoded=(getattr(dec, "message", "") or "")[:200],
        lat=lat, lon=lon,
        tags=(getattr(dec, "dxcc", "") or ""),
    )


def signal_from_wspr(spot) -> Signal:
    """WSPRSpot → Signal."""
    lat, lon = _latlon_from_grid(getattr(spot, "grid", "") or "")
    pwr = getattr(spot, "power_dbm", 0)
    grid = getattr(spot, "grid", "") or ""
    return Signal(
        freq_hz=int(getattr(spot, "freq_hz", 0) or 0),
        source="wspr",
        classification="WSPR",
        modulation="MFSK",
        emitter_id=(getattr(spot, "callsign", "") or ""),
        snr_db=float(getattr(spot, "snr", 0) or 0),
        decoded=f"{grid} {pwr}dBm".strip(),
        lat=lat, lon=lon,
    )


def signal_from_dx_spot(spot) -> Signal:
    """DX spot → Signal. Robust to the three in-tree spot shapes:
    `DXSpot`/`Spot` (`.callsign`/`.freq_hz`) and the cluster spot
    (`.dx_call`/`.freq_khz`)."""
    mode = getattr(spot, "mode", "") or ""
    call = getattr(spot, "callsign", "") or getattr(spot, "dx_call", "") or ""
    freq = int(getattr(spot, "freq_hz", 0) or 0)
    if not freq:
        khz = getattr(spot, "freq_khz", 0) or 0
        freq = int(float(khz) * 1000)
    return Signal(
        freq_hz=freq,
        source=(getattr(spot, "source", "") or "dxcluster"),
        classification=(mode or "DX"),
        emitter_id=call,
        snr_db=float(getattr(spot, "snr", 0) or 0),
        decoded=(getattr(spot, "comment", "") or "")[:200],
        tags=(getattr(spot, "country", "") or ""),
    )


def signal_from_occupancy(seg) -> Signal:
    """A spectrum occupancy segment (core.occupancy) → Signal.

    Survey detections carry no emitter id; they correlate by frequency +
    classification, so repeat hits on the same channel merge into one row.
    """
    return Signal(
        freq_hz=int(getattr(seg, "center_hz", 0) or 0),
        bandwidth_hz=int(getattr(seg, "bandwidth_hz", 0) or 0),
        source="survey",
        classification="occupied",
        rssi_dbm=float(getattr(seg, "peak_db", 0.0) or 0.0),
        snr_db=float(getattr(seg, "snr_db", 0.0) or 0.0),
    )


def signal_from_df_estimate(est, freq_hz: int = 0,
                            emitter_id: str = "") -> Signal:
    """A direction-finding LocationEstimate (digital/rfdf) → Signal.

    Records the estimated transmitter location with the fix confidence so it
    appears in the Signal Browser and on the map alongside other captures.
    """
    return Signal(
        freq_hz=int(freq_hz or 0),
        source="df",
        classification="DF fix",
        emitter_id=(emitter_id or ""),
        lat=float(getattr(est, "lat", 0.0) or 0.0),
        lon=float(getattr(est, "lon", 0.0) or 0.0),
        confidence=float(getattr(est, "confidence", 0.0) or 0.0),
        decoded=f"{getattr(est, 'method', 'df')} "
                f"({getattr(est, 'n_inputs', 0)} fixes)",
    )


def signal_from_bookmark(d: dict) -> Signal:
    """SDR signal-ID bookmark dict → Signal."""
    freq = d.get("freq_hz") or d.get("hz") or 0
    if not freq and d.get("freq_mhz"):
        freq = int(float(d["freq_mhz"]) * 1e6)
    return Signal(
        freq_hz=int(freq or 0),
        bandwidth_hz=int(d.get("bandwidth_hz", 0) or 0),
        source="sdr",
        classification=(d.get("name") or d.get("label") or "bookmark"),
        modulation=(d.get("mode") or d.get("modulation") or ""),
        confidence=float(d.get("confidence", 0) or 0),
        decoded=(d.get("notes") or d.get("comment") or "")[:200],
        tags=(d.get("category") or "")[:100],
    )


# ── recording bridge ─────────────────────────────────────────────────────────

def ingest(sig: Signal, store=None) -> int:
    """Record a Signal into the shared store (or `store` for tests).

    Never raises — ingestion must not break a decode/packet handler. Returns
    the row id, or 0 on failure.
    """
    try:
        st = store if store is not None else get_signal_store()
        return st.record(sig)
    except Exception as exc:                       # pragma: no cover
        log.debug("signal ingest failed: %s", exc)
        return 0
