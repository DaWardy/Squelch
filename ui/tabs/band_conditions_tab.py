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
from core.themes import get_theme
from ui.panel import SquelchPanel
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QGroupBox, QFrame, QPushButton,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QSizePolicy, QScrollArea,
    QCheckBox,
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QRectF
from PyQt6.QtGui import QColor, QBrush, QFont, QPainter, QPen, QLinearGradient

from network.propagation import PropagationFeed, get_prop_feed, SolarData, BandCondition
from network.grayline import gray_line_info, format_gray_line_status
from core.band_reliability import band_reliability as _band_reliability, CHART_BANDS as _CHART_BANDS

log = logging.getLogger(__name__)



class BandReliabilityChart(QWidget):
    """Paints a colour-coded reliability bar for each HF band on a given path."""

    ROW_H = 17
    LABEL_W = 34
    VALUE_W = 38

    def __init__(self, parent=None):
        super().__init__(parent)
        self._muf    = 0.0
        self._luf    = 3.0
        self._path   = 0.0
        h = len(_CHART_BANDS) * self.ROW_H + 6
        self.setMinimumHeight(h)
        self.setMaximumHeight(h)

    def update_path(self, muf_mhz: float, luf_mhz: float, path_km: float):
        self._muf  = muf_mhz
        self._luf  = luf_mhz
        self._path = path_km
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W = self.width()
        bar_x  = self.LABEL_W
        bar_w  = max(40, W - self.LABEL_W - self.VALUE_W - 6)

        p.setFont(QFont("Courier New", 7))
        for row, (band, freq) in enumerate(_CHART_BANDS):
            y = row * self.ROW_H + 2
            rel, status = _band_reliability(freq, self._muf, self._luf, self._path)

            # Band label
            p.setPen(QColor("#aabbcc"))
            p.drawText(2, y + self.ROW_H - 4, band)

            # Colour bar
            filled = int(bar_w * rel)
            track_col = QColor(30, 40, 55)
            p.fillRect(bar_x, y + 3, bar_w, self.ROW_H - 6, QBrush(track_col))
            if filled > 2:
                r = int(255 * (1.0 - rel))
                g = int(220 * rel)
                bar_col = QColor(max(0, min(255, r)), max(0, min(220, g)), 30)
                lg = QLinearGradient(bar_x, 0, bar_x + filled, 0)
                lg.setColorAt(0.0, bar_col.lighter(120))
                lg.setColorAt(1.0, bar_col)
                p.fillRect(bar_x, y + 3, filled, self.ROW_H - 6, QBrush(lg))

            # Status text
            pct = f"{int(rel*100)}%" if rel > 0 else "—"
            p.setPen(QColor("#778899") if rel < 0.05
                     else QColor("#ffcc66") if rel < 0.60
                     else QColor("#88dd88"))
            p.drawText(bar_x + bar_w + 4, y + self.ROW_H - 4, pct)


