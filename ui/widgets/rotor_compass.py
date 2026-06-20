from __future__ import annotations
"""RotorCompass — QPainter compass rose showing azimuth and elevation."""
import math

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (QPainter, QPen, QBrush, QColor, QFont,
                          QPainterPath, QLinearGradient)
from PyQt6.QtWidgets import QWidget


_CARDINALS = {0: "N", 90: "E", 180: "S", 270: "W"}
_INTERCARDS = {45: "NE", 135: "SE", 225: "SW", 315: "NW"}


class RotorCompass(QWidget):
    """Compass-rose widget for antenna rotor azimuth/elevation display.

    Current azimuth: solid green needle.
    Target azimuth:  dashed orange ring sector (shown when target differs).
    Elevation:       small arc overlay on the inner ring (0° = horizon rim).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._az_cur:    float = 0.0
        self._el_cur:    float = 0.0
        self._az_target: float | None = None
        self.setMinimumSize(140, 140)

    # ── Public setters ────────────────────────────────────────────────────

    def set_current(self, az: float, el: float = 0.0) -> None:
        self._az_cur = float(az) % 360
        self._el_cur = max(0.0, min(90.0, float(el)))
        self.update()

    def set_target(self, az: float | None) -> None:
        self._az_target = (float(az) % 360) if az is not None else None
        self.update()

    # ── Paint ─────────────────────────────────────────────────────────────

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H  = self.width(), self.height()
        cx, cy = W / 2, H / 2
        r = min(cx, cy) - 6

        self._draw_background(p, cx, cy, r)
        self._draw_ticks(p, cx, cy, r)
        self._draw_labels(p, cx, cy, r)
        self._draw_elevation(p, cx, cy, r)
        if self._az_target is not None:
            self._draw_target_sector(p, cx, cy, r)
        self._draw_needle(p, cx, cy, r)
        self._draw_centre_text(p, cx, cy)

    def _draw_background(self, p: QPainter, cx, cy, r):
        # Outer ring
        bg = QLinearGradient(cx - r, cy - r, cx + r, cy + r)
        bg.setColorAt(0.0, QColor(18, 22, 30))
        bg.setColorAt(1.0, QColor(10, 14, 20))
        p.setPen(QPen(QColor("#2a3a50"), 2))
        p.setBrush(QBrush(bg))
        p.drawEllipse(QPointF(cx, cy), r, r)

    def _draw_ticks(self, p: QPainter, cx, cy, r):
        for deg in range(0, 360, 5):
            rad    = math.radians(deg - 90)
            is_ten = deg % 10 == 0
            is_thirty = deg % 30 == 0
            t_len  = r * (0.14 if is_thirty else 0.09 if is_ten else 0.05)
            col    = QColor("#4a6080") if is_thirty else QColor("#2a3a50")
            p.setPen(QPen(col, 1 if is_ten else 0.5))
            x1 = cx + (r - t_len) * math.cos(rad)
            y1 = cy + (r - t_len) * math.sin(rad)
            x2 = cx + r * math.cos(rad)
            y2 = cy + r * math.sin(rad)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def _draw_labels(self, p: QPainter, cx, cy, r):
        for deg, lbl in {**_CARDINALS, **_INTERCARDS}.items():
            rad  = math.radians(deg - 90)
            dist = r * 0.76
            x    = cx + dist * math.cos(rad)
            y    = cy + dist * math.sin(rad)
            is_card = deg in _CARDINALS
            p.setFont(QFont("", 8 if is_card else 7,
                            QFont.Weight.Bold if is_card else QFont.Weight.Normal))
            col = QColor("#5fb8ff") if lbl == "N" else \
                  QColor("#8ab8d8") if is_card else QColor("#507080")
            p.setPen(col)
            fm  = p.fontMetrics()
            tw  = fm.horizontalAdvance(lbl)
            th  = fm.height()
            p.drawText(QRectF(x - tw/2, y - th/2, tw + 1, th + 1), lbl)

    def _draw_elevation(self, p: QPainter, cx, cy, r):
        """Small arc on the inner ring showing elevation (0°=horizon=rim)."""
        if self._el_cur <= 0.5:
            return
        el_r = r * 0.30
        arc_span = self._el_cur / 90.0 * 360
        p.setPen(QPen(QColor(80, 200, 120, 140), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        start_angle = int(90 * 16)           # 12 o'clock in Qt degrees×16
        span_angle  = int(arc_span * 16)
        p.drawArc(QRectF(cx - el_r, cy - el_r, el_r*2, el_r*2),
                  start_angle, span_angle)

    def _draw_target_sector(self, p: QPainter, cx, cy, r):
        if self._az_target is None:
            return
        diff = abs((self._az_target - self._az_cur + 360) % 360)
        if diff < 1.0:
            return
        rad   = math.radians(self._az_target - 90)
        inner = r * 0.45
        outer = r * 0.92
        p.setPen(QPen(QColor(255, 140, 0, 160), 1, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(cx + inner * math.cos(rad),
                           cy + inner * math.sin(rad)),
                   QPointF(cx + outer * math.cos(rad),
                           cy + outer * math.sin(rad)))
        p.setPen(QColor(255, 140, 0, 200))
        p.setFont(QFont("", 7))
        tx = cx + (r + 2) * math.cos(rad) * 0.88
        ty = cy + (r + 2) * math.sin(rad) * 0.88
        p.drawText(QRectF(tx - 14, ty - 7, 28, 14),
                   Qt.AlignmentFlag.AlignCenter,
                   f"→{int(self._az_target)}°")

    def _draw_needle(self, p: QPainter, cx, cy, r):
        """Filled arrow needle pointing at current azimuth."""
        rad   = math.radians(self._az_cur - 90)
        tip_x = cx + r * 0.85 * math.cos(rad)
        tip_y = cy + r * 0.85 * math.sin(rad)
        # Small back fin
        back_x = cx - r * 0.22 * math.cos(rad)
        back_y = cy - r * 0.22 * math.sin(rad)
        perp = rad + math.pi / 2
        w  = r * 0.06
        lx = cx + w * math.cos(perp)
        ly = cy + w * math.sin(perp)
        rx = cx - w * math.cos(perp)
        ry = cy - w * math.sin(perp)

        needle = QPainterPath()
        needle.moveTo(tip_x, tip_y)
        needle.lineTo(lx, ly)
        needle.lineTo(back_x, back_y)
        needle.lineTo(rx, ry)
        needle.closeSubpath()

        p.setBrush(QBrush(QColor("#3fbe6f")))
        p.setPen(QPen(QColor("#2a8050"), 1))
        p.drawPath(needle)
        # Centre pivot dot
        p.setBrush(QBrush(QColor("#1a2830")))
        p.setPen(QPen(QColor("#3fbe6f"), 1))
        p.drawEllipse(QPointF(cx, cy), r * 0.07, r * 0.07)

    def _draw_centre_text(self, p: QPainter, cx, cy):
        az_txt = f"{int(self._az_cur):03d}°"
        el_txt = f"El {int(self._el_cur):02d}°"
        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QColor("#3fbe6f"))
        fm = p.fontMetrics()
        p.drawText(QRectF(cx - 22, cy + 4, 44, 14),
                   Qt.AlignmentFlag.AlignCenter, az_txt)
        p.setFont(QFont("Courier New", 7))
        p.setPen(QColor("#5a9070"))
        p.drawText(QRectF(cx - 22, cy + 17, 44, 12),
                   Qt.AlignmentFlag.AlignCenter, el_txt)
