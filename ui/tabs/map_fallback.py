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

import math
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

        # Legend / status
        self._draw_status(p, w, h)

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

    def _draw_status(self, p: QPainter,
                     w: int, h: int):
        """Draw gray line status text."""
        if not self._gl_info:
            return
        from network.grayline import format_gray_line_status
        text = format_gray_line_status(self._gl_info)
        p.setFont(QFont("Courier New", 11))
        color = ("#3fbe6f" if self._gl_info.is_gray_line
                 else "#666")
        p.setPen(QPen(QColor(color)))
        # Semi-transparent background
        fm   = p.fontMetrics()
        tw   = fm.horizontalAdvance(text)
        th   = fm.height()
        bx   = w//2 - tw//2 - 8
        by   = h - th - 12
        p.setBrush(QBrush(QColor(0, 0, 0, 160)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bx, by, tw+16, th+8), 4, 4)
        p.setPen(QPen(QColor(color)))
        p.drawText(bx+8, by+th, text)

    def _draw_landmasses(self, p: QPainter,
                         w: int, h: int):
        """
        Draw simplified continental outlines.
        Very approximate — just for orientation.
        """
        p.setBrush(QBrush(QColor("#1a2d1a")))
        p.setPen(QPen(QColor("#2a4a2a"), 1))

        # Each "continent" is a list of (lat, lon) points
        continents = [
            # North America (very rough)
            [(70,-140),(70,-70),(50,-55),(25,-80),
             (10,-85),(10,-77),(20,-87),(30,-97),
             (32,-117),(50,-125),(60,-140),(70,-140)],
            # South America
            [(10,-73),(0,-50),(-10,-37),(-33,-71),
             (-55,-67),(-55,-65),(-33,-70),(-10,-40),
             (0,-50),(10,-73)],
            # Europe
            [(70,30),(70,10),(60,5),(45,0),(36,5),
             (36,28),(45,35),(60,30),(70,30)],
            # Africa
            [(36,5),(36,28),(10,42),(0,42),(-35,18),
             (-35,17),(0,9),(10,15),(36,5)],
            # Asia
            [(70,30),(70,140),(60,140),(45,135),
             (22,120),(10,105),(0,105),(10,80),
             (25,70),(45,60),(60,40),(70,30)],
            # Australia
            [(-15,130),(-15,145),(-37,148),
             (-38,140),(-32,116),(-22,114),
             (-15,130)],
        ]

        for continent in continents:
            poly = QPolygonF()
            for lat, lon in continent:
                x, y = self._latlon_to_xy(lat, lon, w, h)
                poly.append(QPointF(x, y))
            p.drawPolygon(poly)
