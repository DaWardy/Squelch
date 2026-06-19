from __future__ import annotations
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
        # Propagation zone overlay toggles
        self._show_gw_zone:   bool = True
        self._show_nvis_zone: bool = True
        self._show_sw_zone:   bool = True

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

    def set_show_zones(self, gw: bool, nvis: bool, sw: bool) -> None:
        """Toggle propagation-zone overlays and repaint."""
        self._show_gw_zone   = gw
        self._show_nvis_zone = nvis
        self._show_sw_zone   = sw
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

    def _draw_background(self, p: "QPainter", H: int) -> bool:
        """Fill sky gradient; return False if no path is set (caller should return)."""
        sky = QLinearGradient(0, 0, 0, H)
        sky.setColorAt(0.0, QColor("#020410"))
        sky.setColorAt(0.5, QColor("#0a1830"))
        sky.setColorAt(0.9, QColor("#1a3050"))
        p.fillRect(self.rect(), QBrush(sky))
        if self._path_km <= 0:
            p.setPen(QColor("#888888"))
            p.setFont(QFont("", 10))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "Enter a Path-to target above to visualize propagation\n"
                       "(grid square, callsign, ZIP, or city)")
            return False
        return True

    def _build_terrain_sampler(self, n_samples: int,
                               max_terrain_px: int) -> "tuple[list, object]":
        """Return (terrain_pts, _terrain_px_fn) for n_samples+1 points."""
        terrain_pts: "list[float]" = []
        if self._terrain_elev and len(self._terrain_elev) >= n_samples:
            elev      = self._terrain_elev[:n_samples + 1]
            elev_min  = min(elev)
            elev_range = max(max(elev) - elev_min, 1.0)
            terrain_pts.extend(elev)

            def _terrain_px(i: int) -> float:
                t = i / n_samples
                taper = min(1.0, 6 * t * (1 - t))
                return (terrain_pts[i] - elev_min) / elev_range * max_terrain_px * taper
        else:
            seed = int(self._path_km) % 997
            for i in range(n_samples + 1):
                t = i / n_samples
                e = (0.55 * math.sin(t * 7.3  + seed * 0.13) +
                     0.30 * math.sin(t * 19.1 + seed * 0.27) +
                     0.15 * math.sin(t * 41.7 + seed * 0.41))
                terrain_pts.append(e * min(1.0, 4 * t * (1 - t)))

            def _terrain_px(i: int) -> float:
                return terrain_pts[i] * max_terrain_px

        return terrain_pts, _terrain_px

    def _draw_terrain(self, p: "QPainter", ground: int, x0: int, x1: int,
                      plot_w: int, H: int, bulge_px: float):
        """Draw the curved Earth surface with terrain relief."""
        n_samples = 60
        max_terrain_px = max(8, int(H * 0.10))
        _, _terrain_px = self._build_terrain_sampler(n_samples, max_terrain_px)

        ground_path = QPainterPath()
        ground_path.moveTo(x0, ground)
        for i in range(n_samples + 1):
            t = i / n_samples
            ground_path.lineTo(x0 + t * plot_w,
                               ground + bulge_px * 4 * t * (1 - t) - _terrain_px(i))
        ground_path.lineTo(x1, H)
        ground_path.lineTo(x0, H)
        ground_path.closeSubpath()

        gg = QLinearGradient(0, ground - max_terrain_px, 0, H)
        gg.setColorAt(0.0, QColor("#4a6038"))
        gg.setColorAt(0.3, QColor("#3a5028"))
        gg.setColorAt(1.0, QColor("#1a2810"))
        p.fillPath(ground_path, QBrush(gg))

        p.setPen(QPen(QColor("#5a7038"), 2))
        surface = QPainterPath()
        surface.moveTo(x0, ground)
        for i in range(n_samples + 1):
            t = i / n_samples
            surface.lineTo(x0 + t * plot_w,
                           ground + bulge_px * 4 * t * (1 - t) - _terrain_px(i))
        p.drawPath(surface)

    @staticmethod
    def _extra_path_loss_db(mode: str, path_km: float, freq_mhz: float) -> float:
        """Extra loss beyond FSPL: ionospheric absorption + ground reflections.

        Uses a simplified ITU/CCIR model (educational approximation, not VOACAP):
        - Skywave:    ~10 dB/hop ionospheric absorption + ~8 dB/ground reflection
        - NVIS:       single-hop; D-layer absorption rises sharply below 10 MHz
        - Groundwave: surface attenuation increases with path length and frequency
        - Beyond/Absorbed: signal effectively lost
        """
        if mode == "skywave":
            hops = 2 if path_km > 4000 else 1
            return 10 * hops + 8 * (hops - 1)   # absorption + ground reflections
        if mode == "nvis":
            # D-layer is worst at low frequencies; 20 dB at 2 MHz → 0 dB at 10 MHz
            d_layer = max(0.0, 20.0 * (1.0 - min(freq_mhz, 10.0) / 10.0))
            return 10.0 + d_layer
        if mode == "groundwave":
            # Surface wave decays faster than free space; rough freq-scaled model
            freq_factor = max(0.5, math.log10(max(freq_mhz, 0.1)) + 1.0)
            return 0.5 * path_km * freq_factor / 10.0
        if mode in ("beyond", "absorbed"):
            return 60.0
        return 0.0

    def _draw_propagation_zones(self, p: "QPainter",
                                x0: int, x1: int, ground: int,
                                f_top: int, plot_w: int) -> None:
        """Draw semi-transparent groundwave / NVIS / skywave zone overlays.

        These are educational shading bands showing WHERE each propagation
        mode can reach, independent of which mode currently dominates.
        """
        if not (self._show_gw_zone or self._show_nvis_zone or self._show_sw_zone):
            return
        path = self._path_km
        if path <= 0:
            return
        freq = self._freq_mhz
        muf  = self._muf_mhz
        px_per_km = plot_w / path
        sky_h = ground - f_top          # pixel height of "sky" region

        p.setFont(QFont("", 7))

        # ── Groundwave zone ───────────────────────────────────────────────
        # Surface wave range: roughly 300 / freq_mhz km at HF; tapers to ~5 km at 100 MHz
        if self._show_gw_zone and freq > 0:
            gw_km = min(300.0 / max(freq, 0.1), path)
            x_gw  = int(x0 + gw_km * px_per_km)
            zone_h = max(18, int((ground - f_top) * 0.12))
            p.fillRect(x0, ground - zone_h, x_gw - x0, zone_h,
                       QBrush(QColor(255, 204, 0, 55)))
            p.setPen(QColor(255, 200, 0, 200))
            p.drawText(x0 + 3, ground - 3, f"GW ~{gw_km:.0f} km")

        # ── NVIS zone ────────────────────────────────────────────────────
        # Near-Vertical Incidence Skywave: typically 2–10 MHz, path < ~500 km
        if self._show_nvis_zone:
            nvis_km  = min(500.0, path)
            x_nv     = int(x0 + nvis_km * px_per_km)
            in_band  = freq > 0 and 2.0 <= freq <= 10.0
            alpha    = 45 if in_band else 15
            p.fillRect(x0, f_top, x_nv - x0, sky_h,
                       QBrush(QColor(68, 200, 255, alpha)))
            if x_nv - x0 > 25:
                p.setPen(QColor(68, 200, 255, 190 if in_band else 90))
                suffix = "" if in_band else " (out of band)"
                p.drawText(x0 + 3, f_top + 11, f"NVIS{suffix}")

        # ── Skywave zones — skip zone + illuminated zone ──────────────────
        if self._show_sw_zone and freq > 0 and muf > freq > 0:
            # Skip distance: 2·h·f / √(MUF²−f²), capped at 80% of path
            denom    = math.sqrt(max(muf ** 2 - freq ** 2, 0.01))
            skip_km  = min(2.0 * F_LAYER_KM * freq / denom, path * 0.8)
            x_skip   = int(x0 + skip_km * px_per_km)
            # Dead zone (skip) — deep purple tint
            if x_skip > x0 + 4:
                p.fillRect(x0, f_top, x_skip - x0, sky_h,
                           QBrush(QColor(60, 0, 90, 55)))
                p.setPen(QColor(160, 100, 220, 180))
                p.drawText(x0 + 3, f_top + 23, f"Skip ~{skip_km:.0f} km")
            # Illuminated zone — soft blue
            if x_skip < x1 - 4:
                p.fillRect(x_skip, f_top, x1 - x_skip, sky_h,
                           QBrush(QColor(51, 102, 255, 22)))

    def _draw_path_loss_bar(self, p: "QPainter", x0: int, plot_w: int,
                            top: int, H: int):
        """Draw EIRP/path-loss signal-strength bar and terrain source label."""
        if self._path_km > 0 and self._freq_mhz > 0:
            mode    = self._propagation_mode()
            eirp_dbm = self._eirp_dbw + 30          # dBW → dBm
            fspl    = (20 * math.log10(max(self._path_km, 1)) +
                       20 * math.log10(max(self._freq_mhz, 0.1)) + 92.45)
            extra   = self._extra_path_loss_db(mode, self._path_km, self._freq_mhz)
            prx_dbm = eirp_dbm - fspl - extra
            norm    = max(0.0, min(1.0, (prx_dbm + 130) / 57))
            bar_w   = int(plot_w * norm)
            if bar_w > 4:
                sig_y    = top + int((H // 3 - 20) * 0.75)
                sig_grad = QLinearGradient(x0, sig_y, x0 + bar_w, sig_y)
                sig_grad.setColorAt(0.0, QColor("#ff440044"))
                sig_grad.setColorAt(0.5, QColor("#ffaa0066"))
                sig_grad.setColorAt(1.0, QColor("#00ff8866"))
                p.fillRect(x0, sig_y, bar_w, 8, QBrush(sig_grad))
                p.setPen(QColor("#99aabb"))
                p.setFont(QFont("", 7))
                total_loss = fspl + extra
                # EIRP summary above bar, Prx label below — no horizontal collision
                p.drawText(x0 + 2, sig_y - 2,
                           f"EIRP {self._eirp_dbw:.0f} dBW  "
                           f"FSPL {fspl:.0f} dB  "
                           f"+{extra:.0f} dB  "
                           f"= {total_loss:.0f} dB loss")
                p.drawText(x0 + bar_w + 4, sig_y + 8,
                           f"Prx≈{prx_dbm:.0f} dBm")
        if self._terrain_label:
            ground = int(self.height() * 0.82)
            p.setPen(QColor("#778899"))
            p.setFont(QFont("", 7))
            p.drawText(x0 + 2, ground - 3, self._terrain_label)

    def _draw_ionosphere(self, p: "QPainter", x0: int, x1: int,
                         plot_w: int, top: int,
                         ground: int) -> "tuple[int, int]":
        """Draw F-layer band and return (f_top, f_bot)."""
        f_top = top + int((ground - top) * 0.15)
        f_bot = top + int((ground - top) * 0.35)
        ig = QLinearGradient(0, f_top, 0, f_bot)
        ig.setColorAt(0.0, QColor(120,  80, 200, 30))
        ig.setColorAt(0.5, QColor(150, 100, 220, 70))
        ig.setColorAt(1.0, QColor(120,  80, 200, 30))
        p.fillRect(QRectF(x0, f_top, plot_w, f_bot - f_top), QBrush(ig))
        p.setPen(QPen(QColor(170, 120, 230, 120), 1, Qt.PenStyle.DashLine))
        p.drawLine(x0, (f_top + f_bot) // 2, x1, (f_top + f_bot) // 2)
        p.setPen(QColor("#b48eea"))
        p.setFont(QFont("", 8))
        band_h = f_bot - f_top
        label_y = f_top + band_h // 2 + 4  # centred inside the band
        if band_h >= 12:
            p.drawText(x0 + 4, label_y, f"F-layer  ~{F_LAYER_KM:.0f} km")
        return f_top, f_bot

    def _draw_station_markers(self, p: "QPainter",
                              tx_x: int, tx_y: int,
                              rx_x: int, rx_y: int):
        """Draw TX/RX antenna mast markers."""
        p.setPen(QPen(QColor("#3fbe6f"), 2))
        p.drawLine(tx_x, tx_y - 18, tx_x, tx_y)
        p.drawLine(rx_x, rx_y - 18, rx_x, rx_y)
        p.setBrush(QBrush(QColor("#3fbe6f")))
        p.drawEllipse(QPointF(tx_x, tx_y - 18), 3, 3)
        p.drawEllipse(QPointF(rx_x, rx_y - 18), 3, 3)
        p.setPen(QColor("#3fbe6f"))
        p.setFont(QFont("", 8))
        p.drawText(tx_x - 6, tx_y - 22, "TX")
        p.drawText(rx_x - 6, rx_y - 22, "RX")

    def _draw_banner_labels(self, p: "QPainter", x0: int, top: int,
                            H: int, mode: str, msg: str):
        """Draw top info banner and bottom mode message."""
        from PyQt6.QtGui import QFont as _QFont
        _shadow = QColor(0, 0, 0, 180)

        def _shadowed_text(px, py, text, fg, font):
            p.setFont(font)
            p.setPen(_shadow)
            p.drawText(px + 1, py + 1, text)
            p.setPen(QColor(fg))
            p.drawText(px, py, text)
        _shadowed_text(x0, top + 13,
                       (f"{self._target or 'Path'}  •  "
                        f"{self._path_km:,.0f} km"
                        + (f"  •  TX {self._freq_mhz:.3f} MHz"
                           if self._freq_mhz > 0 else "")),
                       "#e0e0e0", _QFont("", 9))
        if self._muf_mhz > 0:
            fot   = round(0.85 * self._muf_mhz, 1)
            line2 = (f"LUF {self._luf_mhz:.1f} MHz  |  "
                     f"FOT {fot:.1f} MHz  |  "
                     f"MUF {self._muf_mhz:.1f} MHz")
            _shadowed_text(x0, top + 27, line2, "#c8d8eb", _QFont("", 8))
        if msg:
            color = {"groundwave": "#ffcc00", "nvis": "#66ddff",
                     "skywave": "#66ddff", "beyond": "#ff7777",
                     "absorbed": "#dd9966"}.get(mode, "#999999")
            p.setPen(QColor(color))
            p.setFont(QFont("", 9, QFont.Weight.Bold))
            p.drawText(x0, H - 6, msg)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        if not self._draw_background(p, H):
            return

        top    = int(H * 0.05)
        ground = int(H * 0.82)
        path   = max(self._path_km, 1.0)
        x0, x1 = 60, W - 20
        plot_w  = max(50, x1 - x0)

        # Earth bulge: sagitta ≈ d²/(8R), scaled to ~10% of plot height
        sagitta  = (path ** 2) / (8 * EARTH_R_KM)
        bulge_px = min(H * 0.10, sagitta / 50.0 * H * 0.10)

        self._draw_terrain(p, ground, x0, x1, plot_w, H, bulge_px)
        self._draw_path_loss_bar(p, x0, plot_w, top, H)
        f_top, f_bot = self._draw_ionosphere(p, x0, x1, plot_w, top, ground)
        self._draw_propagation_zones(p, x0, x1, ground, f_top, plot_w)
        self._draw_station_markers(p, x0, ground, x1, ground)

        mode = self._propagation_mode()
        msg  = self._draw_propagation_path(
            p, mode, x0, x1, ground, ground, ground, f_top, f_bot,
            bulge_px, path, top)

        self._draw_banner_labels(p, x0, top, H, mode, msg)
