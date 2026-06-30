from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/tabs/log_io_mixin.py

Logbook import / export handlers for the Log tab, extracted from log_tab.py
(HOUSE-CS complexity split). Covers ADIF / CSV / Cabrillo export (filter-aware)
and ADIF import (with duplicate skip + field mapping).

`_LogIOMixin` is mixed into `LogTab`. It relies on host-class state:
  * self.cfg               — Config (grid, contest exchange, operating callsign)
  * self.log_db            — LogDB (export_adif/csv/cabrillo, has_qso_at, log_qso)
  * self._all_qsos         — full QSO list (filter-active detection)
  * self._current_filtered — active filter result, if any
  * self._load_log()       — refresh the table after an import
"""

from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from core.log_db import QSO
from core.guest_op import operating_callsign
from core.validator import callsign_soft, grid_square_soft


class _LogIOMixin:
    """ADIF / CSV / Cabrillo export + ADIF import handlers."""

    def _export_qsos(self) -> list[QSO]:
        """Return QSOs to export: filtered set when a filter is active."""
        filtered = getattr(self, "_current_filtered", [])
        all_qs   = getattr(self, "_all_qsos", [])
        if filtered and len(filtered) < len(all_qs):
            return filtered
        return all_qs or self.log_db.recent_qsos(limit=999999)

    def _export_adif(self):
        qsos = self._export_qsos()
        is_filtered = len(qsos) < len(self._all_qsos)
        label = (f"Export ADIF — {len(qsos)} filtered QSOs"
                 if is_filtered else "Export ADIF")
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr(label),
            f"squelch_log_{datetime.now().strftime('%Y%m%d')}.adi",
            "ADIF Files (*.adi *.adif)")
        if not path:
            return
        try:
            count = self.log_db.export_adif(Path(path), qsos=qsos)
            QMessageBox.information(
                self, self.tr("Export Complete"),
                f"Exported {count} QSOs to {Path(path).name}")
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", str(e))

    def _export_csv(self):
        qsos = self._export_qsos()
        is_filtered = len(qsos) < len(self._all_qsos)
        label = (f"Export CSV — {len(qsos)} filtered QSOs"
                 if is_filtered else "Export CSV")
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr(label),
            f"squelch_log_{datetime.now().strftime('%Y%m%d')}.csv",
            "CSV Files (*.csv)")
        if not path:
            return
        try:
            count = self.log_db.export_csv(Path(path), qsos=qsos)
            QMessageBox.information(
                self, self.tr("Export Complete"),
                f"Exported {count} QSOs to {Path(path).name}")
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", str(e))

    def _export_cabrillo(self):
        """Export log in Cabrillo 3.0 format for contest submission."""
        from PyQt6.QtWidgets import (QDialog, QFormLayout, QLineEdit,
                                     QDialogButtonBox, QFileDialog, QLabel)
        from core.guest_op import operating_callsign

        # Pre-export dialog: let user confirm contest name and exchange.
        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("Cabrillo Export"))
        dlg.setMinimumWidth(340)
        fl = QFormLayout(dlg)
        fl.setSpacing(10)
        fl.setContentsMargins(16, 16, 16, 16)

        contest_edit = QLineEdit()
        contest_edit.setPlaceholderText("e.g. CQ-WW-SSB")
        fl.addRow("Contest name:", contest_edit)

        exchange_edit = QLineEdit()
        exchange_edit.setText(
            self.cfg.get("station.contest_exchange", "") or "")
        exchange_edit.setPlaceholderText("e.g. 5NN OH")
        fl.addRow("My exchange (sent):", exchange_edit)

        note = QLabel(self.tr(
            "Received exchange taken from QSO comment field.\n"
            "Leave contest name blank to fill in manually."))
        note.setStyleSheet("font-size:10px;color:#888888;")
        fl.addRow(note)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        fl.addRow(bb)

        if not dlg.exec():
            return

        contest  = contest_edit.text().strip()
        exchange = exchange_edit.text().strip()
        if exchange:
            self.cfg.set("station.contest_exchange", exchange)

        cs   = operating_callsign(self.cfg) or "NOCALL"
        grid = self.cfg.grid or ""
        qsos = self._export_qsos()
        is_filtered = len(qsos) < len(self._all_qsos)
        label = (f"Export Cabrillo — {len(qsos)} filtered QSOs"
                 if is_filtered else "Export Cabrillo")

        path, _ = QFileDialog.getSaveFileName(
            self, self.tr(label),
            f"{cs.lower()}.cbr",
            "Cabrillo (*.cbr *.log);;All Files (*)")
        if not path:
            return
        try:
            count = self.log_db.export_cabrillo(
                Path(path), qsos=qsos,
                my_call=cs, my_grid=grid,
                contest=contest, exchange=exchange)
            QMessageBox.information(
                self, self.tr("Cabrillo Exported"),
                f"Exported {count} QSOs to {Path(path).name}\n\n"
                "Review CONTEST: header before submitting\n"
                "to the contest robot.")
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", str(e))

    def _import_adif(self):
        from ui.tabs.log_tab import _adif_to_iso
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Import ADIF"),
            "", "ADIF Files (*.adi *.adif *.ADI *.ADIF)")
        if not path:
            return
        try:
            import adif_io
            with open(path, 'r', encoding='utf-8',
                      errors='replace') as f:
                records, _ = adif_io.read_from_string(f.read())

            imported = skipped = errors = 0
            my_call = operating_callsign(self.cfg)
            for record in records:
                try:
                    call = callsign_soft(record.get('CALL', ''))
                    if not call:
                        continue
                    dt_on = _adif_to_iso(
                        record.get('QSO_DATE', ''),
                        record.get('TIME_ON', ''))
                    if self.log_db.has_qso_at(call, dt_on):
                        skipped += 1
                        continue
                    try:
                        freq_hz = int(float(
                            record.get('FREQ', 0) or 0) * 1e6)
                    except (ValueError, TypeError):
                        freq_hz = 0
                    try:
                        tx_pwr = float(record.get('TX_PWR', 0) or 0)
                    except (ValueError, TypeError):
                        tx_pwr = 0.0
                    try:
                        cqz = int(record.get('CQZ', 0) or 0)
                    except (ValueError, TypeError):
                        cqz = 0
                    try:
                        ituz = int(record.get('ITUZ', 0) or 0)
                    except (ValueError, TypeError):
                        ituz = 0
                    dt_off = _adif_to_iso(
                        record.get('QSO_DATE_OFF',
                                   record.get('QSO_DATE', '')),
                        record.get('TIME_OFF', ''))
                    qso = QSO(
                        call         = call,
                        datetime_on  = dt_on,
                        datetime_off = dt_off,
                        band         = record.get('BAND', '').lower(),
                        freq_hz      = freq_hz,
                        mode         = record.get('MODE', '').upper(),
                        submode      = record.get('SUBMODE', '').upper(),
                        rst_sent     = record.get('RST_SENT', '59'),
                        rst_rcvd     = record.get('RST_RCVD', '59'),
                        grid         = grid_square_soft(
                            record.get('GRIDSQUARE', '')),
                        name         = record.get('NAME', '')[:50],
                        comment      = (record.get('COMMENT', '')
                                        or record.get('NOTES', ''))[:200],
                        dxcc         = record.get('DXCC', ''),
                        country      = record.get('COUNTRY', '')[:60],
                        state        = record.get('STATE', '')[:10],
                        cqz          = cqz,
                        ituz         = ituz,
                        tx_pwr_w     = tx_pwr,
                        my_call      = my_call,
                        my_grid      = self.cfg.grid,
                        source       = "adif_import",
                    )
                    self.log_db.log_qso(qso)
                    imported += 1
                except Exception:
                    errors += 1

            self._load_log()
            msg = f"Imported {imported} QSOs."
            if skipped:
                msg += f"\nSkipped {skipped} duplicates."
            if errors:
                msg += f"\n{errors} records had errors and were skipped."
            QMessageBox.information(
                self, self.tr("Import Complete"), msg)
        except Exception as e:
            QMessageBox.warning(
                self, "Import Failed", str(e))
