# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
#
# This program is free software: you can redistribute it
# and/or modify it under the terms of the GNU General
# Public License as published by the Free Software
# Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General
# Public License along with this program. If not, see
# <https://www.gnu.org/licenses/>.

from __future__ import annotations
"""Squelch -- core/log_db.py
SQLite QSO log. ADIF import/export. LoTW and QRZ upload queues.
Duplicate detection. Awards tracking (DXCC, WAS, grids).
"""

import sqlite3
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict

log = logging.getLogger(__name__)

from core.config import USER_DIR, LOG_DIR
DB_PATH = LOG_DIR / "squelch_log.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS qso (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    datetime_on   TEXT    NOT NULL,
    datetime_off  TEXT,
    call          TEXT    NOT NULL COLLATE NOCASE,
    band          TEXT,
    freq_hz       INTEGER,
    mode          TEXT,
    submode       TEXT,
    rst_sent      TEXT,
    rst_rcvd      TEXT,
    name          TEXT,
    grid          TEXT,
    lat           REAL DEFAULT 0,
    lon           REAL DEFAULT 0,
    dxcc          TEXT,
    country       TEXT,
    state         TEXT,
    cqz           INTEGER,
    ituz          INTEGER,
    tx_pwr_w      REAL,
    comment       TEXT,
    my_call       TEXT,
    my_grid       TEXT,
    my_lat        REAL DEFAULT 0,
    my_lon        REAL DEFAULT 0,
    lotw_status   TEXT    DEFAULT 'none',
    qrz_status    TEXT    DEFAULT 'none',
    source        TEXT    DEFAULT 'manual',
    adif_extra    TEXT
);

