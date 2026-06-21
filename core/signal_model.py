# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.

from __future__ import annotations
"""Squelch -- core/signal_model.py

The unified Signal record and store (ROADMAP Phase 1 — the data foundation).

Every pillar (search / identify / correlate / decode / geolocate / query)
reads and writes a single `Signal` record so findings stop living in per-tab
silos. A `Signal` captures what was seen (freq, bandwidth, modulation,
classification, decoded payload), where/when (lat/lon/alt, first/last seen),
how strong (RSSI/SNR), who (emitter id — callsign / MAC / radio id /
talkgroup), and a reference to any IQ capture.

`SignalStore.record()` merges repeat observations of the same emitter into one
row (bumping a count and refreshing last-seen) — the seed of correlation.
`SignalStore.add()` always inserts. All queries are parameterized.
"""

import sqlite3
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

log = logging.getLogger(__name__)

from core.config import LOG_DIR
DB_PATH = LOG_DIR / "signals.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS signal (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    freq_hz        INTEGER NOT NULL,
    bandwidth_hz   INTEGER DEFAULT 0,
    first_seen     TEXT,
    last_seen      TEXT,
    rssi_dbm       REAL    DEFAULT 0,
    snr_db         REAL    DEFAULT 0,
    lat            REAL    DEFAULT 0,
    lon            REAL    DEFAULT 0,
    alt_m          REAL    DEFAULT 0,
    modulation     TEXT    DEFAULT '',
    classification TEXT    DEFAULT '',
    confidence     REAL    DEFAULT 0,
    decoded        TEXT    DEFAULT '',
    emitter_id     TEXT    DEFAULT '',
    source         TEXT    DEFAULT '',
    iq_ref         TEXT    DEFAULT '',
    tags           TEXT    DEFAULT '',
    count          INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_signal_freq    ON signal(freq_hz);
