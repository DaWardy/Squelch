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

"""
Squelch -- ui/tabs/band_conditions_tab.py
Band conditions: solar indices, K/A/SFI, band-by-band
conditions, aurora alerts, recommendations.
PSKReporter and WSPRnet spot feeds.
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QGroupBox, QFrame, QPushButton,
    QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QSizePolicy, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QBrush, QFont

from network.propagation import PropagationFeed, get_prop_feed, SolarData, BandCondition
from network.grayline import gray_line_info, format_gray_line_status

log = logging.getLogger(__name__)


class BandConditionsTab(QWidget):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.cfg   = config
        self._feed = get_prop_feed()
        # Start fetching BEFORE building UI so data arrives sooner
        self._feed.on_solar_update(self._on_solar)
        self._feed.on_alert(self._on_alert)
        if not self._feed._running:
            self._feed.start()
        self._build()
        self._show_fetching_state()
        # If feed already has data (re-opened tab), show immediately
        if self._feed.solar.sfi > 0:
            QTimer.singleShot(50, self._refresh_display)
        else:
            # Wait for first fetch - check every 2 seconds
            QTimer.singleShot(2000, self._refresh_display)

        # Refresh UI every 60 seconds
        self._timer = QTimer(self)
        self._timer.setInterval(60_000)
        self._timer.timeout.connect(self._refresh_display)
        self._timer.start()

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── Header bar ────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        self._summary_lbl = QLabel(
            self.tr("Fetching solar data…"))
        self._summary_lbl.setStyleSheet(
            "font-weight:bold;color:#3fbe6f;")
        hdr.addWidget(self._summary_lbl)
        hdr.addStretch()

        refresh_btn = QPushButton(self.tr("↺ Refresh"))
        refresh_btn.setFixedWidth(90)
        refresh_btn.clicked.connect(self._manual_refresh)
        hdr.addWidget(refresh_btn)

        self._age_lbl = QLabel("")
        self._age_lbl.setStyleSheet(
            "")
        hdr.addWidget(self._age_lbl)
        root.addLayout(hdr, 0)   # stretch=0 — thin top band

        # ── Splitter: left=solar, right=bands ─────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(
            "QSplitter::handle{background:#1a1a1a;width:3px;}")

        # ── Left: Solar indices ───────────────────────────────────────────
        left = QWidget()
        ll   = QVBoxLayout(left)
        ll.setAlignment(Qt.AlignmentFlag.AlignTop)
        ll.setContentsMargins(0, 0, 4, 0)
        ll.setSpacing(6)
        left.setMinimumWidth(260)
        left.setMaximumWidth(320)

        solar_grp = QGroupBox(self.tr("Solar Indices"))
        sg = QGridLayout(solar_grp)
        sg.setSpacing(4)

        self._solar_widgets = {}
        indices = [
            ("sfi",    self.tr("Solar Flux (SFI)"),   "0",   "10.7cm emission"),
            ("sn",     self.tr("Sunspot Number"),       "0",   "Daily count"),
            ("k",      self.tr("K-Index"),              "0",   "3-hour geomag"),
            ("a",      self.tr("A-Index"),              "0",   "Daily geomag"),
            ("xray",   self.tr("X-Ray Class"),          "A",   "Solar flare class"),
            ("storm",  self.tr("Storm Level"),          "G0",  "Geomagnetic"),
        ]
        for row, (key, label, default, tip) in enumerate(indices):
            lbl = QLabel(label)
            lbl.setStyleSheet("")
            lbl.setToolTip(tip)
            sg.addWidget(lbl, row, 0)

            val = QLabel(default)
            val.setStyleSheet(
                "color:#3fbe6f;"
                "font-weight:bold;font-family:'Courier New';")
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            sg.addWidget(val, row, 1)

            trend = QLabel("")
            trend.setStyleSheet("")
            trend.setFixedWidth(20)
            sg.addWidget(trend, row, 2)

            self._solar_widgets[key] = (val, trend)

        ll.addWidget(solar_grp)

        # Recommendations
        rec_grp = QGroupBox(self.tr("Band Recommendations"))
        rl      = QVBoxLayout(rec_grp)
        self._rec_labels = []
        for _ in range(4):
            lbl = QLabel("—")
            lbl.setStyleSheet("")
            lbl.setWordWrap(True)
            rl.addWidget(lbl)
            self._rec_labels.append(lbl)
        ll.addWidget(rec_grp)

        # Aurora alert
        self._aurora_widget = QGroupBox("")
        aw = QVBoxLayout(self._aurora_widget)
        self._aurora_lbl = QLabel("")
        self._aurora_lbl.setWordWrap(True)
        self._aurora_lbl.setStyleSheet(
            "color:#ffaa00;")
        aw.addWidget(self._aurora_lbl)
        self._aurora_widget.hide()
        ll.addWidget(self._aurora_widget)

        ll.addStretch()
        splitter.addWidget(left)

        # ── Right: Band conditions grid ────────────────────────────────────
        right = QWidget()
        rl2   = QVBoxLayout(right)
        rl2.setAlignment(Qt.AlignmentFlag.AlignTop)
        rl2.setContentsMargins(4, 0, 0, 0)
        rl2.setSpacing(4)

        bands_grp = QGroupBox(self.tr("Band Conditions"))
        bg = QGridLayout(bands_grp)
        bg.setSpacing(6)

        headers = [self.tr("Band"), self.tr("Condition"),
                   self.tr("Indicator")]
        for col, h in enumerate(headers):
            lbl = QLabel(h)
            lbl.setStyleSheet(
                "font-weight:bold;")
            bg.addWidget(lbl, 0, col)

        self._band_rows = {}
        bands = ["160m","80m","40m","30m","20m",
                 "17m","15m","12m","10m","6m"]

        for row, band in enumerate(bands, 1):
            band_lbl = QLabel(band)
            band_lbl.setStyleSheet(
                ""
                "font-family:'Courier New';")
            bg.addWidget(band_lbl, row, 0)

            cond_lbl = QLabel("—")
            cond_lbl.setStyleSheet(
                "")
            bg.addWidget(cond_lbl, row, 1)

            bar = QProgressBar()
            bar.setRange(0, 4)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(12)
            bar.setStyleSheet(
                "QProgressBar{background:#111;"
                "border:1px solid #222;border-radius:3px;}"
                "QProgressBar::chunk{"
                "background:#3fbe6f;border-radius:2px;}")
            bg.addWidget(bar, row, 2)

            self._band_rows[band] = (cond_lbl, bar)

        rl2.addWidget(bands_grp)

        # PSKReporter spots panel
        spots_grp = QGroupBox(
            self.tr("PSKReporter — Hearing You"))
        spl = QVBoxLayout(spots_grp)

        self._spots_table = QTableWidget(0, 4)
        self._spots_table.setHorizontalHeaderLabels([
            self.tr("Spotter"),
            self.tr("Band"),
            self.tr("SNR"),
            self.tr("Location"),
        ])
        self._spots_table.horizontalHeader()\
            .setSectionResizeMode(
                QHeaderView.ResizeMode.ResizeToContents)
        self._spots_table.horizontalHeader()\
            .setSectionResizeMode(
                3, QHeaderView.ResizeMode.Stretch)
        self._spots_table.setMaximumHeight(160)
        self._spots_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._spots_table.setStyleSheet(
            "QTableWidget{background:#0d0d0d;"
            "gridline-color:#1a1a1a;"
            "alternate-background-color:#111;}"
            "QHeaderView::section{background:#141414;"
            "border:none;}")
        self._spots_table.setAlternatingRowColors(True)
        spl.addWidget(self._spots_table)
        rl2.addWidget(spots_grp)

        rl2.addStretch()
        splitter.addWidget(right)
        splitter.setSizes([280, 600])
        root.addWidget(splitter, 1)   # stretch=1 so it fills below the header

    # ── Callbacks ─────────────────────────────────────────────────────────

    def _update_grayline(self):
        """Update gray line status from config location."""
        try:
            lat = self.cfg.get("location.lat", 0.0) or 0.0
            lon = self.cfg.get("location.lon", 0.0) or 0.0
            if not (lat or lon):
                grid = self.cfg.grid or ""
                if grid:
                    from core.location import _grid_to_latlon
                    lat, lon = _grid_to_latlon(grid)
            if lat or lon:
                info   = gray_line_info(lat, lon)
                status = format_gray_line_status(info)
                self._gl_lbl.setText(status)
                if info.is_gray_line:
                    self._gl_lbl.setStyleSheet(
                        "background:#0a1a0a;color:#3fbe6f;"
                        ""
                        "font-family:'Courier New';"
                        "border:1px solid #3fbe6f;"
                        "border-radius:3px;padding:2px 8px;")
                else:
                    self._gl_lbl.setStyleSheet(
                        "background:#0a0a0a;"
                        ""
                        "font-family:'Courier New';"
                        "border:1px solid #1a1a1a;"
                        "border-radius:3px;padding:2px 8px;")
            else:
                self._gl_lbl.setText(
                    "Set location to see gray line status")
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(
                f"Gray line update: {e}")
        # Update every 60s
        QTimer.singleShot(60_000, self._update_grayline)

    def _show_fetching_state(self):
        """Show placeholder while solar data is being fetched."""
        if self._feed.solar.sfi == 0.0:
            self._summary_lbl.setText(
                "Fetching solar data from NOAA…")
            self._summary_lbl.setStyleSheet(
                "")
            self._age_lbl.setText("Connecting…")

    def _on_solar(self, solar: SolarData):
        QTimer.singleShot(0,
            lambda s=solar: self._apply_solar(s))

    def _on_alert(self, title: str,
                   msg: str, severity: str):
        QTimer.singleShot(0,
            lambda t=title, m=msg: self._show_alert(t, m))

    def _apply_solar(self, solar: SolarData):
        """Update all solar index displays."""
        # Summary
        self._summary_lbl.setText(solar.conditions_summary)

        # Color summary by conditions
        if solar.storm_level >= 2:
            color = "#cc4444"
        elif solar.storm_level >= 1 or solar.k_index >= 4:
            color = "#eeaa22"
        elif solar.sfi >= 150:
            color = "#00aa44"
        else:
            color = "#3fbe6f"
        self._summary_lbl.setStyleSheet(
            f"font-weight:bold;color:{color};")

        # Indices
        def _set(key, text, trend_text="", color="#3fbe6f"):
            val_lbl, trend_lbl = self._solar_widgets[key]
            val_lbl.setText(text)
            val_lbl.setStyleSheet(
                f"color:{color};"
                "font-weight:bold;font-family:'Courier New';")
            trend_lbl.setText(trend_text)

        _set("sfi",  f"{solar.sfi:.0f}",
             "↑" if solar.sfi_trend == "rising" else
             "↓" if solar.sfi_trend == "falling" else "→")
        _set("sn",   str(solar.sunspot_num))
        kp_color = ("#cc4444" if solar.k_index >= 5
                    else "#eeaa22" if solar.k_index >= 3
                    else "#3fbe6f")
        _set("k",    f"{solar.k_index:.1f}",
             "↑" if solar.k_trend == "rising" else
             "↓" if solar.k_trend == "falling" else "→",
             kp_color)
        _set("a",    f"{solar.a_index:.0f}")
        _set("xray", solar.xray_class)

        storm_color = ("#cc4444" if solar.storm_level >= 2
                       else "#eeaa22" if solar.storm_level >= 1
                       else "#3fbe6f")
        _set("storm",
             f"G{solar.storm_level}",
             color=storm_color)

        # Recommendations
        recs = solar.band_recommendations
        for i, lbl in enumerate(self._rec_labels):
            lbl.setText(recs[i] if i < len(recs) else "")

        # Aurora
        if solar.aurora_alert:
            self._aurora_lbl.setText(
                f"🌌 Aurora alert — Kp={solar.k_index:.0f}\n"
                f"Enhanced propagation possible on 10m/6m/VHF.")
            self._aurora_widget.show()
        else:
            self._aurora_widget.hide()

        # Age
        self._age_lbl.setText(
            f"Updated {solar.age_minutes:.0f}m ago")

        # Band conditions
        self._refresh_band_display()

    def _refresh_band_display(self):
        conditions = self._feed.band_conditions
        cond_map = {c.band: c for c in conditions}
        level_map = {
            "excellent": 4,
            "good":      3,
            "fair":      2,
            "poor":      1,
            "closed":    0,
        }
        color_map = {
            "excellent": "#00aa44",
            "good":      "#3fbe6f",
            "fair":      "#aaaa22",
            "poor":      "#cc8822",
            "closed":    "#cc4444",
        }
        for band, (cond_lbl, bar) in self._band_rows.items():
            c = cond_map.get(band)
            if not c:
                continue
            cond_lbl.setText(c.condition.capitalize())
            cond_lbl.setStyleSheet(
                f"color:{color_map.get(c.condition,'#555')};"
                "")
            bar.setValue(level_map.get(c.condition, 0))
            bar.setStyleSheet(
                f"QProgressBar{{background:#111;"
                f"border:1px solid #222;border-radius:3px;}}"
                f"QProgressBar::chunk{{background:"
                f"{color_map.get(c.condition,'#555')};"
                f"border-radius:2px;}}")

    def _show_alert(self, title: str, msg: str):
        self._aurora_lbl.setText(f"⚠ {title}\n{msg}")
        self._aurora_widget.setTitle(title)
        self._aurora_widget.show()

    def add_pskreporter_spot(self, callsign: str,
                              band: str, snr: int,
                              location: str):
        """Called from spot feed when a new spot arrives."""
        row = self._spots_table.rowCount()
        if row > 50:
            self._spots_table.removeRow(0)
            row = self._spots_table.rowCount()
        self._spots_table.insertRow(row)
        for col, val in enumerate(
                [callsign, band, f"{snr:+d} dB", location]):
            item = QTableWidgetItem(val)
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter)
            self._spots_table.setItem(row, col, item)

    def _manual_refresh(self):
        self._feed._fetch_all()
        self._age_lbl.setText("Refreshing…")

    def _refresh_display(self):
        solar = self._feed.solar
        if solar.sfi > 0:
            self._apply_solar(solar)
        else:
            # Still waiting - try again in 3 seconds
            QTimer.singleShot(3000, self._poll_for_data)

    def _poll_for_data(self):
        """Keep checking until data arrives."""
        solar = self._feed.solar
        if solar.sfi > 0:
            self._apply_solar(solar)
        elif self._feed._running:
            # Still fetching - check again
            QTimer.singleShot(3000, self._poll_for_data)
        else:
            self._summary_lbl.setText(
                "Could not fetch solar data — check internet connection")
