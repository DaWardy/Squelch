# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
#
# This program is free software: you can redistribute it
# and/or modify it under the terms of the GNU General
# Public License as published by the Free Software
# Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General
# Public License along with this program. If not, see
# <https://www.gnu.org/licenses/>.

"""
Squelch -- ui/widgets/spectrum_widget.py
Mini spectrum analyzer + waterfall for the Rig tab.
Driven by IC-7100 audio (primary) or SoapySDR (if available).
Band plan segments overlaid with color coding and hover tooltips.
"""

import logging
import threading
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QSlider, QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

log = logging.getLogger(__name__)

try:
    import pyqtgraph as pg
    from pyqtgraph import mkBrush, mkPen
    HAS_PG = True
    pg.setConfigOptions(antialias=False, useOpenGL=False)
except ImportError:
    HAS_PG = False
    log.warning("pyqtgraph not installed — spectrum widget unavailable")

try:
    import sounddevice as sd
    HAS_SD = True
except ImportError:
    HAS_SD = False

from core.band_plan import segments_in_range, band_at_freq, SEG_COLORS, SegType

# FFT config
FFT_SIZE    = 2048
SAMPLE_RATE = 48000       # IC-7100 USB audio
WATERFALL_ROWS = 80       # number of history rows

# Palette: jet-style waterfall colors
_JET = np.zeros((256, 3), dtype=np.uint8)
for i in range(256):
    t = i / 255.0
    if t < 0.25:
        _JET[i] = [0, int(t*4*255), 255]
    elif t < 0.5:
        _JET[i] = [0, 255, int((1-(t-0.25)*4)*255)]
    elif t < 0.75:
        _JET[i] = [int((t-0.5)*4*255), 255, 0]
    else:
        _JET[i] = [255, int((1-(t-0.75)*4)*255), 0]


def _make_colormap():
    if not HAS_PG:
        return None
    pos   = np.linspace(0, 1, 256)
    color = np.column_stack([_JET, np.full(256, 255, dtype=np.uint8)])
    return pg.ColorMap(pos, color)



