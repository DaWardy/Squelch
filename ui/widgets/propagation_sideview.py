"""2D side-view propagation visualization widget.

Shows a curved-Earth cross-section between two stations with:
  • Groundwave path along the surface
  • Skywave path(s) reflecting off the ionospheric F-layer
  • MUF / LUF / current-band context labels
  • NVIS indication when the path is short and the operator's freq is low
  • Day/night gray-line shading along the path

This is an EDUCATIONAL approximation, not VOACAP. It uses simple geometry
and the current MUF estimate from network.propagation. The goal is for the
operator to SEE why a frequency may or may not work for a given path —
something a static "band conditions" panel can't convey.
"""
from __future__ import annotations
import math
from typing import Optional

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (QPainter, QPen, QBrush, QColor, QFont,
                          QPainterPath, QLinearGradient)
from PyQt6.QtWidgets import QWidget


# Approximate ionospheric F-layer altitude (km). Day/night varies 200-400.
F_LAYER_KM = 300.0
EARTH_R_KM = 6371.0


class PropagationSideView(QWidget):
    """Cross-sectional propagation visualization."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(220)
        self.setAutoFillBackground(True)
        # State — set by update_state(); widget repaints on change
        self._path_km:    float = 0.0
        self._muf_mhz:    float = 0.0
        self._luf_mhz:    float = 3.0
        self._freq_mhz:   float = 0.0
        self._target:     str   = ""

    def update_state(self,
                     path_km:  float,
                     muf_mhz:  float,
                     luf_mhz:  float = 3.0,
                     freq_mhz: float = 0.0,
                     target:   str   = ""):
        """Refresh state and repaint."""
        self._path_km  = max(0.0, float(path_km))
        self._muf_mhz  = max(0.0, float(muf_mhz))
        self._luf_mhz  = max(0.0, float(luf_mhz))
        self._freq_mhz = max(0.0, float(freq_mhz))
        self._target   = target or ""
        self.update()

    # ── Geometry helpers ──────────────────────────────────────────────────

    def _propagation_mode(self) -> str:
        """Decide what propagation mode dominates given path + frequency.
        Returns: 'groundwave', 'nvis', 'skywave', 'beyond' (no useful path).
        """
        if self._freq_mhz <= 0 or self._muf_mhz <= 0:
            return ""
        f = self._freq_mhz
        if f > self._muf_mhz:
            return "beyond"    # above MUF → no F2 reflection, signal lost
        if f < self._luf_mhz:
            return "absorbed"  # below LUF → D-layer absorbs
        if self._path_km < 400:
            # NVIS regime: low freq + short path = near-vertical bounce
            if f < 10:
                return "nvis"
            return "groundwave"
        return "skywave"

    # ── Painting ──────────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Background: sky → space gradient
        sky = QLinearGradient(0, 0, 0, H)
        sky.setColorAt(0.0, QColor("#020410"))    # space
        sky.setColorAt(0.5, QColor("#0a1830"))    # high atmosphere
        sky.setColorAt(0.9, QColor("#1a3050"))    # troposphere
        p.fillRect(self.rect(), QBrush(sky))

        # If no path set, show "set a target" prompt
        if self._path_km <= 0:
            p.setPen(QColor("#888888"))
            p.setFont(QFont("", 10))
            p.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter,
                "Enter a Path-to target above to visualize propagation\n"
                "(grid square, callsign, ZIP, or city)")
            return

        # Reserve top 5% for labels, bottom 18% for the ground curve
        top    = int(H * 0.05)
        ground = int(H * 0.82)

        # The plot maps:
        #   x = distance along the great circle (0 → path_km)
        #   y = altitude above ground (0 → some max above F-layer)
        # We exaggerate vertical scale heavily — real ionosphere is
        # ~300 km high vs 3000 km path, almost flat. Educational view
        # needs the bounce to be visible, so we plot in normalized units.
        path = max(self._path_km, 1.0)
        # Margin so labels don't crowd the edges
        x0   = 60
        x1   = W - 20
        plot_w = max(50, x1 - x0)

        # Curved Earth: parabolic approximation of the surface dropping
        # toward the horizon between the two stations.
        # Earth bulge sagitta over distance d: s ≈ d² / (8R)
        # Then scaled into the available vertical range.
        sagitta = (path ** 2) / (8 * EARTH_R_KM)
        # Scale so a typical HF path's bulge fits in ~10% of the plot
        bulge_px = min(H * 0.10, sagitta / 50.0 * H * 0.10)

        # ── Draw Earth surface with terrain undulation ────────────────
        # Generate a deterministic "representative" elevation profile
        # along the great circle. We don't have real terrain data so we
        # use a small sum-of-sines based on the path distance, seeded by
        # int(path) so the same path gives the same mountains. The result
        # *suggests* mountains without claiming to be DEM-accurate.
        import math
        terrain_pts = []
        n_samples = 60
        max_terrain_px = max(8, int(H * 0.06))   # max peak height
        seed = int(path) % 997
        for i in range(n_samples + 1):
            t = i / n_samples
            # Three offset sines for variety; phase-shifted by seed
            elev = (
                0.55 * math.sin(t * 7.3 + seed * 0.13) +
                0.30 * math.sin(t * 19.1 + seed * 0.27) +
                0.15 * math.sin(t * 41.7 + seed * 0.41))
            # Force endpoints to baseline so they meet TX/RX masts cleanly
            taper = min(1.0, 4 * t * (1 - t))
            elev *= taper
            terrain_pts.append(elev)

        # Build ground polygon: combine earth-bulge curve + terrain bumps
        ground_path = QPainterPath()
        ground_path.moveTo(x0, ground)
        for i in range(n_samples + 1):
            t = i / n_samples
            px = x0 + t * plot_w
            bulge = bulge_px * 4 * t * (1 - t)   # max at midpoint
            terrain = terrain_pts[i] * max_terrain_px
            py = ground + bulge - terrain
            ground_path.lineTo(px, py)
        ground_path.lineTo(x1, H)
        ground_path.lineTo(x0, H)
        ground_path.closeSubpath()

        ground_grad = QLinearGradient(0, ground - max_terrain_px, 0, H)
        ground_grad.setColorAt(0.0, QColor("#4a6038"))
        ground_grad.setColorAt(0.3, QColor("#3a5028"))
        ground_grad.setColorAt(1.0, QColor("#1a2810"))
        p.fillPath(ground_path, QBrush(ground_grad))

        # Surface outline (mountains visible against sky)
        p.setPen(QPen(QColor("#5a7038"), 2))
        surface = QPainterPath()
        surface.moveTo(x0, ground)
        for i in range(n_samples + 1):
            t = i / n_samples
            px = x0 + t * plot_w
            bulge = bulge_px * 4 * t * (1 - t)
            terrain = terrain_pts[i] * max_terrain_px
            surface.lineTo(px, ground + bulge - terrain)
        p.drawPath(surface)

        # ── Ionosphere F-layer band ───────────────────────────────────
        # Drawn at fixed altitude above the curved ground
        f_top    = top + int((ground - top) * 0.15)
        f_bot    = top + int((ground - top) * 0.35)
        iono_grad = QLinearGradient(0, f_top, 0, f_bot)
        iono_grad.setColorAt(0.0, QColor(120,  80, 200, 30))
        iono_grad.setColorAt(0.5, QColor(150, 100, 220, 70))
        iono_grad.setColorAt(1.0, QColor(120,  80, 200, 30))
        p.fillRect(QRectF(x0, f_top, plot_w, f_bot - f_top),
                   QBrush(iono_grad))
        p.setPen(QPen(QColor(170, 120, 230, 120), 1, Qt.PenStyle.DashLine))
        p.drawLine(x0, (f_top + f_bot) // 2,
                   x1, (f_top + f_bot) // 2)

        # F-layer label
        p.setPen(QColor("#b48eea"))
        p.setFont(QFont("", 8))
        p.drawText(
            x0 + 4, f_top - 2,
            f"F-layer  ~{F_LAYER_KM:.0f} km")

        # ── TX / RX station markers ───────────────────────────────────
        tx_x = x0
        rx_x = x1
        tx_y = ground
        rx_y = ground
        # Antenna mast (visual cue)
        p.setPen(QPen(QColor("#3fbe6f"), 2))
        p.drawLine(tx_x, tx_y - 18, tx_x, tx_y)
        p.drawLine(rx_x, rx_y - 18, rx_x, rx_y)
        # Whip top markers
        p.setBrush(QBrush(QColor("#3fbe6f")))
        p.drawEllipse(QPointF(tx_x, tx_y - 18), 3, 3)
        p.drawEllipse(QPointF(rx_x, rx_y - 18), 3, 3)
        p.setPen(QColor("#3fbe6f"))
        p.setFont(QFont("", 8))
        p.drawText(tx_x - 6, tx_y - 22, "TX")
        p.drawText(rx_x - 6, rx_y - 22, "RX")

        # ── Draw the propagation path(s) ──────────────────────────────
        mode = self._propagation_mode()
        msg  = ""

        if mode == "groundwave":
            # Hugs the surface (use the same curve as ground but offset
            # slightly up so it's visible)
            p.setPen(QPen(QColor("#ffcc00"), 2))
            gw = QPainterPath()
            gw.moveTo(tx_x, tx_y - 18)
            gw.quadTo(
                (tx_x + rx_x) / 2,
                ground + bulge_px - 8,
                rx_x, rx_y - 18)
            p.drawPath(gw)
            msg = "Groundwave — short-path, surface-following"

        elif mode == "nvis":
            # Near-vertical incidence skywave: almost straight up, off the
            # F-layer, almost straight down. Drawn as a steep V.
            p.setPen(QPen(QColor("#66ddff"), 2))
            mid_x = (tx_x + rx_x) / 2
            apex_y = (f_top + f_bot) / 2
            nv = QPainterPath()
            nv.moveTo(tx_x, tx_y - 18)
            nv.lineTo(mid_x, apex_y)
            nv.lineTo(rx_x, rx_y - 18)
            p.drawPath(nv)
            msg = "NVIS — near-vertical bounce, short-path HF"

        elif mode == "skywave":
            # One- or two-hop skywave. For paths > 4000 km, draw 2 hops.
            hops = 2 if path > 4000 else 1
            p.setPen(QPen(QColor("#66ddff"), 2))
            sw = QPainterPath()
            sw.moveTo(tx_x, tx_y - 18)
            for hop in range(hops):
                # x of this hop's apex
                seg_start = tx_x + (rx_x - tx_x) * hop / hops
                seg_end   = tx_x + (rx_x - tx_x) * (hop + 1) / hops
                apex_x    = (seg_start + seg_end) / 2
                apex_y    = (f_top + f_bot) / 2
                sw.quadTo(
                    apex_x, apex_y - 30,
                    seg_end, rx_y - 18 if hop == hops - 1 else ground - 4)
            p.drawPath(sw)
            hop_str = "1-hop" if hops == 1 else f"{hops}-hop"
            msg = f"Skywave — {hop_str} F-layer refraction"

        elif mode == "beyond":
            # Above MUF: signal punches through ionosphere, no return
            p.setPen(QPen(QColor("#ff5555"), 2, Qt.PenStyle.DashLine))
            esc = QPainterPath()
            esc.moveTo(tx_x, tx_y - 18)
            esc.quadTo(
                (tx_x + rx_x) / 2 - 60, top + 10,
                (tx_x + rx_x) / 2, top + 5)
            p.drawPath(esc)
            p.setPen(QColor("#ff7777"))
            p.drawText(
                int((tx_x + rx_x) / 2 + 8), top + 12,
                "→ space")
            msg = (f"Above MUF ({self._muf_mhz:.1f} MHz) — "
                   "signal escapes ionosphere")

        elif mode == "absorbed":
            # Below LUF: D-layer absorbs (especially daytime)
            p.setPen(QPen(QColor("#aa4422"), 2, Qt.PenStyle.DotLine))
            ab = QPainterPath()
            ab.moveTo(tx_x, tx_y - 18)
            ab.quadTo(
                (tx_x + rx_x) / 4, ground - 25,
                (tx_x + rx_x) / 3, ground - 5)
            p.drawPath(ab)
            msg = (f"Below LUF ({self._luf_mhz:.1f} MHz) — "
                   "D-layer absorption")

        else:
            msg = ("Set an operating frequency in Rig tab "
                   "to see propagation mode")

        # ── Top-banner labels (two lines) ─────────────────────────────
        p.setPen(QColor("#cccccc"))
        p.setFont(QFont("", 9))
        title = (f"{self._target or 'Path'}  •  "
                 f"{self._path_km:,.0f} km")
        if self._freq_mhz > 0:
            title += f"  •  TX {self._freq_mhz:.3f} MHz"
        p.drawText(x0, top + 12, title)

        # Second line: propagation envelope (LUF / FOT / MUF). FOT
        # (Frequency of Optimum Transmission) is the practical sweet
        # spot — conventionally 0.85 × MUF for daytime F2 paths.
        if self._muf_mhz > 0:
            fot = 0.85 * self._muf_mhz
            envelope = (
                f"LUF {self._luf_mhz:.1f}  •  "
                f"FOT {fot:.1f}  •  "
                f"MUF {self._muf_mhz:.1f} MHz")
            p.setPen(QColor("#9fb8d4"))
            p.drawText(x0, top + 26, envelope)

        # ── Mode message at the bottom ────────────────────────────────
        if msg:
            color = {
                "groundwave": "#ffcc00",
                "nvis":       "#66ddff",
                "skywave":    "#66ddff",
                "beyond":     "#ff7777",
                "absorbed":   "#dd9966",
            }.get(mode, "#999999")
            p.setPen(QColor(color))
            p.setFont(QFont("", 9, QFont.Weight.Bold))
            p.drawText(x0, H - 6, msg)
