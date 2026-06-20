from __future__ import annotations
"""WSPRPolarChart — azimuthal equidistant polar chart of WSPR heard stations.

Center = operator's location.  North at top, clockwise bearings.
Distance rings at 1000 / 3000 / 6000 / 9000 km.
Each spot is a coloured dot at (bearing, distance):
  dark blue → blue → cyan → green → yellow → red  as SNR improves.
"""
import math
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (QPainter, QPen, QBrush, QColor, QFont,
                          QLinearGradient)
from PyQt6.QtWidgets import QWidget

_RINGS_KM   = (1000, 3000, 6000, 9000)
_MAX_KM     = 10_000   # clip beyond this
_CARDINALS  = {0: "N", 90: "E", 180: "S", 270: "W"}


def _snr_color(snr: float) -> QColor:
    """Map SNR (-30 to +10 dB) to a colour gradient."""
    frac = max(0.0, min(1.0, (snr + 30) / 40))   # 0 at -30dB, 1 at +10dB
    if frac < 0.25:
        return QColor(30, 30, int(200 * frac / 0.25))
    if frac < 0.5:
        t = (frac - 0.25) / 0.25
        return QColor(0, int(180 * t), 200)
    if frac < 0.75:
        t = (frac - 0.5) / 0.25
        return QColor(0, 200, int(200 * (1 - t)))
    t = (frac - 0.75) / 0.25
    return QColor(int(255 * t), int(200 * (1 - t * 0.5)), 0)


class WSPRPolarChart(QWidget):
    """Polar propagation chart for WSPR heard stations."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._spots: list = []   # list of dict with bearing_deg, distance_km, snr, callsign, band
        self.setMinimumSize(220, 220)

    def set_spots(self, spots: list) -> None:
        """Update with list of dicts: {bearing_deg, distance_km, snr, callsign, band}."""
        self._spots = [s for s in spots if s.get("distance_km", 0) > 0]
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H  = self.width(), self.height()
        cx, cy = W / 2, H / 2
        radius = min(cx, cy) - 22

        # Dark background
        p.fillRect(self.rect(), QBrush(QColor(6, 10, 18)))

        # Distance rings
        for ring_km in _RINGS_KM:
            r = radius * ring_km / _MAX_KM
            p.setPen(QPen(QColor(40, 55, 75), 1, Qt.PenStyle.DotLine))
            p.drawEllipse(QPointF(cx, cy), r, r)
            p.setPen(QColor(55, 75, 100))
            p.setFont(QFont("", 7))
            p.drawText(QRectF(cx + 2, cy - r - 9, 45, 10),
                       Qt.AlignmentFlag.AlignLeft,
                       f"{ring_km//1000}Mm")

        # Bearing lines every 30°
        for deg in range(0, 360, 30):
            rad = math.radians(deg - 90)
            x1  = cx + (radius * 0.10) * math.cos(rad)
            y1  = cy + (radius * 0.10) * math.sin(rad)
            x2  = cx + radius * math.cos(rad)
            y2  = cy + radius * math.sin(rad)
            p.setPen(QPen(QColor(30, 45, 65), 1))
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # Cardinal labels
        p.setFont(QFont("", 8, QFont.Weight.Bold))
        for deg, lbl in _CARDINALS.items():
            rad = math.radians(deg - 90)
            lx  = cx + (radius + 10) * math.cos(rad) - 5
            ly  = cy + (radius + 10) * math.sin(rad) + 5
            p.setPen(QColor(100, 130, 170))
            p.drawText(int(lx), int(ly), lbl)

        # Spots
        p.setPen(Qt.PenStyle.NoPen)
        for sp in self._spots:
            bearing = float(sp.get("bearing_deg", 0))
            dist    = min(float(sp.get("distance_km", 0)), _MAX_KM)
            snr     = float(sp.get("snr", -20))
            if dist <= 0:
                continue
            rad  = math.radians(bearing - 90)
            r    = radius * dist / _MAX_KM
            x    = cx + r * math.cos(rad)
            y    = cy + r * math.sin(rad)
            col  = _snr_color(snr)
            p.setBrush(QBrush(col))
            p.drawEllipse(QPointF(x, y), 4, 4)

        # Centre dot (station)
        p.setBrush(QBrush(QColor("#3fbe6f")))
        p.setPen(QPen(QColor("#3fbe6f"), 1))
        p.drawEllipse(QPointF(cx, cy), 5, 5)

        # Legend: spot count
        p.setPen(QColor(80, 110, 150))
        p.setFont(QFont("", 7))
        p.drawText(4, H - 4,
                   f"{len(self._spots)} spots  (max {_MAX_KM//1000} Mm)")
