from __future__ import annotations
"""Grid Square Calculator dialog.

Converts between Maidenhead grid locators, latitude/longitude,
MGRS (Military Grid Reference System), and What3Words addresses.
"""
from PyQt6.QtWidgets import (QDialog, QFormLayout, QLineEdit, QLabel,
                              QPushButton, QDialogButtonBox, QHBoxLayout,
                              QVBoxLayout, QFrame, QTabWidget, QWidget)
from PyQt6.QtCore import Qt


class GridCalcDialog(QDialog):
    """Grid ↔ lat/lon ↔ MGRS ↔ What3Words calculator."""

    def __init__(self, cfg=None, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("Grid Square Calculator")
        self.setMinimumWidth(380)
        self.resize(420, 380)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        tabs = QTabWidget()
        tabs.addTab(self._build_grid_tab(),  "Grid / Lat·Lon")
        tabs.addTab(self._build_mgrs_tab(),  "MGRS")
        tabs.addTab(self._build_w3w_tab(),   "What3Words")
        root.addWidget(tabs)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.accept)
        root.addWidget(btns)

    # ── Tab builders ──────────────────────────────────────────────────────

    def _build_grid_tab(self) -> QWidget:
        w  = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(8, 8, 8, 8)
        vl.setSpacing(8)

        # Grid → lat/lon
        f1 = QFormLayout(); f1.setSpacing(5)
        self._grid_in = QLineEdit()
        self._grid_in.setPlaceholderText("e.g. FN31pr or FN31")
        self._grid_in.setMaxLength(8)
        self._grid_in.setToolTip("Maidenhead grid locator (4 or 6 characters)")
        self._grid_in.returnPressed.connect(self._calc_from_grid)
        f1.addRow("Grid →", self._grid_in)
        b1 = QPushButton("Calculate"); b1.clicked.connect(self._calc_from_grid)
        f1.addRow("", b1)
        self._lat_out  = QLabel("—")
        self._lon_out  = QLabel("—")
        self._dist_bear_out = QLabel("—")
        self._mgrs_from_grid = QLabel("—")
        self._w3w_from_grid  = QLabel("—")
        for lbl in (self._lat_out, self._lon_out, self._dist_bear_out,
                    self._mgrs_from_grid, self._w3w_from_grid):
            lbl.setStyleSheet("color:#3fbe6f;font-family:'Courier New';")
        f1.addRow("Latitude:",    self._lat_out)
        f1.addRow("Longitude:",   self._lon_out)
        f1.addRow("MGRS:",        self._mgrs_from_grid)
        f1.addRow("W3W:",         self._w3w_from_grid)
        f1.addRow("From station:", self._dist_bear_out)
        vl.addLayout(f1)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        vl.addWidget(sep)

        # Lat/lon → grid
        f2 = QFormLayout(); f2.setSpacing(5)
        row = QHBoxLayout()
        self._lat_in = QLineEdit(); self._lat_in.setPlaceholderText("Latitude");  self._lat_in.setFixedWidth(100)
        self._lon_in = QLineEdit(); self._lon_in.setPlaceholderText("Longitude"); self._lon_in.setFixedWidth(100)
        row.addWidget(self._lat_in); row.addWidget(QLabel(",")); row.addWidget(self._lon_in)
        f2.addRow("Lat, Lon →", row)
        b2 = QPushButton("Calculate"); b2.clicked.connect(self._calc_from_latlon)
        f2.addRow("", b2)
        self._grid_out = QLabel("—")
        self._grid_out.setStyleSheet("color:#3fbe6f;font-family:'Courier New';font-size:14px;")
        f2.addRow("Grid:", self._grid_out)
        vl.addLayout(f2)
        vl.addStretch()
        return w

    def _build_mgrs_tab(self) -> QWidget:
        w  = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(8, 8, 8, 8)
        vl.setSpacing(8)
        f = QFormLayout(); f.setSpacing(5)
        self._mgrs_in = QLineEdit()
        self._mgrs_in.setPlaceholderText("e.g. 18SUJ2338208028")
        self._mgrs_in.setToolTip(
            "Military Grid Reference System coordinate.\n"
            "Requires the 'mgrs' Python package.")
        self._mgrs_in.returnPressed.connect(self._calc_from_mgrs)
        f.addRow("MGRS →", self._mgrs_in)
        bm = QPushButton("Calculate"); bm.clicked.connect(self._calc_from_mgrs)
        f.addRow("", bm)
        self._mgrs_lat  = QLabel("—")
        self._mgrs_lon  = QLabel("—")
        self._mgrs_grid = QLabel("—")
        self._mgrs_dist = QLabel("—")
        for lbl in (self._mgrs_lat, self._mgrs_lon, self._mgrs_grid, self._mgrs_dist):
            lbl.setStyleSheet("color:#3fbe6f;font-family:'Courier New';")
        f.addRow("Latitude:",    self._mgrs_lat)
        f.addRow("Longitude:",   self._mgrs_lon)
        f.addRow("Grid:",        self._mgrs_grid)
        f.addRow("From station:", self._mgrs_dist)
        note = QLabel("Tip: grid calcualtor auto-shows MGRS in the Grid/Lat·Lon tab.")
        note.setStyleSheet("color:#556677;font-size:9px;")
        note.setWordWrap(True)
        f.addRow("", note)
        vl.addLayout(f)
        vl.addStretch()
        return w

    def _build_w3w_tab(self) -> QWidget:
        w  = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(8, 8, 8, 8)
        vl.setSpacing(8)
        f = QFormLayout(); f.setSpacing(5)
        self._w3w_in = QLineEdit()
        self._w3w_in.setPlaceholderText("///word.word.word")
        self._w3w_in.setToolTip(
            "What3Words address (three words separated by dots).\n"
            "Enter with or without the leading ///.\n"
            "Requires a W3W API key in Settings → APIs.")
        self._w3w_in.returnPressed.connect(self._calc_from_w3w)
        f.addRow("W3W →", self._w3w_in)
        bw = QPushButton("Calculate"); bw.clicked.connect(self._calc_from_w3w)
        f.addRow("", bw)
        self._w3w_lat  = QLabel("—")
        self._w3w_lon  = QLabel("—")
        self._w3w_grid = QLabel("—")
        self._w3w_mgrs = QLabel("—")
        self._w3w_dist = QLabel("—")
        for lbl in (self._w3w_lat, self._w3w_lon, self._w3w_grid,
                    self._w3w_mgrs, self._w3w_dist):
            lbl.setStyleSheet("color:#3fbe6f;font-family:'Courier New';")
        f.addRow("Latitude:",    self._w3w_lat)
        f.addRow("Longitude:",   self._w3w_lon)
        f.addRow("Grid:",        self._w3w_grid)
        f.addRow("MGRS:",        self._w3w_mgrs)
        f.addRow("From station:", self._w3w_dist)
        key_note = QLabel(
            "Requires a free What3Words API key.\n"
            "Get one at what3words.com/select-plan → Free\n"
            "Set in Settings → APIs → What3Words API Key.")
        key_note.setStyleSheet("color:#556677;font-size:9px;")
        key_note.setWordWrap(True)
        f.addRow("", key_note)
        vl.addLayout(f)
        vl.addStretch()
        return w

    # ── Calculation helpers ────────────────────────────────────────────────

    def _populate_outputs(self, lat: float, lon: float) -> None:
        """Fill all output labels from a resolved lat/lon."""
        from core.location import _latlon_to_grid, _latlon_to_mgrs, _latlon_to_w3w
        grid = _latlon_to_grid(lat, lon)
        mgrs = _latlon_to_mgrs(lat, lon) or "—  (pip install mgrs)"
        w3w  = _latlon_to_w3w(lat, lon, self.cfg) or "—  (needs W3W API key)"
        dist = self._from_station(lat, lon)
        # Grid tab
        self._lat_out.setText(f"{lat:.6f}°")
        self._lon_out.setText(f"{lon:.6f}°")
        self._mgrs_from_grid.setText(mgrs)
        self._w3w_from_grid.setText(w3w)
        self._dist_bear_out.setText(dist)
        self._grid_out.setText(grid)
        self._grid_in.setText(grid)

    def _calc_from_grid(self):
        grid = self._grid_in.text().strip().upper()
        if len(grid) < 4:
            self._lat_out.setText("Need ≥ 4 characters")
            return
        try:
            from core.location import _grid_to_latlon
            lat, lon = _grid_to_latlon(grid)
            self._populate_outputs(lat, lon)
        except Exception as e:
            self._lat_out.setText(f"Error: {e}")

    def _calc_from_latlon(self):
        try:
            lat = float(self._lat_in.text().strip())
            lon = float(self._lon_in.text().strip())
        except ValueError:
            self._grid_out.setText("Invalid coordinates")
            return
        try:
            self._populate_outputs(lat, lon)
        except Exception as e:
            self._grid_out.setText(f"Error: {e}")

    def _calc_from_mgrs(self):
        mgrs_str = self._mgrs_in.text().strip()
        if not mgrs_str:
            return
        try:
            from core.location import _mgrs_to_latlon, _latlon_to_grid, _latlon_to_w3w
            result = _mgrs_to_latlon(mgrs_str)
            if result is None:
                self._mgrs_lat.setText("MGRS library not installed  (pip install mgrs)")
                return
            lat, lon = result
            grid = _latlon_to_grid(lat, lon)
            w3w  = _latlon_to_w3w(lat, lon, self.cfg) or "—"
            self._mgrs_lat.setText(f"{lat:.6f}°")
            self._mgrs_lon.setText(f"{lon:.6f}°")
            self._mgrs_grid.setText(grid)
            self._mgrs_dist.setText(self._from_station(lat, lon))
            # Also populate the Grid tab outputs
            self._populate_outputs(lat, lon)
        except Exception as e:
            self._mgrs_lat.setText(f"Error: {e}")

    def _calc_from_w3w(self):
        raw = self._w3w_in.text().strip().lstrip("/")
        if not raw:
            return
        try:
            from core.location import _w3w_to_latlon, _is_w3w
            if not _is_w3w(raw):
                self._w3w_lat.setText("Format: word.word.word")
                return
            result = _w3w_to_latlon(raw, self.cfg)
            if result is None:
                self._w3w_lat.setText(
                    "—  check W3W API key in Settings → APIs")
                return
            lat, lon = result
            from core.location import _latlon_to_grid, _latlon_to_mgrs
            grid = _latlon_to_grid(lat, lon)
            mgrs = _latlon_to_mgrs(lat, lon) or "—"
            self._w3w_lat.setText(f"{lat:.6f}°")
            self._w3w_lon.setText(f"{lon:.6f}°")
            self._w3w_grid.setText(grid)
            self._w3w_mgrs.setText(mgrs)
            self._w3w_dist.setText(self._from_station(lat, lon))
            self._populate_outputs(lat, lon)
        except Exception as e:
            self._w3w_lat.setText(f"Error: {e}")

    def _from_station(self, lat: float, lon: float) -> str:
        """Distance and bearing from station location."""
        if not self.cfg:
            return "—"
        try:
            my_lat = float(self.cfg.get("location.lat", 0.0) or 0.0)
            my_lon = float(self.cfg.get("location.lon", 0.0) or 0.0)
            if not my_lat and not my_lon:
                return "Set station location in Settings"
            from network.aprs_anomaly import _haversine_km
            import math
            km = _haversine_km(my_lat, my_lon, lat, lon)
            # Great-circle bearing
            lat1 = math.radians(my_lat); lat2 = math.radians(lat)
            dlon = math.radians(lon - my_lon)
            x = math.sin(dlon) * math.cos(lat2)
            y = (math.cos(lat1) * math.sin(lat2) -
                 math.sin(lat1) * math.cos(lat2) * math.cos(dlon))
            bear = (math.degrees(math.atan2(x, y)) + 360) % 360
            compass = _compass_point(bear)
            return f"{km:,.0f} km  •  {bear:.0f}° {compass}"
        except Exception:
            return "—"


def _compass_point(deg: float) -> str:
    pts = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
           "S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return pts[int((deg + 11.25) / 22.5) % 16]
