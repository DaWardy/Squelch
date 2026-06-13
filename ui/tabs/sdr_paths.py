from __future__ import annotations
"""Squelch -- ui/tabs/sdr_paths.py
Lightweight path helpers for SDR file storage.
No Qt dependency — safe to import in headless test contexts.
"""

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def _safe_recordings_path(cfg, default="recordings") -> Path:
    """Resolve IQ recordings path from config.

    Blocks path traversal (e.g. ../../Windows/System32).
    Falls back to default if unsafe or outside user data.
    """
    raw = str(cfg.get("paths.iq_recordings", default) or default)
    raw = raw.replace("\x00", "").strip()
    if ".." in raw or raw.startswith("/"):
        log.warning("Blocked unsafe recordings path: %r", raw)
        raw = default
    p = Path(raw)
    if not p.is_absolute():
        from core.config import USER_DIR
        p = USER_DIR / raw
    p.mkdir(parents=True, exist_ok=True)
    return p
