from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- network/eqsl_sync.py
eQSL.cc logbook upload integration.

Uploads QSOs as ADIF to eQSL.cc via their UploadADIF endpoint.
Free account at eqsl.cc.

API protocol:
  POST https://www.eqsl.cc/qslcard/UploadADIF.aspx
  Form fields: ADIFData=<adif>, QTHNickname=<username>, Password=<password>
  Response: text — contains "added" on success, "Error" on failure.
  Duplicate handling: eQSL silently accepts duplicates (re-upload safe).
"""

import logging
import threading
from dataclasses import dataclass
from typing import Callable

from core.netlog import record_connection

log = logging.getLogger(__name__)

EQSL_UPLOAD_URL = "https://www.eqsl.cc/qslcard/UploadADIF.aspx"
_REQUEST_TIMEOUT = 30  # seconds — eQSL can be slow on large uploads


@dataclass
class EQSLResult:
    success: bool
    message: str = ""
    error:   str = ""


class EQSLSync:
    """
    Uploads ADIF log to eQSL.cc.

    Usage:
        sync = EQSLSync(cfg)
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
            name="EQSLUpload")
        thread.start()

    def _upload_worker(self, log_db) -> None:
        result = self._do_upload(log_db)
        if self._on_complete:
            try:
                self._on_complete(result)
            except Exception:
                pass

    def _do_upload(self, log_db) -> EQSLResult:
        username, password = self._get_credentials()
        if not username or not password:
            return EQSLResult(
                success=False,
                error="eQSL username and password not set.\n"
                      "Add them in Settings → APIs → eQSL.cc.")

        try:
            import requests
        except ImportError:
            return EQSLResult(
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
                return EQSLResult(success=True, message="No QSOs to upload.")
            adif_content = tmp_path.read_text(encoding="utf-8")
            tmp_path.unlink(missing_ok=True)
        except Exception as exc:
            return EQSLResult(
                success=False, error=f"ADIF export failed: {exc}")

        self._notify(f"Uploading {count} QSOs to eQSL.cc…", 40)

        try:
            record_connection("eqsl_upload", EQSL_UPLOAD_URL, "POST")
            resp = requests.post(
                EQSL_UPLOAD_URL,
                data={
                    "ADIFData":     adif_content,
                    "QTHNickname":  username,
                    "Password":     password,
                },
                timeout=_REQUEST_TIMEOUT)
            resp.raise_for_status()
        except Exception as exc:
            return EQSLResult(
                success=False,
                error=f"Network error: {exc}")

        self._notify("Upload complete.", 100)

        body = resp.text.strip()
        if "error" in body.lower():
            return EQSLResult(success=False, error=body[:300])
        return EQSLResult(
            success=True,
            message=f"{count} QSOs uploaded to eQSL.cc successfully.")

    def _get_credentials(self) -> tuple[str, str]:
        try:
            from core.credentials import get_store
            store = get_store(self.cfg.get("profile.name", "default"))
            username = self.cfg.get("apis.eqsl_username", "")
            password = store.retrieve("eqsl_password")
            return username, password
        except Exception:
            return "", ""

    def _notify(self, msg: str, pct: int) -> None:
        if self._on_progress:
            try:
                self._on_progress(msg, pct)
            except Exception:
                pass
