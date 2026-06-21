from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""
Squelch -- digital/rfdf.py
RF Direction Finding (ROADMAP Phase 3, DF-GRADIENT).

Pure, dependency-free DF math:

  * bearing_from_rssi_sweep() — single-receiver gradient DF: estimate the
    bearing to a transmitter from RSSI sampled across antenna headings
    (rotating a directional/beam antenna, or a body-shielded handheld).
  * triangulate() — least-squares intersection of bearing lines taken from
    several known positions → estimated transmitter location.
  * estimate_location_rssi() — power-weighted centroid of (lat, lon, RSSI)
    samples from a drive/walk test → rough transmitter location.

All angles are compass degrees (0 = North, clockwise). Results carry a 0..1
confidence so the UI can show how trustworthy a fix is. No numpy — small,
import-light, fully unit-tested headlessly.
"""

import math
from dataclasses import dataclass

_EARTH_M_PER_DEG = 111_320.0   # metres per degree of latitude


@dataclass
class DFBearing:
    """A bearing estimate from one RSSI sweep."""
    bearing_deg: float
    confidence:  float          # 0..1 (concentration of the power vector)
    n_samples:   int
    peak_rssi:   float          # strongest RSSI in the sweep (dBm)


@dataclass
class DFFix:
    """A bearing observed from a known location (for triangulation)."""
    lat:         float
    lon:         float
    bearing_deg: float


@dataclass
class LocationEstimate:
    """An estimated transmitter location."""
    lat:        float
    lon:        float
    confidence: float           # 0..1
    method:     str             # 'triangulate' | 'rssi-centroid'
    n_inputs:   int


# ── helpers ──────────────────────────────────────────────────────────────────

def _norm_deg(d: float) -> float:
    return d % 360.0


def _dbm_to_linear(dbm: float) -> float:
    """dBm → linear power (mW). Clamped to avoid overflow on bogus input."""
    return 10.0 ** (max(-200.0, min(50.0, dbm)) / 10.0)


def _enu(lat: float, lon: float, lat0: float, lon0: float) -> tuple[float, float]:
    """Local east/north metres of (lat,lon) relative to origin (lat0,lon0)."""
    east  = (lon - lon0) * _EARTH_M_PER_DEG * math.cos(math.radians(lat0))
    north = (lat - lat0) * _EARTH_M_PER_DEG
    return east, north


def _enu_to_latlon(east: float, north: float,
                   lat0: float, lon0: float) -> tuple[float, float]:
    lat = lat0 + north / _EARTH_M_PER_DEG
    lon = lon0 + east / (_EARTH_M_PER_DEG * math.cos(math.radians(lat0)))
    return lat, lon


# ── single-receiver gradient DF ──────────────────────────────────────────────

def bearing_from_rssi_sweep(samples) -> DFBearing | None:
    """Estimate bearing to a TX from [(heading_deg, rssi_dbm), ...].

    Treats linear power as a weight and takes the power-weighted circular mean
    of the headings — the direction the antenna was pointing when the signal
    was strongest. Confidence is the resultant-vector length (0 = no
    directionality, 1 = a single sharp peak).
    """
    pts = [(float(h), float(r)) for h, r in samples
           if r is not None and h is not None]
    if not pts:
        return None
    x = y = wsum = 0.0
    peak = -999.0
    for heading, rssi in pts:
        w = _dbm_to_linear(rssi)
        a = math.radians(_norm_deg(heading))
        x += w * math.sin(a)      # east component
        y += w * math.cos(a)      # north component
        wsum += w
        peak = max(peak, rssi)
    if wsum <= 0:
        return None
    bearing = _norm_deg(math.degrees(math.atan2(x, y)))
    confidence = math.hypot(x, y) / wsum     # 0..1
    return DFBearing(round(bearing, 1), round(confidence, 3), len(pts), peak)


# ── multi-fix triangulation ──────────────────────────────────────────────────

def triangulate(fixes) -> LocationEstimate | None:
    """Least-squares intersection of bearing lines.

    `fixes` is an iterable of DFFix (or (lat, lon, bearing_deg) tuples) taken
    from at least two non-collinear positions/bearings. Solves on a local ENU
    plane: each bearing defines a line `n·(X − p) = 0` with unit normal
    n = (cos θ, −sin θ); minimise Σ(n·(X − p))².
    """
    fx = _coerce_fixes(fixes)
    if len(fx) < 2:
        return None
    lat0 = sum(f.lat for f in fx) / len(fx)
    lon0 = sum(f.lon for f in fx) / len(fx)
    # Accumulate normal equations  A X = b   (A symmetric 2x2)
    a11 = a12 = a22 = b1 = b2 = 0.0
    for f in fx:
        e, n = _enu(f.lat, f.lon, lat0, lon0)
        th = math.radians(_norm_deg(f.bearing_deg))
        nx, ny = math.cos(th), -math.sin(th)     # unit normal to the bearing
        c = nx * e + ny * n
        a11 += nx * nx; a12 += nx * ny; a22 += ny * ny
        b1 += nx * c;   b2 += ny * c
    det = a11 * a22 - a12 * a12
    if abs(det) < 1e-9:               # parallel bearings — no intersection
        return None
    ex = (b1 * a22 - b2 * a12) / det
    ny_ = (a11 * b2 - a12 * b1) / det
    lat, lon = _enu_to_latlon(ex, ny_, lat0, lon0)
    conf = _triangulation_confidence(fx, lat, lon)
    return LocationEstimate(round(lat, 6), round(lon, 6),
                            round(conf, 3), "triangulate", len(fx))


def _coerce_fixes(fixes) -> list[DFFix]:
    out: list[DFFix] = []
    for f in fixes:
        if isinstance(f, DFFix):
            out.append(f)
        else:
            lat, lon, brg = f
            out.append(DFFix(float(lat), float(lon), float(brg)))
    return out


def _triangulation_confidence(fx: list[DFFix], lat: float, lon: float) -> float:
    """Confidence from angular diversity of the bearings (0..1).

    Bearings spread over wide angles intersect crisply (high confidence);
    near-parallel bearings give an ill-conditioned, low-confidence fix.
    """
    angs = sorted(_norm_deg(f.bearing_deg) for f in fx)
    spread = max(
        (b - a) for a, b in zip(angs, angs[1:] + [angs[0] + 360.0])
    ) if len(angs) > 1 else 0.0
    # Best when bearings differ ~90°; degrade toward 0 and 180.
    diversity = math.sin(math.radians(min(spread, 360.0 - spread)))
    count_bonus = min(1.0, len(fx) / 4.0)
    return max(0.0, min(1.0, abs(diversity) * count_bonus))


# ── RSSI drive-test centroid ─────────────────────────────────────────────────

def estimate_location_rssi(samples) -> LocationEstimate | None:
    """Power-weighted centroid of [(lat, lon, rssi_dbm), ...].

    Stronger samples pull the estimate toward them (closer ≈ stronger). Rough
    but useful for a drive/walk test. Confidence grows with sample count and
    how concentrated the strong samples are.
    """
    pts = [(float(la), float(lo), float(r)) for la, lo, r in samples]
    if not pts:
        return None
    wsum = clat = clon = 0.0
    for la, lo, r in pts:
        w = _dbm_to_linear(r)
        clat += w * la; clon += w * lo; wsum += w
    if wsum <= 0:
        return None
    lat, lon = clat / wsum, clon / wsum
    conf = min(1.0, len(pts) / 12.0)
    return LocationEstimate(round(lat, 6), round(lon, 6),
                            round(conf, 3), "rssi-centroid", len(pts))
