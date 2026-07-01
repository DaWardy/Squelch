from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/tabs/log_entry_mixin.py

Manual QSO-entry dialog for the Log tab, extracted from log_tab.py
(HOUSE-CS complexity split). Builds the entry form, wires callsign
auto-complete / QRZ lookup / inline duplicate-check, and logs on accept.

`_LogEntryMixin` is mixed into `LogTab`. It relies on host-class state:
  * self.cfg            — Config (freq units, location, dupe-warn pref, grid)
  * self.log_db         — LogDB (distinct_callsigns, last_qso_with, is_duplicate,
                          worked_before, log_qso)
  * self._BANDS / self._MODES / self._RST_DEFAULTS  — class-level field choices
  * self._load_log()    — refresh the table after a QSO is logged
"""

from PyQt6.QtCore import Qt, QDateTime
from PyQt6.QtWidgets import (
    QLineEdit, QLabel, QDateTimeEdit, QDialog,
    QFormLayout, QDialogButtonBox, QMessageBox,
)

from core.freq_format import freq_placeholder, freq_label, parse_freq_input
from core.guest_op import operating_callsign
from core.log_db import QSO
from core.validator import callsign_soft, grid_square_soft


class _LogEntryMixin:
    """Manual QSO entry: form build, field wiring, and log-on-accept."""

    def _build_manual_entry_fields(self, lay: "QFormLayout") -> "dict":
        """Populate *lay* with QSO entry widgets; return fields dict."""
        from PyQt6.QtWidgets import QComboBox
        cs_edit = QLineEdit()
        cs_edit.setPlaceholderText("e.g. W4XYZ")
        cs_edit.setMaxLength(15)
        lay.addRow("Callsign:", cs_edit)

        dupe_label = QLabel("")
        dupe_label.setStyleSheet("font-size:10px;font-style:italic;")
        lay.addRow("", dupe_label)

        _fu = self.cfg.get("display.freq_units", "MHz") if self.cfg else "MHz"
        freq_edit = QLineEdit()
        freq_edit.setPlaceholderText(freq_placeholder(_fu))
        freq_edit.setMaxLength(16)
        freq_edit.setToolTip(
            f"Frequency in {_fu} — auto-fills Band when recognised")
        lay.addRow(f"{freq_label(_fu)}:", freq_edit)

        band_combo = QComboBox()
        band_combo.addItems(self._BANDS)
        band_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        band_combo.setCurrentText("20m")
        lay.addRow("Band:", band_combo)

        def _freq_to_band():
            from core.band_plan import band_at_freq
            hz = parse_freq_input(freq_edit.text(), _fu)
            if hz:
                b = band_at_freq(hz)
                if b:
                    band_combo.setCurrentText(b.name)
        freq_edit.editingFinished.connect(_freq_to_band)

        now_utc = QDateTime.currentDateTimeUtc()
        dt_edit = QDateTimeEdit(now_utc)
        dt_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        dt_edit.setTimeSpec(Qt.TimeSpec.UTC)
        dt_edit.setToolTip("QSO date/time in UTC")
        lay.addRow("DateTime (UTC):", dt_edit)

        mode_combo = QComboBox()
        mode_combo.addItems(self._MODES)
        mode_combo.setEditable(True)
        mode_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        mode_combo.setCurrentText("SSB")
        lay.addRow("Mode:", mode_combo)

        rst_sent = QLineEdit("59")
        rst_sent.setMaxLength(6)
        rst_rcvd = QLineEdit("59")
        rst_rcvd.setMaxLength(6)
        mode_combo.currentTextChanged.connect(
            lambda m: (rst_sent.setText(self._RST_DEFAULTS.get(m, "59")),
                       rst_rcvd.setText(self._RST_DEFAULTS.get(m, "59"))))
        lay.addRow("RST Sent:", rst_sent)
        lay.addRow("RST Rcvd:", rst_rcvd)

        grid_edit = QLineEdit()
        grid_edit.setPlaceholderText("e.g. DM79rr")
        grid_edit.setMaxLength(8)
        lay.addRow("Their Grid:", grid_edit)

        name_edit = QLineEdit()
        name_edit.setMaxLength(50)
        lay.addRow("Name:", name_edit)

        lkp_status = QLabel("")
        lkp_status.setStyleSheet("color:#888;font-style:italic;font-size:10px;")
        lay.addRow("", lkp_status)

        bearing_label = QLabel("")
        bearing_label.setStyleSheet("color:#aaa;font-size:10px;")
        lay.addRow("Path:", bearing_label)

        comment_edit = QLineEdit()
        comment_edit.setMaxLength(200)
        lay.addRow("Comment:", comment_edit)

        return {
            "cs_edit": cs_edit, "freq_edit": freq_edit,
            "band_combo": band_combo, "dt_edit": dt_edit,
            "mode_combo": mode_combo, "rst_sent": rst_sent,
            "rst_rcvd": rst_rcvd, "grid_edit": grid_edit,
            "name_edit": name_edit, "lkp_status": lkp_status,
            "bearing_label": bearing_label,
            "comment_edit": comment_edit,
            "dupe_label": dupe_label,
            "_qrz_info": None,
        }

    def _build_manual_entry_dialog(self):
        """Build and return (dialog, fields_dict) for manual QSO entry."""
        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("Manual QSO Entry"))
        dlg.setMinimumWidth(420)
        lay = QFormLayout(dlg)
        lay.setSpacing(8)
        fields = self._build_manual_entry_fields(lay)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addRow(btns)
        return dlg, fields

    def _wire_callsign_autocomplete(self, f: dict) -> None:
        """Attach QCompleter to cs_edit from local log; pre-fill name/grid on pick."""
        from PyQt6.QtWidgets import QCompleter
        from PyQt6.QtCore import QStringListModel, Qt

        calls = self.log_db.distinct_callsigns()
        model = QStringListModel(calls)
        comp = QCompleter()
        comp.setModel(model)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setCompletionMode(
            QCompleter.CompletionMode.InlineCompletion)
        f["cs_edit"].setCompleter(comp)

        def _on_activated(text: str):
            prior = self.log_db.last_qso_with(text)
            if prior is None:
                return
            if not f["grid_edit"].text().strip():
                f["grid_edit"].setText(prior.grid)
            if not f["name_edit"].text().strip():
                f["name_edit"].setText(prior.name)

        comp.activated.connect(_on_activated)

    def _wire_callsign_lookup(self, dlg, f: dict) -> None:
        """Async callsign lookup: on cs_edit editingFinished, auto-fill name+grid."""
        from PyQt6.QtCore import QObject, pyqtSignal

        class _Bridge(QObject):
            found = pyqtSignal(object)

        bridge = _Bridge(dlg)

        def _update_bearing():
            grid = f["grid_edit"].text().strip().upper()
            my_lat = self.cfg.get("location.lat", 0.0)
            my_lon = self.cfg.get("location.lon", 0.0)
            if not grid or not (my_lat or my_lon):
                f["bearing_label"].setText("")
                return
            try:
                from core.location import _grid_to_latlon
                from core.log_db import QSO as _QSO
                q = _QSO(call="X", grid=grid, my_lat=my_lat, my_lon=my_lon)
                if q.dist_km:
                    f["bearing_label"].setText(
                        f"{q.dist_km:.0f} km  ·  {q.bearing_deg:.0f}°")
            except Exception:
                f["bearing_label"].setText("")

        def _on_cs_finished():
            call = f["cs_edit"].text().strip().upper()
            if len(call) < 3:
                return
            f["lkp_status"].setText(self.tr("Looking up…"))
            from network.qrz_lookup import get_lookup
            get_lookup(self.cfg).lookup_async(call, bridge.found.emit)

        def _on_result(info):
            f["_qrz_info"] = info
            if not info:
                f["lkp_status"].setText(self.tr("Not found"))
                return
            if info.name and not f["name_edit"].text().strip():
                f["name_edit"].setText(info.name)
            if info.grid and not f["grid_edit"].text().strip():
                f["grid_edit"].setText(info.grid[:6])
            parts = [p for p in (info.name, info.country or info.dxcc) if p]
            f["lkp_status"].setText(" — ".join(parts) if parts else self.tr("Found"))
            _update_bearing()

        bridge.found.connect(_on_result)
        f["cs_edit"].editingFinished.connect(_on_cs_finished)
        f["grid_edit"].editingFinished.connect(_update_bearing)

    def _wire_dupe_check(self, f: dict) -> None:
        """Show inline dupe warning as callsign/band/mode change."""
        dupe_lbl = f.get("dupe_label")
        if dupe_lbl is None:
            return

        def _check():
            call = f["cs_edit"].text().strip().upper()
            band = f["band_combo"].currentText()
            mode = f["mode_combo"].currentText().upper()
            if not call:
                dupe_lbl.setText("")
                return
            try:
                if self.log_db.is_duplicate(call, band, mode):
                    dupe_lbl.setStyleSheet(
                        "color:#e06c00;font-size:10px;font-style:italic;")
                    dupe_lbl.setText(
                        f"⚠ Worked {call} on {band}/{mode} in last 24h")
                elif self.log_db.worked_before(call):
                    dupe_lbl.setStyleSheet(
                        "color:#888;font-size:10px;font-style:italic;")
                    dupe_lbl.setText(
                        f"ℹ Worked {call} before (different band/mode)")
                else:
                    dupe_lbl.setText("")
            except Exception:
                dupe_lbl.setText("")

        f["cs_edit"].editingFinished.connect(_check)
        f["band_combo"].currentTextChanged.connect(lambda _: _check())
        f["mode_combo"].currentTextChanged.connect(lambda _: _check())

    def _manual_entry(self):
        """Open the manual QSO entry dialog and log on accept."""
        dlg, f = self._build_manual_entry_dialog()
        self._wire_callsign_autocomplete(f)
        self._wire_callsign_lookup(dlg, f)
        self._wire_dupe_check(f)
        if not dlg.exec():
            return
        call = callsign_soft(f["cs_edit"].text())
        if not call:
            QMessageBox.warning(self, "Invalid Callsign",
                                "Please enter a valid callsign.")
            return
        band = f["band_combo"].currentText()
        mode = f["mode_combo"].currentText().upper()
        try:
            if self.cfg.get("log.warn_dupes", True):
                if self.log_db.is_duplicate(call, band, mode):
                    reply = QMessageBox.question(
                        self, "Duplicate QSO",
                        f"{call} already logged on {band} {mode}.\n\n"
                        "Log anyway?",
                        QMessageBox.StandardButton.Yes |
                        QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.No:
                        return
            _fu2 = (self.cfg.get("display.freq_units", "MHz")
                    if self.cfg else "MHz")
            freq_hz = parse_freq_input(f["freq_edit"].text(), _fu2)
            dt_str = (f["dt_edit"].dateTime()
                      .toUTC().toString("yyyy-MM-ddTHH:mm:ssZ"))
            qrz = f.get("_qrz_info")
            qso = QSO(
                call         = call,
                datetime_on  = dt_str,
                band         = band,
                freq_hz      = freq_hz,
                mode         = mode,
                rst_sent     = f["rst_sent"].text().strip() or "59",
                rst_rcvd     = f["rst_rcvd"].text().strip() or "59",
                grid         = grid_square_soft(f["grid_edit"].text()),
                name         = f["name_edit"].text().strip()[:50],
                comment      = f["comment_edit"].text().strip()[:200],
                country      = (qrz.country if qrz else ""),
                dxcc         = (qrz.dxcc    if qrz else ""),
                state        = (qrz.state   if qrz else ""),
                cqz          = (qrz.cq_zone if qrz else 0),
                ituz         = (qrz.itu_zone if qrz else 0),
                my_call      = operating_callsign(self.cfg),
                my_grid      = self.cfg.grid,
                my_lat       = self.cfg.get("location.lat", 0.0),
                my_lon       = self.cfg.get("location.lon", 0.0),
                source       = "manual",
            )
            self.log_db.log_qso(qso)
            self._load_log()
            QMessageBox.information(
                self, self.tr("QSO Logged"),
                f"QSO with {call} on {band} {mode} logged.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not log QSO: {e}")
