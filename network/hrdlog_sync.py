from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- network/hrdlog_sync.py
HRDLog.net logbook upload integration.

Uploads QSOs as ADIF to HRDLog.net via their logbook API.
Free account at hrdlog.net.

API protocol:
  POST https://www.hrdlog.net/api/logbooksubmit/
  Form fields: Callsign=<callsign>, Apikey=<key>, Adif=<adif>
  Response: "OK" on success, error text on failure.
"""

import logging
import threading
from dataclasses import dataclass
from typing import Callable

from core.netlog import record_connection

log = logging.getLogger(__name__)

HRDLOG_UPLOAD_URL = "https://www.hrdlog.net/api/logbooksubmit/"
_REQUEST_TIMEOUT  = 30  # seconds


@dataclass
class HRDLogResult:
    success: bool
    message: str = ""
    error:   str = ""


class HRDLogSync:
    """
    Uploads ADIF log to HRDLog.net.

    Usage:
        sync = HRDLogSync(cfg)
        sync.on_complete(lambda result: ...)
        sync.upload_async(log_db)
    """

    def __init__(self, config):
        self.cfg           = config
        self._on_progress: Callable | None = None
        self._on_complete: Callable | None = None

    def on_progress(self, fn: Callable) -> None:
        self._on_progress = fn

    def on_complete(self, fn: Callable) -> None:
        self._on_complete = fn

    def upload_async(self, log_db) -> None:
        """Export full log as ADIF and upload in a background thread."""
        thread = threading.Thread(
            target=self._upload_worker,
            args=(log_db,),
            daemon=True,
            name="HRDLogUpload")
        thread.start()

    def _upload_worker(self, log_db) -> None:
        result = self._do_upload(log_db)
        if self._on_complete:
            try:
                self._on_complete(result)
            except Exception:
                pass

    def _do_upload(self, log_db) -> HRDLogResult:
        callsign, apikey = self._get_credentials()
        if not callsign or not apikey:
            return HRDLogResult(
                success=False,
                error="HRDLog callsign and API key not set.\n"
                      "Add them in Settings → APIs → HRDLog.net.")

        try:
            import requests
        except ImportError:
            return HRDLogResult(
                success=False,
                error="requests library not available. Run: pip install requests")

        self._notify("Exporting log to ADIF…", 10)

        try:
            import tempfile, os
            from pathlib import Path
            fd, tmp = tempfile.mkstemp(suffix=".adif")
            os.close(fd)
            tmp_path = Path(tmp)
            count = log_db.export_adif(tmp_path)
            if not count:
                tmp_path.unlink(missing_ok=True)
                return HRDLogResult(success=True, message="No QSOs to upload.")
            adif_content = tmp_path.read_text(encoding="utf-8")
            tmp_path.unlink(missing_ok=True)
        except Exception as exc:
            return HRDLogResult(
                success=False, error=f"ADIF export failed: {exc}")

        self._notify(f"Uploading {count} QSOs to HRDLog.net…", 40)

        try:
            record_connection("hrdlog_upload", HRDLOG_UPLOAD_URL, "POST")
            resp = requests.post(
                HRDLOG_UPLOAD_URL,
                data={
                    "Callsign": callsign,
                    "Apikey":   apikey,
                    "Adif":     adif_content,
                },
                timeout=_REQUEST_TIMEOUT)
            resp.raise_for_status()
        except Exception as exc:
            return HRDLogResult(
                success=False,
                error=f"Network error: {exc}")

        self._notify("Upload complete.", 100)

        body = resp.text.strip()
        if body.upper() == "OK":
            return HRDLogResult(
                success=True,
                message=f"{count} QSOs uploaded to HRDLog.net successfully.")
        return HRDLogResult(success=False, error=body[:300])

    def _get_credentials(self) -> tuple[str, str]:
        try:
            from core.credentials import get_store
            store = get_store(self.cfg.get("profile.name", "default"))
            callsign = self.cfg.get("apis.hrdlog_callsign", "")
            apikey = store.retrieve("hrdlog_key")
            return callsign, apikey
        except Exception:
            return "", ""

    def _notify(self, msg: str, pct: int) -> None:
        if self._on_progress:
            try:
                self._on_progress(msg, pct)
            except Exception:
                pass
