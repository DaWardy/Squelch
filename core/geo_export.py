# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/geo_export.py

Export located signals / DF tracks / emitters to **KML** (Google Earth) and
**GPX** (GPS tools) — the map-interop half of the geolocate pillar. Anything with
a latitude/longitude can be written out: Signal records with a fix, a
direction-finding track, correlated emitter locations.

  * `signals_to_kml(signals)` / `signals_to_gpx(signals)` — Signal records that
    have a position → placemarks / waypoints (freq, identity, decoded payload in
    the description).
  * `points_to_kml(points)` / `points_to_gpx(points, track=…)` — generic
    (lat, lon, name, desc) points → placemarks / waypoints, or a GPX track.
  * `save(path, content)` — write the string to disk.

Pure Python (stdlib XML escaping); no deps. All free-text is XML-escaped (RF /
decoded strings are untrusted). Never raises — returns a valid empty document
rather than crashing.
"""

import logging
from xml.sax.saxutils import escape as _xesc

log = logging.getLogger(__name__)


def _pt_from_signal(sig) -> dict | None:
    """A signal → an export point, or None if it has no usable position."""
    lat = float(getattr(sig, "lat", 0.0) or 0.0)
    lon = float(getattr(sig, "lon", 0.0) or 0.0)
    if lat == 0.0 and lon == 0.0:
        return None
    if abs(lat) > 90.0 or abs(lon) > 180.0:
        return None
    mhz = float(getattr(sig, "freq_hz", 0) or 0) / 1e6
    name = getattr(sig, "classification", "") or getattr(sig, "emitter_id", "") \
        or (f"{mhz:.4f} MHz" if mhz else "signal")
    desc_bits = []
    if mhz:
        desc_bits.append(f"{mhz:.4f} MHz")
    for attr, lbl in (("modulation", "mod"), ("source", "src"),
                      ("decoded", "decoded"), ("emitter_id", "id")):
        v = getattr(sig, attr, "")
        if v:
            desc_bits.append(f"{lbl}: {v}")
    return {"lat": lat, "lon": lon, "name": str(name),
            "desc": "  •  ".join(desc_bits)}


def _points(signals) -> list:
    out = []
    for s in signals or []:
        p = _pt_from_signal(s)
        if p is not None:
            out.append(p)
    return out


def _norm(points) -> list:
    """Normalise generic point inputs (dicts or (lat,lon[,name[,desc]]) tuples)."""
    out = []
    for p in points or []:
        try:
            if isinstance(p, dict):
                lat, lon = float(p["lat"]), float(p["lon"])
                name, desc = str(p.get("name", "")), str(p.get("desc", ""))
            else:
                lat, lon = float(p[0]), float(p[1])
                name = str(p[2]) if len(p) > 2 else ""
                desc = str(p[3]) if len(p) > 3 else ""
            if abs(lat) <= 90.0 and abs(lon) <= 180.0:
                out.append({"lat": lat, "lon": lon, "name": name, "desc": desc})
        except Exception:                            # pragma: no cover
            continue
    return out


# ── KML ──────────────────────────────────────────────────────────────────────
def points_to_kml(points, name: str = "Squelch") -> str:
    pts = _norm(points)
    marks = []
    for p in pts:
        marks.append(
            "<Placemark>"
            f"<name>{_xesc(p['name'])}</name>"
            + (f"<description>{_xesc(p['desc'])}</description>" if p['desc'] else "")
            + f"<Point><coordinates>{p['lon']:.6f},{p['lat']:.6f},0</coordinates>"
            "</Point></Placemark>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
            f"<name>{_xesc(name)}</name>{''.join(marks)}</Document></kml>\n")


def signals_to_kml(signals, name: str = "Squelch Signals") -> str:
    return points_to_kml(_points(signals), name)


# ── GPX ──────────────────────────────────────────────────────────────────────
def points_to_gpx(points, name: str = "Squelch", *, track: bool = False) -> str:
    pts = _norm(points)
    head = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<gpx version="1.1" creator="Squelch" '
            'xmlns="http://www.topografix.com/GPX/1/1">')
    if track:
        seg = "".join(f'<trkpt lat="{p["lat"]:.6f}" lon="{p["lon"]:.6f}"></trkpt>'
                      for p in pts)
        body = f"<trk><name>{_xesc(name)}</name><trkseg>{seg}</trkseg></trk>"
    else:
        body = "".join(
            f'<wpt lat="{p["lat"]:.6f}" lon="{p["lon"]:.6f}">'
            f"<name>{_xesc(p['name'])}</name>"
            + (f"<desc>{_xesc(p['desc'])}</desc>" if p['desc'] else "")
            + "</wpt>"
            for p in pts)
    return f"{head}{body}</gpx>\n"


def signals_to_gpx(signals, name: str = "Squelch Signals") -> str:
    return points_to_gpx(_points(signals), name)


# ── write ──────────────────────────────────────────────────────────────────
def save(path, content: str) -> bool:
    """Write `content` to `path`. Returns True on success. Never raises."""
    try:
        from pathlib import Path
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return True
    except Exception as exc:                          # pragma: no cover
        log.debug("geo_export save failed: %s", exc)
        return False
