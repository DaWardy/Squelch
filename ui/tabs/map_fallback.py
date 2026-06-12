from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- ui/tabs/map_fallback.py
SVG-based world map with gray line terminator.
Works on Python 3.14 without PyQtWebEngine.
Renders gray line, station marker, and QSO paths
using pure Qt drawing (no WebEngine required).
"""

import logging
from datetime import datetime, timezone
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QComboBox, QPushButton, QFrame,
    QScrollArea, QSizePolicy)
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QPolygonF,
    QFont, QLinearGradient)

from network.grayline import (
    terminator_points, gray_line_info,
    format_gray_line_status, solar_position)
from core.location import _valid_grid, _grid_to_latlon

log = logging.getLogger(__name__)

# Simplified Natural Earth outlines (~30-50 pts per continent), (lat, lon)
_CONTINENT_OUTLINES: "list[list[tuple[float, float]]]" = [
    # North America
    [(72,-140),(70,-130),(71,-115),(70,-90),(75,-80),(78,-75),
     (77,-65),(70,-65),(60,-65),(55,-58),(50,-55),(47,-53),
     (45,-60),(44,-66),(42,-70),(41,-72),(35,-76),(30,-81),
     (25,-80),(20,-87),(16,-86),(10,-83),(8,-77),(8,-77),
     (10,-75),(12,-71),(16,-62),(18,-67),(20,-73),(22,-80),
     (24,-81),(28,-82),(30,-88),(29,-95),(26,-97),(22,-105),
     (22,-108),(25,-110),(29,-114),(32,-117),(35,-121),
     (38,-122),(42,-124),(47,-124),(50,-125),(54,-130),
     (58,-137),(60,-146),(63,-162),(65,-168),(68,-166),
     (70,-160),(70,-140),(72,-140)],
    # South America
    [(12,-72),(11,-63),(10,-62),(8,-60),(6,-60),(5,-52),
     (4,-51),(2,-50),(0,-50),(-3,-42),(-5,-35),(-8,-35),
     (-10,-37),(-14,-39),(-18,-39),(-20,-40),(-23,-43),
     (-23,-45),(-25,-48),(-28,-49),(-30,-50),(-33,-53),
     (-35,-58),(-38,-57),(-40,-62),(-42,-65),(-45,-66),
     (-48,-66),(-52,-69),(-54,-68),(-55,-64),(-53,-61),
     (-52,-58),(-48,-65),(-45,-65),(-42,-64),(-38,-62),
     (-33,-71),(-25,-70),(-18,-70),(-14,-76),(-10,-76),
     (-4,-82),(0,-80),(4,-77),(8,-77),(10,-75),(12,-72)],
    # Europe
    [(71,28),(70,20),(70,10),(69,18),(68,14),(67,14),
     (65,14),(63,5),(58,5),(56,8),(55,9),(54,10),
     (52,4),(51,2),(50,2),(48,0),(46,-2),(44,0),
     (43,3),(42,3),(40,0),(39,-9),(37,-9),(36,-6),
     (36,0),(37,3),(39,3),(40,0),(41,2),(42,3),
     (44,8),(44,10),(45,13),(45,15),(44,17),(45,19),
     (46,20),(47,17),(48,17),(50,18),(52,22),(54,22),
     (57,21),(58,22),(60,25),(63,25),(65,25),(68,28),
     (70,28),(71,28)],
    # Africa
    [(37,9),(36,10),(37,11),(36,12),(32,12),(29,13),
     (24,16),(18,16),(16,17),(12,14),(8,4),(5,2),
     (4,6),(2,9),(0,9),(-4,12),(-5,13),(-5,12),
     (-11,14),(-14,12),(-15,12),(-14,16),(-12,17),
     (-10,16),(-8,13),(-6,12),(-4,15),(-2,17),
     (0,20),(2,22),(4,24),(6,25),(8,28),(10,30),
     (11,34),(12,36),(12,40),(12,43),(11,44),(11,42),
     (11,40),(14,41),(17,40),(18,37),(22,37),(25,34),
     (28,34),(30,32),(31,32),(32,35),(33,36),(34,36),
     (36,14),(37,9)],
    # Asia (simplified)
    [(70,30),(72,50),(73,70),(72,100),(70,130),(68,140),
     (65,143),(60,151),(55,160),(50,156),(45,152),(42,142),
     (38,140),(35,137),(33,130),(30,122),(25,119),(22,114),
     (20,110),(18,110),(15,108),(12,109),(10,104),(8,98),
     (6,100),(4,103),(1,104),(1,104),(3,101),(5,103),
     (8,99),(10,98),(13,100),(16,97),(18,94),(22,92),
     (22,88),(20,85),(18,82),(15,80),(12,80),(8,77),
     (8,76),(10,76),(12,80),(16,80),(20,73),(22,68),
     (22,62),(24,58),(22,56),(20,57),(16,52),(12,44),
     (12,40),(20,37),(26,37),(28,34),(30,34),(32,36),
     (34,36),(38,36),(38,40),(40,44),(42,48),(44,50),
     (44,53),(46,60),(48,68),(50,75),(52,80),(55,83),
     (58,80),(58,73),(60,70),(62,68),(62,62),(60,58),
     (60,50),(62,44),(62,38),(64,34),(64,30),(67,30),
     (70,30)],
    # Australia
    [(-12,136),(-10,130),(-12,124),(-14,122),(-18,122),
     (-22,114),(-26,113),(-30,115),(-32,116),(-34,118),
     (-35,117),(-35,118),(-33,122),(-32,127),(-32,134),
     (-34,136),(-36,140),(-38,145),(-37,148),(-33,152),
     (-28,153),(-24,151),(-20,148),(-18,146),(-16,145),
     (-14,144),(-12,142),(-12,136)],
    # Greenland
    [(84,-40),(84,-30),(78,-18),(72,-22),(68,-24),(64,-40),
     (66,-55),(68,-54),(72,-54),(76,-66),(80,-50),(84,-40)],
    # Antarctica (simplified band)
    [(-75,0),(-75,30),(-75,60),(-75,90),(-75,120),
     (-75,150),(-75,180),(-75,-150),(-75,-120),(-75,-90),
     (-75,-60),(-75,-30),(-75,0)],
]


class WorldMapWidget(QWidget):
    """
    Custom world map widget using Qt drawing.
    Shows station location, gray line terminator,
    and QSO great circle paths.
    No external dependencies — works on Python 3.14.
    """

    W = 800
    H = 400

    def __init__(self, parent=None):
        super().__init__(parent)
        self._station_lat  = 0.0
        self._station_lon  = 0.0
        self._station_call = ""
        self._qso_paths    = []
        self._terminator   = []
        self._satellites   = []
        self._show_gl      = True
        self._show_qsos    = True
        self._gl_info      = None
        self.setMinimumSize(400, 200)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding)

    def set_station(self, lat: float, lon: float,
                    call: str = ""):
        self._station_lat  = lat
        self._station_lon  = lon
        self._station_call = call
        self.update()

    def set_terminator(self, points: list):
        self._terminator = points
        self.update()

    def set_qso_paths(self, paths: list):
        self._qso_paths = paths
        self.update()

    def _draw_aprs(self, p, w: int, h: int):
        """Draw APRS station positions as orange diamonds."""
        from PyQt6.QtCore import QPoint
        from PyQt6.QtGui import QPolygon
        for sta in getattr(self, '_aprs_stations', [])[:100]:
            lat = sta.get('lat', 0.0); lon = sta.get('lon', 0.0)
            if not lat and not lon: continue
            x, y = self._latlon_to_xy(lat, lon, w, h)
            p.setPen(QPen(QColor('#ffaa00'), 1))
            p.setBrush(QBrush(QColor('#ffaa00').darker(180)))
            pts = QPolygon([QPoint(int(x), int(y)-7),
                            QPoint(int(x)+5, int(y)),
                            QPoint(int(x), int(y)+7),
                            QPoint(int(x)-5, int(y))])
            p.drawPolygon(pts)
            p.setPen(QPen(QColor('#ffcc44'), 1))
            p.setFont(QFont('Courier New', 8))
            p.drawText(int(x)+7, int(y)+4, sta.get('callsign','')[:8])

    def _draw_dx_spots(self, p, w: int, h: int):
        """Draw DX cluster spots as pink dots."""
        for spot in getattr(self, '_dx_spots', [])[:50]:
            lat = spot.get('lat', 0.0); lon = spot.get('lon', 0.0)
            if not lat and not lon: continue
            x, y = self._latlon_to_xy(lat, lon, w, h)
            p.setPen(QPen(QColor('#ff4488'), 2))
            p.setBrush(QBrush(QColor('#ff4488').darker(200)))
            p.drawEllipse(int(x)-4, int(y)-4, 8, 8)

    def set_aprs_stations(self, stations: list):
        self._aprs_stations = stations
        self.update()

    def set_dx_spots(self, spots: list):
        self._dx_spots = spots
        self.update()


    def set_hearing_me(self, stations_dict: dict):
        """Update the 'who heard me' layer (PSKReporter spots)."""
        self._hearing_me = stations_dict
        self.update()

    def _draw_hearing_me(self, p, w: int, h: int):
        """Draw stations that heard us as orange triangles."""
        from PyQt6.QtGui import QPen, QBrush, QPolygonF, QFont, QColor
        from PyQt6.QtCore import QPointF
        for sta in getattr(self, '_hearing_me', {}).values():
            lat = sta.get('lat', 0.0)
            lon = sta.get('lon', 0.0)
            # Resolve grid if no lat/lon yet
            if not lat and not lon:
                grid = sta.get('grid', '')
                if not grid:
                    continue
                try:
                    from core.location import _grid_to_latlon
                    lat, lon = _grid_to_latlon(grid.upper())
                    sta['lat'] = lat; sta['lon'] = lon
                except Exception:
                    continue
            x, y = self._latlon_to_xy(lat, lon, w, h)
            # Orange upward-pointing triangle
            size = 8
            tri = QPolygonF([
                QPointF(x, y - size),
                QPointF(x - size * 0.7, y + size * 0.4),
                QPointF(x + size * 0.7, y + size * 0.4),
            ])
            p.setPen(QPen(QColor('#ff8800'), 2))
            p.setBrush(QBrush(QColor('#803000')))
            p.drawPolygon(tri)
            # Callsign label
            p.setPen(QPen(QColor('#ffcc88'), 1))
            p.setFont(QFont('Courier New', 8))
            p.drawText(int(x) + 10, int(y) + 4,
                       sta.get('callsign', '')[:8])

    def _draw_heard(self, p, w: int, h: int):
        """Draw stations heard from FT8/decodes/etc as green dots."""
        for sta in getattr(self, '_heard_stations', {}).values():
            lat = sta.get('lat', 0.0); lon = sta.get('lon', 0.0)
            if not lat and not lon: continue
            x, y = self._latlon_to_xy(lat, lon, w, h)
            # Bright green dot for heard stations — distinct from APRS
            # (orange diamonds) and DX cluster (pink dots).
            p.setPen(QPen(QColor('#3fbe6f'), 2))
            p.setBrush(QBrush(QColor('#1a7a3f')))
            p.drawEllipse(int(x)-5, int(y)-5, 10, 10)
            # Callsign label
            p.setPen(QPen(QColor('#7fdf9f'), 1))
            p.setFont(QFont('Courier New', 8))
            p.drawText(int(x)+8, int(y)+4, sta.get('callsign', '')[:8])

    def set_heard_stations(self, stations_dict: dict):
        """Update the heard-stations pin layer."""
        self._heard_stations = stations_dict
        self.update()

    def set_satellite_positions(self, sats: list):
        """Update satellite positions for display."""
        self._satellites = sats
        self.update()

    def set_gl_info(self, info):
        self._gl_info = info
        self.update()

    def _latlon_to_xy(self, lat: float, lon: float,
                      w: int, h: int
                      ) -> tuple[float, float]:
        """Equirectangular projection."""
        x = (lon + 180) / 360 * w
        y = (90 - lat) / 180 * h
        return x, y

    def paintEvent(self, event):
        p    = QPainter(self)
        w, h = self.width(), self.height()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Ocean background
        p.fillRect(0, 0, w, h, QColor("#0a1628"))

        # Simple land masses (rough continental outlines)
        self._draw_landmasses(p, w, h)

        # Gray line night side
        if self._show_gl and self._terminator:
            self._draw_night_side(p, w, h)

        # Grid lines
        self._draw_grid(p, w, h)

        # QSO paths
        if self._show_qsos:
            self._draw_qso_paths(p, w, h)

        # Station marker
        if self._station_lat or self._station_lon:
            self._draw_station(p, w, h)

        # Satellites
        if self._satellites:
            self._draw_satellites(p, w, h)
        self._draw_aprs(p, w, h)
        self._draw_dx_spots(p, w, h)
        self._draw_heard(p, w, h)
        self._draw_hearing_me(p, w, h)

        # Status text shown in the _gl_bar QLabel below the canvas

        p.end()

    def _draw_grid(self, p: QPainter, w: int, h: int):
        """Draw latitude/longitude grid."""
        p.setPen(QPen(QColor("#1a2a3a"), 1,
                      Qt.PenStyle.DotLine))
        # Longitude lines every 30°
        for lon in range(-180, 181, 30):
            x, _ = self._latlon_to_xy(0, lon, w, h)
            p.drawLine(int(x), 0, int(x), h)
        # Latitude lines every 30°
        for lat in range(-60, 91, 30):
            _, y = self._latlon_to_xy(lat, 0, w, h)
            p.drawLine(0, int(y), w, int(y))

    def _draw_night_side(self, p: QPainter,
                         w: int, h: int):
        """Shade the night side of the Earth."""
        if not self._terminator:
            return
        # Simple approach: shade right or left half based on terminator
        # Full polygon approach
        poly = QPolygonF()
        for lat, lon in self._terminator:
            x, y = self._latlon_to_xy(lat, lon, w, h)
            poly.append(QPointF(x, y))

        if poly.isEmpty():
            return

        # Shade with semi-transparent dark blue
        p.setBrush(QBrush(QColor(0, 0, 30, 120)))
        p.setPen(QPen(QColor("#3366aa"), 1.5))
        p.drawPolygon(poly)

        # Draw gray line itself
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("#4488cc"), 2))
        p.drawPolyline(poly)

    def _draw_qso_paths(self, p: QPainter,
                        w: int, h: int):
        """Draw great circle paths to QSO contacts."""
        mode_colors = {
            "FT8":  "#4488ff",
            "FT4":  "#44aaff",
            "WSPR": "#8844ff",
            "CW":   "#ffaa22",
            "SSB":  "#3fbe6f",
        }
        for path in self._qso_paths[:50]:
            color = mode_colors.get(
                path.get("mode", ""), "#335533")
            p.setPen(QPen(QColor(color), 1,
                          Qt.PenStyle.DashLine))
            x1, y1 = self._latlon_to_xy(
                path["from"][0], path["from"][1], w, h)
            x2, y2 = self._latlon_to_xy(
                path["to"][0], path["to"][1], w, h)
            p.drawLine(int(x1), int(y1),
                       int(x2), int(y2))
            # DX marker
            p.setBrush(QBrush(QColor(color)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(x2-3, y2-3, 6, 6))
            p.setPen(QPen(QColor(color), 1))

    def _draw_station(self, p: QPainter,
                      w: int, h: int):
        """Draw station location marker."""
        x, y = self._latlon_to_xy(
            self._station_lat,
            self._station_lon, w, h)
        # Glow effect
        for r, alpha in [(12, 30), (8, 60), (5, 120)]:
            p.setBrush(QBrush(QColor(63, 190, 111, alpha)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(x-r, y-r, r*2, r*2))
        # Center dot
        p.setBrush(QBrush(QColor("#3fbe6f")))
        p.setPen(QPen(QColor("white"), 1))
        p.drawEllipse(QRectF(x-4, y-4, 8, 8))
        # Callsign label
        if self._station_call:
            p.setPen(QPen(QColor("#3fbe6f")))
            p.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
            p.drawText(int(x)+8, int(y)-4,
                       self._station_call)

    def _draw_satellites(self, p: QPainter,
                          w: int, h: int):
        """Draw satellite positions with orbit indicator."""
        for sat in self._satellites[:30]:
            lat = sat.get("lat", 0.0)
            lon = sat.get("lon", 0.0)
            name = sat.get("name", "")
            alt  = sat.get("alt_km", 0.0)
            visible = sat.get("visible", False)

            x, y = self._latlon_to_xy(lat, lon, w, h)

            # Color: visible = yellow, below horizon = dim
            color = QColor("#ffcc00") if visible else QColor("#554400")
            p.setBrush(QBrush(color))
            p.setPen(QPen(QColor("#332200"), 1))
            p.drawEllipse(QRectF(x-4, y-4, 8, 8))

            # ISS gets a bigger marker
            if "ISS" in name.upper():
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor("#ff8800"), 1))
                p.drawEllipse(QRectF(x-7, y-7, 14, 14))

            # Label
            p.setPen(QPen(color))
            p.setFont(QFont("Courier New", 8))
            short = name.split("(")[0].strip()[:12]
            if alt > 0:
                short += f" {alt:.0f}km"
            p.drawText(int(x)+6, int(y)-2, short)

    def _draw_status(self, p, w, h):
        """Status text is shown in the QLabel below; not drawn on canvas."""
        pass

    def _draw_landmasses(self, p: QPainter, w: int, h: int):
        """Draw simplified continental outlines (approximate, orientation only)."""
        p.setBrush(QBrush(QColor("#1a2d1a")))
        p.setPen(QPen(QColor("#2a4a2a"), 1))
        for poly_coords in _CONTINENT_OUTLINES:
            pts = QPolygonF([
                QPointF((lon + 180) / 360.0 * w,
                        (90 - lat) / 180.0 * h)
                for lat, lon in poly_coords])
            p.drawPolygon(pts)
