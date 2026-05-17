from __future__ import annotations
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
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- ui/tabs/map_tab.py
Embedded Leaflet map tab.
Shows: station location, QSO paths, gray line,
       APRS stations, ADS-B aircraft, repeaters.
Requires QtWebEngine (PyQtWebEngine).
Shows a graceful fallback if not installed.
"""

import sys
import logging
from datetime import datetime, timezone

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame,
    QCheckBox, QComboBox, QSizePolicy,
    QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices

from network.grayline import (
    gray_line_info, format_gray_line_status)

log = logging.getLogger(__name__)

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineSettings
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

# Map refresh interval — gray line moves visibly over ~60s
MAP_REFRESH_S = 60


class MapTab(QWidget):
    """
    Full-featured map tab with Leaflet.
    Falls back to a setup guide if QtWebEngine not installed.
    """

    def __init__(self, config, log_db=None,
                 parent=None):
        super().__init__(parent)
        self.cfg     = config
        self.log_db  = log_db
        self._timer  = None
        self._repeaters      = []
        self._aprs_stations  = []
        self._build()

    # ── Build ─────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        if not HAS_WEBENGINE:
            self._build_no_webengine(root)
            return

        # Toolbar
        root.addWidget(self._build_toolbar())

        # Map view
        self._view = QWebEngineView()
        self._view.settings().setAttribute(
            QWebEngineSettings.WebAttribute
            .JavascriptEnabled, True)
        self._view.settings().setAttribute(
            QWebEngineSettings.WebAttribute
            .LocalContentCanAccessRemoteUrls, True)
        self._view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding)
        root.addWidget(self._view, 1)

        # Gray line status bar
        self._gl_bar = QLabel("Computing gray line…")
        self._gl_bar.setFixedHeight(24)
        self._gl_bar.setAlignment(
            Qt.AlignmentFlag.AlignCenter)
        self._gl_bar.setStyleSheet(
            "background:#0a0a0a;color:#3fbe6f;"
            "font-size:11px;font-family:'Courier New';"
            "border-top:1px solid #1a1a1a;")
        root.addWidget(self._gl_bar)

        # Load initial map
        QTimer.singleShot(500, self._refresh_map)

        # Auto-refresh for gray line
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_map)
        self._timer.start(MAP_REFRESH_S * 1000)

    def _build_toolbar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(38)
        bar.setStyleSheet(
            "background:#0d0d0d;"
            "border-bottom:1px solid #1a1a1a;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(8)

        # Layer toggles
        self._show_gl = QCheckBox("Gray line")
        self._show_gl.setChecked(True)
        self._show_gl.toggled.connect(
            lambda _: self._refresh_map())
        lay.addWidget(self._show_gl)

        self._show_qso = QCheckBox("QSO paths")
        self._show_qso.setChecked(True)
        self._show_qso.toggled.connect(
            lambda _: self._refresh_map())
        lay.addWidget(self._show_qso)

        self._show_rep = QCheckBox("Repeaters")
        self._show_rep.setChecked(False)
        self._show_rep.toggled.connect(
            lambda _: self._refresh_map())
        lay.addWidget(self._show_rep)

        self._show_adsb = QCheckBox("ADS-B")
        self._show_adsb.setChecked(True)
        self._show_adsb.toggled.connect(
            lambda _: self._refresh_map())
        lay.addWidget(self._show_adsb)

        self._show_aprs = QCheckBox("APRS")
        self._show_aprs.setChecked(True)
        self._show_aprs.toggled.connect(
            lambda _: self._refresh_map())
        lay.addWidget(self._show_aprs)

        lay.addWidget(_vsep())

        # QSO filter
        lay.addWidget(QLabel("QSOs:"))
        self._qso_filter = QComboBox()
        self._qso_filter.addItems([
            "All", "Last 50", "Last 24h",
            "Last 7 days", "Current band"])
        self._qso_filter.setFixedWidth(100)
        self._qso_filter.currentTextChanged.connect(
            lambda _: self._refresh_map())
        lay.addWidget(self._qso_filter)

        lay.addStretch()

        # Refresh button
        refresh_btn = QPushButton("↺ Refresh")
        refresh_btn.setFixedHeight(26)
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self._refresh_map)
        lay.addWidget(refresh_btn)

        # Center on station
        center_btn = QPushButton("⌂ My Station")
        center_btn.setFixedHeight(26)
        center_btn.setFixedWidth(90)
        center_btn.clicked.connect(self._center_on_station)
        lay.addWidget(center_btn)

        return bar

    def _build_no_webengine(self, layout):
        """Shown when PyQtWebEngine is not installed."""
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(40, 40, 40, 40)
        l.setSpacing(10)

        title = QLabel("🗺  Map — Setup Required")
        title.setStyleSheet(
            "color:#3fbe6f;font-size:16px;"
            "font-weight:bold;")
        l.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#1a1a1a;")
        l.addWidget(sep)

        msg = QLabel(
            "The map requires PyQtWebEngine (QtWebEngine).\n\n"
            "Install it with:\n\n"
            "    pip install PyQtWebEngine\n\n"
            "or:\n\n"
            "    python installer.py\n\n"
            "Then restart Squelch.")
        msg.setWordWrap(True)
        msg.setStyleSheet(
            "color:#888;font-size:12px;"
            "font-family:'Courier New';")
        l.addWidget(msg)

        # Features preview
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color:#1a1a1a;margin-top:8px;")
        l.addWidget(sep2)

        features = QLabel(
            "Map features (when installed):\n\n"
            "  ● Gray line terminator — updates every 60 seconds\n"
            "  ● QSO paths — great circle lines to logged contacts\n"
            "  ● Station location with grid square overlay\n"
            "  ● ADS-B aircraft from dump1090-fa\n"
            "  ● APRS stations (v0.7.1)\n"
            "  ● Nearest repeaters from Local RF tab\n"
            "  ● Dark map tile layer")
        features.setStyleSheet(
            "color:#555;font-size:11px;")
        l.addWidget(features)
        l.addStretch()
        layout.addWidget(w)

    # ── Map rendering ──────────────────────────────────────────

    def _refresh_map(self):
        """Rebuild and reload the map HTML."""
        if not HAS_WEBENGINE:
            return

        try:
            from network.map_data import build_map_html

            reps = self._repeaters \
                   if self._show_rep.isChecked() else []

            html = build_map_html(
                config            = self.cfg,
                log_db            = self.log_db,
                repeaters         = reps,
                aprs_stations     = (self._aprs_stations
                    if self._show_aprs.isChecked() else []),
                show_grayline     = self._show_gl.isChecked(),
                show_qso_paths    = self._show_qso.isChecked(),
                show_adsb         = self._show_adsb.isChecked(),
                show_aprs         = self._show_aprs.isChecked(),
                center_on_station = True,
            )
            self._view.setHtml(html)

            # Update gray line status bar
            self._update_gl_status()

        except Exception as e:
            log.error(f"Map refresh: {e}")
            import traceback
            traceback.print_exc()

    def _update_gl_status(self):
        """Update the gray line status bar text."""
        try:
            lat = self.cfg.get("location.lat", 0.0)
            lon = self.cfg.get("location.lon", 0.0)
            if lat or lon:
                info   = gray_line_info(lat, lon)
                status = format_gray_line_status(info)
                self._gl_bar.setText(status)
                if info.is_gray_line:
                    self._gl_bar.setStyleSheet(
                        "background:#0a1a0a;color:#3fbe6f;"
                        "font-size:11px;"
                        "font-family:'Courier New';"
                        "border-top:1px solid #3fbe6f;")
                else:
                    self._gl_bar.setStyleSheet(
                        "background:#0a0a0a;color:#666;"
                        "font-size:11px;"
                        "font-family:'Courier New';"
                        "border-top:1px solid #1a1a1a;")
        except Exception as e:
            log.debug(f"GL status: {e}")

    def _center_on_station(self):
        """Re-center map on station location."""
        self._refresh_map()

    # ── Public API ────────────────────────────────────────────

    def set_repeaters(self, repeaters: list):
        """Called by Local RF tab when search results arrive."""
        self._repeaters = repeaters
        if self._show_rep.isChecked():
            self._refresh_map()

    def set_aprs_stations(self, stations: list):
        """Called when APRS packet received — update map."""
        self._aprs_stations = stations
        if self._show_aprs.isChecked():
            # Throttle refreshes — don't rebuild map every packet
            if not hasattr(self, '_aprs_refresh_pending'):
                self._aprs_refresh_pending = False
            if not self._aprs_refresh_pending:
                self._aprs_refresh_pending = True
                QTimer.singleShot(
                    5000,   # Batch updates every 5 seconds
                    self._refresh_aprs)

    def _refresh_aprs(self):
        self._aprs_refresh_pending = False
        if HAS_WEBENGINE:
            self._refresh_map()

    def on_location_change(self, loc, _rr=False):
        """Called when station location changes."""
        QTimer.singleShot(0, self._refresh_map)

    def showEvent(self, event):
        """Refresh map when tab becomes visible."""
        super().showEvent(event)
        QTimer.singleShot(200, self._refresh_map)


def _vsep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setStyleSheet("color:#1e1e1e;")
    f.setFixedWidth(1)
    return f
