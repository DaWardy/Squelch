from __future__ import annotations
from dataclasses import dataclass, field
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
from core.themes import get_theme as _map_get_theme
from datetime import datetime, timezone

from ui.panel import SquelchPanel
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame,
    QCheckBox, QComboBox, QLineEdit, QSizePolicy,
    QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal

from network.grayline import (
    gray_line_info, format_gray_line_status)

log = logging.getLogger(__name__)

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False
    QWebEnginePage = object   # sentinel for subclassing guard


class _MapPage(QWebEnginePage):
    """QWebEnginePage that intercepts squelch:// navigation URLs.

    When the user clicks "Analyze propagation" in the Leaflet right-click
    popup, the popup's href navigates to squelch://path-analysis?lat=X&lon=Y.
    This page class catches that URL, emits path_analysis_requested, and
    cancels the navigation so the map stays in place.
    """
    path_analysis_requested = pyqtSignal(float, float)

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if url.scheme() == "squelch" and url.host() == "path-analysis":
            try:
                from urllib.parse import parse_qs
                params = parse_qs(url.query())
                lat = float(params["lat"][0])
                lon = float(params["lon"][0])
                self.path_analysis_requested.emit(lat, lon)
            except Exception:
                pass
            return False   # cancel navigation — map stays visible
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)

# Map refresh interval — gray line moves visibly over ~60s
MAP_REFRESH_S = 60

# Amateur band frequency ranges in MHz (ITU Region 2)
BAND_RANGES = {
    "160m": (1.8,   2.0),
    "80m":  (3.5,   4.0),
    "40m":  (7.0,   7.3),
    "20m":  (14.0,  14.35),
    "15m":  (21.0,  21.45),
    "10m":  (28.0,  29.7),
    "6m":   (50.0,  54.0),
    "2m":   (144.0, 148.0),
}


@dataclass
class HeardSpot:
    """Data for a station heard by any RF source (FT8, PSKReporter, etc.).

    Pass to MapTab.add_heard_station() instead of individual keyword args.
    Future pin sources (Winlink gateways, Local RF) use this same type.
    """
    callsign: str
    grid:     str   = ""
    lat:      float = 0.0
    lon:      float = 0.0
    source:   str   = "decode"
    freq_mhz: float = 0.0
    snr_db:   float = 0.0