CREATE INDEX IF NOT EXISTS idx_signal_source  ON signal(source);
CREATE INDEX IF NOT EXISTS idx_signal_emitter ON signal(emitter_id);
CREATE INDEX IF NOT EXISTS idx_signal_last    ON signal(last_seen);
"""

# Default frequency tolerance for treating two observations as the same signal.
DEFAULT_FREQ_TOL_HZ = 500


@dataclass
class Signal:
    """One observed RF signal / emitter."""
    freq_hz:        int    = 0
    bandwidth_hz:   int    = 0
    first_seen:     str    = ""    # ISO UTC  e.g. 2026-06-21T14:32:00Z
    last_seen:      str    = ""    # ISO UTC
    rssi_dbm:       float  = 0.0   # 0 = unknown
    snr_db:         float  = 0.0
    lat:            float  = 0.0   # observation / estimated emitter location
    lon:            float  = 0.0
    alt_m:          float  = 0.0
    modulation:     str    = ""    # AM/FM/SSB/OOK/ASK/FSK/PSK/OFDM/...
    classification: str    = ""    # label e.g. APRS / FT8 / P25 / unknown
    confidence:     float  = 0.0   # 0..1
    decoded:        str    = ""    # decoded payload / text snippet
    emitter_id:     str    = ""    # callsign / MAC / radio id / talkgroup
    source:         str    = ""    # producing pillar/tab: aprs/ft8/sdr/df/...
    iq_ref:         str    = ""    # path/reference to an IQ capture
    tags:           str    = ""    # comma-separated free-form tags
    count:          int    = 1     # times observed (merged)
    id:             int    = 0     # set after insert

    def __post_init__(self):
        now = _utcnow()
        if not self.first_seen:
            self.first_seen = now
        if not self.last_seen:
            self.last_seen = self.first_seen
        if self.emitter_id:
            self.emitter_id = self.emitter_id.strip()


class SignalStore:
    """Thread-safe SQLite store for Signal records.

    All public methods are safe to call from any thread.
    """

    def __init__(self, db_path: Path | str = DB_PATH):
        self._path = db_path
        self._conn = None
        self._lock = threading.Lock()
        self._open()

    def _open(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        if self._path != ":memory:":
            self._path = Path(self._path)
            self._path.parent.mkdir(parents=True, exist_ok=True)
            path_str = str(self._path)
        else:
            path_str = ":memory:"
        self._conn = sqlite3.connect(
            path_str, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        log.info("Signal store: %s", path_str)
        return self._conn

    # ── Write ─────────────────────────────────────────────────────────────

    def add(self, sig: Signal) -> int:
        """Always insert a new row. Returns the new id."""
        with self._lock:
            data = asdict(sig)
            data.pop("id", None)
            cols = ", ".join(data.keys())
            ph   = ", ".join(f":{k}" for k in data)
            cur = self._conn.execute(
                f"INSERT INTO signal ({cols}) VALUES ({ph})", data)
            self._conn.commit()
            sig.id = cur.lastrowid
            return sig.id

    def record(self, sig: Signal,
               freq_tol_hz: int = DEFAULT_FREQ_TOL_HZ) -> int:
        """Merge a repeat observation into an existing signal, else insert.

        A match is the same `source`, a frequency within `freq_tol_hz`, and
        either the same non-empty `emitter_id`, or (when no emitter id) the
        same `classification`. On merge: bump count, advance last_seen, and
        fill blank fields / refresh non-zero measurements.
        """
        with self._lock:
            match = self._find_match(sig, freq_tol_hz)
            if match is None:
                return self._insert_locked(sig)
            self._merge_locked(match, sig)
            return match["id"]

    def _insert_locked(self, sig: Signal) -> int:
        data = asdict(sig)
        data.pop("id", None)
        cols = ", ".join(data.keys())
        ph   = ", ".join(f":{k}" for k in data)
        cur = self._conn.execute(
            f"INSERT INTO signal ({cols}) VALUES ({ph})", data)
        self._conn.commit()
        sig.id = cur.lastrowid
        return sig.id

    def _find_match(self, sig: Signal, tol: int) -> sqlite3.Row | None:
        lo, hi = sig.freq_hz - tol, sig.freq_hz + tol
        if sig.emitter_id:
            row = self._conn.execute(
                "SELECT * FROM signal WHERE source=? AND emitter_id=? "
                "AND freq_hz BETWEEN ? AND ? ORDER BY last_seen DESC LIMIT 1",
                (sig.source, sig.emitter_id, lo, hi)).fetchone()
        else:
            row = self._conn.execute(
                "SELECT * FROM signal WHERE source=? AND classification=? "
                "AND emitter_id='' AND freq_hz BETWEEN ? AND ? "
                "ORDER BY last_seen DESC LIMIT 1",
                (sig.source, sig.classification, lo, hi)).fetchone()
        return row

    def _merge_locked(self, row: sqlite3.Row, sig: Signal) -> None:
        """Update an existing row with a fresh observation. Lock held."""
        upd = {
            "last_seen":  max(row["last_seen"] or "", sig.last_seen or ""),
            "count":      (row["count"] or 1) + 1,
            "confidence": max(row["confidence"] or 0.0, sig.confidence or 0.0),
        }
        # Refresh measurements when the new observation provides them.
        for fld in ("rssi_dbm", "snr_db", "lat", "lon", "alt_m", "bandwidth_hz"):
            val = getattr(sig, fld)
            if val:
                upd[fld] = val
        # Fill text fields only when the stored value is blank.
        for fld in ("modulation", "classification", "decoded", "iq_ref", "tags"):
            val = getattr(sig, fld)
            if val and not (row[fld] or ""):
                upd[fld] = val
        sets = ", ".join(f"{k}=:{k}" for k in upd)
        upd["id"] = row["id"]
        self._conn.execute(f"UPDATE signal SET {sets} WHERE id=:id", upd)
        self._conn.commit()

    def delete(self, signal_id: int) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM signal WHERE id=?", (signal_id,))
            self._conn.commit()
            return cur.rowcount > 0

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM signal")
            self._conn.commit()

    # ── Read ──────────────────────────────────────────────────────────────

    def get(self, signal_id: int) -> Signal | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM signal WHERE id=?", (signal_id,)).fetchone()
            return _row_to_signal(row) if row else None

    def count_total(self) -> int:
        with self._lock:
            return self._conn.execute(
                "SELECT COUNT(*) FROM signal").fetchone()[0]

    def recent(self, limit: int = 200) -> list[Signal]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM signal ORDER BY last_seen DESC LIMIT ?",
                (limit,)).fetchall()
            return [_row_to_signal(r) for r in rows]

    def search(self, freq_min: int = 0, freq_max: int = 0,
               source: str = "", classification: str = "",
               emitter_id: str = "", modulation: str = "",
               since: str = "", limit: int = 500) -> list[Signal]:
        """Flexible, parameterized query. Zero/empty args are ignored."""
        parts = ["SELECT * FROM signal WHERE 1=1"]
        params: list = []
        if freq_min:
            parts.append("AND freq_hz >= ?"); params.append(freq_min)
        if freq_max:
            parts.append("AND freq_hz <= ?"); params.append(freq_max)
        if source:
            parts.append("AND source = ?"); params.append(source)
        if classification:
            parts.append("AND classification = ?"); params.append(classification)
        if emitter_id:
            parts.append("AND emitter_id = ?"); params.append(emitter_id.strip())
        if modulation:
            parts.append("AND modulation = ?"); params.append(modulation)
        if since:
            parts.append("AND last_seen >= ?"); params.append(since)
        parts.append("ORDER BY last_seen DESC LIMIT ?"); params.append(limit)
        with self._lock:
            rows = self._conn.execute(" ".join(parts), params).fetchall()
            return [_row_to_signal(r) for r in rows]

    def distinct_emitters(self, source: str = "") -> list[str]:
        with self._lock:
            if source:
                rows = self._conn.execute(
                    "SELECT DISTINCT emitter_id FROM signal "
                    "WHERE emitter_id != '' AND source=? ORDER BY emitter_id",
                    (source,)).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT DISTINCT emitter_id FROM signal "
                    "WHERE emitter_id != '' ORDER BY emitter_id").fetchall()
        return [r[0] for r in rows]


# ── module helpers ────────────────────────────────────────────────────────

def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row_to_signal(row: sqlite3.Row) -> Signal:
    d = dict(row)
    d.pop("id", None)
    sig = Signal(**{k: v for k, v in d.items()
                    if k in Signal.__dataclass_fields__})
    sig.id = row["id"]
    return sig


_instance: SignalStore | None = None


def get_signal_store() -> SignalStore:
    """Process-wide singleton store (lazy)."""
    global _instance
    if _instance is None:
        _instance = SignalStore()
    return _instance