class FreqAxisItem(pg.AxisItem):
    """
    Custom X axis that displays frequency in readable format.
    Shows MHz absolute or kHz offset from center.
    """
    def __init__(self, center_hz=14_074_000,
                 show_absolute=True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._center_hz    = center_hz
        self._show_absolute = show_absolute
        self.setStyle(tickFont=_small_font())

    def set_center(self, hz: int):
        self._center_hz = hz

    def toggle_mode(self):
        self._show_absolute = not self._show_absolute

    def tickStrings(self, values, scale, spacing):
        """Format tick labels as MHz or kHz offset."""
        result = []
        for v in values:
            try:
                if self._show_absolute:
                    # Show as MHz e.g. "14.074"
                    mhz = v / 1_000_000
                    if mhz >= 100:
                        result.append(f"{mhz:.1f}")
                    elif mhz >= 10:
                        result.append(f"{mhz:.3f}")
                    else:
                        result.append(f"{mhz:.4f}")
                else:
                    # Show as kHz offset from center
                    offset_khz = (v - self._center_hz) / 1_000
                    if abs(offset_khz) >= 1:
                        result.append(f"{offset_khz:+.1f}k")
                    else:
                        result.append(f"{offset_khz*1000:+.0f}Hz")
            except Exception:
                result.append("")
        return result


class DBAxisItem(pg.AxisItem):
    """
    Custom Y axis showing signal level in clean dBm steps.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyle(tickFont=_small_font())

    def tickStrings(self, values, scale, spacing):
        result = []
        for v in values:
            try:
                db = float(v)
                result.append(f"{db:.0f}")
            except Exception:
                result.append("")
        return result


class SpectrumWidget(QWidget):
    """
    Toggleable spectrum + waterfall panel.
    Attaches below the VFO controls on the Rig tab.
    Center frequency tracks the IC-7100 VFO automatically.
    Band plan segments drawn as colored regions with tooltips.
    """

    freq_clicked = pyqtSignal(int)   # user clicked a frequency on spectrum

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.cfg         = config
        self._center_hz  = 14_074_000
        self._span_hz    = 48_000        # audio bandwidth at 48k SR
        self._gain       = 1.0
        self._running    = False
        self._audio_buf  = np.zeros(FFT_SIZE)
        self._wf_data    = np.zeros((WATERFALL_ROWS, FFT_SIZE // 2))
        self._stream     = None
        self._lock       = threading.Lock()

        self._build_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(100)   # 10 fps
        self._refresh_timer.timeout.connect(self._update_plots)

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 4, 0, 0)
        root.setSpacing(2)

        # ── Toolbar ───────────────────────────────────────────────────────
        bar = QHBoxLayout()
        bar.setContentsMargins(4, 0, 4, 0)

        lbl = QLabel("Spectrum / Waterfall")
        lbl.setStyleSheet("color:#777; font-size:10px;")
        bar.addWidget(lbl)
        bar.addStretch()

        span_lbl = QLabel("Span:")
        span_lbl.setStyleSheet("color:#666; font-size:10px;")
        bar.addWidget(span_lbl)
        self._span_combo = QComboBox()
        self._span_combo.addItems(["5 kHz", "10 kHz", "25 kHz",
                                    "48 kHz", "96 kHz", "192 kHz"])
        self._span_combo.setCurrentIndex(3)
        self._span_combo.setFixedWidth(75)
        self._span_combo.setStyleSheet(
            "font-size:10px; background:#1a1a1a; color:#aaa; border:1px solid #333;")
        self._span_combo.currentIndexChanged.connect(self._on_span)
        bar.addWidget(self._span_combo)

        gain_lbl = QLabel("Gain:")
        gain_lbl.setStyleSheet("color:#666; font-size:10px;")
        bar.addWidget(gain_lbl)
        self._gain_slider = QSlider(Qt.Orientation.Horizontal)
        self._gain_slider.setRange(1, 20)
        self._gain_slider.setValue(10)
        self._gain_slider.setFixedWidth(70)
        self._gain_slider.valueChanged.connect(self._on_gain)
        bar.addWidget(self._gain_slider)

        self._axis_toggle = QPushButton("MHz")
        self._axis_toggle.setFixedSize(36, 20)
        self._axis_toggle.setToolTip(
            "Toggle between absolute MHz and kHz offset display")
        self._axis_toggle.setStyleSheet(
            "font-size:9px;border:1px solid #333;border-radius:3px;"
            "background:#1a1a1a;color:#888;")
        self._axis_toggle.clicked.connect(self._toggle_axis_mode)
        bar.addWidget(self._axis_toggle)

        self._src_lbl = QLabel("● Audio")
        self._src_lbl.setStyleSheet("color:#555; font-size:10px;")
        bar.addWidget(self._src_lbl)

        root.addLayout(bar)

        # ── Plots ─────────────────────────────────────────────────────────
        if not HAS_PG:
            placeholder = QLabel(
                "pyqtgraph not installed\n"
                "Run: pip install pyqtgraph --no-cache-dir")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("color:#555; font-size:11px;")
            root.addWidget(placeholder)
            return

        # Spectrum plot
        self._freq_axis = FreqAxisItem(orientation='bottom')
        self._db_axis   = DBAxisItem(orientation='left')
        self._spec_plot = pg.PlotWidget(
            background="#0a0a0a",
            axisItems={'bottom': self._freq_axis,
                       'left':   self._db_axis})
        self._spec_plot.setFixedHeight(90)
        self._spec_plot.showGrid(x=False, y=True, alpha=0.2)
        self._spec_plot.setMouseEnabled(x=False, y=False)
        self._spec_plot.setYRange(-130, -20, padding=0.05)
        self._spec_plot.setMenuEnabled(False)
        self._spec_plot.getAxis("bottom").setStyle(tickFont=_small_font())
        self._spec_plot.getAxis("left").setStyle(tickFont=_small_font())
        self._spec_plot.getAxis("left").setWidth(32)
        self._spec_plot.setLabel("left", "dBm", color="#555",
                                  **{"font-size": "9px"})
        self._spec_plot.setLabel("bottom", "MHz", color="#555",
                                   **{"font-size": "9px"})
        self._spec_curve = self._spec_plot.plot(
            pen=pg.mkPen("#3fbe6f", width=1))

        # VFO marker line
        self._vfo_line = pg.InfiniteLine(
            angle=90, movable=False,
            pen=pg.mkPen("#ff4444", width=1, style=Qt.PenStyle.DashLine))
        self._spec_plot.addItem(self._vfo_line)

        # BW markers
        self._bw_lo = pg.InfiniteLine(
            angle=90, movable=False,
            pen=pg.mkPen("#ffaa00", width=1, style=Qt.PenStyle.DotLine))
        self._bw_hi = pg.InfiniteLine(
            angle=90, movable=False,
            pen=pg.mkPen("#ffaa00", width=1, style=Qt.PenStyle.DotLine))
        self._spec_plot.addItem(self._bw_lo)
        self._spec_plot.addItem(self._bw_hi)

        # Waterfall image
        self._wf_widget = pg.PlotWidget(background="#0a0a0a")
        self._wf_widget.setFixedHeight(100)
        self._wf_widget.setMouseEnabled(x=False, y=False)
        self._wf_widget.setMenuEnabled(False)
        self._wf_widget.hideAxis("left")
        self._wf_freq_axis = FreqAxisItem(orientation='bottom')
        self._wf_widget.setAxisItems({'bottom': self._wf_freq_axis})
        self._wf_widget.getAxis("bottom").setStyle(tickFont=_small_font())

        self._wf_img = pg.ImageItem()
        cmap = _make_colormap()
        if cmap:
            self._wf_img.setColorMap(cmap)
        self._wf_widget.addItem(self._wf_img)

        # Band segment overlays (drawn on spec plot)
        self._seg_items = []

        # Click on spectrum → emit freq
        self._spec_plot.scene().sigMouseClicked.connect(self._on_spec_click)

        root.addWidget(self._spec_plot)
        root.addWidget(self._wf_widget)
        self._draw_band_segments()

    # ── Public API ────────────────────────────────────────────────────────

    def start(self):
        """Start audio capture and spectrum updates."""
        if not HAS_PG or not HAS_SD:
            return
        self._start_audio()
        self._refresh_timer.start()
        self._running = True

    def stop(self):
        self._running = False
        self._refresh_timer.stop()
        self._stop_audio()

    def set_center_freq(self, hz: int):
        """Called when IC-7100 VFO changes."""
        self._center_hz = hz
        self._draw_band_segments()
        self._update_axes()
        if HAS_PG:
            self._vfo_line.setValue(hz)
            self._freq_axis.set_center(hz)
            if hasattr(self, '_wf_freq_axis'):
                self._wf_freq_axis.set_center(hz)

    def set_bandwidth_hz(self, bw_hz: int):
        """Show filter bandwidth markers."""
        if not HAS_PG:
            return
        half = bw_hz / 2
        self._bw_lo.setValue(self._center_hz - half)
        self._bw_hi.setValue(self._center_hz + half)

    # ── Audio capture ─────────────────────────────────────────────────────

    def _start_audio(self):
        if not HAS_SD:
            return
        try:
            dev = self._find_rig_audio()
            self._stream = sd.InputStream(
                device=dev,
                channels=1,
                samplerate=SAMPLE_RATE,
                blocksize=FFT_SIZE,
                callback=self._audio_cb,
            )
            self._stream.start()
            dev_name = sd.query_devices(dev)["name"] if dev is not None else "default"
            self._src_lbl.setText(f"● {dev_name[:20]}")
            self._src_lbl.setStyleSheet("color:#3fbe6f; font-size:10px;")
            log.info(f"Spectrum audio: {dev_name}")
        except Exception as e:
            log.warning(f"Spectrum audio start failed: {e}")
            self._src_lbl.setText("● No audio")
            self._src_lbl.setStyleSheet("color:#cc4444; font-size:10px;")

    def _stop_audio(self):
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def _audio_cb(self, indata, frames, time_info, status):
        with self._lock:
            self._audio_buf = indata[:, 0].copy()

    @staticmethod
    def _find_rig_audio() -> Optional[int]:
        if not HAS_SD:
            return None
        devs = sd.query_devices()
        for i, d in enumerate(devs):
            name = d["name"].upper()
            if any(x in name for x in
                   ["USB AUDIO", "USB CODEC", "IC-7100", "USB2.0"]):
                if d["max_input_channels"] > 0:
                    return i
        return None

    # ── Plot updates ──────────────────────────────────────────────────────

    def _update_plots(self):
        if not HAS_PG:
            return
        with self._lock:
            buf = self._audio_buf.copy()

        # FFT
        window  = np.hanning(len(buf))
        fft_out = np.abs(np.fft.rfft(buf * window))
        fft_db  = 20 * np.log10(fft_out / FFT_SIZE + 1e-10) * self._gain

        # Frequency axis (audio-relative, centered on VFO)
        half_sr = SAMPLE_RATE / 2
        freqs   = np.linspace(
            self._center_hz - half_sr,
            self._center_hz + half_sr,
            len(fft_db))

        self._spec_curve.setData(freqs, fft_db)

        # Waterfall: roll and add new row
        self._wf_data = np.roll(self._wf_data, -1, axis=0)
        row = np.interp(
            np.linspace(0, len(fft_db)-1, FFT_SIZE//2),
            np.arange(len(fft_db)), fft_db)
        self._wf_data[-1, :] = row

        self._wf_img.setImage(
            self._wf_data.T,
            autoLevels=False,
            levels=(-80, 0))

    def _update_axes(self):
        if not HAS_PG:
            return
        half = self._span_hz / 2
        lo   = self._center_hz - half
        hi   = self._center_hz + half
        self._spec_plot.setXRange(lo, hi, padding=0)
        self._wf_widget.setXRange(lo, hi, padding=0)
        if hasattr(self, '_wf_freq_axis'):
            self._wf_freq_axis.set_center(self._center_hz)

    # ── Band segments ─────────────────────────────────────────────────────

    def _draw_band_segments(self):
        if not HAS_PG:
            return
        # Remove old overlays
        for item in self._seg_items:
            try:
                self._spec_plot.removeItem(item)
            except Exception:
                pass
        self._seg_items.clear()

        half = self._span_hz / 2
        lo   = self._center_hz - half
        hi   = self._center_hz + half
        segs = segments_in_range(int(lo), int(hi))

        for seg in segs:
            seg_lo = max(seg.freq_lo, int(lo))
            seg_hi = min(seg.freq_hi, int(hi))
            region = pg.LinearRegionItem(
                values=[seg_lo, seg_hi],
                movable=False,
                brush=pg.mkBrush(seg.color),
            )
            region.setToolTip(seg.tooltip)
            region.setZValue(-10)
            self._spec_plot.addItem(region)
            self._seg_items.append(region)

            # Label in center of segment if wide enough
            if seg_hi - seg_lo > (hi - lo) * 0.05:
                label = pg.TextItem(
                    text=seg.label,
                    color="#aaaaaa",
                    anchor=(0.5, 1.0))
                label.setFont(_small_font())
                label.setPos((seg_lo + seg_hi) / 2, -20)
                self._spec_plot.addItem(label)
                self._seg_items.append(label)

    # ── Interaction ───────────────────────────────────────────────────────

    def _on_spec_click(self, event):
        if not HAS_PG:
            return
        try:
            pos = self._spec_plot.plotItem.vb.mapSceneToView(event.scenePos())
            hz  = int(pos.x())
            if hz > 0:
                self.freq_clicked.emit(hz)
        except Exception:
            pass

    def _on_span(self, idx: int):
        spans = [5_000, 10_000, 25_000, 48_000, 96_000, 192_000]
        self._span_hz = spans[min(idx, len(spans)-1)]
        self._draw_band_segments()
        self._update_axes()

    def _on_gain(self, val: int):
        self._gain = val / 10.0

    def _toggle_axis_mode(self):
        """Toggle between absolute MHz and kHz offset display."""
        if not HAS_PG:
            return
        self._freq_axis.toggle_mode()
        if hasattr(self, '_wf_freq_axis'):
            self._wf_freq_axis.toggle_mode()
        # Update button label
        mode = "±kHz" if not self._freq_axis._show_absolute else "MHz"
        self._axis_toggle.setText(mode)
        # Force redraw
        self._update_axes()


# ── Helpers ───────────────────────────────────────────────────────────────

def _small_font():
    from PyQt6.QtGui import QFont
    f = QFont("Segoe UI")
    f.setPointSize(8)  # explicit, never -1
    return f


# Optional type hint only
try:
    from typing import Optional
except ImportError:
    pass
