from __future__ import annotations
"""2D propagation side-view — redesigned visualization.

Shows a scaled cross-section from TX to RX with:
  • Multi-layer ionosphere  (D / E / F1 / F2)
  • Altitude scale (left axis, 0-400 km)
  • Distance scale (bottom axis)
  • Glowing signal-path arc with mode-specific colour
  • Groundwave / NVIS / skip-zone overlays as surface bands
  • Signal strength bar (EIRP → Prx estimate)

Educational approximation — not VOACAP.
"""
import math
from typing import Optional

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (QPainter, QPen, QBrush, QColor, QFont,
                          QPainterPath, QLinearGradient, QRadialGradient)
from PyQt6.QtWidgets import QWidget


F_LAYER_KM  = 300.0   # nominal F2 peak
EARTH_R_KM  = 6371.0
ALT_MAX_KM  = 450.0   # top of visible altitude range

# Layer altitude ranges (km) for drawing
_LAYERS = {
    "D":  (60,  90,  QColor(220, 100, 40, 0),   QColor(220, 100, 40, 35)),
    "E":  (90,  150, QColor(80,  180, 220, 0),   QColor(80,  180, 220, 30)),
    "F1": (150, 250, QColor(130, 90,  230, 0),   QColor(130, 90,  230, 45)),
    "F2": (250, 400, QColor(160, 100, 255, 20),  QColor(160, 100, 255, 75)),
}

# Colour per propagation mode
_MODE_COLOR = {
    "groundwave": QColor(255, 204, 0),
    "nvis":       QColor(80,  220, 255),
    "skywave":    QColor(80,  160, 255),
    "beyond":     QColor(255, 80,  80),
    "absorbed":   QColor(200, 100, 50),
}


