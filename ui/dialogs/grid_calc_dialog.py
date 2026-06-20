from __future__ import annotations
"""Grid Square Calculator dialog.

Converts between Maidenhead grid locators and latitude/longitude,
and computes distance/bearing from the station location.
"""
from PyQt6.QtWidgets import (QDialog, QFormLayout, QLineEdit, QLabel,
                              QPushButton, QDialogButtonBox, QHBoxLayout,
                              QVBoxLayout, QFrame)
from PyQt6.QtCore import Qt


class GridCalcDialog(QDialog):
    """Simple grid ↔ lat/lon calculator with distance/bearing from station."""

    def __init__(self, cfg=None, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("Grid Square Calculator")
        self.setMinimumWidth(340)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # Grid → lat/lon section
        f1 = QFormLayout()
        f1.setSpacing(6)
        self._grid_in = QLineEdit()
        self._grid_in.setPlaceholderText("e.g. FN31pr or FN31")
        self._grid_in.setMaxLength(8)
        self._grid_in.setToolTip("Maidenhead grid locator (4 or 6 characters)")
        self._grid_in.returnPressed.connect(self._calc_from_grid)
        f1.addRow("Grid →", self._grid_in)
        calc_btn1 = QPushButton("Calculate")
        calc_btn1.clicked.connect(self._calc_from_grid)
        f1.addRow("", calc_btn1)
        self._lat_out = QLabel("—")
        self._lon_out = QLabel("—")
        self._dist_bear_out = QLabel("—")
        self._lat_out.setStyleSheet("color:#3fbe6f;font-family:'Courier New';")
        self._lon_out.setStyleSheet("color:#3fbe6f;font-family:'Courier New';")
        self._dist_bear_out.setStyleSheet("color:#3fbe6f;font-family:'Courier New';")
        f1.addRow("Latitude:", self._lat_out)
        f1.addRow("Longitude:", self._lon_out)
        f1.addRow("From station:", self._dist_bear_out)
        root.addLayout(f1)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep)

        # Lat/lon → grid section
        f2 = QFormLayout()
        f2.setSpacing(6)
        latlon_row = QHBoxLayout()
        self._lat_in = QLineEdit()
        self._lat_in.setPlaceholderText("Latitude")
        self._lat_in.setFixedWidth(100)
        self._lon_in = QLineEdit()
        self._lon_in.setPlaceholderText("Longitude")
        self._lon_in.setFixedWidth(100)
        latlon_row.addWidget(self._lat_in)
        latlon_row.addWidget(QLabel(","))
        latlon_row.addWidget(self._lon_in)
        f2.addRow("Lat, Lon →", latlon_row)
        calc_btn2 = QPushButton("Calculate")
        calc_btn2.clicked.connect(self._calc_from_latlon)
        f2.addRow("", calc_btn2)
        self._grid_out = QLabel("—")
        self._grid_out.setStyleSheet("color:#3fbe6f;font-family:'Courier New';font-size:14px;")
        f2.addRow("Grid:", self._grid_out)
        root.addLayout(f2)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.accept)
        root.addWidget(btns)

    # ── Calculation ────────────────────────────────────────────────────────

    def _calc_from_grid(self):
        grid = self._grid_in.text().strip().upper()
        if len(grid) < 4:
            self._lat_out.setText("Need ≥ 4 characters")
            return
        try:
            from core.location import _grid_to_latlon
            lat, lon = _grid_to_latlon(grid)
            self._lat_out.setText(f"{lat:.6f}°")
            self._lon_out.setText(f"{lon:.6f}°")
            self._dist_bear_out.setText(self._from_station(lat, lon))
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
            from core.location import _latlon_to_grid
            grid = _latlon_to_grid(lat, lon)
            self._grid_out.setText(grid)
            self._grid_in.setText(grid)   # also populate the top field
            self._lat_out.setText(f"{lat:.6f}°")
            self._lon_out.setText(f"{lon:.6f}°")
            self._dist_bear_out.setText(self._from_station(lat, lon))
        except Exception as e:
            self._grid_out.setText(f"Error: {e}")

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