CREATE TABLE IF NOT EXISTS lotw_queue (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    qso_id    INTEGER REFERENCES qso(id),
    queued_at TEXT,
    uploaded  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS qrz_queue (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    qso_id    INTEGER REFERENCES qso(id),
    queued_at TEXT,
    uploaded  INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_qso_call ON qso(call);
CREATE INDEX IF NOT EXISTS idx_qso_band ON qso(band);
CREATE INDEX IF NOT EXISTS idx_qso_datetime ON qso(datetime_on);
"""

# LoTW / QRZ status values
STATUS_NONE      = "none"
STATUS_PENDING   = "pending"
STATUS_QUEUED    = "queued"
STATUS_UPLOADED  = "uploaded"
STATUS_CONFIRMED = "confirmed"
STATUS_ERROR     = "error"


@dataclass
class QSO:
    call:         str
    datetime_on:  str      = ""     # ISO UTC  e.g. 2024-05-04T14:32:00Z
    datetime_off: str      = ""
    band:         str      = ""
    freq_hz:      int      = 0
    mode:         str      = ""
    submode:      str      = ""     # FT8, FT4, WSPR etc.
    rst_sent:     str      = "599"
    rst_rcvd:     str      = "599"
    name:         str      = ""
    grid:         str      = ""
    lat:          float    = 0.0   # their lat (derived from grid)
    lon:          float    = 0.0   # their lon (derived from grid)
    dxcc:         str      = ""
    country:      str      = ""
    state:        str      = ""
    cqz:          int      = 0
    ituz:         int      = 0
    tx_pwr_w:     float    = 0.0
    comment:      str      = ""
    my_call:      str      = ""
    my_grid:      str      = ""
    my_lat:       float    = 0.0   # our lat at time of QSO
    my_lon:       float    = 0.0   # our lon at time of QSO
    lotw_status:  str      = STATUS_PENDING
    qrz_status:   str      = STATUS_PENDING
    source:       str      = "manual"
    adif_extra:   str      = ""
    id:           int      = 0      # set after insert

    def __post_init__(self):
        if not self.datetime_on:
            self.datetime_on = _utcnow()
        self.call = self.call.upper().strip()
        # Auto-derive lat/lon from grid if not supplied
        if self.grid and not (self.lat or self.lon):
            try:
                from core.location import _grid_to_latlon
                self.lat, self.lon = _grid_to_latlon(
                    self.grid)
            except Exception:
                pass


class LogDB:
    """
    Thread-safe SQLite QSO log.
    All public methods are safe to call from any thread.
    """

    def __init__(self, db_path: Path = DB_PATH):
        self._path = db_path
        self._conn = None   # lazy-opened by first _open() call
        self._lock = threading.Lock()
        self._open()

    def _open(self) -> sqlite3.Connection:
        """Open (or reuse) the database connection. Always returns a valid connection."""
        if self._conn is not None:
            return self._conn
        self._path = Path(self._path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._path),
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        log.info(f"Log database: {self._path}")
        return self._conn

    # ── Write ─────────────────────────────────────────────────────────────

    def log_qso(self, qso: QSO) -> int:
        """Insert a QSO. Returns the new row id."""
        with self._lock:
            cur = self._conn.execute("""
                INSERT INTO qso
                  (datetime_on, datetime_off, call, band, freq_hz,
                   mode, submode, rst_sent, rst_rcvd, name, grid, lat, lon,
                   dxcc, country, state, cqz, ituz, tx_pwr_w,
                   comment, my_call, my_grid, my_lat, my_lon, lotw_status, qrz_status,
                   source, adif_extra)
                VALUES
                  (:datetime_on, :datetime_off, :call, :band, :freq_hz,
                   :mode, :submode, :rst_sent, :rst_rcvd, :name, :grid, :lat, :lon,
                   :dxcc, :country, :state, :cqz, :ituz, :tx_pwr_w,
                   :comment, :my_call, :my_grid, :my_lat, :my_lon, :lotw_status, :qrz_status,
                   :source, :adif_extra)
            """, asdict(qso))
            qso_id = cur.lastrowid

            # Auto-queue for LoTW and QRZ if configured
            if qso.lotw_status == STATUS_PENDING:
                self._conn.execute(
                    "INSERT INTO lotw_queue (qso_id, queued_at) VALUES (?,?)",
                    (qso_id, _utcnow()))
            if qso.qrz_status == STATUS_PENDING:
                self._conn.execute(
                    "INSERT INTO qrz_queue (qso_id, queued_at) VALUES (?,?)",
                    (qso_id, _utcnow()))

            self._conn.commit()
            qso.id = qso_id
            log.info(f"Logged QSO #{qso_id}: {qso.call} {qso.band} {qso.mode}")
            return qso_id

    # ── Read ──────────────────────────────────────────────────────────────

    def get_qso(self, qso_id: int) -> QSO | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM qso WHERE id=?", (qso_id,)).fetchone()
            return _row_to_qso(row) if row else None

    def recent_qsos(self, limit: int = 100) -> list[QSO]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM qso ORDER BY datetime_on DESC LIMIT ?",
                (limit,)).fetchall()
            return [_row_to_qso(r) for r in rows]

    def search_qsos(self, call: str = "", band: str = "",
                    mode: str = "", limit: int = 500) -> list[QSO]:
        parts = ["SELECT * FROM qso WHERE 1=1"]
        params = []
        if call:
            parts.append("AND call LIKE ?")
            params.append(f"%{call.upper()}%")
        if band:
            parts.append("AND band=?")
            params.append(band)
        if mode:
            parts.append("AND mode=?")
            params.append(mode)
        parts.append("ORDER BY datetime_on DESC LIMIT ?")
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(" ".join(parts), params).fetchall()
            return [_row_to_qso(r) for r in rows]

    def total_qsos(self) -> int:
        with self._lock:
            return self._conn.execute(
                "SELECT COUNT(*) FROM qso").fetchone()[0]

    # ── Duplicate detection ───────────────────────────────────────────────

    def is_duplicate(self, call: str, band: str, mode: str,
                     hours: int = 24) -> bool:
        """True if same call/band/mode worked within the last N hours."""
        with self._lock:
            row = self._conn.execute("""
                SELECT id FROM qso
                WHERE call=? AND band=? AND mode=?
                  AND datetime_on > datetime('now', ?)
                LIMIT 1
            """, (call.upper(), band, mode,
                  f"-{hours} hours")).fetchone()
            return row is not None

    def worked_before(self, call: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM qso WHERE call=? LIMIT 1",
                (call.upper(),)).fetchone()
            return row is not None

    # ── Awards tracking ───────────────────────────────────────────────────

    def dxcc_count(self) -> int:
        with self._lock:
            return self._conn.execute(
                "SELECT COUNT(DISTINCT dxcc) FROM qso "
                "WHERE dxcc != '' AND dxcc IS NOT NULL").fetchone()[0]

    def was_count(self) -> int:
        """US States worked."""
        with self._lock:
            return self._conn.execute(
                "SELECT COUNT(DISTINCT state) FROM qso "
                "WHERE state != '' AND state IS NOT NULL "
                "AND country IN ('United States','USA','K')").fetchone()[0]

    def grids_worked(self) -> int:
        """Unique 4-char grid squares worked."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT SUBSTR(grid,1,4) FROM qso "
                "WHERE length(grid) >= 4").fetchall()
            return len([r[0] for r in rows if r[0]])

    def stats(self) -> dict:
        return {
            "total_qsos":   self.total_qsos(),
            "dxcc_worked":  self.dxcc_count(),
            "was_worked":   self.was_count(),
            "grids_worked": self.grids_worked(),
        }

    # ── ADIF export ───────────────────────────────────────────────────────

    def delete_qso(self, qso) -> bool:
        """Delete a QSO by its id."""
        qso_id = getattr(qso, "id", None)
        if qso_id is None:
            log.warning("delete_qso: no id on QSO object")
            return False
        with self._lock:
            conn = self._open()
            conn.execute("DELETE FROM qso WHERE id=?", (qso_id,))
            conn.commit()
        return True

    def update_qso(self, qso) -> bool:
        """Update an edited QSO in the database."""
        qso_id = getattr(qso, "id", None)
        if qso_id is None:
            return False
        with self._lock:
            conn = self._open()
            conn.execute("""
                UPDATE qso SET
                    call=?, band=?, mode=?,
                    rst_sent=?, rst_rcvd=?,
                    grid=?, name=?, comment=?
                WHERE id=?
            """, (qso.call, qso.band, qso.mode,
                  qso.rst_sent, qso.rst_rcvd,
                  qso.grid, qso.name,
                  qso.comment, qso_id))
            conn.commit()
            # keep connection open
        return True

    def export_adif(self, path: Path, qsos: list[QSO] | None = None, qso_ids: list[int] | None = None) -> int:
        if qso_ids is not None and qsos is None:
            with self._lock:
                rows = self._conn.execute(
                    "SELECT * FROM qso WHERE id IN "
                    + f"({chr(44).join(chr(63) for _ in qso_ids)})",
                    qso_ids).fetchall()
            qsos = [QSO(*r) for r in rows]
        """Export to ADIF. Returns number of records written."""
        if qsos is None:
            qsos = self.recent_qsos(limit=999999)
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "ADIF Export from Squelch\n",
            f"<ADIF_VER:5>3.1.4\n",
            f"<CREATED_TIMESTAMP:15>"
            f"{datetime.now(timezone.utc).strftime('%Y%m%d %H%M%S')}\n",
            "<PROGRAMID:6>Squelch\n",
            "<EOH>\n\n",
        ]
        for q in qsos:
            lines.append(_qso_to_adif(q) + "\n")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)
        except (OSError, PermissionError) as e:
            log.error(f"ADIF export failed: {e}")
            raise
        log.info(f"ADIF export: {len(qsos)} records → {path}")
        return len(qsos)

    # ── LoTW / QRZ queue ─────────────────────────────────────────────────

    def lotw_pending(self) -> list[QSO]:
        with self._lock:
            rows = self._conn.execute("""
                SELECT q.* FROM qso q
                JOIN lotw_queue lq ON lq.qso_id = q.id
                WHERE lq.uploaded = 0
                ORDER BY q.datetime_on
            """).fetchall()
            return [_row_to_qso(r) for r in rows]

    def qrz_pending(self) -> list[QSO]:
        with self._lock:
            rows = self._conn.execute("""
                SELECT q.* FROM qso q
                JOIN qrz_queue qq ON qq.qso_id = q.id
                WHERE qq.uploaded = 0
                ORDER BY q.datetime_on
            """).fetchall()
            return [_row_to_qso(r) for r in rows]

    def mark_lotw_uploaded(self, qso_id: int):
        with self._lock:
            self._conn.execute(
                "UPDATE lotw_queue SET uploaded=1 WHERE qso_id=?", (qso_id,))
            self._conn.execute(
                "UPDATE qso SET lotw_status=? WHERE id=?",
                (STATUS_UPLOADED, qso_id))
            self._conn.commit()

    def mark_qrz_uploaded(self, qso_id: int):
        with self._lock:
            self._conn.execute(
                "UPDATE qrz_queue SET uploaded=1 WHERE qso_id=?", (qso_id,))
            self._conn.execute(
                "UPDATE qso SET qrz_status=? WHERE id=?",
                (STATUS_UPLOADED, qso_id))
            self._conn.commit()

    def close(self):
        with self._lock:
            self._conn.close()