class PropagationSideView(QWidget):
    """Cross-sectional propagation visualization widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(240)
        self.setAutoFillBackground(True)
        self._path_km:    float = 0.0
        self._muf_mhz:    float = 0.0
        self._luf_mhz:    float = 3.0
        self._freq_mhz:   float = 0.0
        self._target:     str   = ""
        self._tx_lat:     float = 0.0
        self._tx_lon:     float = 0.0
        self._rx_lat:     float = 0.0
        self._rx_lon:     float = 0.0
        self._terrain_mode:  str              = "off"
        self._terrain_elev:  Optional[list[float]] = None
        self._terrain_busy:  bool             = False
        self._terrain_label: str              = ""
        self._eirp_dbw:      float            = 10.0
        self._show_gw_zone:  bool = True
        self._show_nvis_zone: bool = True
        self._show_sw_zone:  bool = True

    # ── Public API ────────────────────────────────────────────────────────

    def set_terrain_mode(self, mode: str):
        self._terrain_mode = mode
        self._terrain_elev = None
        self._terrain_label = ""
        if mode != "off":
            self._fetch_terrain_async()
        self.update()

    def set_eirp_dbw(self, dbw: float):
        self._eirp_dbw = dbw
        self.update()

    def set_show_zones(self, gw: bool, nvis: bool, sw: bool) -> None:
        self._show_gw_zone   = gw
        self._show_nvis_zone = nvis
        self._show_sw_zone   = sw
        self.update()

    def update_state(self, path_km, muf_mhz, luf_mhz=3.0, freq_mhz=0.0,
                     target="", tx_lat=0.0, tx_lon=0.0, rx_lat=0.0, rx_lon=0.0):
        path_changed = abs(path_km - self._path_km) > 1.0
        self._path_km  = max(0.0, float(path_km))
        self._muf_mhz  = max(0.0, float(muf_mhz))
        self._luf_mhz  = max(0.0, float(luf_mhz))
        self._freq_mhz = max(0.0, float(freq_mhz))
        self._target   = target or ""
        if tx_lat or tx_lon:
            self._tx_lat, self._tx_lon = tx_lat, tx_lon
            self._rx_lat, self._rx_lon = rx_lat, rx_lon
        if path_changed and self._terrain_mode != "off":
            self._terrain_elev = None
            self._fetch_terrain_async()
        self.update()

    # ── Terrain async ─────────────────────────────────────────────────────

    def _fetch_terrain_async(self):
        if self._terrain_busy:
            return
        if (not self._tx_lat and not self._tx_lon) or self._path_km <= 0:
            return
        from PyQt6.QtCore import pyqtSignal, QObject
        import threading

        class _Worker(QObject):
            done = pyqtSignal(object, str)

        worker = _Worker()
        worker.done.connect(self._on_terrain_done)
        self._terrain_busy  = True
        self._terrain_label = "Fetching terrain…"
        self.update()
        mode = self._terrain_mode
        lat1, lon1 = self._tx_lat, self._tx_lon
        lat2, lon2 = self._rx_lat, self._rx_lon

        def _run():
            label = ""
            try:
                from core.terrain import elevation_profile
                elev = elevation_profile(lat1, lon1, lat2, lon2, n=60, mode=mode)
                label = (f"Terrain: {'SRTM' if mode == 'offline' else 'OpenTopo/SRTM30m'}"
                         if elev else
                         ("Offline tiles not downloaded" if mode == "offline"
                          else "Terrain fetch failed"))
            except Exception as e:
                elev  = None
                label = f"Terrain error: {e}"
            worker.done.emit(elev, label)

        threading.Thread(target=_run, daemon=True, name="TerrainFetch").start()

    def _on_terrain_done(self, elev, label: str):
        self._terrain_busy  = False
        self._terrain_elev  = elev
        self._terrain_label = label
        self.update()

    # ── Geometry helpers ──────────────────────────────────────────────────

    def _propagation_mode(self) -> str:
        if self._freq_mhz <= 0 or self._muf_mhz <= 0:
            return ""
        f = self._freq_mhz
        if f > self._muf_mhz:
            return "beyond"
        if f < self._luf_mhz:
            return "absorbed"
        if self._path_km < 400:
            return "nvis" if f < 10 else "groundwave"
        return "skywave"

    def _alt_to_y(self, alt_km: float, top: int, ground: int) -> int:
        """Convert altitude (km) to Y pixel — ground=0 km, top=ALT_MAX_KM."""
        frac = alt_km / ALT_MAX_KM
        return int(ground - frac * (ground - top))

    @staticmethod
    def _extra_path_loss_db(mode: str, path_km: float, freq_mhz: float) -> float:
        if mode == "skywave":
            hops = 2 if path_km > 4000 else 1
            return 10 * hops + 8 * (hops - 1)
        if mode == "nvis":
            return 10.0 + max(0.0, 20.0 * (1.0 - min(freq_mhz, 10.0) / 10.0))
        if mode == "groundwave":
            return 0.5 * path_km * max(0.5, math.log10(max(freq_mhz, 0.1)) + 1.0) / 10.0
        if mode in ("beyond", "absorbed"):
            return 60.0
        return 0.0

    # ── Paint helpers — layout constants per-call ─────────────────────────

    def _layout(self) -> tuple:
        """Return (W, H, top, ground, x0, x1, plot_w, left_margin)."""
        W, H = self.width(), self.height()
        lm     = 42   # left margin for altitude labels
        top    = int(H * 0.04)
        ground = int(H * 0.83)
        x0     = lm
        x1     = W - 8
        return W, H, top, ground, x0, x1, max(50, x1 - x0), lm

    # ── Drawing methods ───────────────────────────────────────────────────

    def _draw_sky(self, p: QPainter, W: int, H: int, top: int, ground: int):
        """Atmospheric gradient from deep space (top) to troposphere (ground)."""
        sky = QLinearGradient(0, top, 0, ground)
        sky.setColorAt(0.00, QColor(2,   2,   12))   # space
        sky.setColorAt(0.10, QColor(4,   4,   20))   # exosphere
        sky.setColorAt(0.30, QColor(8,   10,  35))   # thermosphere / F2 base
        sky.setColorAt(0.55, QColor(6,   18,  50))   # mesosphere
        sky.setColorAt(0.75, QColor(8,   24,  60))   # stratosphere
        sky.setColorAt(1.00, QColor(12,  32,  72))   # upper troposphere
        p.fillRect(0, top, W, ground - top, QBrush(sky))
        # Space above widget top
        p.fillRect(0, 0, W, top, QBrush(QColor(2, 2, 12)))

    def _draw_ionosphere_layers(self, p: QPainter, x0: int, x1: int,
                                 top: int, ground: int) -> tuple:
        """Draw D/E/F1/F2 layer bands; return (f2_top, f2_bot)."""
        f2_top = f2_bot = top
        for name, (lo_km, hi_km, col0, col1) in _LAYERS.items():
            y_top = self._alt_to_y(hi_km, top, ground)
            y_bot = self._alt_to_y(lo_km, top, ground)
            h_px  = max(1, y_bot - y_top)
            lg = QLinearGradient(0, y_top, 0, y_bot)
            lg.setColorAt(0.0, col0)
            lg.setColorAt(0.5, col1)
            lg.setColorAt(1.0, col0)
            p.fillRect(QRectF(x0, y_top, x1 - x0, h_px), QBrush(lg))
            # Boundary dashes + label
            col_dim = QColor(col1.red(), col1.green(), col1.blue(), 80)
            p.setPen(QPen(col_dim, 1, Qt.PenStyle.DashLine))
            p.drawLine(x0, y_top, x1, y_top)
            if h_px >= 10:
                p.setPen(QColor(col1.red(), col1.green(), col1.blue(), 160))
                p.setFont(QFont("", 7))
                mid_y = y_top + h_px // 2 + 4
                p.drawText(x0 + 4, mid_y,
                           f"{name}-layer  ({lo_km}-{hi_km} km)")
            if name == "F2":
                f2_top, f2_bot = y_top, y_bot
        return f2_top, f2_bot

    def _draw_terrain(self, p: QPainter, x0: int, x1: int,
                      ground: int, H: int, bulge_px: float):
        """Draw curved Earth surface with terrain relief."""
        n = 60
        max_tp = max(8, int((H - ground) * 0.6 + 12))
        if self._terrain_elev and len(self._terrain_elev) >= n:
            elev = self._terrain_elev[:n + 1]
            e_min, e_rng = min(elev), max(max(elev) - min(elev), 1.0)
            def _tp(i):
                t = i / n
                return (elev[i] - e_min) / e_rng * max_tp * min(1.0, 6*t*(1-t))
        else:
            seed = int(self._path_km) % 997
            pts = [(0.55 * math.sin(i/n * 7.3  + seed*0.13) +
                    0.30 * math.sin(i/n * 19.1 + seed*0.27) +
                    0.15 * math.sin(i/n * 41.7 + seed*0.41))
                   * min(1.0, 4*(i/n)*(1-i/n)) for i in range(n+1)]
            def _tp(i): return pts[i] * max_tp

        surf = QPainterPath()
        surf.moveTo(x0, ground + bulge_px * 0 - _tp(0))
        for i in range(1, n + 1):
            t = i / n
            surf.lineTo(x0 + t * (x1 - x0),
                        ground + bulge_px * 4*t*(1-t) - _tp(i))

        ground_path = QPainterPath(surf)
        ground_path.lineTo(x1, H)
        ground_path.lineTo(x0, H)
        ground_path.closeSubpath()
        gg = QLinearGradient(0, ground - max_tp, 0, H)
        gg.setColorAt(0.0, QColor("#50683a"))
        gg.setColorAt(0.2, QColor("#3a5028"))
        gg.setColorAt(1.0, QColor("#161e0a"))
        p.fillPath(ground_path, QBrush(gg))
        p.setPen(QPen(QColor("#6a8848"), 1))
        p.drawPath(surf)

    def _draw_propagation_zones(self, p: QPainter, x0: int, x1: int,
                                 ground: int, top: int, plot_w: int):
        """Surface-hugging zone bands with boundary lines."""
        if not (self._show_gw_zone or self._show_nvis_zone or self._show_sw_zone):
            return
        path = self._path_km
        if path <= 0:
            return
        freq, muf = self._freq_mhz, self._muf_mhz
        ppk = plot_w / path
        bh  = min(max(14, int((ground - top) * 0.14)), 44)  # band height px

        p.setFont(QFont("", 7))

        if self._show_gw_zone and freq > 0:
            gw_km = min(300.0 / max(freq, 0.1), path)
            x_gw  = int(x0 + gw_km * ppk)
            g = QLinearGradient(x0, 0, x_gw, 0)
            g.setColorAt(0.0, QColor(255, 200, 0, 65))
            g.setColorAt(1.0, QColor(255, 200, 0, 0))
            p.fillRect(x0, ground - bh, x_gw - x0, bh, QBrush(g))
            p.setPen(QPen(QColor(255, 200, 0, 140), 1, Qt.PenStyle.DashLine))
            p.drawLine(x_gw, ground - bh, x_gw, ground)
            p.setPen(QColor(255, 215, 60, 230))
            p.drawText(x0 + 3, ground - bh - 3, f"GW ~{gw_km:.0f} km")

        if self._show_nvis_zone:
            nvis_km = min(500.0, path)
            x_nv    = int(x0 + nvis_km * ppk)
            in_band = freq > 0 and 2.0 <= freq <= 10.0
            a       = 55 if in_band else 18
            g2 = QLinearGradient(x0, 0, x_nv, 0)
            g2.setColorAt(0.0, QColor(50, 190, 255, a))
            g2.setColorAt(1.0, QColor(50, 190, 255, 0))
            p.fillRect(x0, ground - bh, x_nv - x0, bh, QBrush(g2))
            p.setPen(QPen(QColor(50, 190, 255, 130 if in_band else 50),
                          1, Qt.PenStyle.DashLine))
            p.drawLine(x_nv, ground - bh, x_nv, ground)
            if x_nv - x0 > 30:
                p.setPen(QColor(70, 210, 255, 220 if in_band else 80))
                p.drawText(x0 + 3, ground - bh - 12,
                           "NVIS" + ("" if in_band else " (off-band)"))

        if self._show_sw_zone and freq > 0 and muf > freq:
            denom   = math.sqrt(max(muf**2 - freq**2, 0.01))
            skip_km = min(2.0 * F_LAYER_KM * freq / denom, path * 0.8)
            x_skip  = int(x0 + skip_km * ppk)
            sb_y    = self._alt_to_y(200, top, ground)   # skip band at ~200 km
            sb_h    = max(6, int((ground - top) * 0.06))
            if x_skip > x0 + 4:
                p.fillRect(x0, sb_y, x_skip - x0, sb_h,
                           QBrush(QColor(140, 60, 210, 45)))
                p.setPen(QPen(QColor(170, 100, 230, 130), 1, Qt.PenStyle.DotLine))
                p.drawLine(x_skip, sb_y, x_skip, ground)
                p.setPen(QColor(180, 120, 240, 210))
                p.drawText(x0 + 3, sb_y + sb_h + 10, f"Skip ~{skip_km:.0f} km")
            if x_skip < x1 - 4:
                p.fillRect(x_skip, sb_y, x1 - x_skip, sb_h,
                           QBrush(QColor(60, 100, 255, 30)))

    def _draw_signal_path(self, p: QPainter, mode: str,
                          x0: int, x1: int, ground: int,
                          f2_top: int, f2_bot: int,
                          bulge_px: float, path: float, top: int) -> str:
        """Draw glowing signal path arc; return status text."""
        col = _MODE_COLOR.get(mode, QColor(150, 150, 150))
        if not mode:
            return "Set an operating frequency in Rig tab"

        arc = QPainterPath()
        ant_h = 22    # antenna tip offset above ground

        if mode == "groundwave":
            arc.moveTo(x0, ground - ant_h)
            arc.quadTo((x0+x1)/2, ground + bulge_px - 6, x1, ground - ant_h)
            msg = "Groundwave - surface-following, short-path"

        elif mode == "nvis":
            f2_mid = (f2_top + f2_bot) // 2
            arc.moveTo(x0, ground - ant_h)
            arc.cubicTo(x0 + 30, f2_mid + 20,
                        x1 - 30, f2_mid + 20,
                        x1, ground - ant_h)
            msg = "NVIS - near-vertical, F-layer bounce, local/regional"

        elif mode == "skywave":
            hops  = 2 if path > 4000 else 1
            f2_mid = (f2_top * 2 + f2_bot) // 3   # upper F2
            arc.moveTo(x0, ground - ant_h)
            for h in range(hops):
                x_s = x0 + (x1 - x0) * h / hops
                x_e = x0 + (x1 - x0) * (h + 1) / hops
                cx  = (x_s + x_e) / 2
                arc.quadTo(cx, f2_mid - 10,
                           x_e, (ground - ant_h) if h == hops-1 else ground - 2)
            msg = f"Skywave - {'1-hop' if hops == 1 else '2-hop'} F2 refraction"

        elif mode == "beyond":
            arc.moveTo(x0, ground - ant_h)
            arc.quadTo((x0+x1)//2 - 50, top + 8, (x0+x1)//2, top + 4)
            p.setPen(QPen(col, 2, Qt.PenStyle.DashLine))
            p.drawPath(arc)
            p.setPen(col.lighter(130))
            p.setFont(QFont("", 8))
            p.drawText((x0+x1)//2 + 6, top + 14, "↑ escapes to space")
            return f"Above MUF ({self._muf_mhz:.1f} MHz) - signal lost to space"

        elif mode == "absorbed":
            d = int((x1 - x0) * 0.30)
            arc.moveTo(x0, ground - ant_h)
            arc.quadTo(x0 + d//2, ground - 30, x0 + d, ground - 4)
            p.setPen(QPen(col, 2, Qt.PenStyle.DotLine))
            p.drawPath(arc)
            return f"Below LUF ({self._luf_mhz:.1f} MHz) - D-layer absorbed"

        else:
            return ""

        # Three-pass glow: outer → mid → core
        for width, alpha in ((9, 18), (5, 50), (1.5, 220)):
            pen_col = QColor(col.red(), col.green(), col.blue(), int(alpha))
            p.setPen(QPen(pen_col, width, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPath(arc)
        return msg

    def _draw_stations(self, p: QPainter, x0: int, x1: int, ground: int):
        """TX/RX mast markers with glow dots."""
        mast_h = 20
        for x, lbl in ((x0, "TX"), (x1, "RX")):
            glow = QRadialGradient(x, ground - mast_h, 12)
            glow.setColorAt(0.0, QColor(63, 190, 111, 100))
            glow.setColorAt(1.0, QColor(63, 190, 111, 0))
            p.fillRect(x - 12, ground - mast_h - 12, 24, 24, QBrush(glow))
            p.setPen(QPen(QColor("#3fbe6f"), 2))
            p.drawLine(x, ground, x, ground - mast_h)
            p.setBrush(QBrush(QColor("#3fbe6f")))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(x, ground - mast_h), 4, 4)
            p.setPen(QColor("#3fbe6f"))
            p.setFont(QFont("", 8, QFont.Weight.Bold))
            p.drawText(x - 8, ground - mast_h - 5, lbl)

    def _draw_altitude_scale(self, p: QPainter, lm: int, top: int, ground: int):
        """Left-axis altitude labels (km)."""
        p.setPen(QColor(100, 130, 160, 180))
        p.setFont(QFont("", 7))
        for alt in (0, 100, 200, 300, 400):
            y = self._alt_to_y(alt, top, ground)
            if top <= y <= ground + 2:
                p.drawText(2, y + 4, f"{alt}")
                p.setPen(QPen(QColor(60, 80, 110, 60), 1, Qt.PenStyle.DotLine))
                p.drawLine(lm - 2, y, lm + 2, y)
                p.setPen(QColor(100, 130, 160, 180))
        # "km" unit label rotated
        p.save()
        p.translate(9, (top + ground) // 2)
        p.rotate(-90)
        p.drawText(-12, 0, "km")
        p.restore()

    def _draw_distance_scale(self, p: QPainter, x0: int, x1: int,
                              ground: int, H: int, path: float):
        """Bottom distance axis with tick marks."""
        p.setPen(QColor(100, 130, 160, 160))
        p.setFont(QFont("", 7))
        plot_w = x1 - x0
        step_km = self._nice_step(path, 5)
        km = 0.0
        while km <= path + 0.5:
            x = int(x0 + km / path * plot_w)
            p.drawLine(x, ground + 2, x, ground + 6)
            lbl = f"{int(km)}" if km == 0 else f"{int(km)} km" if km >= path - 1 else f"{int(km)}"
            p.drawText(x - (0 if km == 0 else 12), H - 3, lbl)
            km += step_km

    @staticmethod
    def _nice_step(total: float, max_ticks: int) -> float:
        raw = total / max_ticks
        for n in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000):
            if raw <= n:
                return float(n)
        return round(raw / 1000) * 1000

    def _draw_signal_meter(self, p: QPainter, x0: int, x1: int,
                            ground: int, H: int, mode: str):
        """Compact signal-strength bar just above the distance scale."""
        if self._path_km <= 0 or self._freq_mhz <= 0 or not mode:
            return
        eirp_dbm = self._eirp_dbw + 30
        fspl = (20 * math.log10(max(self._path_km, 1)) +
                20 * math.log10(max(self._freq_mhz, 0.1)) + 92.45)
        extra  = self._extra_path_loss_db(mode, self._path_km, self._freq_mhz)
        prx    = eirp_dbm - fspl - extra
        norm   = max(0.0, min(1.0, (prx + 130) / 57))
        bar_y  = H - 18
        bar_w  = int((x1 - x0) * norm)
        sg = QLinearGradient(x0, bar_y, x0 + (x1-x0), bar_y)
        sg.setColorAt(0.0, QColor(200, 40,  40,  200))
        sg.setColorAt(0.5, QColor(220, 160, 20,  200))
        sg.setColorAt(1.0, QColor(40,  200, 100, 200))
        p.setPen(Qt.PenStyle.NoPen)
        p.fillRect(x0, bar_y, x1 - x0, 5, QBrush(QColor(30, 40, 55, 140)))
        p.fillRect(x0, bar_y, bar_w, 5, QBrush(sg))
        p.setPen(QColor(120, 150, 180, 200))
        p.setFont(QFont("", 7))
        p.drawText(x0, bar_y - 2,
                   f"EIRP {self._eirp_dbw:.0f} dBW  •  "
                   f"Path loss {fspl+extra:.0f} dB  •  "
                   f"Prx ≈ {prx:.0f} dBm")
        if self._terrain_label:
            p.drawText(x0, bar_y + 13, self._terrain_label)

    def _draw_info_panel(self, p: QPainter, x0: int, top: int,
                          H: int, mode: str, msg: str):
        """Top info strip: path + LUF/FOT/MUF; bottom mode status."""
        def _shadow(px, py, text, fg, font, bold=False):
            p.setFont(QFont("", font, QFont.Weight.Bold if bold else QFont.Weight.Normal))
            p.setPen(QColor(0, 0, 0, 160))
            p.drawText(px + 1, py + 1, text)
            p.setPen(QColor(fg))
            p.drawText(px, py, text)

        _shadow(x0, top + 14,
                (f"{self._target or 'Path'}  •  {self._path_km:,.0f} km"
                 + (f"  •  {self._freq_mhz:.3f} MHz" if self._freq_mhz > 0 else "")),
                "#dde8f0", 9)
        if self._muf_mhz > 0:
            fot = round(0.85 * self._muf_mhz, 1)
            _shadow(x0, top + 27,
                    f"LUF {self._luf_mhz:.1f}  |  FOT {fot:.1f}  |  MUF {self._muf_mhz:.1f} MHz",
                    "#9ab8d0", 8)
        if msg:
            col = _MODE_COLOR.get(mode, QColor(160, 160, 160))
            hex_col = f"#{col.red():02x}{col.green():02x}{col.blue():02x}"
            _shadow(x0, H - 22, msg, hex_col, 9, bold=True)

    # ── paintEvent ────────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H, top, ground, x0, x1, plot_w, lm = self._layout()

        # Background
        p.fillRect(self.rect(), QBrush(QColor(2, 2, 12)))

        if self._path_km <= 0:
            p.setPen(QColor("#6688aa"))
            p.setFont(QFont("", 10))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "Enter a Path-to target above to visualize propagation\n"
                       "(grid square, callsign, ZIP, or city)")
            return

        path     = max(self._path_km, 1.0)
        sagitta  = (path ** 2) / (8 * EARTH_R_KM)
        bulge_px = min(H * 0.08, sagitta / 50.0 * H * 0.08)

        self._draw_sky(p, W, H, top, ground)
        f2_top, f2_bot = self._draw_ionosphere_layers(p, x0, x1, top, ground)
        self._draw_terrain(p, x0, x1, ground, H, bulge_px)
        self._draw_propagation_zones(p, x0, x1, ground, top, plot_w)
        self._draw_altitude_scale(p, lm, top, ground)

        mode = self._propagation_mode()
        msg  = self._draw_signal_path(
            p, mode, x0, x1, ground, f2_top, f2_bot, bulge_px, path, top)

        self._draw_stations(p, x0, x1, ground)
        self._draw_distance_scale(p, x0, x1, ground, H, path)
        self._draw_signal_meter(p, x0, x1, ground, H, mode)
        self._draw_info_panel(p, x0, top, H, mode, msg)
