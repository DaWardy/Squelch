from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- network/lotw_sync.py
ARRL Logbook of the World (LoTW) integration.

Upload: signs ADIF log with TQSL, submits to LoTW.
Download: fetches QSL confirmations from LoTW API.

Requires: TQSL installed (tqsl.arrl.org).
LoTW credentials stored in OS keyring.
"""

import logging
import subprocess
import threading
import tempfile
import time
from pathlib import Path
from typing import Callable
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class LoTWResult:
    success:     bool
    uploaded:    int   = 0
    confirmations: int = 0
    message:     str   = ""
    error:       str   = ""


class LoTWSync:
    """
    Synchronizes QSO log with ARRL LoTW.
    Upload: ADIF → TQSL → signed TQ8 → LoTW HTTPS.
    Download: LoTW QSL confirmations → update log.
    """

    LOTW_UPLOAD_URL  = (
        "https://lotw.arrl.org/lotw-user-access/"
        "adif-upload.php")
    LOTW_FETCH_URL   = (
        "https://lotw.arrl.org/lotwuser/lotwreport.adi"
        "?login={user}&password={pass}"
        "&qso_query=1&qso_qslsince=2000-01-01"
        "&qso_owncall={callsign}&qso_qsldetail=yes")

    def __init__(self, config):
        self.cfg          = config
        self._on_progress: Callable = None
        self._on_complete: Callable = None

    def upload_async(self, log_db,
                     qsos=None) -> None:
        """Upload QSOs to LoTW in a background thread."""
        thread = threading.Thread(
            target=self._upload_worker,
            args=(log_db, qsos),
            daemon=True, name="LoTWUpload")
        thread.start()

    def _upload_worker(self, log_db, qsos):
        result = self._do_upload(log_db, qsos)
        if self._on_complete:
            try:
                self._on_complete(result)
            except Exception:
                pass

    def _do_upload(self, log_db,
                   qsos=None) -> LoTWResult:
        """
        Upload QSOs to LoTW.
        1. Export ADIF to temp file
        2. Sign with TQSL
        3. Submit signed file to LoTW
        """
        # Get TQSL path
        tqsl_path = self.cfg.get("paths.tqsl", "")
        if not tqsl_path or not Path(tqsl_path).exists():
            return LoTWResult(
                success=False,
                error="TQSL not found. Install from "
                      "tqsl.arrl.org and set path in "
                      "Settings → Paths.")

        # Get credentials
        try:
            from core.credentials import get_store
            store  = get_store(
                self.cfg.get("profile.name", "default"))
            lotw_pass = store.retrieve("lotw_password") or ""
        except Exception:
            lotw_pass = ""

        callsign = self.cfg.callsign
        lotw_user = self.cfg.get(
            "apis.lotw_user", "") or callsign
        if not lotw_user:
            return LoTWResult(
                success=False,
                error="LoTW username not set. "
                      "Configure in Settings → APIs.")

        self._notify_progress("Exporting ADIF…", 10)

        # Export ADIF to temp file
        try:
            fd, adif_path = tempfile.mkstemp(suffix=".adif")
            import os
            os.close(fd)
            adif_path = Path(adif_path)

            if qsos:
                from core.log_db import _adif_field, _utcnow
                lines = ["ADIF Export from Squelch\n"
                         f"<PROGRAMID:7>Squelch\n"
                         f"<EOH>\n"]
                for q in qsos:
                    from core.log_db import _qso_to_adif
                    lines.append(_qso_to_adif(q))
                adif_path.write_text(
                    "".join(lines), encoding="utf-8")
            else:
                count = log_db.export_adif(adif_path)
                if not count:
                    adif_path.unlink(missing_ok=True)
                    return LoTWResult(
                        success=False,
                        error="No QSOs to upload.")

        except Exception as e:
            return LoTWResult(
                success=False,
                error=f"ADIF export failed: {e}")

        self._notify_progress("Signing with TQSL…", 30)

        # Sign with TQSL
        try:
            fd2, signed_path = tempfile.mkstemp(suffix=".tq8")
            import os
            os.close(fd2)
            signed_path = Path(signed_path)

            cmd = [
                tqsl_path,
                "--batch",
                "-d",
                "-s",
                str(adif_path),
                "-o", str(signed_path),
                "-l", callsign,
            ]
            result = subprocess.run(  # nosec B603
                cmd,
                capture_output=True,
                text=True,
                timeout=60)

            adif_path.unlink(missing_ok=True)

            if result.returncode != 0:
                signed_path.unlink(missing_ok=True)
                err = (result.stderr or
                       result.stdout or
                       "TQSL failed").strip()[:200]
                return LoTWResult(
                    success=False,
                    error=f"TQSL signing failed: {err}")

        except subprocess.TimeoutExpired:
            return LoTWResult(
                success=False,
                error="TQSL timed out after 60 seconds.")
        except Exception as e:
            return LoTWResult(
                success=False,
                error=f"TQSL error: {e}")

        self._notify_progress("Uploading to LoTW…", 60)

        # Upload signed file to LoTW
        try:
            import requests
            with open(signed_path, "rb") as f:
                signed_data = f.read()

            signed_path.unlink(missing_ok=True)

            resp = requests.post(
                self.LOTW_UPLOAD_URL,
                data={"upfile": signed_data},
                auth=(lotw_user, lotw_pass),
                timeout=30)

            if resp.status_code != 200:
                return LoTWResult(
                    success=False,
                    error=(f"LoTW upload failed: "
                           f"HTTP {resp.status_code}"))

            # LoTW returns text with result
            response_text = resp.text[:500]
            if "Errors" in response_text:
                return LoTWResult(
                    success=False,
                    error=f"LoTW error: {response_text}")

            self._notify_progress("Upload complete", 100)
            return LoTWResult(
                success=True,
                message=f"Uploaded to LoTW successfully.")

        except Exception as e:
            return LoTWResult(
                success=False,
                error=f"Upload error: {e}")

    def download_confirmations_async(self) -> None:
        """Download QSL confirmations from LoTW."""
        threading.Thread(
            target=self._download_worker,
            daemon=True,
            name="LoTWDownload").start()

    def _download_worker(self):
        result = self._do_download()
        if self._on_complete:
            try:
                self._on_complete(result)
            except Exception:
                pass

    def _do_download(self) -> LoTWResult:
        """Fetch LoTW confirmations via ADIF API."""
        callsign  = self.cfg.callsign
        lotw_user = self.cfg.get("apis.lotw_user",
                                  callsign) or callsign
        if not lotw_user:
            return LoTWResult(
                success=False,
                error="LoTW username not set.")
        try:
            from core.credentials import get_store
            store     = get_store(
                self.cfg.get("profile.name", "default"))
            lotw_pass = store.retrieve(
                "lotw_password") or ""
        except Exception:
            lotw_pass = ""

        if not lotw_pass:
            return LoTWResult(
                success=False,
                error="LoTW password not set. "
                      "Configure in Settings → APIs.")

        try:
            import requests
            url = (
                f"https://lotw.arrl.org/lotwuser/"
                f"lotwreport.adi?"
                f"login={lotw_user}"
                f"&password={lotw_pass}"
                f"&qso_query=1"
                f"&qso_qslsince=2000-01-01"
                f"&qso_owncall={callsign}"
                f"&qso_qsldetail=yes")

            resp = requests.get(url, timeout=30)
            if resp.status_code != 200:
                return LoTWResult(
                    success=False,
                    error=(f"LoTW fetch failed: "
                           f"HTTP {resp.status_code}"))

            # Parse ADIF confirmations
            import re
            confirms = re.findall(
                r'<APP_LoTW_NUMREC:(\d+)>', resp.text)
            count = int(confirms[0]) if confirms else 0

            return LoTWResult(
                success=True,
                confirmations=count,
                message=(f"Downloaded {count} "
                         f"LoTW confirmations."))

        except Exception as e:
            return LoTWResult(
                success=False,
                error=f"Download error: {e}")

    def _notify_progress(self, msg: str, pct: int):
        if self._on_progress:
            try:
                self._on_progress(msg, pct)
            except Exception:
                pass

    def on_progress(self, cb: Callable):
        self._on_progress = cb

    def on_complete(self, cb: Callable):
        self._on_complete = cb
