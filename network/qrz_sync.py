from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- network/qrz_sync.py
QRZ.com Logbook API integration.

Uploads QSOs via the QRZ Logbook XML API v2 (https://logbook.qrz.com/api).
Requires a QRZ Logbook API key (free — from qrz.com → Logbook → Settings → API).
Credentials stored in OS keyring. No QRZ subscription required for logbook.

API protocol:
  POST https://logbook.qrz.com/api
  Body (urlencoded): KEY=<api_key>&ACTION=INSERT&ADIF=<one_adif_record>
  Response (text): status=OK;LOGIDS=123456  or  status=FAIL;REASON=...
  Duplicate detection: REASON=Duplicate — treat as already uploaded, not an error.
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Callable
from core.netlog import record_connection

log = logging.getLogger(__name__)

QRZ_LOGBOOK_URL = "https://logbook.qrz.com/api"
_REQUEST_TIMEOUT = 20  # seconds per QSO — generous for slow connections


@dataclass
class QRZSyncResult:
    success:    bool
    uploaded:   int  = 0
    skipped:    int  = 0   # duplicates already in QRZ
    failed:     int  = 0
    message:    str  = ""
    error:      str  = ""


class QRZSync:
    """
    Uploads pending QSOs to the QRZ.com logbook via their HTTP API.

    Usage:
        sync = QRZSync(cfg)
        sync.on_progress(lambda msg, pct: ...)
        sync.on_complete(lambda result: ...)
        sync.upload_async(log_db, pending_qsos)
    """

    def __init__(self, config):
        self.cfg            = config
        self._on_progress:  Callable | None = None
        self._on_complete:  Callable | None = None

    def on_progress(self, fn: Callable) -> None:
        self._on_progress = fn

    def on_complete(self, fn: Callable) -> None:
        self._on_complete = fn

    def upload_async(self, log_db, qsos: list) -> None:
        """Upload QSOs in a background daemon thread."""
        thread = threading.Thread(
            target=self._upload_worker,
            args=(log_db, qsos),
            daemon=True,
            name="QRZLogbookUpload")
        thread.start()

    def _upload_worker(self, log_db, qsos: list) -> None:
        result = self._do_upload(log_db, qsos)
        if self._on_complete:
            try:
                self._on_complete(result)
            except Exception:
                pass

    def _do_upload(self, log_db, qsos: list) -> QRZSyncResult:
        api_key = self._get_api_key()
        if not api_key:
            return QRZSyncResult(
                success=False,
                error="QRZ Logbook API key not set.\n"
                      "Add it in Settings → APIs → QRZ.com → Logbook API Key.")

        try:
            import requests
        except ImportError:
            return QRZSyncResult(
                success=False,
                error="requests library not available.\n"
                      "Run: pip install requests")

        from core.log_db import _qso_to_adif

        total    = len(qsos)
        uploaded = 0
        skipped  = 0
        failed   = 0
        errors   = []

        for i, qso in enumerate(qsos):
            pct = int((i / total) * 90)
            self._notify(
                f"Uploading QSO {i+1}/{total}: {qso.call} …", pct)

            adif_record = _qso_to_adif(qso)
            try:
                record_connection("qrz_logbook_upload",
                                  QRZ_LOGBOOK_URL, "POST")
                resp = requests.post(
                    QRZ_LOGBOOK_URL,
                    data={"KEY": api_key,
                          "ACTION": "INSERT",
                          "ADIF": adif_record},
                    timeout=_REQUEST_TIMEOUT)
                resp.raise_for_status()

                result_map = _parse_qrz_response(resp.text)
                status = result_map.get("status", "FAIL").upper()
                reason = result_map.get("reason", "")

                if status == "OK":
                    log_db.mark_qrz_uploaded(qso.id)
                    uploaded += 1
                elif "duplicate" in reason.lower():
                    log_db.mark_qrz_uploaded(qso.id)
                    skipped += 1
                    log.debug(f"QRZ: {qso.call} already in logbook (duplicate)")
                else:
                    failed += 1
                    errors.append(f"{qso.call}: {reason or 'unknown error'}")
                    log.warning(
                        f"QRZ logbook INSERT failed for {qso.call}: {reason}")

            except Exception as exc:
                failed += 1
                errors.append(f"{qso.call}: {exc}")
                log.error(f"QRZ upload error for {qso.call}: {exc}")

        self._notify("Upload complete.", 100)

        success = uploaded + skipped > 0 or failed == 0
        parts = []
        if uploaded:
            parts.append(f"{uploaded} uploaded")
        if skipped:
            parts.append(f"{skipped} already in QRZ (skipped)")
        if failed:
            parts.append(f"{failed} failed")
        msg = ", ".join(parts) if parts else "Nothing to do."

        return QRZSyncResult(
            success=success,
            uploaded=uploaded,
            skipped=skipped,
            failed=failed,
            message=msg,
            error="\n".join(errors[:5]) if errors else "")

    def _get_api_key(self) -> str:
        try:
            from core.credentials import get_store
            profile = self.cfg.get("profile.name", "default")
            return get_store(profile).retrieve("qrz_logbook_key")
        except Exception:
            return ""

    def _notify(self, msg: str, pct: int) -> None:
        if self._on_progress:
            try:
                self._on_progress(msg, pct)
            except Exception:
                pass


def _parse_qrz_response(text: str) -> dict:
    """
    Parse QRZ Logbook API response.
    Format: "status=OK;LOGIDS=1234567" or "status=FAIL;REASON=Duplicate"
    Returns dict with lowercase keys.
    """
    result = {}
    for part in text.strip().split(";"):
        if "=" in part:
            k, _, v = part.partition("=")
            result[k.strip().lower()] = v.strip()
    return result
