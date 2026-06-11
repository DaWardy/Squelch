from __future__ import annotations
from pathlib import Path
from core.units import format_distance, distance_suffix
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
#
# This program is free software: you can redistribute it
# and/or modify it under the terms of the GNU General
# Public License as published by the Free Software
# Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General
# Public License along with this program. If not, see
# <https://www.gnu.org/licenses/>.
import logging
from ui.panel import SquelchPanel
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QGroupBox, QFrame, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QLineEdit, QCheckBox, QMessageBox,
    QDoubleSpinBox, QSizePolicy, QTextEdit
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont

from ui.widgets.launch_bar import LaunchBar
from network.repeaterbook import Repeater, nearest_async

log = logging.getLogger(__name__)

MODE_COLORS = {
    "FM":     "#3fbe6f",
    "DMR":    "#44aaff",
    "P25":    "#ffaa22",
    "YSF":    "#ff66aa",
    "DSTAR":  "#aa66ff",
    "D-STAR": "#aa66ff",
    "NXDN":   "#ff8844",
    "FUSION": "#ff66aa",
}


class LocalRFTab(SquelchPanel, QWidget):
    panel_id    = "localrf"
    panel_title = "Local RF"

    def __init__(self, config, rig=None, parent=None):
        super().__init__(parent)
        self.cfg      = config
        self.rig      = rig
        self._repeaters: list[Repeater] = []
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Launch bar
        self._launch_bar = LaunchBar(
            "localrf", self.cfg,
            rescan_callback=self._rescan)
        root.addWidget(self._launch_bar)

        # Search bar
        root.addWidget(self._build_search_bar())

        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(
            "QSplitter::handle{background:#1a1a1a;width:3px;}")

        # Left: repeater list
        left = self._build_repeater_panel()
        splitter.addWidget(left)

        # Right: detail + APRS
        right = self._build_detail_panel()
        right.setMaximumWidth(340)
        splitter.addWidget(right)

        splitter.setSizes([680, 320])
        root.addWidget(splitter, 1)

    def _build_search_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(44)
        bar.setStyleSheet(
            "background:#0d0d0d;border-bottom:1px solid #1a1a1a;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(8)
        lay.addWidget(QLabel("Nearest repeaters:"))
        self._searchbar_add_location_controls(lay)
        self._searchbar_add_action_buttons(lay)
        return bar

    def _searchbar_add_location_controls(self, lay) -> None:
        lay.addWidget(QLabel("From:"))
        self._from_edit = QLineEdit()
        self._from_edit.setPlaceholderText("grid / ZIP / city (blank = my location)")
        self._from_edit.setMaximumWidth(220)
        self._from_edit.setToolTip(
            "Search from a different location than your station — "
            "enter a Maidenhead grid, ZIP code, or city. Leave blank to "
            "use your configured location.")
        lay.addWidget(self._from_edit)
        lay.addWidget(QLabel("Within:"))
        self._radius = QDoubleSpinBox()
        self._radius.setRange(5, 200)
        self._radius.setValue(50)
        self._radius.setSuffix(distance_suffix(self.cfg))
        self._radius.setFixedWidth(85)
        lay.addWidget(self._radius)
        lay.addWidget(QLabel("Mode:"))
        self._mode_filter = QComboBox()
        self._mode_filter.addItems(["All", "FM", "DMR", "P25", "YSF", "D-STAR", "NXDN"])
        self._mode_filter.setFixedWidth(75)
        self._mode_filter.currentTextChanged.connect(self._apply_mode_filter)
        lay.addWidget(self._mode_filter)

    def _searchbar_add_action_buttons(self, lay) -> None:
        self._search_btn = QPushButton("🔍 Search")
        self._search_btn.setFixedWidth(90)
        self._search_btn.setStyleSheet(
            "background:#1a3a1a;color:#3fbe6f;"
            "border:1px solid #3fbe6f;border-radius:4px;")
        self._search_btn.setToolTip(
            "Search RepeaterBook for nearby repeaters\n"
            "Free, no API key required\n"
            "Requires location set in top bar")
        self._search_btn.clicked.connect(self._do_search)
        lay.addWidget(self._search_btn)
        # CHIRP CSV import — operator's own data, no token, no scraping.
        # The most reliable path: drop a Proximity Query export from CHIRP.
        self._import_btn = QPushButton("📂 Import CHIRP CSV")
        self._import_btn.setFixedWidth(180)
        self._import_btn.setToolTip(
            "Import a CHIRP-format repeater list (.csv).\n"
            "In CHIRP: Radio → Query Source → RepeaterBook → "
            "Proximity Query, then File → Export to .csv.\n"
            "No API token or RepeaterBook account required.")
        self._import_btn.clicked.connect(self._do_import_chirp)
        lay.addWidget(self._import_btn)
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("")
        lay.addWidget(self._status_lbl)
        lay.addStretch()
        self._loc_lbl = QLabel("Location: not set")
        self._loc_lbl.setStyleSheet("")
        lay.addWidget(self._loc_lbl)

    def _build_repeater_panel(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)
        lay.addWidget(self._build_repeater_table())
        self._no_results = QLabel(
            "Click Search to find nearest repeaters.\n\n"
            "Data from RepeaterBook.com\n"
            "(free, no API key required)\n\n"
            "Double-click a repeater to tune the rig.\n"
            "Right-click to save to memory.")
        self._no_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_results.setStyleSheet("")
        lay.addWidget(self._no_results)
        lay.addLayout(self._build_repeater_btn_row())
        return w

    def _build_repeater_table(self) -> QTableWidget:
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels([
            "Callsign", "Output MHz", "Offset",
            "Tone", "Mode", "City", "Dist"])
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            "QTableWidget{background:#0a0a0a;gridline-color:#1a1a1a;"
            "alternate-background-color:#0d0d0d;font-family:'Courier New';"
            "selection-background-color:#1a3a1a;border:1px solid #1a1a1a;}"
            "QHeaderView::section{background:#141414;border:none;padding:3px;}")
        self._table.clicked.connect(self._on_row_click)
        self._table.doubleClicked.connect(self._tune_to_selected)
        return self._table

    def _build_repeater_btn_row(self) -> QHBoxLayout:
        btn_row = QHBoxLayout()
        self._tune_btn = QPushButton("📻 Tune Rig")
        self._tune_btn.setEnabled(False)
        self._tune_btn.setToolTip(
            "Tune rig to selected repeater frequency\n"
            "Requires rig connected in Rig tab")
        self._tune_btn.clicked.connect(self._tune_to_selected)
        btn_row.addWidget(self._tune_btn)
        self._memory_btn = QPushButton("💾 Save to Memory")
        self._memory_btn.setEnabled(False)
        self._memory_btn.setToolTip(
            "Save repeater to CHIRP CSV file\n"
            "Import the CSV into CHIRP to program your radio")
        self._memory_btn.clicked.connect(self._save_to_memory)
        btn_row.addWidget(self._memory_btn)
        self._chirp_btn = QPushButton("🔧 Open in CHIRP")
        self._chirp_btn.setEnabled(False)
        self._chirp_btn.setToolTip(
            "Launch CHIRP radio programming software\n"
            "Set path in File → Paths & Executables")
        self._chirp_btn.clicked.connect(self._open_chirp)
        btn_row.addWidget(self._chirp_btn)
        export_btn = QPushButton("📁 Export All → CHIRP")
        export_btn.setToolTip("Export all search results to CHIRP CSV format")
        export_btn.clicked.connect(self._export_all_to_chirp)
        btn_row.addWidget(export_btn)
        manual_btn = QPushButton("✏️ Add Manually")
        manual_btn.setToolTip(
            "Add a repeater manually by frequency and tone\n"
            "Useful when RepeaterBook search is unavailable")
        manual_btn.clicked.connect(self._add_manual_repeater)
        btn_row.addWidget(manual_btn)
        return btn_row

    def _build_detail_panel(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 6, 6, 6)
        lay.setSpacing(6)
        detail_grp = QGroupBox("Repeater Detail")
        dl = QVBoxLayout(detail_grp)
        self._detail_text = QTextEdit()
        self._detail_text.setReadOnly(True)
        self._detail_text.setMaximumHeight(220)
        self._detail_text.setStyleSheet(
            "background:#0a0a0a;font-family:'Courier New';"
            "border:1px solid #1a1a1a;")
        self._detail_text.setPlaceholderText("Select a repeater to see details…")
        dl.addWidget(self._detail_text)
        lay.addWidget(detail_grp)
        lay.addWidget(self._build_detail_rr_group())
        lay.addWidget(self._build_detail_aprs_group())
        lay.addStretch()
        return w

    def _build_detail_rr_group(self) -> QGroupBox:
        rr_grp = QGroupBox("RadioReference Premium")
        rl = QVBoxLayout(rr_grp)
        rr_msg = QLabel(
            "RadioReference Premium API provides\n"
            "frequency databases for public safety,\n"
            "aviation, marine, and business radio.\n\n"
            "Requires a Premium subscription.\n"
            "Configure API key in Settings.")
        rr_msg.setStyleSheet("")
        rr_msg.setWordWrap(True)
        rl.addWidget(rr_msg)
        rr_btn = QPushButton("Configure API Key →")
        rr_btn.setStyleSheet("")
        rr_btn.clicked.connect(self._open_rr_settings)
        rl.addWidget(rr_btn)
        return rr_grp

    def _build_detail_aprs_group(self) -> QGroupBox:
        aprs_grp = QGroupBox("APRS-IS")
        al = QVBoxLayout(aprs_grp)
        self._aprs_status = QLabel("● Not connected")
        self._aprs_status.setStyleSheet("font-family:'Courier New';")
        al.addWidget(self._aprs_status)
        self._aprs_count = QLabel("Stations: 0")
        self._aprs_count.setStyleSheet("")
        al.addWidget(self._aprs_count)
        aprs_btns = QHBoxLayout()
        self._aprs_conn_btn = QPushButton("Connect")
        self._aprs_conn_btn.setFixedHeight(24)
        self._aprs_conn_btn.clicked.connect(self._toggle_aprs)
        aprs_btns.addWidget(self._aprs_conn_btn)
        beacon_btn = QPushButton("Beacon Now")
        beacon_btn.setFixedHeight(24)
        beacon_btn.clicked.connect(self._send_beacon)
        aprs_btns.addWidget(beacon_btn)
        al.addLayout(aprs_btns)
        aprs_note = QLabel("APRS-IS: internet receive-only.\nRF TX requires Direwolf + TNC.")
        aprs_note.setStyleSheet("")
        aprs_note.setWordWrap(True)
        al.addWidget(aprs_note)
        self._aprs_client = None
        return aprs_grp

    # ── Search ────────────────────────────────────────────────────────────

    def _latlon_from_override(self, override: str) -> tuple[float, float]:
        """Resolve lat/lon from a user-entered grid, ZIP, or city string."""
        try:
            from core.location import _grid_to_latlon
            return _grid_to_latlon(override)
        except Exception:
            pass
        try:
            from core.location import geocode_place
            return geocode_place(override)
        except Exception:
            return 0.0, 0.0

    def _latlon_from_config(self) -> tuple[float, float]:
        """Return lat/lon from the station's configured location."""
        grid = self.cfg.get("location.grid_square", "") or self.cfg.grid or ""
        lat  = float(self.cfg.get("location.lat", 0.0) or 0.0)
        lon  = float(self.cfg.get("location.lon", 0.0) or 0.0)
        if grid and not (lat and lon):
            try:
                from core.location import _grid_to_latlon
                lat, lon = _grid_to_latlon(grid)
            except Exception:
                pass
        return lat, lon

    def _resolve_search_origin(self) -> tuple[float, float]:
        """Return (lat, lon) for the search start point — override or config."""
        override = self._from_edit.text().strip() if hasattr(self, "_from_edit") else ""
        if override:
            return self._latlon_from_override(override)
        return self._latlon_from_config()

    def _do_search(self):
        lat, lon = self._resolve_search_origin()

        if not (lat or lon):
            override = self._from_edit.text().strip() if hasattr(self, "_from_edit") else ""
            if override:
                QMessageBox.warning(
                    self, "Location Error",
                    "Could not determine lat/lon from that location.\n"
                    "Try a Maidenhead grid, ZIP code, or city name.")
            else:
                QMessageBox.warning(
                    self, "Location Required",
                    "Set your location in the top bar first.\n"
                    "Click the grid square field and enter\n"
                    "your Maidenhead grid or ZIP code.")
            return

        radius = self._radius.value()
        from core.units import units_pref, KM_PER_MILE
        if units_pref(self.cfg) == "imperial":
            radius = radius * KM_PER_MILE
        mode = self._mode_filter.currentText()
        mode = "" if mode == "All" else mode

        self._search_btn.setEnabled(False)
        self._search_btn.setText("Fetching…")
        self._no_results.hide()
        self._table.setRowCount(0)

        from network.repeaterbook import _rb_token
        if bool(_rb_token()):
            src = "RepeaterBook"
        elif mode.lower() in ("dmr", "p25", "nxdn", "d-star"):
            src = "RadioID.net (free, no token)"
        else:
            src = "no source — see error for guidance"
        self._status_lbl.setText(
            f"Fetching from {src}… filtering within "
            f"{self._radius.value():.0f}{distance_suffix(self.cfg)}")
        self._loc_lbl.setText(f"Location: {lat:.4f}, {lon:.4f}")

        nearest_async(
            lat, lon,
            callback=self._on_results,
            radius_km=radius,
            mode=mode,
            error_callback=self._on_search_error)

        self._search_pending = True
        def _watchdog():
            if getattr(self, "_search_pending", False):
                self._search_btn.setEnabled(True)
                self._search_btn.setText("🔍 Search")
                self._status_lbl.setText(
                    "Search timed out. Try again.")
        QTimer.singleShot(40000, _watchdog)


    def _on_search_error(self, message: str, needs_token: bool):
        """Show search errors with honest guidance about data-source state."""
        from PyQt6.QtCore import QTimer
        def _show():
            self._search_pending = False
            self._search_btn.setEnabled(True)
            self._search_btn.setText("\U0001F50D Search")
            # If hearham 403'd (the free fallback now blocks our requests),
            # tell the user the truth and point them at the token path.
            if "403" in message or "hearham" in message.lower():
                self._status_lbl.setText("No free data source available")
                self._no_results.setText(
                    "Local RF currently has no working free data source.\n\n"
                    "• RepeaterBook: requires an approved API token (free for "
                    "non-commercial use). Apply at:\n"
                    "  repeaterbook.com/api/token_request.php\n"
                    "  Then paste the token in Settings → APIs.\n\n"
                    "• hearham.com (previously the free fallback): now "
                    "returns HTTP 403 to our requests, so the free path is "
                    "currently unavailable.\n\n"
                    "We are actively looking for another no-token source.")
            else:
                self._status_lbl.setText(
                    "No repeaters found" if needs_token else "Search error")
                self._no_results.setText(message)
            self._no_results.show()
        QTimer.singleShot(0, _show)

    def _on_results(self, repeaters: list[Repeater]):
        self._search_pending = False
        QTimer.singleShot(0,
            lambda r=repeaters: self._populate(r))

    def _do_import_chirp(self):
        """Import a CHIRP-format CSV — no token, no scraping, fully offline."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        path, _ = QFileDialog.getOpenFileName(
            self, "Import CHIRP CSV",
            "",
            "CHIRP CSV (*.csv);;All files (*)")
        if not path:
            return
        try:
            from network.chirp_import import parse_chirp_csv
            reps = parse_chirp_csv(path)
        except Exception as e:
            QMessageBox.warning(
                self, "Import failed",
                f"Could not read CHIRP CSV:\n\n{e}\n\n"
                "Expected a generic CHIRP-format CSV with the standard "
                "headers (Location, Name, Frequency, Duplex, Offset, Tone…). "
                "In CHIRP: File → Export to .csv after a Proximity Query.")
            return
        if not reps:
            QMessageBox.information(
                self, "Import",
                "The CSV had no valid repeater rows.")
            return
        # CHIRP CSV has no lat/lon, so distance-from-me is unknown.
        # Hide the distance column or sort by frequency instead. The
        # _populate path already tolerates distance_km == 0 (won't sort
        # by distance when all zeros).
        self._no_results.hide()
        self._status_lbl.setText(
            f"Imported {len(reps)} repeaters from CHIRP CSV "
            f"({path.split('/')[-1].split(chr(92))[-1]})")
        self._populate(reps)

    def _populate(self, repeaters: list[Repeater]):
        self._repeaters = repeaters
        self._search_btn.setEnabled(True)
        self._search_btn.setText("🔍 Search")

        self._table.setRowCount(0)

        if not repeaters:
            self._status_lbl.setText(
                "No repeaters found — check internet connection")
            self._no_results.setText(
                "No repeaters found.\n\n"
                "Possible causes:\n"
                "  • Location not set in top bar\n"
                "  • No internet connection\n"
                "  • RepeaterBook.com temporarily unavailable\n\n"
                "Try:\n"
                "  • Set location in top bar (click grid field)\n"
                "  • Increase search radius\n"
                "  • Visit repeaterbook.com in a browser to check")
            self._no_results.show()
            self._populate([])   # clear table, show empty state
            return

        self._no_results.hide()
        self._status_lbl.setText(
            f"{len(repeaters)} repeaters found")

        for rep in repeaters:
            row = self._table.rowCount()
            self._table.insertRow(row)

            color = MODE_COLORS.get(
                rep.mode.upper(), "#3fbe6f")

            cells = [
                rep.callsign,
                rep.output_str,
                rep.offset_str,
                rep.tone_str or "—",
                rep.mode or "FM",
                rep.city or rep.county,
                format_distance(rep.distance_km, self.cfg),
            ]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(val)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter)
                if col == 4:  # mode
                    item.setForeground(QColor(color))
                self._table.setItem(row, col, item)

    def _apply_mode_filter(self, mode: str):
        for row in range(self._table.rowCount()):
            mode_item = self._table.item(row, 4)
            if not mode_item:
                continue
            if mode == "All":
                self._table.setRowHidden(row, False)
            else:
                hide = mode_item.text().upper() != mode.upper()
                self._table.setRowHidden(row, hide)

    # ── Row selection ─────────────────────────────────────────────────────

    def _on_row_click(self, index):
        row = index.row()
        if row < 0 or row >= len(self._repeaters):
            return
        rep = self._repeaters[row]
        self._show_detail(rep)
        self._tune_btn.setEnabled(True)
        self._memory_btn.setEnabled(True)
        self._chirp_btn.setEnabled(True)

    def _show_detail(self, rep: Repeater):
        lines = [
            f"Callsign:    {rep.callsign}",
            f"Output:      {rep.output_str} MHz",
            f"Input:       {rep.input_mhz:.4f} MHz",
            f"Offset:      {rep.offset_str} MHz",
            f"Tone:        {rep.tone_str or 'None'}",
            f"Mode:        {rep.mode or 'FM'}",
            f"Band:        {rep.band}",
            f"City:        {rep.city}",
            f"County:      {rep.county}",
            f"State:       {rep.state}",
            f"Distance:    {format_distance(rep.distance_km, self.cfg)}",
            f"Status:      {rep.status}",
            f"Use:         {rep.use_code}",
            f"Digital:     {'Yes' if rep.is_digital else 'No'}",
            f"Last update: {rep.last_updated}",
        ]
        if rep.notes:
            lines.append(f"\nNotes:\n{rep.notes}")
        self._detail_text.setPlainText(
            "\n".join(lines))

    def _selected_repeater(self) -> Repeater | None:
        rows = self._table.selectedItems()
        if not rows:
            return None
        row = rows[0].row()
        if row < 0 or row >= len(self._repeaters):
            return None
        return self._repeaters[row]

    # ── Actions ───────────────────────────────────────────────────────────

    def _tune_to_selected(self, _index=None):
        rep = self._selected_repeater()
        if not rep:
            return
        if not self.rig or not self.rig.is_connected:
            QMessageBox.information(
                self, "Rig Not Connected",
                f"Connect your rig first.\n\n"
                f"Repeater output: {rep.output_str} MHz\n"
                f"Tone: {rep.tone_str or 'None'}")
            return
        try:
            hz = int(rep.output_mhz * 1_000_000)
            self.rig.set_freq(hz)
            # Set mode
            mode = "FM"
            if rep.mode.upper() in ("DMR", "P25", "NXDN"):
                mode = "FM"   # still FM modulation at RF
            self.rig.set_mode(mode)
            log.info(
                f"Tuned to {rep.callsign}: "
                f"{rep.output_str} MHz {rep.tone_str}")
        except Exception as e:
            QMessageBox.warning(
                self, "Tune Failed", str(e))

    def _save_to_memory(self):
        rep = self._selected_repeater()
        if not rep:
            return
        from core.memory_channels import MemoryBank
        from PyQt6.QtWidgets import QFileDialog

        # Build a bank with this repeater
        bank = MemoryBank()
        # Load any existing channels from this session
        if not hasattr(self, "_memory_bank"):
            self._memory_bank = MemoryBank()
        ch_num = self._memory_bank.next_free()
        from core.memory_channels import MemoryChannel
        ch = MemoryChannel.from_repeater(ch_num, rep)
        self._memory_bank.add(ch)

        # Ask where to save
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Memory Channels",
            f"repeaters_{rep.city or 'local'}.csv",
            "CHIRP CSV (*.csv);All Files (*)")

        if not path:
            return

        try:
            count = self._memory_bank.save_chirp_csv(
                Path(path))
            QMessageBox.information(
                self, "Memory Channels Exported",
                f"Exported {count} channel(s) to:\n{path}\n\n"
                f"Open in CHIRP: Radio → Upload To Radio\n"
                f"Select your radio model, choose the CSV file.")
        except Exception as e:
            QMessageBox.warning(
                self, "Export Failed",
                f"Could not export channels:\n{e}")

    def _add_manual_repeater(self):
        """Let user add a repeater manually."""
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox
        dlg, callsign, freq_mhz, offset, tone, mode, city = \
            self._build_manual_repeater_dialog()
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        rep = self._manual_repeater_to_namespace(
            callsign.text(), freq_mhz.value(),
            offset.currentText(), tone.text(),
            mode.currentText(), city.text())
        if not hasattr(self, "_repeaters"):
            self._repeaters = []
        self._repeaters.append(rep)
        self._populate(self._repeaters)
        self._status_lbl.setText(
            f"{len(self._repeaters)} repeaters (includes manual entries)")

    def _build_manual_repeater_dialog(self) -> "tuple":
        """Build the Add Repeater dialog; return (dlg, callsign, freq, offset, tone, mode, city)."""
        from PyQt6.QtWidgets import (
            QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox as _DSB)
        dlg = QDialog(self)
        dlg.setWindowTitle("Add Repeater Manually")
        dlg.setMinimumWidth(340)
        f = QFormLayout(dlg)
        f.setSpacing(8)
        f.setContentsMargins(12, 12, 12, 12)
        callsign = QLineEdit()
        callsign.setPlaceholderText("e.g. W4XYZ")
        callsign.setMaxLength(10)
        f.addRow("Callsign:", callsign)
        freq_mhz = _DSB()
        freq_mhz.setRange(50.0, 1300.0)
        freq_mhz.setValue(146.520)
        freq_mhz.setDecimals(4)
        freq_mhz.setSuffix(" MHz")
        f.addRow("Output Freq:", freq_mhz)
        offset = QComboBox()
        offset.addItems([
            "Simplex (+0.000)", "+0.600 (2m standard)", "-0.600 (2m standard)",
            "+5.000 (70cm standard)", "-5.000 (70cm standard)",
            "+1.600 (1.25m standard)", "Custom…"])
        f.addRow("Offset:", offset)
        tone = QLineEdit()
        tone.setPlaceholderText("e.g. 100.0 (leave blank for none)")
        f.addRow("CTCSS Tone:", tone)
        mode = QComboBox()
        mode.addItems(["FM", "DMR", "P25", "YSF", "D-STAR", "NXDN"])
        f.addRow("Mode:", mode)
        city = QLineEdit()
        city.setPlaceholderText("e.g. Denver CO")
        f.addRow("Location:", city)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        f.addRow(btns)
        return dlg, callsign, freq_mhz, offset, tone, mode, city

    @staticmethod
    def _manual_repeater_to_namespace(
            cs_text, freq_val, off_text, tone_text, mode_text, city_text):
        """Build a SimpleNamespace repeater from Add Repeater dialog values."""
        from types import SimpleNamespace
        OFF_MAP = {
            "+0.600 (2m standard)": +0.600,  "-0.600 (2m standard)": -0.600,
            "+5.000 (70cm standard)": +5.000, "-5.000 (70cm standard)": -5.000,
            "+1.600 (1.25m standard)": +1.600,
        }
        cs       = cs_text.strip().upper() or "MANUAL"
        off_mhz  = OFF_MAP.get(off_text, 0.0)
        tone_val = tone_text.strip()
        return SimpleNamespace(
            callsign=cs, output_mhz=freq_val,
            output_str=f"{freq_val:.4f}", offset_mhz=off_mhz,
            tone=tone_val,
            tone_str=f"CTCSS {tone_val}" if tone_val else "None",
            mode=mode_text, city=city_text.strip(),
            state="", lat=0.0, lon=0.0,
        )

    def _export_all_to_chirp(self):
        """Export all search results to CHIRP CSV."""
        if not self._repeaters:
            QMessageBox.information(
                self, "No Repeaters",
                "Search for repeaters first.")
            return
        from core.memory_channels import MemoryBank
        from PyQt6.QtWidgets import QFileDialog

        bank = MemoryBank()
        bank.from_repeaters(self._repeaters)

        path, _ = QFileDialog.getSaveFileName(
            self, "Export All to CHIRP",
            "squelch_repeaters.csv",
            "CHIRP CSV (*.csv);All Files (*)")
        if not path:
            return
        try:
            count = bank.save_chirp_csv(Path(path))
            QMessageBox.information(
                self, "Export Complete",
                f"Exported {count} repeaters to:\n{path}\n\n"
                f"Open in CHIRP → File → Open to import.")
        except Exception as e:
            QMessageBox.warning(
                self, "Export Failed", str(e))

    def _open_chirp(self):
        from core.launcher import get_launcher
        launcher = get_launcher(self.cfg)
        if not launcher.launch("paths.chirp"):
            QMessageBox.information(
                self, "CHIRP Not Found",
                "CHIRP not configured.\n\n"
                "Download: chirpmyradio.com\n"
                "Then set the path in:\n"
                "File → Paths & Executables → Programming")

    def _open_rr_settings(self):
        from ui.dialogs.paths_dialog import PathsDialog
        dlg = PathsDialog(self.cfg, parent=self)
        dlg.exec()

    def _toggle_aprs(self):
        """Connect or disconnect from APRS-IS."""
        # Try to get client from main window
        if self._aprs_client is None:
            try:
                mw = self.window()
                if hasattr(mw, "_aprs_client"):
                    self._aprs_client = mw._aprs_client
                    if self._aprs_client:
                        self._aprs_client.on_status(
                            self._on_aprs_status)
                        self._aprs_client.on_packet(
                            self._on_aprs_packet)
            except Exception:
                pass

        if self._aprs_client is None:
            from aprs.aprs_client import APRSClient
            self._aprs_client = APRSClient(self.cfg)
            self._aprs_client.on_status(
                self._on_aprs_status)
            self._aprs_client.on_packet(
                self._on_aprs_packet)

        if self._aprs_client.is_connected:
            self._aprs_client.disconnect()
            self._aprs_conn_btn.setText("Connect")
        else:
            ok = self._aprs_client.connect()
            if ok:
                self._aprs_conn_btn.setText("Disconnect")
                self.cfg.set("aprs.auto_connect", True)
                self.cfg.save()
            else:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self, "APRS-IS",
                    "Could not connect to APRS-IS.\n"
                    "Check internet connection.\n\n"
                    "Server: rotate.aprs2.net:14580")

    def _on_aprs_status(self, status: str):
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0,
            lambda s=status: self._apply_aprs_status(s))

    def _apply_aprs_status(self, status: str):
        colors = {
            "connected":    "#3fbe6f",
            "disconnected": "#555",
            "error":        "#cc4444",
        }
        color = colors.get(status, "#888")
        self._aprs_status.setText(
            f"● {status.capitalize()}")
        self._aprs_status.setStyleSheet(
            f"color:{color};"
            "font-family:'Courier New';")
        if status == "connected":
            self._aprs_conn_btn.setText("Disconnect")
        else:
            self._aprs_conn_btn.setText("Connect")

    def _on_aprs_packet(self, packet):
        if self._aprs_client:
            count = self._aprs_client.packet_count
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0,
                lambda c=count:
                    self._aprs_count.setText(
                        f"Stations: {c}"))

    def _send_beacon(self):
        try:
            mw = self.window()
            if hasattr(mw, "_aprs_beacon") and                mw._aprs_beacon:
                sent = mw._aprs_beacon.send_now()
                if sent:
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.information(
                        self, "APRS Beacon",
                        "Beacon sent via APRS-IS.")
                else:
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.warning(
                        self, "APRS Beacon",
                        "Beacon not sent.\n"
                        "Connect to APRS-IS first.\n"
                        "Or set location in top bar.")
        except Exception as e:
            log.warning(f"Beacon: {e}")

    def _rescan(self):
        self._launch_bar.refresh()

    def showEvent(self, event):
        """Update location label when tab is shown."""
        super().showEvent(event)
        grid = self.cfg.get("location.grid_square", "") or \
               self.cfg.grid or ""
        if grid:
            self._loc_lbl.setText(f"Location: {grid}")