# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/freq_database.py

Frequency database — schedule-aware "who is on this channel?" lookup (the SDR
Console "Frequency Database" feature). Complements core/sigid_db.py: sigid_db
says what *kind* of signal a fingerprint is; this says which *station* is
transmitting on a frequency, and — for broadcast schedules — at what time.

A `FreqDatabase` holds `FreqEntry` rows (freq, station, language, country,
target, UTC on/off time, days, source). `lookup(freq, utc)` returns the entries
near that frequency that are active at that time. Catalogues are imported, not
bundled:

  * `import_eibi()` parses the EiBi shortwave schedule CSV (the de-facto public
    format: `kHz;time;days;ITU;station;lang;target;remarks;P;start;stop`).
  * `import_csv()` maps an arbitrary CSV (Aoki / HFCC / FMLIST / custom).

LICENSING: no catalogue data ships with Squelch. The user downloads EiBi / Aoki
/ HFCC / etc. themselves; each entry keeps its `source` for attribution, and the
user is responsible for those catalogues' terms — same posture as sigid_db and
the SigIDWiki/Artemis handling. Pure Python, never raises on a bad row.
"""

import csv
import io
import json
import logging
from dataclasses import dataclass, field, asdict

log = logging.getLogger(__name__)

DEFAULT_FREQ_TOL_HZ = 1_000


@dataclass
class FreqEntry:
    """One frequency-list entry (a station on a channel, optionally scheduled)."""
    freq_hz:    int
    station:    str = ""
    kind:       str = ""       # broadcast / utility / ham / … (free-form)
    language:   str = ""
    country:    str = ""       # ITU / country code
    target:     str = ""       # target area
    time_start: str = ""       # UTC "HHMM"  ("" = all day)
    time_end:   str = ""       # UTC "HHMM"
    days:       str = ""       # e.g. "1234567" ("" = daily)
    notes:      str = ""
    source:     str = "user"   # attribution: eibi / aoki / hfcc / user …

    def active_at(self, utc_hhmm: str | None) -> bool:
        """Is this entry on-air at UTC time `utc_hhmm` ('HHMM')? No time set on
        the entry, or no query time, ⇒ always considered active."""
        if not utc_hhmm or not (self.time_start or self.time_end):
            return True
        try:
            t = int(utc_hhmm)
            lo = int(self.time_start or "0000")
            hi = int(self.time_end or "2400")
        except (TypeError, ValueError):
            return True
        if lo == hi:
            return True
        if lo < hi:
            return lo <= t < hi
        return t >= lo or t < hi            # window wraps past 0000 UTC


class FreqDatabase:
    """Frequency-list store with schedule-aware lookup."""

    def __init__(self, entries=None):
        self._entries: list = list(entries or [])

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def entries(self) -> list:
        return list(self._entries)

    def add(self, entry: FreqEntry) -> None:
        self._entries.append(entry)

    # ── lookup ────────────────────────────────────────────────────────────
    def lookup(self, freq_hz: int, *, tol_hz: int = DEFAULT_FREQ_TOL_HZ,
               utc_hhmm: str | None = None, limit: int = 20) -> list:
        """Entries within `tol_hz` of `freq_hz`, active at `utc_hhmm`, nearest
        first."""
        f = int(freq_hz or 0)
        hits = []
        for e in self._entries:
            d = abs(int(e.freq_hz) - f)
            if d <= tol_hz and e.active_at(utc_hhmm):
                hits.append((d, e))
        hits.sort(key=lambda t: t[0])
        return [e for _, e in hits[:limit]]

    def best(self, freq_hz: int, **kw):
        hits = self.lookup(freq_hz, limit=1, **kw)
        return hits[0] if hits else None

    # ── EiBi shortwave schedule import ────────────────────────────────────
    def import_eibi(self, text: str, source: str = "eibi") -> int:
        """Parse the EiBi CSV schedule (`;`-separated). Returns rows added."""
        n = 0
        for line in (text or "").splitlines():
            line = line.strip()
            if not line or line.lower().startswith("khz"):   # header/blank
                continue
            e = _parse_eibi_row(line, source)
            if e is not None:
                self._entries.append(e)
                n += 1
        return n

    # ── generic CSV import ────────────────────────────────────────────────
    def import_csv(self, text: str, mapping: dict, *, source: str = "user",
                   freq_unit: str = "khz") -> int:
        """Import an arbitrary CSV. `mapping` maps FreqEntry fields to column
        names, e.g. {'freq':'Frequency','station':'Station'}. `freq_unit` is
        'khz','mhz', or 'hz'."""
        try:
            reader = csv.DictReader(io.StringIO(text))
        except Exception:
            return 0
        n = 0
        for row in reader:
            try:
                e = _entry_from_row(row, mapping, source, freq_unit)
            except Exception:
                continue
            if e is not None:
                self._entries.append(e)
                n += 1
        return n

    # ── persistence ───────────────────────────────────────────────────────
    def to_dicts(self) -> list:
        return [asdict(e) for e in self._entries]

    @classmethod
    def from_dicts(cls, dicts) -> "FreqDatabase":
        db = cls()
        for d in dicts or []:
            try:
                db._entries.append(FreqEntry(**{
                    k: v for k, v in d.items()
                    if k in FreqEntry.__dataclass_fields__}))
            except Exception:
                continue
        return db

    def save(self, path) -> None:
        from pathlib import Path
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dicts(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path) -> "FreqDatabase":
        from pathlib import Path
        return cls.from_dicts(json.loads(Path(path).read_text(encoding="utf-8")))


def apply_freq_database(sig, db: "FreqDatabase", *, utc_hhmm: str | None = None,
                        tol_hz: int = DEFAULT_FREQ_TOL_HZ):
    """Enrich a Signal record in place with the station name from a frequency
    database (schedule-aware). Fills `decoded` when blank; tags 'freqdb'.
    Chainable, never raises."""
    if sig is None or db is None:
        return sig
    try:
        e = db.best(int(getattr(sig, "freq_hz", 0) or 0),
                    tol_hz=tol_hz, utc_hhmm=utc_hhmm)
        if e is not None and e.station:
            if not str(getattr(sig, "decoded", "") or ""):
                sig.decoded = e.station
            tags = [t.strip() for t in
                    (str(getattr(sig, "tags", "") or "")).split(",") if t.strip()]
            if "freqdb" not in tags:
                tags.append("freqdb")
            sig.tags = ",".join(tags)
    except Exception as exc:                       # pragma: no cover
        log.debug("apply_freq_database failed: %s", exc)
    return sig


# ── helpers ───────────────────────────────────────────────────────────────

def _to_hz(value, unit: str) -> int:
    v = float(str(value).strip())
    return int(round(v * {"hz": 1, "khz": 1_000, "mhz": 1_000_000}.get(unit, 1)))


def _split_time(field: str):
    """'0600-0800' → ('0600', '0800'); '0600' → ('0600',''); '' → ('','')."""
    field = (field or "").strip()
    if "-" in field:
        a, _, b = field.partition("-")
        return a.strip(), b.strip()
    return field, ""


def _parse_eibi_row(line: str, source: str):
    """One EiBi `;`-separated row → FreqEntry, or None if unparseable.
    Columns: kHz;time;days;ITU;station;lang;target;remarks;P;start;stop"""
    f = line.split(";")
    if len(f) < 5:
        return None
    try:
        freq_hz = _to_hz(f[0], "khz")
    except Exception:
        return None
    if freq_hz <= 0:
        return None
    start, end = _split_time(f[1] if len(f) > 1 else "")

    def g(i):
        return f[i].strip() if len(f) > i else ""
    return FreqEntry(
        freq_hz=freq_hz, station=g(4), kind="broadcast",
        language=g(5), country=g(3), target=g(6),
        time_start=start, time_end=end, days=g(2),
        notes=g(7), source=source)


def _entry_from_row(row: dict, mapping: dict, source: str, freq_unit: str):
    def m(field):
        col = mapping.get(field)
        return (row.get(col, "") if col else "") or ""
    freq_raw = m("freq")
    if not str(freq_raw).strip():
        return None
    start, end = _split_time(m("time"))
    return FreqEntry(
        freq_hz=_to_hz(freq_raw, freq_unit),
        station=str(m("station")), kind=str(m("kind") or "broadcast"),
        language=str(m("language")), country=str(m("country")),
        target=str(m("target")),
        time_start=(m("time_start") or start),
        time_end=(m("time_end") or end),
        days=str(m("days")), notes=str(m("notes")),
        source=str(m("source") or source))
