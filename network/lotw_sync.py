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
from pathlib import Path
from typing import Callable
from dataclasses import dataclass
from core.sanitize import redact_url as _redact_url

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

    def _export_adif_to_temp(self, log_db, qsos) -> "tuple[Path | None, LoTWResult | None]":
        """Write QSOs to a temp ADIF file. Returns (path, None) or (None, error)."""
        import os
        try:
            fd, adif_path = tempfile.mkstemp(suffix=".adif")
            os.close(fd)
            adif_path = Path(adif_path)
            if qsos:
                lines = ["ADIF Export from Squelch\n<PROGRAMID:7>Squelch\n<EOH>\n"]
                for q in qsos:
                    from core.log_db import _qso_to_adif
                    lines.append(_qso_to_adif(q))
                adif_path.write_text("".join(lines), encoding="utf-8")
            else:
                count = log_db.export_adif(adif_path)
                if not count:
                    adif_path.unlink(missing_ok=True)
                    return None, LoTWResult(success=False, error="No QSOs to upload.")
            return adif_path, None
        except Exception as e:
            return None, LoTWResult(success=False, error=f"ADIF export failed: {e}")

    def _sign_adif_with_tqsl(self, tqsl_path: str, callsign: str,
                              adif_path: "Path") -> "tuple[Path | None, LoTWResult | None]":
        """Sign an ADIF file with TQSL. Returns (signed_path, None) or (None, error)."""
        import os
        try:
            fd2, signed_path = tempfile.mkstemp(suffix=".tq8")
            os.close(fd2)
            signed_path = Path(signed_path)
            cmd = [tqsl_path, "--batch", "-d", "-s",
                   str(adif_path), "-o", str(signed_path), "-l", callsign]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)  # nosec B603
            adif_path.unlink(missing_ok=True)
            if result.returncode != 0:
                signed_path.unlink(missing_ok=True)
                err = (result.stderr or result.stdout or "TQSL failed").strip()[:200]
                return None, LoTWResult(success=False, error=f"TQSL signing failed: {err}")
            return signed_path, None
        except subprocess.TimeoutExpired:
            return None, LoTWResult(success=False, error="TQSL timed out after 60 seconds.")
        except Exception as e:
            return None, LoTWResult(success=False, error=f"TQSL error: {e}")

    def _submit_to_lotw(self, signed_path: "Path",
                        lotw_user: str, lotw_pass: str) -> LoTWResult:
        """POST signed TQ8 file to LoTW. Returns LoTWResult."""
        try:
            import requests
            signed_data = signed_path.read_bytes()
            signed_path.unlink(missing_ok=True)
            resp = requests.post(self.LOTW_UPLOAD_URL,
                                 data={"upfile": signed_data},
                                 auth=(lotw_user, lotw_pass),
                                 timeout=30)
            if resp.status_code != 200:
                return LoTWResult(success=False,
                                  error=f"LoTW upload failed: HTTP {resp.status_code}")
            response_text = resp.text[:500]
            if "Errors" in response_text:
                return LoTWResult(success=False, error=f"LoTW error: {response_text}")
            self._notify_progress("Upload complete", 100)
            return LoTWResult(success=True, message="Uploaded to LoTW successfully.")
        except Exception as e:
            return LoTWResult(success=False, error=f"Upload error: {e}")

    def _do_upload(self, log_db, qsos=None) -> LoTWResult:
        """Upload QSOs to LoTW: export ADIF → sign with TQSL → submit."""
        tqsl_path = self.cfg.get("paths.tqsl", "")
        if not tqsl_path or not Path(tqsl_path).exists():
            return LoTWResult(success=False,
                              error="TQSL not found. Install from "
                                    "tqsl.arrl.org and set path in Settings → Paths.")

        try:
            from core.credentials import get_store
            store     = get_store(self.cfg.get("profile.name", "default"))
            lotw_pass = store.retrieve("lotw_password") or ""
        except Exception:
            lotw_pass = ""

        callsign  = self.cfg.callsign
        lotw_user = self.cfg.get("apis.lotw_user", "") or callsign
        if not lotw_user:
            return LoTWResult(success=False,
                              error="LoTW username not set. Configure in Settings → APIs.")

        self._notify_progress("Exporting ADIF…", 10)
        adif_path, err = self._export_adif_to_temp(log_db, qsos)
        if err:
            return err

        self._notify_progress("Signing with TQSL…", 30)
        signed_path, err = self._sign_adif_with_tqsl(tqsl_path, callsign, adif_path)
        if err:
            return err

        self._notify_progress("Uploading to LoTW…", 60)
        return self._submit_to_lotw(signed_path, lotw_user, lotw_pass)

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