class MapTab(SquelchPanel, QWidget):
    panel_id    = "map"
    panel_title = "Map"

    # Emitted when user right-clicks map → "Analyze propagation to this point"
    path_analysis_requested = pyqtSignal(float, float)   # lat, lon

    """
    Full-featured map tab with Leaflet.
    Falls back to a setup guide if QtWebEngine not installed.
    """

    def panel_actions(self) -> list:
        """Toolbar actions for workspace-mode title bar."""
        from PyQt6.QtGui import QAction
        a_ref = QAction("↺ Map", self)
        a_ref.setToolTip("Refresh map")
        a_ref.triggered.connect(self._refresh_map)

        a_psk = QAction("PSK", self)
        a_psk.setToolTip("Fetch PSKReporter 'who heard me' data")
        a_psk.triggered.connect(self._refresh_psk_hearing)

        return [a_ref, a_psk]

    def __init__(self, config, log_db=None,
                 parent=None):
        super().__init__(parent)
        self.cfg     = config
        self.log_db  = log_db
        self._timer  = None
        self._repeaters        = []
        self._aprs_stations    = []
        self._satellites       = []
        self._winlink_gateways = []
        self._wspr_spots:  list = []
        self._dx_spots:    list = []
        self._build()
        # Debounce timer for callsign search field
        self._cs_timer = QTimer(self)
        self._cs_timer.setSingleShot(True)
        self._cs_timer.timeout.connect(self._refresh_map)
        # PSK timer started lazily when callsign is configured
        from PyQt6.QtCore import QTimer as _QT
        _QT.singleShot(15000, self._start_psk_timer)
        self._start_psk_timer()

    # ── Build ─────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        if not HAS_WEBENGINE:
            self._build_no_webengine(root)
            return  # fallback map handles its own refresh

        # Toolbar
        root.addWidget(self._build_toolbar())

        # Map view — use _MapPage to intercept squelch:// navigation
        self._view = QWebEngineView()
        self._map_page = _MapPage(self._view)
        self._map_page.path_analysis_requested.connect(
            self.path_analysis_requested)
        self._view.setPage(self._map_page)
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
            "font-family:'Courier New';"
            "border-top:1px solid #1a1a1a;")
        root.addWidget(self._gl_bar)

        # Load initial map
        QTimer.singleShot(500, self._refresh_map)

        # Auto-refresh for gray line
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_map)
        self._timer.start(MAP_REFRESH_S * 1000)

    def _build_toolbar(self) -> QFrame:
        _t = _map_get_theme(self.cfg.get("ui.theme", "Dark"))
        bar = QFrame()
        bar.setFixedHeight(38)
        bar.setStyleSheet(
            f"background:{_t.bg_secondary};border-bottom:1px solid {_t.border};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(8)
        self._toolbar_add_layer_toggles(lay)
        lay.addWidget(_vsep(_t.border))
        lay.addWidget(QLabel("QSOs:"))
        self._qso_filter = QComboBox()
        self._qso_filter.addItems(
            ["All", "Last 50", "Last 24h", "Last 7 days", "Current band"])
        self._qso_filter.setFixedWidth(100)
        self._qso_filter.currentTextChanged.connect(lambda _: self._refresh_map())
        lay.addWidget(self._qso_filter)
        lay.addWidget(_vsep(_t.border))
        lay.addWidget(QLabel("Band:"))
        self._band_combo = QComboBox()
        self._band_combo.addItems(
            ["All", "160m", "80m", "40m", "20m", "15m", "10m", "6m", "2m"])
        self._band_combo.setFixedWidth(72)
        self._band_combo.setToolTip("Filter heard stations by frequency band")
        self._band_combo.currentTextChanged.connect(lambda _: self._refresh_map())
        lay.addWidget(self._band_combo)
        self._cs_edit = QLineEdit()
        self._cs_edit.setPlaceholderText("Search…")
        self._cs_edit.setFixedWidth(90)
        self._cs_edit.setFixedHeight(24)
        self._cs_edit.setToolTip(
            "Filter heard and APRS stations by callsign prefix")
        self._cs_edit.textChanged.connect(
            lambda _: self._cs_timer.start(400))
        lay.addWidget(self._cs_edit)
        lay.addWidget(_vsep(_t.border))
        # APRS beacon toggle
        self._beacon_btn = QPushButton("⚑ Beacon")
        self._beacon_btn.setCheckable(True)
        self._beacon_btn.setFixedHeight(26)
        self._beacon_btn.setFixedWidth(76)
        self._beacon_btn.setToolTip(
            "Transmit APRS position beacon via APRS-IS.\n"
            "Requires APRS connection (connect in Local RF tab).\n"
            "Interval and comment set in Settings → APIs → APRS.")
        self._beacon_btn.toggled.connect(self._on_beacon_toggle)
        lay.addWidget(self._beacon_btn)
        self._beacon_status = QLabel("")
        self._beacon_status.setStyleSheet(
            f"color:{_t.fg_muted};font-size:9px;")
        self._beacon_status.setFixedWidth(80)
        lay.addWidget(self._beacon_status)
        lay.addStretch()
        self._stats_lbl = QLabel("")
        self._stats_lbl.setStyleSheet(
            f"color:{_t.fg_muted};font-size:10px;")
        lay.addWidget(self._stats_lbl)
        lay.addWidget(_vsep(_t.border))
        refresh_btn = QPushButton("↺ Refresh")
        refresh_btn.setFixedHeight(26)
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self._refresh_map)
        lay.addWidget(refresh_btn)
        center_btn = QPushButton("⌂ My Station")
        center_btn.setFixedHeight(26)
        center_btn.setFixedWidth(90)
        center_btn.clicked.connect(self._center_on_station)
        lay.addWidget(center_btn)
        return bar

    def _toolbar_add_layer_toggles(self, lay) -> None:
        self._show_gl = QCheckBox("Gray line")
        self._show_gl.setChecked(True)
        self._show_gl.setToolTip(
            "Show day/night terminator on map\n"
            "The gray line is the best time for DX\n"
            "Updates every 60 seconds")
        self._show_gl.toggled.connect(lambda _: self._refresh_map())
        lay.addWidget(self._show_gl)
        self._show_qso = QCheckBox("QSO paths")
        self._show_qso.setChecked(True)
        self._show_qso.setToolTip(
            "Draw great circle paths to logged QSOs\n"
            "Color-coded by mode (FT8=blue, CW=orange, SSB=green)")
        self._show_qso.toggled.connect(lambda _: self._refresh_map())
        lay.addWidget(self._show_qso)
        self._show_rep = QCheckBox("Repeaters")
        self._show_rep.setChecked(False)
        self._show_rep.toggled.connect(lambda _: self._refresh_map())
        lay.addWidget(self._show_rep)
        self._show_adsb = QCheckBox("ADS-B")
        self._show_adsb.setChecked(True)
        self._show_adsb.setToolTip(
            "Show aircraft from dump1090-fa\n"
            "Requires dump1090-fa running locally")
        self._show_adsb.toggled.connect(lambda _: self._refresh_map())
        lay.addWidget(self._show_adsb)
        self._show_aprs = QCheckBox("APRS")
        self._show_aprs.setChecked(True)
        self._show_aprs.setToolTip(
            "Show APRS stations from APRS-IS\n"
            "Connect in Local RF tab first")
        self._show_aprs.toggled.connect(lambda _: self._refresh_map())
        lay.addWidget(self._show_aprs)
        self._show_wl_gw = QCheckBox("Winlink GW")
        self._show_wl_gw.setChecked(True)
        self._show_wl_gw.setToolTip(
            "Show Winlink RMS gateway pins\n"
            "Fetch via Winlink tab → Gateways → Refresh")
        self._show_wl_gw.toggled.connect(lambda _: self._refresh_map())
        lay.addWidget(self._show_wl_gw)

    def _build_fallback_toolbar(self) -> "QFrame":
        """Controls bar for the Qt fallback map."""
        _t = _map_get_theme(self.cfg.get("ui.theme", "Dark"))
        bar = QFrame()
        bar.setFixedHeight(36)
        bar.setStyleSheet(
            f"background:{_t.bg_secondary};border-bottom:1px solid {_t.border};")
        tl = QHBoxLayout(bar)
        tl.setContentsMargins(8, 4, 8, 4)
        tl.setSpacing(8)
        self._show_gl = QCheckBox("Gray line")
        self._show_gl.setChecked(True)
        self._show_gl.setToolTip(
            "Show the day/night terminator\n"
            "Best DX propagation near the gray line")
        self._show_gl.toggled.connect(self._refresh_fallback_map)
        tl.addWidget(self._show_gl)
        self._show_qso = QCheckBox("QSO paths")
        self._show_qso.setChecked(True)
        self._show_qso.setToolTip("Draw great circle paths to logged QSOs")
        self._show_qso.toggled.connect(self._refresh_fallback_map)
        tl.addWidget(self._show_qso)
        self._show_aprs = QCheckBox("APRS")
        self._show_aprs.setChecked(True)
        self._show_aprs.setToolTip("Show APRS stations — connect in Local RF tab")
        self._show_aprs.toggled.connect(self._refresh_fallback_map)
        tl.addWidget(self._show_aprs)
        tl.addStretch()
        note = QLabel("ℹ  Qt fallback renderer")
        note.setStyleSheet("")
        tl.addWidget(note)
        refresh_btn = QPushButton("↺")
        refresh_btn.setFixedSize(28, 26)
        refresh_btn.setToolTip("Refresh gray line and QSO paths")
        refresh_btn.clicked.connect(self._refresh_fallback_map)
        tl.addWidget(refresh_btn)
        return bar

    def _build_no_webengine(self, layout):
        """Fallback map — pure Qt drawing, no WebEngine needed."""
        from ui.tabs.map_fallback import WorldMapWidget
        layout.addWidget(self._build_fallback_toolbar())
        self._fallback_map = WorldMapWidget()
        layout.addWidget(self._fallback_map, 1)
        self._gl_bar = QLabel("Computing gray line…")
        self._gl_bar.setFixedHeight(24)
        self._gl_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._gl_bar.setStyleSheet(
            "background:#0a0a0a;font-family:'Courier New';"
            "border-top:1px solid #1a1a1a;")
        layout.addWidget(self._gl_bar)
        self._fb_timer = QTimer(self)
        self._fb_timer.timeout.connect(self._refresh_fallback_map)
        self._fb_timer.start(60_000)

    # ── Map rendering ──────────────────────────────────────────

    def _refresh_map(self):
        """Rebuild and reload the map HTML."""
        if not HAS_WEBENGINE:
            return

        try:
            from network.map_data import build_map_html

            reps = self._repeaters \
                   if self._show_rep.isChecked() else []
            wl_gws = (self._winlink_gateways
                      if getattr(self, "_show_wl_gw", None)
                         and self._show_wl_gw.isChecked()
                      else [])
            heard = self._filtered_heard()
            aprs  = self._filtered_aprs() if self._show_aprs.isChecked() else []
            html = build_map_html(
                config              = self.cfg,
                log_db              = self.log_db,
                repeaters           = reps,
                aprs_stations       = aprs,
                show_grayline       = self._show_gl.isChecked(),
                show_qso_paths      = self._show_qso.isChecked(),
                show_adsb           = self._show_adsb.isChecked(),
                show_aprs           = self._show_aprs.isChecked(),
                center_on_station   = True,
                heard_stations      = heard,
                hearing_me          = getattr(self, "_hearing_me", {}),
                winlink_gateways    = wl_gws,
                satellites          = list(self._satellites),
                wspr_spots          = list(self._wspr_spots),
                dx_spots            = list(self._dx_spots),
            )
            self._view.setHtml(html)
            self._update_layer_stats(heard, aprs)
            self._update_gl_status()

        except Exception as e:
            log.error(f"Map refresh: {e}")
            import traceback
            traceback.print_exc()

    def _filtered_heard(self) -> dict:
        """Return _heard_stations filtered by active band and callsign search."""
        heard = dict(getattr(self, "_heard_stations", {}))
        band = getattr(self, "_band_combo", None)
        band = band.currentText() if band else "All"
        if band != "All" and band in BAND_RANGES:
            lo, hi = BAND_RANGES[band]
            heard = {k: v for k, v in heard.items()
                     if lo <= v.get("freq_mhz", 0.0) <= hi}
        search = self._active_search()
        if search:
            heard = {k: v for k, v in heard.items()
                     if k.upper().startswith(search)}
        return heard

    def _filtered_aprs(self) -> list:
        """Return _aprs_stations filtered by active callsign search."""
        aprs = list(self._aprs_stations)
        search = self._active_search()
        if search:
            aprs = [a for a in aprs
                    if a.get("call", "").upper().startswith(search)]
        return aprs

    def _active_search(self) -> str:
        """Return uppercase callsign search prefix, or empty string."""
        edit = getattr(self, "_cs_edit", None)
        return edit.text().strip().upper() if edit else ""

    def _update_layer_stats(self, heard: dict, aprs: list) -> None:
        """Update the toolbar layer-count label."""
        lbl = getattr(self, "_stats_lbl", None)
        if lbl is None:
            return
        parts = []
        if heard:
            parts.append(f"Heard: {len(heard)}")
        if aprs:
            parts.append(f"APRS: {len(aprs)}")
        psk = len(getattr(self, "_hearing_me", {}))
        if psk:
            parts.append(f"PSK: {psk}")
        if self._show_rep.isChecked() and self._repeaters:
            parts.append(f"Reps: {len(self._repeaters)}")
        lbl.setText("  ".join(parts))

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
                        ""
                        "font-family:'Courier New';"
                        "border-top:1px solid #3fbe6f;")
                else:
                    self._gl_bar.setStyleSheet(
                        "background:#0a0a0a;"
                        ""
                        "font-family:'Courier New';"
                        "border-top:1px solid #1a1a1a;")
        except Exception as e:
            log.debug(f"GL status: {e}")

    def _center_on_station(self):
        """Re-center map on station location."""
        self._refresh_map()

    # ── Public API ────────────────────────────────────────────

    def set_winlink_gateways(self, gateways: list):
        """Called by Winlink tab after gateway fetch completes."""
        self._winlink_gateways = gateways
        if getattr(self, "_show_wl_gw", None) and self._show_wl_gw.isChecked():
            QTimer.singleShot(0, self._refresh_map)

    def set_repeaters(self, repeaters: list):
        """Called by Local RF tab when search results arrive."""
        self._repeaters = repeaters
        if self._show_rep.isChecked():
            self._refresh_map()

    def set_satellite_positions(self, sats: list):
        """Called when satellite positions update."""
        self._satellites = sats
        if not HAS_WEBENGINE:
            if hasattr(self, "_fallback_map"):
                self._fallback_map.set_satellite_positions(
                    sats)
        else:
            # Refresh Leaflet map
            QTimer.singleShot(0, self._refresh_map)

    # ── APRS beacon ───────────────────────────────────────────────────────

    def _on_beacon_toggle(self, checked: bool) -> None:
        """Start or stop the APRS position beacon."""
        try:
            mw = self.window()
            beacon = getattr(mw, "_aprs_beacon", None)
            if not beacon:
                self._beacon_btn.setChecked(False)
                self._beacon_status.setText("No APRS conn")
                return
            if checked:
                interval = int(self.cfg.get("aprs.beacon_interval_s",
                                            600) or 600)
                beacon.on_beacon(self._on_beacon_sent)
                beacon.start(interval)
                self._beacon_btn.setStyleSheet("color:#3fbe6f;")
                self._beacon_status.setText("Arming…")
                self._beacon_countdown_timer = QTimer(self)
                self._beacon_countdown_timer.timeout.connect(
                    self._update_beacon_countdown)
                self._beacon_countdown_timer.start(10_000)
            else:
                if beacon.is_running:
                    beacon.stop()
                self._beacon_btn.setStyleSheet("")
                self._beacon_status.setText("")
                if hasattr(self, "_beacon_countdown_timer"):
                    self._beacon_countdown_timer.stop()
        except Exception:
            pass

    def _on_beacon_sent(self, packet: str, success: bool) -> None:
        """Callback from APRSBeacon — runs in beacon thread."""
        from PyQt6.QtCore import QTimer as _QT
        _QT.singleShot(0, lambda p=packet, s=success: self._apply_beacon_status(p, s))

    def _apply_beacon_status(self, packet: str, success: bool) -> None:
        if success:
            self._beacon_status.setText("Sent ✓")
            self._beacon_status.setStyleSheet("color:#3fbe6f;font-size:9px;")
        else:
            self._beacon_status.setText("Send failed")
            self._beacon_status.setStyleSheet("color:#cc4444;font-size:9px;")

    def _update_beacon_countdown(self) -> None:
        try:
            mw = self.window()
            beacon = getattr(mw, "_aprs_beacon", None)
            if beacon and beacon.is_running:
                secs = beacon.seconds_until_next
                if secs > 0:
                    self._beacon_status.setText(f"In {secs//60}m{secs%60:02d}s")
                    self._beacon_status.setStyleSheet(
                        "color:#888;font-size:9px;")
        except Exception:
            pass

    def set_wspr_spots(self, spots: list) -> None:
        """Called when a new WSPR spot is decoded; accumulates for map display."""
        self._wspr_spots = spots
        if HAS_WEBENGINE:
            QTimer.singleShot(0, self._refresh_map)

    def set_dx_spots(self, spots: list) -> None:
        """Update DX cluster spots on map."""
        self._dx_spots = spots
        if HAS_WEBENGINE:
            QTimer.singleShot(0, self._refresh_map)

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

    def _latlon_from_spot(self, spot: "HeardSpot") -> tuple[float, float] | None:
        """Resolve (lat, lon) from a HeardSpot, trying grid if coords are missing.

        Returns None if no coordinates can be determined.
        """
        lat, lon = spot.lat, spot.lon
        if not lat and not lon and spot.grid:
            try:
                from core.location import _grid_to_latlon
                lat, lon = _grid_to_latlon(spot.grid.upper())
            except Exception:
                return None
        return (lat, lon) if (lat or lon) else None

    def add_heard_station(self, callsign: str, spot: "HeardSpot | None" = None):
        """Pin a station heard from any source. Idempotent — same callsign updates.

        spot: HeardSpot dataclass.  If None a bare-minimum entry is stored.
        Legacy keyword-arg callers should migrate to HeardSpot; see HeardSpot
        at module level.
        """
        if spot is None:
            spot = HeardSpot(callsign=callsign)
        coords = self._latlon_from_spot(spot)
        if coords is None:
            return
        lat, lon = coords
        if not hasattr(self, '_heard_stations'):
            self._heard_stations = {}
        import time
        self._heard_stations[callsign.upper()] = {
            "callsign": callsign.upper(),
            "grid":     (spot.grid or "").upper(),
            "lat":      lat,
            "lon":      lon,
            "source":   spot.source,
            "freq_mhz": spot.freq_mhz,
            "snr_db":   spot.snr_db,
            "ts":       time.time(),
        }
        if not getattr(self, "_heard_refresh_pending", False):
            self._heard_refresh_pending = True
            QTimer.singleShot(2000, self._refresh_heard)

    def _refresh_heard(self):
        """Apply pending heard-station updates to the active map view."""
        self._heard_refresh_pending = False
        try:
            if hasattr(self, "_fallback_map") and self._fallback_map:
                self._fallback_map.set_heard_stations(
                    getattr(self, "_heard_stations", {}))
                self._fallback_map.update()
            else:
                # WebEngine path — refresh via the existing refresh hook
                self._refresh_map()
        except Exception:
            pass

    # ── Fallback map (no WebEngine) ──────────────────────────────────────

    def _apply_fallback_terminator(self, now) -> None:
        """Set or clear the gray-line terminator on the fallback map."""
        if hasattr(self, "_show_gl") and self._show_gl.isChecked():
            from network.grayline import terminator_points
            self._fallback_map.set_terminator(terminator_points(now, steps=120))
        else:
            self._fallback_map.set_terminator([])

    def _apply_fallback_qso_paths(self) -> None:
        """Set or clear QSO great-circle paths on the fallback map."""
        if hasattr(self, "_show_qso") and self._show_qso.isChecked() and self.log_db:
            self._fallback_map.set_qso_paths(self._build_qso_paths())
        else:
            self._fallback_map.set_qso_paths([])

    def _apply_fallback_satellites(self) -> None:
        """Set or clear satellite positions on the fallback map."""
        if hasattr(self, '_show_sats') and self._show_sats.isChecked():
            self._fallback_map.set_satellite_positions(self._satellites)
        else:
            self._fallback_map.set_satellite_positions([])

    def _refresh_fallback_map(self):
        """Refresh the Qt-drawn fallback map — gray line, station, QSO paths."""
        if not hasattr(self, "_fallback_map"):
            return
        try:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            lat = float(self.cfg.get("location.lat", 0.0) or 0.0)
            lon = float(self.cfg.get("location.lon", 0.0) or 0.0)

            self._fallback_map.set_station(lat, lon, self.cfg.callsign or "")
            self._apply_fallback_terminator(now)
            self._apply_fallback_qso_paths()
            self._apply_fallback_satellites()

            self._update_fallback_gl_bar(lat, lon, now)

        except Exception as e:
            log.debug(f"Fallback map refresh: {e}")

    def _update_fallback_gl_bar(self, lat: float, lon: float, now):
        """Update the gray-line status bar below the fallback map."""
        if not (lat or lon):
            self._gl_bar.setText("Set location in top bar to show gray line")
            return
        info   = gray_line_info(lat, lon, now)
        status = format_gray_line_status(info)
        self._fallback_map.set_gl_info(info)
        self._gl_bar.setText(status)
        self._gl_bar.setStyleSheet(
            "background:#0a1a0a;color:#3fbe6f;"
            "font-family:'Courier New';border-top:1px solid #3fbe6f;"
            if info.is_gray_line else
            "background:#0a0a0a;"
            "font-family:'Courier New';border-top:1px solid #1a1a1a;")

    def _resolve_qso_coords(self, q):
        """Return (my_lat, my_lon, their_lat, their_lon) for one QSO, or None."""
        my_lat  = float(getattr(q, "my_lat", 0.0) or
                        self.cfg.get("location.lat", 0.0) or 0.0)
        my_lon  = float(getattr(q, "my_lon", 0.0) or
                        self.cfg.get("location.lon", 0.0) or 0.0)
        their_lat = float(getattr(q, "lat", 0.0) or 0.0)
        their_lon = float(getattr(q, "lon", 0.0) or 0.0)
        if not their_lat and getattr(q, "grid", ""):
            try:
                from core.location import _grid_to_latlon
                their_lat, their_lon = _grid_to_latlon(q.grid)
            except Exception:
                pass
        if my_lat and my_lon and their_lat and their_lon:
            return my_lat, my_lon, their_lat, their_lon
        return None

    def _build_qso_paths(self) -> list:
        """Build QSO path dicts for map drawing."""
        paths = []
        try:
            for q in self.log_db.recent_qsos(limit=200):
                coords = self._resolve_qso_coords(q)
                if coords:
                    my_lat, my_lon, their_lat, their_lon = coords
                    paths.append({"from": [my_lat, my_lon],
                                  "to":   [their_lat, their_lon],
                                  "mode": q.mode, "call": q.call})
        except Exception as e:
            log.debug(f"QSO paths: {e}")
        return paths

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
        if HAS_WEBENGINE:
            QTimer.singleShot(200, self._refresh_map)
        else:
            QTimer.singleShot(200, self._refresh_fallback_map)


    # ── PSKReporter "who heard me" layer ──────────────────────────────────

    def _start_psk_timer(self):
        """5-minute refresh of PSKReporter hearing-me pins."""
        cs = (self.cfg.callsign if hasattr(self.cfg, 'callsign')
              else self.cfg.get('station.callsign', ''))
        if not cs or cs == 'NOCALL':
            return   # no callsign — nothing to query
        from PyQt6.QtCore import QTimer
        self._psk_timer = QTimer(self)
        self._psk_timer.setInterval(5 * 60 * 1000)
        self._psk_timer.timeout.connect(self._refresh_psk_hearing)
        self._psk_timer.start()
        QTimer.singleShot(10000, self._refresh_psk_hearing)

    def _refresh_psk_hearing(self):
        """Fetch PSKReporter spots in background thread."""
        callsign = (self.cfg.callsign if hasattr(self.cfg, 'callsign')
                    else self.cfg.get("station.callsign", ""))
        if not callsign or callsign in ("NOCALL", ""):
            return
        import threading
        from PyQt6.QtCore import pyqtSignal, QObject

        class _W(QObject):
            done = pyqtSignal(list)

        w = _W()
        w.done.connect(self._on_psk_spots)

        def _run():
            try:
                from network.pskreporter import fetch_hearing_me
                spots = fetch_hearing_me(callsign, seconds=1800)
            except Exception:
                spots = []
            w.done.emit(spots)

        threading.Thread(target=_run, daemon=True, name="PSKFetch").start()

    def _on_psk_spots(self, spots: list):
        """Update hearing-me layer from PSKReporter results."""
        import time
        self._hearing_me = {}
        for s in spots:
            call = s.get("callsign", "")
            if not call:
                continue
            self._hearing_me[call] = {
                "callsign": call, "grid": s.get("grid", ""),
                "freq_hz": s.get("freq_hz", 0), "mode": s.get("mode", ""),
                "snr": s.get("snr", 0), "lat": 0.0, "lon": 0.0,
                "ts": time.time(),
            }
        if hasattr(self, "_fallback_map") and self._fallback_map:
            self._fallback_map.set_hearing_me(self._hearing_me)
        if HAS_WEBENGINE:
            QTimer.singleShot(0, self._refresh_map)


def _vsep(border: str = "#2a2a2a") -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setStyleSheet(f"color:{border};")
    f.setFixedWidth(1)
    return f

