from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/tabs/log_upload_mixin.py

Logbook upload / sync handlers for the Log tab, extracted from log_tab.py
(HOUSE-CS complexity split). Covers the five online logbook services:
LoTW, QRZ Logbook, ClubLog, eQSL.cc, HRDLog.net.

`_LogUploadMixin` is mixed into `LogTab`. It relies on host-class state:
  * self.cfg     — Config (each sync client reads credentials from it)
  * self.log_db  — LogDB (pending queues, totals, ADIF export, mark-uploaded)
  * self._load_log()  — refresh the table after an upload completes
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QMessageBox, QProgressDialog


class _LogUploadMixin:
    """LoTW / QRZ / ClubLog / eQSL / HRDLog upload dialogs + completion slots."""

    def _show_lotw_queue(self):
        from network.lotw_sync import LoTWSync
        from PyQt6.QtWidgets import QProgressDialog
        pending = self.log_db.lotw_pending()
        if not pending:
            QMessageBox.information(
                self, "LoTW Queue",
                "No QSOs pending LoTW upload.\n\n"
                "All logged QSOs have been uploaded.")
            return

        reply = QMessageBox.question(
            self, "Upload to LoTW",
            f"{len(pending)} QSOs pending upload.\n\n"
            "Upload to LoTW now via TQSL?\n\n"
            "Requires:\n"
            "• TQSL installed (tqsl.arrl.org)\n"
            "• LoTW credentials in Settings → APIs",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Show progress
        prog = QProgressDialog(
            "Uploading to LoTW…", "Cancel",
            0, 100, self)
        prog.setWindowTitle("LoTW Upload")
        prog.setWindowModality(
            Qt.WindowModality.WindowModal)
        prog.show()

        sync = LoTWSync(self.cfg)

        def _on_progress(msg: str, pct: int):
            QTimer.singleShot(0, lambda:
                (prog.setLabelText(msg),
                 prog.setValue(pct)))

        def _on_complete(result):
            QTimer.singleShot(0, lambda r=result:
                self._lotw_done(r, prog))

        sync.on_progress(_on_progress)
        sync.on_complete(_on_complete)
        sync.upload_async(self.log_db, pending)

    def _lotw_done(self, result, prog):
        prog.close()
        if result.success:
            QMessageBox.information(
                self, "LoTW Upload Complete",
                f"{result.message}\n\n"
                "LoTW confirmations typically arrive "
                "within 24-48 hours.")
            # Mark as uploaded
            for q in self.log_db.lotw_pending():
                self.log_db.mark_lotw_uploaded(q.id)
            self._load_log()
        else:
            QMessageBox.warning(
                self, "LoTW Upload Failed",
                f"Upload failed:\n{result.error}\n\n"
                "Check Settings → APIs for credentials\n"
                "and Settings → Paths for TQSL location.")

    def _show_qrz_queue(self):
        from network.qrz_sync import QRZSync
        pending = self.log_db.qrz_pending()
        if not pending:
            QMessageBox.information(
                self, "QRZ Queue",
                "No QSOs pending QRZ sync.\n\n"
                "All logged QSOs have been uploaded.")
            return

        reply = QMessageBox.question(
            self, "Upload to QRZ Logbook",
            f"{len(pending)} QSOs pending upload.\n\n"
            "Upload to QRZ.com logbook now?\n\n"
            "Requires:\n"
            "• QRZ Logbook API key in Settings → APIs\n"
            "  (get it free at qrz.com → Logbook → Settings)",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        prog = QProgressDialog(
            "Uploading to QRZ Logbook…", "Cancel",
            0, 100, self)
        prog.setWindowTitle("QRZ Logbook Upload")
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.show()

        sync = QRZSync(self.cfg)

        def _on_progress(msg: str, pct: int):
            QTimer.singleShot(0, lambda: (
                prog.setLabelText(msg),
                prog.setValue(pct)))

        def _on_complete(result):
            QTimer.singleShot(0,
                lambda r=result: self._qrz_done(r, prog))

        sync.on_progress(_on_progress)
        sync.on_complete(_on_complete)
        sync.upload_async(self.log_db, pending)

    def _qrz_done(self, result, prog):
        prog.close()
        if result.success:
            QMessageBox.information(
                self, "QRZ Upload Complete",
                f"{result.message}\n\n"
                "QSOs are now visible in your QRZ logbook.")
            self._load_log()
        else:
            QMessageBox.warning(
                self, "QRZ Upload Failed",
                f"Upload failed:\n{result.error}\n\n"
                "Check Settings → APIs for your QRZ Logbook API key.\n"
                "Get the key free at qrz.com → Logbook → Settings.")

    def _show_clublog_upload(self):
        from network.dx_cluster import ClubLogClient
        client = ClubLogClient(self.cfg)
        if not client.has_credentials:
            QMessageBox.warning(
                self, "ClubLog Credentials Missing",
                "No ClubLog credentials found.\n\n"
                "Add your email and password in Settings → APIs → ClubLog.\n"
                "Register free at clublog.org.")
            return

        total = self.log_db.total_qsos()
        if not total:
            QMessageBox.information(
                self, "ClubLog",
                "No QSOs in log to upload.")
            return

        reply = QMessageBox.question(
            self, "Upload to ClubLog",
            f"Upload all {total} QSOs to ClubLog now?\n\n"
            "ClubLog will merge duplicates automatically.",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        prog = QProgressDialog(
            "Building ADIF for ClubLog…", "Cancel",
            0, 0, self)
        prog.setWindowTitle("ClubLog Upload")
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.show()

        import threading, tempfile
        from pathlib import Path as _P
        def _worker():
            try:
                fd, tmp = tempfile.mkstemp(suffix=".adif")
                import os; os.close(fd)
                tmp_path = _P(tmp)
                self.log_db.export_adif(tmp_path)
                adif = tmp_path.read_text(encoding="utf-8")
                tmp_path.unlink(missing_ok=True)
                ok = client.upload_adif(adif)
                QTimer.singleShot(0, lambda: self._clublog_done(ok, prog))
            except Exception as exc:
                QTimer.singleShot(0, lambda e=exc:
                    self._clublog_done(False, prog, str(e)))
        threading.Thread(target=_worker, daemon=True,
                         name="ClubLogUpload").start()

    def _clublog_done(self, ok: bool, prog, error: str = "") -> None:
        prog.close()
        if ok:
            QMessageBox.information(
                self, "ClubLog Upload Complete",
                "Log uploaded to ClubLog successfully.\n\n"
                "ClubLog processes uploads within a few minutes.")
        else:
            QMessageBox.warning(
                self, "ClubLog Upload Failed",
                f"Upload failed.\n{error}\n\n"
                "Check Settings → APIs for your ClubLog credentials.")

    def _show_eqsl_upload(self):
        from network.eqsl_sync import EQSLSync
        total = self.log_db.total_qsos()
        if not total:
            QMessageBox.information(
                self, "eQSL", "No QSOs in log to upload.")
            return

        reply = QMessageBox.question(
            self, "Upload to eQSL.cc",
            f"Upload all {total} QSOs to eQSL.cc now?\n\n"
            "Requires eQSL username and password in Settings → APIs.",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        prog = QProgressDialog(
            "Uploading to eQSL.cc…", "Cancel",
            0, 100, self)
        prog.setWindowTitle("eQSL Upload")
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.show()

        sync = EQSLSync(self.cfg)

        def _on_progress(msg: str, pct: int):
            QTimer.singleShot(0, lambda: (
                prog.setLabelText(msg),
                prog.setValue(pct)))

        def _on_complete(result):
            QTimer.singleShot(0,
                lambda r=result: self._eqsl_done(r, prog))

        sync.on_progress(_on_progress)
        sync.on_complete(_on_complete)
        sync.upload_async(self.log_db)

    def _eqsl_done(self, result, prog) -> None:
        prog.close()
        if result.success:
            QMessageBox.information(
                self, "eQSL Upload Complete",
                f"{result.message}")
        else:
            QMessageBox.warning(
                self, "eQSL Upload Failed",
                f"Upload failed:\n{result.error}\n\n"
                "Check Settings → APIs for your eQSL credentials.")

    def _show_hrdlog_upload(self):
        from network.hrdlog_sync import HRDLogSync
        total = self.log_db.total_qsos()
        if not total:
            QMessageBox.information(
                self, "HRDLog", "No QSOs in log to upload.")
            return

        reply = QMessageBox.question(
            self, "Upload to HRDLog.net",
            f"Upload all {total} QSOs to HRDLog.net now?\n\n"
            "Requires callsign and API key in Settings → APIs.",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        prog = QProgressDialog(
            "Uploading to HRDLog.net…", "Cancel",
            0, 100, self)
        prog.setWindowTitle("HRDLog Upload")
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.show()

        sync = HRDLogSync(self.cfg)

        def _on_progress(msg: str, pct: int):
            QTimer.singleShot(0, lambda: (
                prog.setLabelText(msg),
                prog.setValue(pct)))

        def _on_complete(result):
            QTimer.singleShot(0,
                lambda r=result: self._hrdlog_done(r, prog))

        sync.on_progress(_on_progress)
        sync.on_complete(_on_complete)
        sync.upload_async(self.log_db)

    def _hrdlog_done(self, result, prog) -> None:
        prog.close()
        if result.success:
            QMessageBox.information(
                self, "HRDLog Upload Complete",
                f"{result.message}")
        else:
            QMessageBox.warning(
                self, "HRDLog Upload Failed",
                f"Upload failed:\n{result.error}\n\n"
                "Check Settings → APIs for your HRDLog credentials.")