class BandConditionsTab(SquelchPanel, QWidget):
    panel_id    = "band_conditions"
    panel_title = "Propagation"

    # Worker thread → main thread: path-to result delivery
    _path_resolved = pyqtSignal(float, float, str, bool, str)

    # Mid-band center frequencies for the "what if I tried this band?" UI
    _BAND_CTR_MHZ = {
        "160m": 1.900,  "80m": 3.750,  "60m": 5.357,
        "40m":  7.150,  "30m": 10.125, "20m": 14.150,
        "17m":  18.110, "15m": 21.250, "12m": 24.940,
        "10m":  28.300, "6m":  50.150,
    }

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


    def save_state(self) -> dict:
        try:
            return {
                "path_target":  self._path_edit.text(),
                "terrain_mode": getattr(self._prop_sideview, "_terrain_mode", "off"),
                "zone_gw":      self._zone_gw.isChecked(),
                "zone_nvis":    self._zone_nvis.isChecked(),
                "zone_sw":      self._zone_sw.isChecked(),
            }
        except Exception:
            return {}

    def restore_state(self, state: dict) -> None:
        try:
            if state.get("path_target"):
                self._path_edit.setText(state["path_target"])
            if state.get("terrain_mode"):
                self._prop_sideview.set_terrain_mode(state["terrain_mode"])
            for key, attr in (("zone_gw", "_zone_gw"),
                               ("zone_nvis", "_zone_nvis"),
                               ("zone_sw", "_zone_sw")):
                if key in state and hasattr(self, attr):
                    getattr(self, attr).setChecked(state[key])
        except Exception:
            pass

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)
        root.addLayout(self._build_header_bar(), 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(
            "QSplitter::handle{background:#1a1a1a;width:3px;}")
        splitter.addWidget(self._build_solar_pane())
        splitter.addWidget(self._build_bands_pane())
        splitter.setSizes([280, 600])
        root.addWidget(splitter, 1)

    def _build_header_bar(self) -> QHBoxLayout:
        from PyQt6.QtWidgets import QPushButton, QDoubleSpinBox
        _t = get_theme(self.cfg.get("ui.theme", "Dark"))
        hdr = QHBoxLayout()
        self._summary_lbl = QLabel(self.tr("Fetching solar data…"))
        self._summary_lbl.setStyleSheet(f"font-weight:bold;color:{_t.accent};")
        hdr.addWidget(self._summary_lbl)
        self._muf_lbl = QLabel("")
        self._muf_lbl.setStyleSheet(f"color:{_t.fg_secondary}; font-size:10px;")
        self._muf_lbl.setToolTip(
            "Estimated Maximum Usable Frequency for a ~3000 km F2 path "
            "based on current SFI. Updates with solar data.")
        hdr.addWidget(self._muf_lbl)
        self._header_add_path_group(hdr)
        self._eirp_spin = QDoubleSpinBox()
        self._eirp_spin.setRange(-30.0, 60.0)
        self._eirp_spin.setSingleStep(1.0)
        self._eirp_spin.setSuffix(" dBW")
        self._eirp_spin.setValue(self.cfg.get("propagation.eirp_dbw", 10.0))
        self._eirp_spin.setMaximumWidth(90)
        self._eirp_spin.setToolTip(
            "EIRP (Effective Isotropic Radiated Power)\n"
            "Used to estimate path loss vs distance.\n"
            "100W + 0dBi dipole ≈ 20 dBW\n"
            "100W + 3dBd Yagi ≈ 23 dBW")
        self._eirp_spin.valueChanged.connect(self._on_eirp_changed)
        hdr.addWidget(QLabel("EIRP:"))
        hdr.addWidget(self._eirp_spin)
        hdr.addStretch()
        refresh_btn = QPushButton(self.tr("↺ Refresh"))
        refresh_btn.setFixedWidth(90)
        refresh_btn.clicked.connect(self._manual_refresh)
        hdr.addWidget(refresh_btn)
        self._age_lbl = QLabel("")
        hdr.addWidget(self._age_lbl)
        return hdr

    def _header_add_path_group(self, hdr) -> None:
        """Add path-to field, Go button, and band filter to the header layout."""
        from PyQt6.QtWidgets import QLineEdit, QPushButton, QComboBox
        _t = get_theme(self.cfg.get("ui.theme", "Dark"))
        path_lbl = QLabel("Path to:")
        path_lbl.setStyleSheet(f"color:{_t.fg_secondary}; font-size:10px;")
        hdr.addWidget(path_lbl)
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("grid / call / city")
        self._path_edit.setMaximumWidth(130)
        self._path_edit.setToolTip(
            "Enter a Maidenhead grid (e.g. JO01), callsign, or city for "
            "path-specific MUF / band predictions.\n"
            "Leave blank for the default 3000 km F2 estimate.")
        self._path_edit.setStyleSheet("font-size:10px;")
        self._path_edit.returnPressed.connect(self._on_path_changed)
        hdr.addWidget(self._path_edit)
        # Go button — visible "apply" affordance; Enter also works
        self._path_go = QPushButton("Go")
        self._path_go.setMaximumWidth(40)
        self._path_go.setToolTip("Calculate path-specific MUF/distance/bearing")
        self._path_go.clicked.connect(self._on_path_changed)
        hdr.addWidget(self._path_go)
        # Band filter — uses band centre freq instead of live rig frequency
        self._band_filter = QComboBox()
        self._band_filter.addItems([
            "Auto", "160m", "80m", "60m", "40m", "30m", "20m",
            "17m", "15m", "12m", "10m", "6m"])
        self._band_filter.setMaximumWidth(70)
        self._band_filter.setToolTip(
            "Try a specific HAM band for this path.\n"
            "Auto uses the rig's current frequency.")
        self._band_filter.currentTextChanged.connect(
            lambda *_: self._on_path_changed())
        hdr.addWidget(self._band_filter)

    def _build_solar_pane(self) -> QWidget:
        left = QWidget()
        ll   = QVBoxLayout(left)
        ll.setAlignment(Qt.AlignmentFlag.AlignTop)
        ll.setContentsMargins(0, 0, 4, 0)
        ll.setSpacing(6)
        left.setMinimumWidth(260)
        left.setMaximumWidth(320)
        ll.addWidget(self._build_solar_indices_group())
        rec_grp = QGroupBox(self.tr("Band Recommendations"))
        rl      = QVBoxLayout(rec_grp)
        self._rec_labels = []
        for _ in range(4):
            lbl = QLabel("—")
            lbl.setWordWrap(True)
            rl.addWidget(lbl)
            self._rec_labels.append(lbl)
        ll.addWidget(rec_grp)
        self._aurora_widget = QGroupBox("")
        aw = QVBoxLayout(self._aurora_widget)
        _t = get_theme(self.cfg.get("ui.theme", "Dark"))
        self._aurora_lbl = QLabel("")
        self._aurora_lbl.setWordWrap(True)
        self._aurora_lbl.setStyleSheet(f"color:{_t.warn_color};")
        aw.addWidget(self._aurora_lbl)
        self._aurora_widget.hide()
        ll.addWidget(self._aurora_widget)
        ll.addStretch()
        return left

    def _build_solar_indices_group(self) -> QGroupBox:
        solar_grp = QGroupBox(self.tr("Solar Indices"))
        sg = QGridLayout(solar_grp)
        sg.setSpacing(4)
        self._solar_widgets = {}
        indices = [
            ("sfi",   self.tr("Solar Flux (SFI)"),  "0",  "10.7cm emission"),
            ("sn",    self.tr("Sunspot Number"),      "0",  "Daily count"),
            ("k",     self.tr("K-Index"),             "0",  "3-hour geomag"),
            ("a",     self.tr("A-Index"),             "0",  "Daily geomag"),
            ("xray",  self.tr("X-Ray Class"),         "A",  "Solar flare class"),
            ("storm", self.tr("Storm Level"),         "G0", "Geomagnetic"),
        ]
        for row, (key, label, default, tip) in enumerate(indices):
            lbl = QLabel(label)
            lbl.setToolTip(tip)
            sg.addWidget(lbl, row, 0)
            val = QLabel(default)
            val.setStyleSheet(
                "color:#3fbe6f;font-weight:bold;font-family:'Courier New';")
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            sg.addWidget(val, row, 1)
            trend = QLabel("")
            trend.setFixedWidth(20)
            sg.addWidget(trend, row, 2)
            self._solar_widgets[key] = (val, trend)
        return solar_grp

    def _build_bands_pane(self) -> QWidget:
        right = QWidget()
        rl2   = QVBoxLayout(right)
        rl2.setAlignment(Qt.AlignmentFlag.AlignTop)
        rl2.setContentsMargins(4, 0, 0, 0)
        rl2.setSpacing(4)
        rl2.addWidget(self._build_bands_group())
        rl2.addWidget(self._build_path_reliability_group())
        rl2.addWidget(self._build_muf_chart_group())
        rl2.addWidget(self._build_sideview_group())
        rl2.addWidget(self._build_pskreporter_group())
        rl2.addStretch()
        # Scroll the right column so the many groups (incl. the 240px side-view)
        # keep their full height instead of being compressed to overlap.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(right)
        return scroll

    def _build_path_reliability_group(self) -> QGroupBox:
        """Band-by-band reliability chart for the entered TX→RX path."""
        grp = QGroupBox(self.tr("Path Band Reliability"))
        grp.setToolTip(
            "Estimated reliability for each HF band on the entered path.\n"
            "Green = likely open, amber = marginal, — = not viable.\n"
            "Adjusts for NVIS (<400 km) and multi-hop (>5000 km) paths.\n"
            "Enter a Path-to target in the side-view controls below to activate.")
        lay = QVBoxLayout(grp)
        lay.setContentsMargins(6, 4, 6, 4)
        self._reliability_chart = BandReliabilityChart()
        lay.addWidget(self._reliability_chart)
        self._reliability_note = QLabel(
            "Enter a Path-to target below to see path-specific band reliability.")
        self._reliability_note.setStyleSheet("color:#667788;font-size:9px;")
        self._reliability_note.setWordWrap(True)
        lay.addWidget(self._reliability_note)
        return grp

    def _build_bands_group(self) -> QGroupBox:
        bands_grp = QGroupBox(self.tr("Band Conditions"))
        bg = QGridLayout(bands_grp)
        bg.setSpacing(6)
        for col, h in enumerate([self.tr("Band"), self.tr("Condition"),
                                  self.tr("Indicator")]):
            lbl = QLabel(h)
            lbl.setStyleSheet("font-weight:bold;")
            bg.addWidget(lbl, 0, col)
        self._band_rows = {}
        for row, band in enumerate(
                ["160m", "80m", "40m", "30m", "20m",
                 "17m", "15m", "12m", "10m", "6m"], 1):
            band_lbl = QLabel(band)
            band_lbl.setStyleSheet("font-family:'Courier New';")
            bg.addWidget(band_lbl, row, 0)
            cond_lbl = QLabel("—")
            bg.addWidget(cond_lbl, row, 1)
            bar = QProgressBar()
            bar.setRange(0, 4)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(12)
            bar.setStyleSheet(
                "QProgressBar{background:#111;border:1px solid #222;"
                "border-radius:3px;}"
                "QProgressBar::chunk{background:#3fbe6f;border-radius:2px;}")
            bg.addWidget(bar, row, 2)
            self._band_rows[band] = (cond_lbl, bar)
        return bands_grp

    def _build_muf_chart_group(self) -> QGroupBox:
        hourly_grp = QGroupBox(self.tr("Hourly MUF Estimate (UTC)"))
        hl = QVBoxLayout(hourly_grp)
        hl.setContentsMargins(4, 4, 4, 4)
        self._muf_chart = QGraphicsView()
        self._muf_chart.setFixedHeight(90)
        self._muf_chart.setFrameShape(QFrame.Shape.NoFrame)
        self._muf_chart.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._muf_chart.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._muf_chart.setToolTip(
            "Estimated MUF across 24 hours UTC.\n"
            "Based on solar flux and ionospheric day/night model.\n"
            "Bars show which bands are likely open each hour.")
        hl.addWidget(self._muf_chart)
        return hourly_grp

    def _build_sideview_group(self) -> QGroupBox:
        from ui.widgets.propagation_sideview import PropagationSideView
        from PyQt6.QtWidgets import QPushButton as _PB, QComboBox as _CB
        sv_grp = QGroupBox(self.tr("Path side-view (educational)"))
        sv_grp.setToolTip(
            "Side-view of the great-circle path between you and the target. "
            "Shows whether the current frequency will groundwave, go skywave "
            "(1- or 2-hop), do NVIS, get absorbed below LUF, or punch through "
            "the ionosphere above MUF.")
        svl = QVBoxLayout(sv_grp)
        svl.setContentsMargins(4, 4, 4, 4)
        svl.setSpacing(4)
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)
        ctrl_row.addWidget(QLabel("Terrain:"))
        self._terrain_combo = _CB()
        self._terrain_combo.addItems(["Off", "Online (SRTM)", "Offline (cached)"])
        self._terrain_combo.setMaximumWidth(145)
        self._terrain_combo.setToolTip(
            "Off     — no terrain data (fast, deterministic noise).\n"
            "Online  — fetches real SRTM 30m elevation from OpenTopoData.\n"
            "           Free, no key. Requires internet. ~1s per path.\n"
            "Offline — reads locally cached SRTM tiles (download below).\n"
            "           Works without internet after first download.")
        self._terrain_combo.currentTextChanged.connect(
            self._on_terrain_mode_changed)
        ctrl_row.addWidget(self._terrain_combo)
        self._terrain_dl_btn = _PB("Download tiles")
        self._terrain_dl_btn.setMaximumWidth(120)
        self._terrain_dl_btn.setToolTip(
            "Download SRTM elevation tiles for the current path to enable\n"
            "offline terrain rendering. ~5-15 tiles, ~0.4 MB each.\n"
            "Source: Amazon open terrain data (NASA SRTM, public domain).")
        self._terrain_dl_btn.clicked.connect(self._download_terrain_tiles)
        ctrl_row.addWidget(self._terrain_dl_btn)
        _t = get_theme(self.cfg.get("ui.theme", "Dark"))
        self._terrain_status = QLabel("")
        self._terrain_status.setStyleSheet(f"color:{_t.fg_secondary};font-size:10px;")
        ctrl_row.addWidget(self._terrain_status, 1)
        svl.addLayout(ctrl_row)

        zone_row = QHBoxLayout()
        zone_row.setSpacing(10)
        zone_row.addWidget(QLabel("Overlays:"))
        self._zone_gw = QCheckBox("Groundwave")
        self._zone_gw.setChecked(True)
        self._zone_gw.setToolTip(
            "Show estimated groundwave range along the surface.\n"
            "Range ≈ 300 / freq_MHz km — shorter at higher frequencies.")
        zone_row.addWidget(self._zone_gw)
        self._zone_nvis = QCheckBox("NVIS")
        self._zone_nvis.setChecked(True)
        self._zone_nvis.setToolTip(
            "Show Near-Vertical Incidence Skywave coverage zone.\n"
            "Active at 2–10 MHz; illuminates paths up to ~500 km.")
        zone_row.addWidget(self._zone_nvis)
        self._zone_sw = QCheckBox("Skywave / Skip")
        self._zone_sw.setChecked(True)
        self._zone_sw.setToolTip(
            "Show skywave zones:\n"
            "• Skip zone (purple) — signal cannot arrive here via skywave\n"
            "• Illuminated zone (blue) — skywave can arrive here\n"
            "Skip distance ≈ 2 · F-layer · freq / √(MUF² − freq²)")
        zone_row.addWidget(self._zone_sw)
        zone_row.addStretch(1)

        def _on_zone_toggle():
            if hasattr(self, "_prop_sideview"):
                self._prop_sideview.set_show_zones(
                    self._zone_gw.isChecked(),
                    self._zone_nvis.isChecked(),
                    self._zone_sw.isChecked())

        self._zone_gw.toggled.connect(_on_zone_toggle)
        self._zone_nvis.toggled.connect(_on_zone_toggle)
        self._zone_sw.toggled.connect(_on_zone_toggle)
        svl.addLayout(zone_row)

        self._prop_sideview = PropagationSideView()
        svl.addWidget(self._prop_sideview)

        # Time-of-day slider — preview conditions at a specific UTC hour
        time_row = QHBoxLayout()
        time_row.setSpacing(6)
        time_row.addWidget(QLabel("Time:"))
        from PyQt6.QtWidgets import QSlider as _QS
        self._time_slider = _QS(Qt.Orientation.Horizontal)
        self._time_slider.setRange(0, 23)
        self._time_slider.setValue(self._current_utc_hour())
        self._time_slider.setTickPosition(_QS.TickPosition.TicksBelow)
        self._time_slider.setTickInterval(6)
        self._time_slider.setToolTip(
            "Drag to preview propagation conditions at a different UTC hour.\n"
            "MUF is scaled by a day/night model from current solar indices.")
        self._time_slider.valueChanged.connect(self._on_time_slider_changed)
        time_row.addWidget(self._time_slider, 1)
        self._time_lbl = QLabel("Now")
        self._time_lbl.setFixedWidth(44)
        self._time_lbl.setStyleSheet("color:#3fbe6f;font-size:9px;")
        time_row.addWidget(self._time_lbl)
        svl.addLayout(time_row)
        return sv_grp

    @staticmethod
    def _current_utc_hour() -> int:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).hour

    def _on_time_slider_changed(self, hour: int) -> None:
        """Recompute MUF for the selected hour and update the sideview."""
        import math
        cur_hour = self._current_utc_hour()
        if hour == cur_hour:
            self._time_lbl.setText("Now")
            self._time_lbl.setStyleSheet("color:#3fbe6f;font-size:9px;")
        else:
            self._time_lbl.setText(f"{hour:02d}:00Z")
            self._time_lbl.setStyleSheet("color:#ffcc00;font-size:9px;")
        try:
            solar = self._solar_data
            if solar is None or solar.sfi <= 0:
                return
            sfi        = max(70.0, float(solar.sfi or 70))
            fof2_day   = math.sqrt(sfi / 25.0) * 4.0
            fof2_night = fof2_day * 0.55
            day_f = 0.5 + 0.5 * math.sin(math.radians((hour - 6) * 15))
            fof2  = fof2_night + (fof2_day - fof2_night) * day_f
            path_km = getattr(self, "_current_path_km", 3000.0) or 3000.0
            path_factor = max(1.5, min(4.5, path_km / 1000.0 + 1.2))
            geo_factor  = max(0.3, 1.0 - 0.08 * float(solar.k_index or 0))
            muf_hz = min(fof2 * geo_factor * path_factor, 35.0)
            self._prop_sideview._muf_mhz = muf_hz
            self._prop_sideview.update()
        except Exception:
            pass

    def _build_pskreporter_group(self) -> QGroupBox:
        spots_grp = QGroupBox(self.tr("PSKReporter — Hearing You"))
        spl = QVBoxLayout(spots_grp)
        self._spots_table = QTableWidget(0, 4)
        self._spots_table.setHorizontalHeaderLabels([
            self.tr("Spotter"), self.tr("Band"),
            self.tr("SNR"), self.tr("Location"),
        ])
        self._spots_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self._spots_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch)
        self._spots_table.setMaximumHeight(160)
        self._spots_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._spots_table.setStyleSheet(
            "QTableWidget{background:#0d0d0d;gridline-color:#1a1a1a;"
            "alternate-background-color:#111;}"
            "QHeaderView::section{background:#141414;border:none;}")
        self._spots_table.setAlternatingRowColors(True)
        spl.addWidget(self._spots_table)
        return spots_grp

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

    def _set_solar_widget(self, key: str, text: str,
                          trend_text: str = "", color: str = "#3fbe6f"):
        """Update one solar index label + trend label."""
        val_lbl, trend_lbl = self._solar_widgets[key]
        val_lbl.setText(text)
        val_lbl.setStyleSheet(
            f"color:{color};font-weight:bold;font-family:'Courier New';")
        trend_lbl.setText(trend_text)

    def _apply_solar_summary(self, solar: SolarData):
        """Update summary text, MUF label, and summary color."""
        self._summary_lbl.setText(solar.conditions_summary)
        try:
            muf = getattr(solar, "muf_estimate_mhz", 0)
            if muf > 0:
                self._muf_lbl.setText(
                    f"  Est. MUF: {muf:.1f} MHz (3000km F2)")
        except Exception:
            pass
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
        # K-index audible alarm
        self._check_k_alarm(solar)

    def _check_k_alarm(self, solar: SolarData) -> None:
        """Beep when K-index meets or exceeds the user's configured threshold."""
        try:
            threshold = int(self.cfg.get("band.k_alarm", 0) or 0)
            if threshold <= 0:
                return
            if solar.k_index >= threshold:
                # Only beep once per K-index level, not on every refresh
                last = getattr(self, "_last_k_alarm_level", -1)
                if solar.k_index > last:
                    from PyQt6.QtWidgets import QApplication
                    QApplication.beep()
                    self._last_k_alarm_level = solar.k_index
                    self._aurora_lbl.setText(
                        f"⚡ K-index alarm: K={solar.k_index:.0f} "
                        f"(threshold {threshold})")
                    self._aurora_widget.show()
            else:
                self._last_k_alarm_level = -1
        except Exception:
            pass

    def _apply_solar_indices(self, solar: SolarData):
        """Update SFI, SN, K, A, X-ray, storm index widgets."""
        trend = lambda t: "↑" if t == "rising" else "↓" if t == "falling" else "→"
        self._set_solar_widget("sfi", f"{solar.sfi:.0f}", trend(solar.sfi_trend))
        self._set_solar_widget("sn",  str(solar.sunspot_num))
        kp_color = ("#cc4444" if solar.k_index >= 5
                    else "#eeaa22" if solar.k_index >= 3 else "#3fbe6f")
        self._set_solar_widget("k", f"{solar.k_index:.1f}",
                               trend(solar.k_trend), kp_color)
        self._set_solar_widget("a",    f"{solar.a_index:.0f}")
        self._set_solar_widget("xray", solar.xray_class)
        storm_color = ("#cc4444" if solar.storm_level >= 2
                       else "#eeaa22" if solar.storm_level >= 1 else "#3fbe6f")
        self._set_solar_widget("storm", f"G{solar.storm_level}",
                               color=storm_color)

    def _apply_solar_aurora(self, solar: SolarData):
        """Update recommendations, aurora widget, and age label."""
        recs = solar.band_recommendations
        for i, lbl in enumerate(self._rec_labels):
            lbl.setText(recs[i] if i < len(recs) else "")
        if solar.aurora_alert:
            self._aurora_lbl.setText(
                f"🌌 Aurora alert — Kp={solar.k_index:.0f}\n"
                "Enhanced propagation possible on 10m/6m/VHF.")
            self._aurora_widget.show()
        else:
            self._aurora_widget.hide()
        self._age_lbl.setText(f"Updated {solar.age_minutes:.0f}m ago")

    def _apply_solar(self, solar: SolarData):
        """Update all solar index displays."""
        self._solar_data = solar
        self._apply_solar_summary(solar)
        self._apply_solar_indices(solar)
        self._apply_solar_aurora(solar)
        self._refresh_band_display()
        try:
            self._update_muf_chart()
        except Exception:
            pass

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



    def _draw_muf_band_lines(self, scene: QGraphicsScene,
                             w: float, h: float, max_muf: float):
        """Draw dotted horizontal threshold lines for each HF band."""
        from PyQt6.QtGui import QPen, QBrush, QColor
        for mhz, label, color in [
            (28.0, "10m", "#3fbe6f"),
            (21.0, "15m", "#55cc88"),
            (14.0, "20m", "#88bb44"),
            (7.0,  "40m", "#aaaa22"),
        ]:
            y = h - (mhz / max_muf) * h
            scene.addLine(0, y, w, y,
                          QPen(QColor(color), 0.5, Qt.PenStyle.DotLine))
            txt = scene.addSimpleText(label)
            txt.setPos(2, y - 11)
            txt.setBrush(QBrush(QColor(color)))
            font = txt.font(); font.setPointSize(7); txt.setFont(font)

    def _draw_muf_bars(self, scene: QGraphicsScene, w: float, h: float,
                       fof2_day: float, fof2_night: float,
                       geo_factor: float, path_factor: float, max_muf: float):
        """Draw 24 hourly MUF bars and UTC hour labels."""
        import math
        from PyQt6.QtGui import QPen, QBrush, QColor
        bar_w = w / 24.0
        for hr in range(24):
            day_f = 0.5 + 0.5 * math.sin(math.radians((hr - 6) * 15))
            fof2  = fof2_night + (fof2_day - fof2_night) * day_f
            muf   = min(fof2 * geo_factor * path_factor, max_muf)
            bh    = (muf / max_muf) * h
            col   = (QColor("#1a7a3f") if muf >= 28
                     else QColor("#3a7a1a") if muf >= 21
                     else QColor("#7a6a1a") if muf >= 14
                     else QColor("#7a3a1a") if muf >= 7
                     else QColor("#5a1a1a"))
            scene.addRect(QRectF(hr * bar_w + 1, h - bh, bar_w - 2, bh),
                          QPen(col.lighter(120), 0.5), QBrush(col))
        for hr in (0, 6, 12, 18):
            txt = scene.addSimpleText(f"{hr:02d}Z")
            txt.setPos(hr * bar_w + 1, h + 1)
            font = txt.font(); font.setPointSize(6); txt.setFont(font)
            txt.setBrush(QBrush(QColor("#666666")))

    def _update_muf_chart(self):
        """Draw a 24-bar hourly MUF chart using the current solar data."""
        try:
            solar = self._solar_data
            if solar is None or solar.sfi <= 0:
                return
        except AttributeError:
            return
        import math
        try:
            scene = QGraphicsScene()
            self._muf_chart.setScene(scene)
            w = max(self._muf_chart.width() - 4, 240)
            h = max(self._muf_chart.height() - 8, 60)
            sfi        = max(70.0, float(solar.sfi or 70))
            path_km    = getattr(self, '_current_path_km', 3000.0) or 3000.0
            path_factor = max(1.5, min(4.5, path_km / 1000.0 + 1.2))
            geo_factor  = max(0.3, 1.0 - 0.08 * float(solar.k_index or 0))
            fof2_day    = math.sqrt(sfi / 25.0) * 4.0
            fof2_night  = fof2_day * 0.55
            max_muf     = 35.0
            self._draw_muf_band_lines(scene, w, h, max_muf)
            self._draw_muf_bars(scene, w, h, fof2_day, fof2_night,
                                geo_factor, path_factor, max_muf)
            scene.setSceneRect(0, 0, w, h + 14)
            self._muf_chart.fitInView(
                scene.sceneRect(),
                Qt.AspectRatioMode.IgnoreAspectRatio)
        except Exception as e:
            log.debug(f"MUF chart: {e}")

    def _on_path_changed(self):
        """Recalculate band conditions for a specific path target."""
        import threading
        target = self._path_edit.text().strip()
        if not target:
            try:
                from network.propagation import get_prop_feed
                get_prop_feed().set_path_km(0)
                self._refresh_display()
                self._muf_lbl.setText("")
            except Exception:
                pass
            return
        # Immediate feedback — geocode round-trip can take ~2s
        self._muf_lbl.setText(f"  Resolving '{target}'…")
        try:
            self._path_resolved.disconnect()
        except TypeError:
            pass
        self._path_resolved.connect(self._apply_path_km)
        threading.Thread(
            target=self._resolve_path_target,
            args=(target,),
            daemon=True,
        ).start()

    def _resolve_path_target(self, target: str) -> None:
        """Worker thread: geocode *target*, compute great-circle km/bearing,
        store terrain coords, then emit _path_resolved signal."""
        from core.location import _grid_to_latlon, geocode_place
        import re as _re
        import math
        import logging
        err_reason = ""
        km = bearing = 0.0
        mlat = mlon = tlat = tlon = 0.0
        ok = False
        try:
            if _re.match(r'^[A-Ra-r]{2}[0-9]{2}', target):
                tlat, tlon = _grid_to_latlon(target.upper())
            else:
                q = f"{target}, USA" if _re.match(r'^\d{5}$', target) else target
                try:
                    tlat, tlon = geocode_place(q)
                except Exception as e:
                    err_reason = (
                        "Geocoder unreachable (check internet)"
                        if "resolve" in str(e).lower() or "Max retries" in str(e)
                        else f"Could not find '{target}'")
                    logging.getLogger(__name__).warning(
                        f"Path-to geocode failed for '{target}': {e}")
                    raise
            mlat = self.cfg.get("location.lat", 0.0)
            mlon = self.cfg.get("location.lon", 0.0)
            if not mlat and not mlon:
                mlat, mlon = _grid_to_latlon(
                    self.cfg.get("location.grid_square", "FN20") or "FN20")
            R = 6371.0
            p1, p2 = math.radians(mlat), math.radians(tlat)
            dp = math.radians(tlat - mlat)
            dl = math.radians(tlon - mlon)
            a = (math.sin(dp / 2) ** 2
                 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
            km = R * 2 * math.asin(min(1.0, math.sqrt(a)))
            y = math.sin(dl) * math.cos(p2)
            x = (math.cos(p1) * math.sin(p2)
                 - math.sin(p1) * math.cos(p2) * math.cos(dl))
            bearing = (math.degrees(math.atan2(y, x)) + 360) % 360
            ok = True
        except Exception:
            if not err_reason:
                err_reason = f"Could not resolve '{target}'"
        # Store resolved coordinates for terrain tile fetch
        self.__terrain_tx_lat = mlat
        self.__terrain_tx_lon = mlon
        self.__terrain_rx_lat = tlat
        self.__terrain_rx_lon = tlon
        self._path_resolved.emit(km, bearing, target, ok, err_reason)



    def _on_eirp_changed(self, val: float):
        self.cfg.set("propagation.eirp_dbw", val)
        self.cfg.save()
        if hasattr(self, "_prop_sideview"):
            self._prop_sideview.set_eirp_dbw(val)

    def _on_terrain_mode_changed(self, text: str):
        """Propagate terrain mode selection to the side-view widget."""
        mode_map = {
            "Off":             "off",
            "Online (SRTM)":  "online",
            "Offline (cached)":"offline",
        }
        mode = mode_map.get(text, "off")
        self.cfg.set("terrain.mode", mode)
        self.cfg.save()
        self._prop_sideview.set_terrain_mode(mode)
        # Update download button state
        if hasattr(self, "_terrain_dl_btn"):
            self._terrain_dl_btn.setEnabled(mode == "offline")

    def _download_terrain_tiles(self):
        """Download SRTM tiles for the current path in a background thread."""
        tx_lat = self._prop_sideview._tx_lat
        tx_lon = self._prop_sideview._tx_lon
        rx_lat = self._prop_sideview._rx_lat
        rx_lon = self._prop_sideview._rx_lon
        if not tx_lat and not tx_lon:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "No path set",
                "Enter a target in the Path-to field first so Squelch "
                "knows which tiles to download.")
            return
        from core.terrain import (gc_profile, tiles_needed,
                                   estimated_download_mb, download_tiles)
        pts = gc_profile(tx_lat, tx_lon, rx_lat, rx_lon, 60)
        mb  = estimated_download_mb(tx_lat, tx_lon, rx_lat, rx_lon, 60)
        n   = len(tiles_needed(pts))
        if mb < 0.1:
            self._terrain_status.setText("All tiles already cached.")
            return
        self._terrain_dl_btn.setEnabled(False)
        self._terrain_status.setText(
            f"Downloading {n} tile(s) (~{mb:.1f} MB)…")
        import threading
        def _fetch():
            from PyQt6.QtCore import QTimer
            done_box = [0]
            def _prog(done, total):
                done_box[0] = done
                QTimer.singleShot(0, lambda d=done, t=total:
                    self._terrain_status.setText(
                        f"Downloading tile {d}/{t}…"))
            ok, total = download_tiles(pts, progress_cb=_prog)
            def _done():
                self._terrain_dl_btn.setEnabled(True)
                self._terrain_status.setText(
                    f"Done — {ok}/{total} tiles cached.")
                # Re-fetch terrain now that tiles exist
                self._prop_sideview.set_terrain_mode("offline")
            QTimer.singleShot(0, _done)
        threading.Thread(target=_fetch, daemon=True,
                         name="TileDownload").start()

    def _apply_path_km(self, km: float, bearing: float = 0.0,
                       target: str = "", ok: bool = True,
                       err_reason: str = ""):
        """Apply resolved path distance to propagation model and show
        distance + compass bearing in the header. On failure, show why."""
        # Set status FIRST — before anything that could throw and let
        # an outer except swallow the user-visible feedback.
        if not ok or km <= 0:
            self._muf_lbl.setText(
                f"  ⚠ {err_reason or f'Could not resolve {target!r}'}")
            return
        try:
            from network.propagation import get_prop_feed
            feed = get_prop_feed()
            feed.set_path_km(km)
            self._refresh_display()
            # Compass-point label for the bearing
            cardinals = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                         "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
            cp = cardinals[int((bearing + 11.25) / 22.5) % 16]
            # Honor metric/imperial pref
            try:
                from core.units import format_distance
                dist_str = format_distance(km, self.cfg, decimals=0)
            except Exception:
                dist_str = f"{km:.0f} km"
            self._muf_lbl.setText(
                f"  → {target}: {dist_str}  "
                f"bearing {bearing:.0f}° ({cp})  "
                f"Est. MUF: {feed._solar.muf_estimate_mhz:.1f} MHz")
            self._current_path_km = km
            self._update_muf_chart()
            self._update_path_sideview(km, target, feed)
        except Exception:
            pass

    def _handle_map_path(self, lat: float, lon: float) -> None:
        """Called when the user right-clicks the map and chooses 'Analyze path'.

        Converts lat/lon to a Maidenhead grid square and sets the Path-to
        field, triggering the same propagation analysis as manual entry.
        """
        try:
            from core.location import _latlon_to_grid
            grid = _latlon_to_grid(lat, lon)
            if hasattr(self, "_path_edit"):
                self._path_edit.setText(grid)
                self._on_path_changed()
        except Exception as e:
            log.debug(f"Map path analysis: {e}")

    def _update_path_sideview(self, km: float, target: str, feed):
        """Update sideview and path reliability chart for the entered path."""
        try:
            band    = self._band_filter.currentText() \
                if hasattr(self, "_band_filter") else "Auto"
            op_freq = (self._BAND_CTR_MHZ[band]
                       if band != "Auto" and band in self._BAND_CTR_MHZ
                       else float(self.cfg.get("rig.last_freq_hz", 0)) / 1e6)
            luf = getattr(feed._solar, "luf_estimate_mhz", 3.0)
            muf = feed._solar.muf_estimate_mhz
            self._prop_sideview.update_state(
                path_km  = km,
                muf_mhz  = muf,
                luf_mhz  = luf,
                freq_mhz = op_freq,
                target   = target,
                tx_lat   = getattr(self, "_BandConditionsTab__terrain_tx_lat", 0.0),
                tx_lon   = getattr(self, "_BandConditionsTab__terrain_tx_lon", 0.0),
                rx_lat   = getattr(self, "_BandConditionsTab__terrain_rx_lat", 0.0),
                rx_lon   = getattr(self, "_BandConditionsTab__terrain_rx_lon", 0.0))
            # Update path reliability chart
            if hasattr(self, "_reliability_chart"):
                self._reliability_chart.update_path(muf, luf, km)
                self._reliability_note.setText(
                    f"Showing reliability for {target or 'path'}  •  {km:,.0f} km  "
                    f"•  MUF {muf:.1f} MHz  •  LUF {luf:.1f} MHz")
        except Exception:
            pass

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
