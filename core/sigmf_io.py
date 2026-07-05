# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/sigmf_io.py

Pure IQ ↔ SigMF codec: load any SigMF capture into a complex64 array, and write
a complex array back out as SigMF. This complements the live streaming recorder
/ player in `sdr/iq_recorder.py` (which handles cf32_le only) with two things
that layer needs and lacks:

  * **datatype-flexible reads** — real-world SigMF files from other tools carry
    many sample formats (RTL-SDR cu8, HackRF ci8, ci16, cf32/cf64, big/little
    endian). `read_iq()` parses `core:datatype` and normalises integer samples
    to floating-point complex64 so any capture can feed the decode / classify /
    survey cores.
  * **a one-shot array writer** — `write_iq(iq, path, …)` turns an in-memory
    array (e.g. the encoder's output) into a `.sigmf-meta` + `.sigmf-data` pair
    for replay, without the threaded recorder.

SigMF: a recording is `<name>.sigmf-data` (raw interleaved samples) plus
`<name>.sigmf-meta` (JSON: global / captures / annotations). No Qt.
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field

import numpy as np

log = logging.getLogger(__name__)

SIGMF_VERSION = "1.0.0"
_META_EXT = ".sigmf-meta"
_DATA_EXT = ".sigmf-data"


# ── datatype parsing ──────────────────────────────────────────────────────────

@dataclass
class DataType:
    np_dtype: object       # numpy dtype for the on-disk samples
    is_complex: bool
    kind: str              # 'f' | 'i' | 'u'
    bits: int


def parse_datatype(datatype: str) -> DataType:
    """Parse a SigMF `core:datatype` string (e.g. 'cf32_le', 'cu8', 'ri16_be').

    Format: optional c/r (complex/real) + f|i|u + bit-width + optional _le/_be.
    Raises ValueError on an unsupported format.
    """
    s = (datatype or "").strip().lower()
    if not s:
        raise ValueError("empty datatype")
    is_complex = s[0] == "c"
    body = s[1:] if s[0] in ("c", "r") else s
    endian = "<"
    if body.endswith("_le"):
        body, endian = body[:-3], "<"
    elif body.endswith("_be"):
        body, endian = body[:-3], ">"
    kind, digits = body[:1], body[1:]
    if kind not in ("f", "i", "u") or not digits.isdigit():
        raise ValueError(f"unsupported datatype: {datatype}")
    bits = int(digits)
    if bits not in (8, 16, 32, 64):
        raise ValueError(f"unsupported bit width: {datatype}")
    np_dtype = np.dtype(f"{endian}{kind}{bits // 8}")
    return DataType(np_dtype, is_complex, kind, bits)


def _to_complex64(raw: np.ndarray, dt: DataType) -> np.ndarray:
    """Normalise on-disk samples to floating complex64 in ~[-1, 1)."""
    if dt.kind == "u":
        off = float(1 << (dt.bits - 1))
        flt = (raw.astype(np.float32) - off) / off
    elif dt.kind == "i":
        flt = raw.astype(np.float32) / float(1 << (dt.bits - 1))
    else:                                   # float — already in range
        flt = raw.astype(np.float32)
    if dt.is_complex:
        return (flt[0::2] + 1j * flt[1::2]).astype(np.complex64)
    return flt.astype(np.complex64)


# ── metadata ──────────────────────────────────────────────────────────────────

@dataclass
class SigMFMeta:
    sample_rate: float = 0.0
    center_hz:   int   = 0
    datatype:    str   = "cf32_le"
    version:     str   = SIGMF_VERSION
    datetime:    str   = ""
    author:      str   = ""
    hw:          str   = ""
    description: str   = ""
    annotations: list  = field(default_factory=list)
    raw:         dict  = field(default_factory=dict)


def _paths(path):
    p = Path(path)
    name = p.name
    for ext in (_META_EXT, _DATA_EXT):
        if name.endswith(ext):
            p = p.with_name(name[: -len(ext)])
            break
    return p.with_name(p.name + _META_EXT), p.with_name(p.name + _DATA_EXT)


def read_meta(path) -> SigMFMeta:
    """Read and parse the .sigmf-meta for a recording."""
    meta_path, _ = _paths(path)
    raw = json.loads(Path(meta_path).read_text(encoding="utf-8"))
    g = raw.get("global", {}) or {}
    caps = raw.get("captures", []) or [{}]
    center = g.get("core:frequency") or (caps[0].get("core:frequency") if caps else 0)
    return SigMFMeta(
        sample_rate=float(g.get("core:sample_rate", 0) or 0),
        center_hz=int(center or 0),
        datatype=g.get("core:datatype", "cf32_le"),
        version=g.get("core:version", SIGMF_VERSION),
        datetime=g.get("core:datetime", "") or (caps[0].get("core:datetime", "") if caps else ""),
        author=g.get("core:author", ""),
        hw=g.get("core:hw", ""),
        description=g.get("core:description", "") or g.get("squelch:notes", ""),
        annotations=raw.get("annotations", []) or [],
        raw=raw)


# ── read ──────────────────────────────────────────────────────────────────────

def read_iq(path):
    """Load a SigMF recording → (iq complex64, SigMFMeta).

    `path` may be the base name or either the .sigmf-meta / .sigmf-data file.
    Integer sample formats are normalised to floating complex64.
    """
    meta = read_meta(path)
    _, data_path = _paths(path)
    dt = parse_datatype(meta.datatype)
    raw = np.frombuffer(Path(data_path).read_bytes(), dtype=dt.np_dtype)
    return _to_complex64(raw, dt), meta


# ── write (cf32_le) ───────────────────────────────────────────────────────────

def write_iq(iq, path, *, sample_rate: float, center_hz: int = 0,
             datetime_iso: str = "", author: str = "", hw: str = "",
             description: str = "", annotations=None):
    """Write a complex array as a SigMF cf32_le recording.

    Returns (meta_path, data_path). `path` is the base name (any SigMF suffix
    is stripped). Hand the encoder's `result.iq` here to persist / replay it.
    """
    meta_path, data_path = _paths(path)
    Path(meta_path).parent.mkdir(parents=True, exist_ok=True)

    iq = np.asarray(iq, dtype=np.complex64)
    inter = np.empty(iq.size * 2, dtype="<f4")
    inter[0::2] = iq.real
    inter[1::2] = iq.imag
    Path(data_path).write_bytes(inter.tobytes())

    dt_iso = datetime_iso or _utcnow_iso()
    meta = {
        "global": {
            "core:datatype":    "cf32_le",
            "core:sample_rate": float(sample_rate),
            "core:version":     SIGMF_VERSION,
            "core:datetime":    dt_iso,
            "core:author":      author,
            "core:hw":          hw,
            "core:description": description,
            "core:num_channels": 1,
        },
        "captures": [{
            "core:sample_start": 0,
            "core:frequency":    int(center_hz),
            "core:datetime":     dt_iso,
        }],
        "annotations": list(annotations or []),
    }
    Path(meta_path).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta_path, data_path


def make_annotation(freq_lo_hz: int, freq_hi_hz: int, *,
                    sample_start: int = 0, sample_count: int = 0,
                    label: str = "") -> dict:
    """Build one SigMF annotation dict (a labelled time/frequency region)."""
    return {
        "core:sample_start":     int(sample_start),
        "core:sample_count":     int(sample_count),
        "core:freq_lower_edge":  int(freq_lo_hz),
        "core:freq_upper_edge":  int(freq_hi_hz),
        "core:label":            label,
    }


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