# ── Helpers ───────────────────────────────────────────────────────────────

def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row_to_qso(row: sqlite3.Row) -> QSO:
    d = dict(row)
    d.pop("id", None)
    qso = QSO(**{k: v for k, v in d.items()
                 if k in QSO.__dataclass_fields__})
    qso.id = row["id"]
    return qso


def _adif_field(tag: str, value) -> str:
    if value is None or value == "" or value == 0:
        return ""
    s = str(value)
    return f"<{tag.upper()}:{len(s)}>{s} "


def _qso_to_adif(q: QSO) -> str:
    parts = []
    parts.append(_adif_field("CALL",        q.call))
    parts.append(_adif_field("QSO_DATE",    q.datetime_on[:10].replace("-","")))
    parts.append(_adif_field("TIME_ON",     q.datetime_on[11:17].replace(":","")))
    parts.append(_adif_field("BAND",        q.band))
    parts.append(_adif_field("FREQ",        f"{q.freq_hz/1e6:.6f}" if q.freq_hz else ""))
    parts.append(_adif_field("MODE",        q.mode))
    parts.append(_adif_field("SUBMODE",     q.submode))
    parts.append(_adif_field("RST_SENT",    q.rst_sent))
    parts.append(_adif_field("RST_RCVD",    q.rst_rcvd))
    parts.append(_adif_field("NAME",        q.name))
    parts.append(_adif_field("GRIDSQUARE",  q.grid))
    if q.lat:
        parts.append(_adif_field("LAT",
            f"{'N' if q.lat>=0 else 'S'}"
            f"{abs(q.lat):010.6f}"))
    if q.lon:
        parts.append(_adif_field("LON",
            f"{'E' if q.lon>=0 else 'W'}"
            f"{abs(q.lon):011.6f}"))
    parts.append(_adif_field("DXCC",        q.dxcc))
    parts.append(_adif_field("COUNTRY",     q.country))
    parts.append(_adif_field("STATE",       q.state))
    parts.append(_adif_field("CQZ",         q.cqz if q.cqz else ""))
    parts.append(_adif_field("ITUZ",        q.ituz if q.ituz else ""))
    parts.append(_adif_field("TX_PWR",      q.tx_pwr_w if q.tx_pwr_w else ""))
    parts.append(_adif_field("COMMENT",     q.comment))
    parts.append(_adif_field("STATION_CALLSIGN", q.my_call))
    parts.append(_adif_field("MY_GRIDSQUARE",    q.my_grid))
    if q.adif_extra:
        parts.append(q.adif_extra + " ")
    parts.append("<EOR>")
    return "".join(p for p in parts if p)


# Module-level singleton
_instance: LogDB | None = None

def get_log_db() -> LogDB:
    global _instance
    if _instance is None:
        _instance = LogDB()
    return _instance
