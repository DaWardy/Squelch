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
        # Endpoint coordinates — needed for terrain lookup
        self._tx_lat:     float = 0.0
        self._tx_lon:     float = 0.0
        self._rx_lat:     float = 0.0
        self._rx_lon:     float = 0.0
        # Terrain state
        self._terrain_mode:  str              = "off"   # "off"/"online"/"offline"
        self._terrain_elev:  Optional[list[float]] = None   # metres, n+1 samples
        self._terrain_busy:  bool             = False
        self._terrain_label: str              = ""
        self._eirp_dbw:      float             = 10.0  # default 10W

    def set_terrain_mode(self, mode: str):
        """Set terrain mode: 'off', 'online', or 'offline'.
        Triggers an async elevation fetch if online/offline."""
        self._terrain_mode = mode
        self._terrain_elev = None
        self._terrain_label = ""
        if mode != "off":
            self._fetch_terrain_async()
        self.update()

    def _fetch_terrain_async(self):
        """Fetch elevation profile in a background thread."""
        if self._terrain_busy:
            return
        if (not self._tx_lat and not self._tx_lon) or self._path_km <= 0:
            return
        from PyQt6.QtCore import pyqtSignal, QObject
        import threading

        class _Worker(QObject):
            done = pyqtSignal(object, str)   # (elev_list_or_None, label)

        worker = _Worker()
        worker.done.connect(self._on_terrain_done)
        self._terrain_busy = True
        self._terrain_label = "Fetching terrain…"
        self.update()

        mode = self._terrain_mode
        lat1, lon1 = self._tx_lat, self._tx_lon
        lat2, lon2 = self._rx_lat, self._rx_lon

        def _run():
            label = ""
            try:
                from core.terrain import elevation_profile
                elev = elevation_profile(lat1, lon1, lat2, lon2,
                                         n=60, mode=mode)
                if elev:
                    src = "SRTM" if mode == "offline" else "OpenTopo/SRTM30m"
                    label = f"Terrain: {src}"
                else:
                    label = ("Offline tiles not downloaded"
                             if mode == "offline"
                             else "Terrain fetch failed")
            except Exception as e:
                elev = None
                label = f"Terrain error: {e}"
            worker.done.emit(elev, label)

        threading.Thread(target=_run, daemon=True,
                         name="TerrainFetch").start()

    def _on_terrain_done(self, elev, label: str):
        self._terrain_busy = False
        self._terrain_elev = elev
        self._terrain_label = label
        self.update()


    def set_eirp_dbw(self, dbw: float):
        self._eirp_dbw = dbw
        self.update()

    def update_state(self,
                     path_km:  float,
                     muf_mhz:  float,
                     luf_mhz:  float = 3.0,
                     freq_mhz: float = 0.0,
                     target:   str   = "",
                     tx_lat:   float = 0.0,
                     tx_lon:   float = 0.0,
                     rx_lat:   float = 0.0,
                     rx_lon:   float = 0.0):
        """Refresh state and repaint. Pass tx/rx coords to enable terrain."""
        path_changed = abs(path_km - self._path_km) > 1.0
        self._path_km  = max(0.0, float(path_km))
        self._muf_mhz  = max(0.0, float(muf_mhz))
        self._luf_mhz  = max(0.0, float(luf_mhz))
        self._freq_mhz = max(0.0, float(freq_mhz))
        self._target   = target or ""
        if tx_lat or tx_lon:
            self._tx_lat, self._tx_lon = tx_lat, tx_lon
            self._rx_lat, self._rx_lon = rx_lat, rx_lon
        # Re-fetch terrain if path changed and mode is active
        if path_changed and self._terrain_mode != "off":
            self._terrain_elev = None
            self._fetch_terrain_async()
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

    # ── Painting helpers ──────────────────────────────────────────────────

    def _draw_propagation_path(self, p, mode, tx_x, rx_x, tx_y, rx_y,
                                ground, f_top, f_bot, bulge_px, path,
                                top) -> str:
        """Draw the mode-specific signal path arc; return the status message."""
        if mode == "groundwave":
            p.setPen(QPen(QColor("#ffcc00"), 2))
            gw = QPainterPath()
            gw.moveTo(tx_x, tx_y - 18)
            gw.quadTo((tx_x + rx_x) / 2, ground + bulge_px - 8,
                      rx_x, rx_y - 18)
            p.drawPath(gw)
            return "Groundwave — short-path, surface-following"

        if mode == "nvis":
            p.setPen(QPen(QColor("#66ddff"), 2))
            mid_x  = (tx_x + rx_x) / 2
            apex_y = (f_top + f_bot) / 2
            nv = QPainterPath()
            nv.moveTo(tx_x, tx_y - 18)
            nv.lineTo(mid_x, apex_y)
            nv.lineTo(rx_x, rx_y - 18)
            p.drawPath(nv)
            return "NVIS — near-vertical bounce, short-path HF"

        if mode == "skywave":
            hops = 2 if path > 4000 else 1
            p.setPen(QPen(QColor("#66ddff"), 2))
            sw = QPainterPath()
            sw.moveTo(tx_x, tx_y - 18)
            for hop in range(hops):
                seg_start = tx_x + (rx_x - tx_x) * hop / hops
                seg_end   = tx_x + (rx_x - tx_x) * (hop + 1) / hops
                apex_x    = (seg_start + seg_end) / 2
                apex_y    = (f_top + f_bot) / 2
                sw.quadTo(apex_x, apex_y - 30,
                          seg_end,
                          rx_y - 18 if hop == hops - 1 else ground - 4)
            p.drawPath(sw)
            hop_str = "1-hop" if hops == 1 else f"{hops}-hop"
            return f"Skywave — {hop_str} F-layer refraction"

        if mode == "beyond":
            p.setPen(QPen(QColor("#ff5555"), 2, Qt.PenStyle.DashLine))
            esc = QPainterPath()
            esc.moveTo(tx_x, tx_y - 18)
            esc.quadTo((tx_x + rx_x) / 2 - 60, top + 10,
                       (tx_x + rx_x) / 2, top + 5)
            p.drawPath(esc)
            p.setPen(QColor("#ff7777"))
            p.drawText(int((tx_x + rx_x) / 2 + 8), top + 12, "→ space")
            return (f"Above MUF ({self._muf_mhz:.1f} MHz) — "
                    "signal escapes ionosphere")

        if mode == "absorbed":
            p.setPen(QPen(QColor("#aa4422"), 2, Qt.PenStyle.DotLine))
            ab = QPainterPath()
            ab.moveTo(tx_x, tx_y - 18)
            ab.quadTo((tx_x + rx_x) / 4, ground - 25,
                      (tx_x + rx_x) / 3, ground - 5)
            p.drawPath(ab)
            return (f"Below LUF ({self._luf_mhz:.1f} MHz) — "
                    "D-layer absorption")

        return "Set an operating frequency in Rig tab to see propagation mode"

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

        # ── Draw Earth surface with terrain ───────────────────────────
        import math
        terrain_pts: list[float] = []
        n_samples = 60
        max_terrain_px = max(8, int(H * 0.10))

        if self._terrain_elev and len(self._terrain_elev) >= n_samples:
            # Real SRTM elevation data — normalise to pixel scale.
            # Find the range across this path so mountains are visible.
            elev = self._terrain_elev[:n_samples + 1]
            elev_min = min(elev)
            elev_max = max(elev)
            elev_range = max(elev_max - elev_min, 1.0)
            for v in elev:
                # Taper endpoints to baseline so TX/RX masts land cleanly
                terrain_pts.append(v)
            def _terrain_px(i: int) -> float:
                t = i / n_samples
                taper = min(1.0, 6 * t * (1 - t))   # smooth at edges
                norm = (terrain_pts[i] - elev_min) / elev_range
                return norm * max_terrain_px * taper
        else:
            # No terrain data — deterministic sine noise (seed from path km)
            seed = int(self._path_km) % 997
            for i in range(n_samples + 1):
                t = i / n_samples
                elev = (0.55 * math.sin(t * 7.3 + seed * 0.13) +
                        0.30 * math.sin(t * 19.1 + seed * 0.27) +
                        0.15 * math.sin(t * 41.7 + seed * 0.41))
                taper = min(1.0, 4 * t * (1 - t))
                terrain_pts.append(elev * taper)

            def _terrain_px(i: int) -> float:
                return terrain_pts[i] * max_terrain_px

        # Build ground polygon
        ground_path = QPainterPath()
        ground_path.moveTo(x0, ground)
        for i in range(n_samples + 1):
            t = i / n_samples
            px = x0 + t * plot_w
            bulge = bulge_px * 4 * t * (1 - t)
            py = ground + bulge - _terrain_px(i)
            ground_path.lineTo(px, py)
        ground_path.lineTo(x1, H)
        ground_path.lineTo(x0, H)
        ground_path.closeSubpath()

        ground_grad = QLinearGradient(0, ground - max_terrain_px, 0, H)
        ground_grad.setColorAt(0.0, QColor("#4a6038"))
        ground_grad.setColorAt(0.3, QColor("#3a5028"))
        ground_grad.setColorAt(1.0, QColor("#1a2810"))
        p.fillPath(ground_path, QBrush(ground_grad))

        p.setPen(QPen(QColor("#5a7038"), 2))
        surface = QPainterPath()
        surface.moveTo(x0, ground)
        for i in range(n_samples + 1):
            t = i / n_samples
            px = x0 + t * plot_w
            bulge = bulge_px * 4 * t * (1 - t)
            surface.lineTo(px, ground + bulge - _terrain_px(i))
        p.drawPath(surface)


        # ── Path-loss contours ────────────────────────────────────────
        # Show approximate received-signal strength along the path
        # using free-space path loss + EIRP. Gives operators a rough
        # idea of whether their station can close the path.
        _sky_h = locals().get("sky_h", H // 3)
        if self._eirp_dbw != 0.0 and self._path_km > 0 and self._freq_mhz > 0:
            import math
            # FSPL = 20*log10(km) + 20*log10(MHz) + 92.45 (dB)
            fspl = (20 * math.log10(max(self._path_km, 1)) +
                    20 * math.log10(max(self._freq_mhz, 0.1)) + 92.45)
            prx_dbm = (self._eirp_dbw * 10) - fspl  # rough Prx in dBm-ish
            # Normalise to a position in the sky region
            # S9 ≈ -73 dBm, usable floor ≈ -130 dBm
            # Draw a "signal strength" bar across the top of the sky
            norm = max(0.0, min(1.0, (prx_dbm + 130) / 57))
            bar_w = int(plot_w * norm)
            if bar_w > 4:
                sig_y = top + int((_sky_h - 20) * 0.75)
                sig_grad = QLinearGradient(x0, sig_y, x0 + bar_w, sig_y)
                sig_grad.setColorAt(0.0, QColor("#ff440044"))
                sig_grad.setColorAt(0.5, QColor("#ffaa0066"))
                sig_grad.setColorAt(1.0, QColor("#00ff8866"))
                p.fillRect(x0, sig_y, bar_w, 8, QBrush(sig_grad))
                # Label
                p.setPen(QColor("#99aabb"))
                p.setFont(QFont("", 7))
                p.drawText(x0 + bar_w + 4, sig_y + 7,
                           f"Prx≈{prx_dbm:.0f} dBm")
                # EIRP label
                p.drawText(x0 + 2, sig_y + 7,
                           f"EIRP {self._eirp_dbw:.0f} dBW → FSPL {fspl:.0f} dB")

        # Terrain label (source + "Fetching..." status)
        if self._terrain_label:
            p.setPen(QColor("#778899"))
            p.setFont(QFont("", 7))
            p.drawText(x0 + 2, ground - 3, self._terrain_label)

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
        msg  = self._draw_propagation_path(
            p, mode, tx_x, rx_x, tx_y, rx_y, ground, f_top, f_bot,
            bulge_px, path, top)

        # ── Top-banner labels (two clear lines) ──────────────────────
        p.setPen(QColor("#cccccc"))
        p.setFont(QFont("", 9))
        line1 = (f"{self._target or 'Path'}  •  "
                 f"{self._path_km:,.0f} km")
        if self._freq_mhz > 0:
            line1 += f"  •  TX {self._freq_mhz:.3f} MHz"
        p.drawText(x0, top + 13, line1)

        # FOT = Frequency of Optimum Transmission ≈ 0.85 × MUF.
        # Render on its own clearly-spaced second line.
        if self._muf_mhz > 0:
            fot = round(0.85 * self._muf_mhz, 1)
            line2 = (f"LUF {self._luf_mhz:.1f} MHz  |  "
                     f"FOT {fot:.1f} MHz  |  "
                     f"MUF {self._muf_mhz:.1f} MHz")
            p.setPen(QColor("#9fb8d4"))
            p.setFont(QFont("", 8))
            p.drawText(x0, top + 27, line2)

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
