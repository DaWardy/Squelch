# Squelch — core/netlog.py
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Network activity log (consumer requirement C-12, Priya the pentester).

Records every outbound connection Squelch makes so a user on a sensitive /
client network can audit exactly what the app contacted, when, why, and
whether the user initiated it. No data leaves the machine — this is a local
record, written to logs/network.log and kept in an in-memory ring buffer for
the in-app viewer.

Security rules served:
  S1 — outbound calls are accountable
  S9 — no unsolicited connections; anything automatic is visibly recorded

Usage (from a network module, before making a request):
    from core.netlog import record_connection
    record_connection("services.swpc.noaa.gov", purpose="band conditions",
                       user_initiated=False)
"""
from __future__ import annotations
import threading
import time
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

_LOCK = threading.Lock()
_RING: deque = deque(maxlen=500)
_LOG_PATH: Path | None = None
_REDACT = ("login", "password", "pass", "key", "token", "apikey", "api_key")


@dataclass
class NetEvent:
    ts_utc:        str
    host:          str
    purpose:       str
    user_initiated: bool


def set_log_path(path) -> None:
    """Point the file log at logs/network.log (called once at startup)."""
    global _LOG_PATH
    try:
        _LOG_PATH = Path(path)
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        _LOG_PATH = None


def _redact(host: str) -> str:
    """Never let a credential-bearing string into the log (S4)."""
    low = host.lower()
    for token in _REDACT:
        if token + "=" in low:
            import re
            host = re.sub(rf"{token}=[^&\s]*", f"{token}=***", host,
                          flags=re.IGNORECASE)
    return host


def record_connection(host: str, purpose: str = "",
                      user_initiated: bool = False) -> None:
    """Record one outbound connection. Thread-safe; never raises."""
    try:
        ev = NetEvent(
            ts_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            host=_redact(str(host)),
            purpose=purpose,
            user_initiated=bool(user_initiated))
        with _LOCK:
            _RING.append(ev)
            if _LOG_PATH is not None:
                tag = "USER" if ev.user_initiated else "AUTO"
                line = (f"{ev.ts_utc}  [{tag}]  {ev.host}"
                        f"  — {ev.purpose}\n")
                with open(_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(line)
    except Exception:
        # A logging failure must never break a feature.
        pass


def recent_events(limit: int = 200) -> list[dict]:
    """Return the most recent connection events (for the in-app viewer)."""
    with _LOCK:
        items = list(_RING)[-limit:]
    return [asdict(e) for e in items]


def auto_connection_count() -> int:
    """How many connections so far were NOT user-initiated.
    Priya can confirm this is only the handful she expects (propagation,
    satellites, optional geolocation) — and zero if she disabled them."""
    with _LOCK:
        return sum(1 for e in _RING if not e.user_initiated)
