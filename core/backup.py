from __future__ import annotations
"""Automatic log database backup with rotation.

Creates timestamped copies of log.db in logs/backups/.
Keeps the most recent MAX_BACKUPS copies; deletes older ones silently.

Usage (call from main.py once on startup and once on shutdown):
    from core.backup import backup_log
    backup_log(log_db_path, max_copies=7)
"""
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

MAX_BACKUPS = 7


def backup_log(log_db_path: "str | Path",
               max_copies: int = MAX_BACKUPS) -> "Path | None":
    """Copy log_db_path to logs/backups/log_YYYYMMDD_HHMMSS.db.

    Returns the backup path on success, None on failure or if source missing.
    Silently rotates old copies beyond max_copies.
    """
    src = Path(log_db_path)
    if not src.exists() or src.stat().st_size == 0:
        return None   # nothing to back up

    backup_dir = src.parent / "backups"
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None

    ts   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"log_{ts}.db"
    try:
        shutil.copy2(src, dest)
        log.info(f"Log backup: {dest.name}  ({dest.stat().st_size:,} bytes)")
    except OSError as e:
        log.warning(f"Log backup failed: {e}")
        return None

    _rotate(backup_dir, max_copies)
    return dest


def _rotate(backup_dir: Path, keep: int) -> None:
    """Delete oldest backups beyond the keep limit."""
    copies = sorted(backup_dir.glob("log_*.db"),
                    key=lambda p: p.stat().st_mtime)
    for old in copies[:-keep] if len(copies) > keep else []:
        try:
            old.unlink()
            log.debug(f"Removed old backup: {old.name}")
        except OSError:
            pass


def last_backup_info(log_db_path: "str | Path") -> "tuple[str, int] | None":
    """Return (ISO timestamp, size_bytes) of the most recent backup, or None."""
    backup_dir = Path(log_db_path).parent / "backups"
    copies = sorted(backup_dir.glob("log_*.db"),
                    key=lambda p: p.stat().st_mtime) if backup_dir.is_dir() else []
    if not copies:
        return None
    latest = copies[-1]
    # Parse timestamp from filename log_YYYYMMDD_HHMMSS.db
    try:
        stem  = latest.stem   # log_YYYYMMDD_HHMMSS
        parts = stem.split("_", 1)[1]   # YYYYMMDD_HHMMSS
        dt    = datetime.strptime(parts, "%Y%m%d_%H%M%S")
        return dt.strftime("%Y-%m-%d %H:%M UTC"), latest.stat().st_size
    except Exception:
        return latest.name, latest.stat().st_size
