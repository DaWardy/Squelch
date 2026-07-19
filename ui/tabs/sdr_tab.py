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

from __future__ import annotations
from ui.panel import SquelchPanel
"""Squelch -- ui/tabs/sdr_tab.py
Full SDR tab.
Waterfall + spectrum, device selector, dynamic RX/TX controls,
IQ recorder/player, scanner, audio routing, signal routing to
Digital tab.
"""

import logging
import threading
import numpy as np
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QSplitter, QPushButton, QLabel, QComboBox,
    QGroupBox, QSlider, QSpinBox, QDoubleSpinBox,
    QFrame, QProgressBar, QCheckBox, QMessageBox,
    QSizePolicy, QScrollArea, QLineEdit, QButtonGroup,
)
from PyQt6.QtCore import Qt, QTimer, QRectF, pyqtSlot
from PyQt6.QtGui import QWheelEvent, QFont

from ui.widgets.launch_bar import LaunchBar
from network.signal_id import get_identifier
from sdr.soapy_device import (
    SoapyManager, SDRDevice, get_sdr_manager, HAS_SOAPY)
from sdr.iq_recorder import IQRecorder, IQPlayer
from core.band_plan import band_at_freq, BAND_EDGES
from core.constants import BAND_EDGES_R2 as BAND_EDGES, FFT_SIZE
from core.themes import get_theme as _sdr_get_theme

log = logging.getLogger(__name__)

try:
    import pyqtgraph as pg
    HAS_PG = True
    pg.setConfigOptions(antialias=False, useOpenGL=False)
except ImportError:
    HAS_PG = False

try:
    from sdr.rtltcp_device import RTLTCPDevice, rtltcp_is_running
    HAS_RTLTCP = True
except ImportError:
    HAS_RTLTCP = False
    def rtltcp_is_running(*a, **kw): return False
    RTLTCPDevice = None

try:
    import sdr.audio_iq_source  # noqa: F401  (probe: rig-audio input support)
    HAS_AUDIO_SRC = True
except ImportError:
    HAS_AUDIO_SRC = False

# Step sizes for SDR frequency tuning (Hz)
SDR_STEP_SIZES = [
    100, 1_000, 5_000, 10_000, 12_500,
    25_000, 100_000, 500_000, 1_000_000
]
SDR_STEP_LABELS = [
    "100Hz", "1kHz", "5kHz", "10kHz", "12.5kHz",
    "25kHz", "100kHz", "500kHz", "1MHz"
]

# Waterfall palettes
PALETTES = {
    "Jet":      [(0,0,255),(0,255,255),(0,255,0),
                 (255,255,0),(255,0,0)],
    "Viridis":  [(68,1,84),(58,82,139),(32,144,140),
                 (94,201,97),(253,231,37)],
    "Hot":      [(0,0,0),(128,0,0),(255,128,0),
                 (255,255,0),(255,255,255)],
    "Grays":    [(0,0,0),(64,64,64),(128,128,128),
                 (192,192,192),(255,255,255)],
    "Night":    [(0,0,0),(0,32,0),(0,128,0),
                 (0,255,0),(128,255,128)],
}

FFT_SIZE     = 2048
WF_ROWS      = 100
AUDIO_SR     = 48_000


def _make_colormap(palette_name: str):
    if not HAS_PG:
        return None
    colors = PALETTES.get(palette_name, PALETTES["Jet"])
    n      = len(colors)
    pos    = np.linspace(0, 1, n)
    rgba   = np.array(
        [(*c, 255) for c in colors], dtype=np.uint8)
    return pg.ColorMap(pos, rgba)


def _fmt_bw(hz: int) -> str:
    """Human bandwidth label the editable BW combo + _bw_hz round-trip,
    e.g. 137400 → '137.4 kHz', 2700 → '2.7 kHz', 500 → '500 Hz'."""
    if hz >= 1_000_000:
        return f"{hz / 1_000_000:g} MHz"
    if hz >= 1_000:
        return f"{hz / 1_000:g} kHz"
    return f"{int(hz)} Hz"


class _PaletteLegend(QWidget):
    """Vertical colour key for the waterfall, shown on its right-hand side.

    Shows the active palette as a top-to-bottom gradient (strong → weak) with
    the current ceiling/floor dB values labelled, so the colours on the
    waterfall have a legible meaning — the way other SDR programs do.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(52)
        self.setToolTip("Waterfall colour key — top = strong, bottom = weak")
        self._colors = PALETTES["Jet"]
        self._lo_db  = -100.0
        self._hi_db  = -20.0

    def set_palette(self, name: str) -> None:
        self._colors = PALETTES.get(name, PALETTES["Jet"])
        self.update()

    def set_range(self, lo_db: float, hi_db: float) -> None:
        self._lo_db, self._hi_db = float(lo_db), float(hi_db)
        self.update()

    def paintEvent(self, _ev):
        from PyQt6.QtGui import QPainter, QLinearGradient, QColor, QPen
        p = QPainter(self)
        try:
            w, h  = self.width(), self.height()
            bar_w = 14
            top, bot = 8, h - 8            # leave room for end labels
            grad  = QLinearGradient(0, top, 0, bot)   # vertical
            n = len(self._colors)
            for i, c in enumerate(self._colors):
                # invert so the strongest colour is at the top
                pos = 1.0 - (i / (n - 1) if n > 1 else 0.0)
                grad.setColorAt(pos, QColor(*c))
            p.fillRect(2, top, bar_w, max(1, bot - top), grad)
            f = p.font()
            f.setPointSize(7)
            p.setFont(f)
            p.setPen(QPen(QColor("#bbbbbb")))
            x = bar_w + 5
            mid = (self._hi_db + self._lo_db) / 2.0
            p.drawText(x, top + 4, f"{self._hi_db:.0f}")
            p.drawText(x, (top + bot) // 2 + 3, f"{mid:.0f}")
            p.drawText(x, bot, f"{self._lo_db:.0f}")
            # unit, rotated up the right edge
            p.save()
            p.translate(w - 2, (top + bot) // 2)
            p.rotate(-90)
            p.setPen(QPen(QColor("#888888")))
            adv = p.fontMetrics().horizontalAdvance("dB")
            p.drawText(-adv // 2, 0, "dB")
            p.restore()
        finally:
            p.end()



from ui.tabs.sdr_setup_guide  import _SDRSetupGuideMixin
from ui.tabs.sdr_device_panels import _SDRDevicePanelsMixin
from ui.tabs.sdr_recording import _SDRRecordingMixin, _safe_recordings_path
from ui.tabs.sdr_scanner import _SDRScannerMixin
from ui.tabs.sdr_signal_id import _SDRSignalIDMixin
from ui.tabs.sdr_profile import _SDRProfileMixin
from ui.tabs.sdr_audio_source import _SDRAudioSourceMixin
from ui.tabs.sdr_controls import _SDRControlsMixin
from ui.tabs.sdr_toolbar import _SDRToolbarMixin
from ui.tabs.sdr_device_connect import _SDRDeviceConnectMixin
from ui.tabs.sdr_bottom_bar import _SDRBottomBarMixin
from ui.tabs.sdr_survey import _SDRSurveyMixin


class SDRTab(SquelchPanel, _SDRSetupGuideMixin, _SDRDevicePanelsMixin,
             _SDRRecordingMixin, _SDRScannerMixin, _SDRSignalIDMixin,
             _SDRProfileMixin, _SDRAudioSourceMixin, _SDRControlsMixin,
             _SDRToolbarMixin, _SDRDeviceConnectMixin, _SDRBottomBarMixin,
             _SDRSurveyMixin, QWidget):
    panel_id    = "sdr"
    panel_title = "SDR"

    def __init__(self, config, rig=None, parent=None):
        super().__init__(parent)
        self._init_state(config, rig)
        self._build()
        self._manager.on_samples(self._on_samples)
        self._ui_timer = QTimer(self)
        self._ui_timer.setInterval(100)
        self._ui_timer.timeout.connect(self._update_plots)
        self._ui_timer.start()
        QTimer.singleShot(500, self._enumerate_devices)

    def _init_state(self, config, rig) -> None:
        """Initialise all instance variables before UI is built."""
        self.cfg      = config
        self.rig      = rig
        self._manager = get_sdr_manager()
        try:
            from core.location import LocationManager
            self.location_mgr = LocationManager(config)
        except Exception:
            self.location_mgr = None
        self._recorder   = IQRecorder(
            Path(config.get("paths.iq_recordings", "recordings")))
        self._player     = IQPlayer()
        self._devices:   list[SDRDevice] = []
        self._current:   SDRDevice = None
        # Lazily-initialized RTL-TCP client — used when SoapySDR finds no
        # devices but rtl_tcp is already running (dongle claimed by server).
        self._rtltcp_dev = None
        # Spectrum state
        self._center_hz  = 100_000_000
        self._sample_rate = 2_400_000
        self._span_hz    = 2_400_000
        self._step_idx   = 4
        self._floor_db   = -100.0
        self._ceiling_db = -20.0
        self._auto_range = True
        self._palette    = "Jet"
        self._peak_hold  = False
        self._scroll_vert_bw = False   # wheel ↕ pans freq; True → adjusts IF BW
        self._y_ref_db   = 0.0   # reference level offset: 0 = dBFS, non-zero = approx dBm
        self._wf_data    = np.full((WF_ROWS, FFT_SIZE // 2), -100.0)
        self._peak_data  = np.full(FFT_SIZE, -100.0)
        self._fft_lock   = threading.Lock()
        self._latest_fft: np.ndarray = None
        # Scanner
        self._scan_running = False
        self._scan_timer   = QTimer(self)
        self._scan_timer.timeout.connect(self._scan_step)
        # Signal routing
        self._route_to_digital = False
        self._decoder_cb       = None
        # Squelch
        self._squelch_enabled = False
        self._squelch_db      = -60.0
        self._squelch_open    = True   # runtime; True when squelch not active or signal above threshold
        # Noise reduction
        self._nr_enabled      = False
        self._nr_level        = 30    # 0-100 %
        # Noise blanker (time-domain impulse removal on IQ)
        self._nb_enabled      = False
        self._nb_strength     = 0.5   # 0.0-1.0
        # IF passband indicator + waterfall colour legend (built with the
        # spectrum/waterfall plots, updated in _update_axes)
        self._passband = None
        self._legend   = None
        # Live wideband survey (ROADMAP §4.5 I-1) — see _SDRSurveyMixin.
        # Engine built lazily on first enable; the pump runs (throttled) from
        # the plot timer so the RX thread stays pristine.
        self._survey         = None
        self._survey_enabled = False
        self._survey_tick_n  = 0
        self._alert_monitor  = None    # core.survey_alert.AlertMonitor (lazy)
        self._survey_alerts  = []      # recent Alert ring (view reads this)
        self._signal_history = None    # core.signal_history.SignalHistory (lazy)
        self._sim_source     = None    # sdr.sim_source.SimSource (no-hardware demo)
        self._audio_rec      = None    # core.audio_record.AudioRecorder (demod→WAV)

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build(self):
        # Create the layout ONCE up front. The except handler reuses it
        # instead of calling QVBoxLayout(self) again (which fails silently
        # when self already has a layout — that caused the blank SDR tab).
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        try:

            if not HAS_SOAPY:
                # Check if RTL-TCP is running as a fallback
                if rtltcp_is_running():
                    self._rtltcp_mode = True
                    self._build_rtltcp(outer)
                else:
                    self._rtltcp_mode = False
                    self._build_no_soapy(outer)
                return
            if not HAS_PG:
                self._build_no_pyqtgraph(outer)
                return

            self._build_full(outer)

        except Exception as e:
            log.error(f"SDR tab build failed: {e}")
            import traceback
            traceback.print_exc()
            # Always show something — never blank. Reuse 'outer'.
            # Clear any partial widgets first.
            while outer.count():
                item = outer.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.deleteLater()
            lay = outer
            lay.setContentsMargins(40, 40, 40, 40)
            title = QLabel("SDR Tab — Load Error")
            title.setStyleSheet(
                "color:#cc4444;font-weight:bold;")
            lay.addWidget(title)
            err_lbl = QLabel(
                f"The SDR tab failed to load:\n\n{e}\n\n"
                "This is usually caused by a missing dependency.\n"
                "Check logs/squelch.log for details.")
            err_lbl.setWordWrap(True)
            err_lbl.setStyleSheet("")
            lay.addWidget(err_lbl)
            lay.addStretch()








    def _build_full(self, layout):
        """Full SDR UI with waterfall."""

        # ── Launch bar ───────────────────────────────────────────────────
        self._launch_bar = LaunchBar("sdr", self.cfg)
        layout.addWidget(self._launch_bar)

        # ── Top toolbar ───────────────────────────────────────────────────
        toolbar = self._build_toolbar()
        layout.addWidget(toolbar)

        # ── Main splitter: waterfall | controls | [sigid panel] ──────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(
            "QSplitter::handle{background:#1a1a1a;width:3px;}")
        self._main_splitter = splitter  # used by _ensure_sigid_panel

        # Waterfall area
        wf_widget = self._build_waterfall()
        splitter.addWidget(wf_widget)

        # Right control panel
        ctrl_panel = self._build_controls()
        ctrl_panel.setMaximumWidth(300)
        splitter.addWidget(ctrl_panel)

        splitter.setSizes([900, 280])
        layout.addWidget(splitter, 1)

        # ── Bottom: IQ recorder / scanner ────────────────────────────────
        bottom = self._build_bottom_bar()
        layout.addWidget(bottom)

    def _build_waterfall(self) -> QWidget:
        from PyQt6.QtWidgets import QSplitter
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self._build_spectrum_plot()
        self._build_waterfall_plot()
        self._seg_items = []
        wf_splitter = QSplitter(Qt.Orientation.Vertical)
        wf_splitter.setStyleSheet(
            "QSplitter::handle{background:#2a2a2a;height:4px;"
            "border-top:1px solid #333;}")
        spec_container = QWidget()
        sc_lay = QVBoxLayout(spec_container)
        sc_lay.setContentsMargins(0, 0, 0, 0)
        sc_lay.addWidget(self._spec_plot)
        wf_container = QWidget()
        wc_lay = QHBoxLayout(wf_container)   # waterfall | [Auto + colour key]
        wc_lay.setContentsMargins(0, 0, 0, 0)
        wc_lay.setSpacing(2)
        wc_lay.addWidget(self._wf_plot, 1)
        key_col = QVBoxLayout()
        key_col.setContentsMargins(0, 0, 0, 0)
        key_col.setSpacing(2)
        self._wf_auto_btn = QPushButton("Auto")
        self._wf_auto_btn.setFixedWidth(52)
        self._wf_auto_btn.setFixedHeight(20)
        self._wf_auto_btn.setToolTip(
            "Auto-scale the waterfall colour range (floor/ceiling) to the signal")
        self._wf_auto_btn.clicked.connect(self._auto_range_set)
        key_col.addWidget(self._wf_auto_btn, 0)
        self._legend = _PaletteLegend()
        self._legend.set_palette(self._palette_combo.currentText()
                                 if hasattr(self, "_palette_combo") else "Jet")
        self._legend.set_range(self._floor_db, self._ceiling_db)
        key_col.addWidget(self._legend, 1)
        wc_lay.addLayout(key_col, 0)
        wf_splitter.addWidget(spec_container)
        wf_splitter.addWidget(wf_container)
        wf_splitter.setSizes([120, 280])   # spectrum 30%, waterfall 70%
        wf_splitter.setChildrenCollapsible(False)
        lay.addWidget(wf_splitter)
        return w

    def _build_spectrum_plot(self) -> None:
        """Build self._spec_plot with curves, CF marker, and level region."""
        self._spec_plot = pg.PlotWidget(background="#080808")
        self._spec_plot.setFixedHeight(120)
        self._spec_plot.showGrid(x=False, y=True, alpha=0.15)
        self._spec_plot.setMenuEnabled(False)
        self._spec_plot.setMouseEnabled(x=False, y=False)
        self._spec_plot.getAxis("left").setWidth(44)
        self._spec_plot.setLabel(
            "left", "dBFS", color="#444", **{"font-size": "9px"})
        self._spec_plot.getAxis("left").setStyle(tickFont=_small_font())
        self._spec_plot.setLabel(
            "bottom", "MHz", color="#444", **{"font-size": "9px"})
        self._spec_plot.getAxis("bottom").setStyle(tickFont=_small_font())
        self._spec_curve = self._spec_plot.plot(
            pen=pg.mkPen("#3fbe6f", width=1))
        self._peak_curve = self._spec_plot.plot(
            pen=pg.mkPen("#ff8800", width=1, style=Qt.PenStyle.DotLine))
        self._peak_curve.hide()
        self._cf_line = pg.InfiniteLine(
            angle=90, movable=False,
            pen=pg.mkPen("#ff4444", width=1, style=Qt.PenStyle.DashLine))
        self._spec_plot.addItem(self._cf_line)
        # Floor/ceiling shading — NOT movable: it's a full-width band that would
        # otherwise swallow drags meant for the IF passband below. Floor/ceiling
        # are set via the Display spin-boxes and the waterfall "Auto" button.
        self._level_region = pg.LinearRegionItem(
            values=[self._floor_db, self._ceiling_db],
            orientation='horizontal', movable=False,
            brush=pg.mkBrush(255, 255, 255, 8))
        self._spec_plot.addItem(self._level_region)
        self._squelch_line = pg.InfiniteLine(
            angle=0, movable=False,
            pen=pg.mkPen("#ff8800", width=1, style=Qt.PenStyle.DashLine))
        self._squelch_line.hide()
        self._spec_plot.addItem(self._squelch_line)
        self._spec_plot.scene().sigMouseClicked.connect(self._on_spec_click)
        self._spec_plot.wheelEvent = self._wheel_waterfall
        # IF passband indicator — a draggable shaded region spanning ±BW/2
        # around the tuned centre.  Drag an edge to change the IF bandwidth;
        # the shaded fill also makes a BW change visible instead of two
        # sub-pixel hairlines.
        self._passband = pg.LinearRegionItem(
            values=[0, 0], movable=True,
            brush=pg.mkBrush(0, 204, 204, 36),
            pen=pg.mkPen("#00cccc", width=1, style=Qt.PenStyle.DashLine),
            hoverBrush=pg.mkBrush(0, 204, 204, 64))
        self._passband.setZValue(20)          # above the (non-movable) level band
        self._passband.setToolTip(
            "IF passband — drag an edge to change bandwidth")
        # Fatter, brighter edges that highlight on hover so they're easy to grab.
        for _ln in self._passband.lines:
            _ln.setPen(pg.mkPen("#00e5e5", width=2))
            _ln.setHoverPen(pg.mkPen("#7fffff", width=4))
        self._passband.sigRegionChangeFinished.connect(self._on_passband_drag)
        self._spec_plot.addItem(self._passband)

    def _build_waterfall_plot(self) -> None:
        """Build self._wf_plot with image item and click/wheel handlers."""
        import threading
        self._wf_plot = pg.PlotWidget(background="#080808")
        self._wf_plot.setMenuEnabled(False)
        self._wf_plot.hideAxis("left")
        self._wf_plot.showAxis("bottom")
        self._wf_plot.setLabel(
            "bottom", "MHz", color="#444", **{"font-size": "9px"})
        self._wf_plot.getAxis("bottom").setStyle(tickFont=_small_font())
        self._wf_img = pg.ImageItem()
        cmap = _make_colormap(self._palette)
        if cmap:
            self._wf_img.setColorMap(cmap)
        self._wf_plot.addItem(self._wf_img)
        self._wf_plot.scene().sigMouseClicked.connect(self._on_wf_click)
        self._wf_plot.wheelEvent = self._wheel_waterfall
        # Load Artemis signal-ID database in background
        threading.Thread(
            target=get_identifier().load_db, daemon=True).start()

    def _build_controls(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea{border:none;background:transparent;}")
        inner = QWidget()
        lay   = QVBoxLayout(inner)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)
        scroll.setWidget(inner)
        lay.addWidget(self._build_profile_group())
        lay.addWidget(self._build_gain_group())
        lay.addWidget(self._build_display_group())
        lay.addWidget(self._build_span_group())
        lay.addWidget(self._build_demod_group())
        lay.addStretch()
        return scroll

    # ── Built-in demod profiles ───────────────────────────────────────────
    _BUILTIN_PROFILES: dict = {
        "SSB / Ham Voice": {"mode": "USB",     "bw": "2.5 kHz", "nr": False, "nr_lvl": 0,  "sq": False, "sq_db": -60.0},
        "CW Contest":      {"mode": "CW",      "bw": "500 Hz",  "nr": True,  "nr_lvl": 50, "sq": False, "sq_db": -60.0},
        "AM Broadcast":    {"mode": "AM",       "bw": "10 kHz",  "nr": True,  "nr_lvl": 20, "sq": False, "sq_db": -60.0},
        "FM Broadcast":    {"mode": "WFM",      "bw": "200 kHz", "nr": False, "nr_lvl": 0,  "sq": False, "sq_db": -60.0},
        "Digital / FT8":   {"mode": "USB",     "bw": "2.5 kHz", "nr": False, "nr_lvl": 0,  "sq": True,  "sq_db": -80.0},
        "NFM Comms":       {"mode": "NFM",      "bw": "10 kHz",  "nr": True,  "nr_lvl": 30, "sq": True,  "sq_db": -90.0},
    }

    # ── Frequency control ─────────────────────────────────────────────────

    def _on_freq_enter(self):
        try:
            val_str = self._freq_edit.text().strip()
            unit = self._freq_unit.currentText()
            val  = float(val_str)
            if unit == "MHz":
                hz = int(val * 1_000_000)
            elif unit == "kHz":
                hz = int(val * 1_000)
            else:
                hz = int(val)
            self._set_freq(hz)
        except ValueError:
            pass

    def _set_freq(self, hz: int):
        self._center_hz = hz
        self._freq_edit.setText(
            f"{hz/1e6:.4f}")
        self._manager.set_frequency(hz)
        self._update_axes()
        self._draw_band_segments()
        self._apply_auto_demod(hz)

    def _on_manual_demod_pick(self, *_args) -> None:
        """User hand-picked a demod mode or bandwidth → pause Auto."""
        cb = getattr(self, "_auto_demod_cb", None)
        if cb and cb.isChecked():
            cb.setChecked(False)

    def _on_bw_change(self, _txt: str = "") -> None:
        """Redraw the IF passband indicator when the bandwidth changes."""
        if HAS_PG and getattr(self, "_passband", None) is not None:
            self._update_axes()

    def _on_passband_drag(self) -> None:
        """User dragged a passband edge → set IF bandwidth to the new width.

        Any custom bandwidth is honoured (not just the combo presets): the
        dragged width is rounded to a readable value and written to the editable
        BW combo, which _bw_hz parses back. Setting it fires currentTextChanged
        → _on_bw_change → _update_axes, which redraws the passband at that width."""
        if not (HAS_PG and getattr(self, "_passband", None) is not None):
            return
        lo_mhz, hi_mhz = self._passband.getRegion()
        new_bw = int(abs(hi_mhz - lo_mhz) * 1e6)
        if new_bw <= 0:
            self._update_axes()
            return
        # Round to the nearest 100 Hz for a clean label; still fully custom.
        new_bw = max(100, int(round(new_bw / 100.0) * 100))
        self._demod_bw.setCurrentText(_fmt_bw(new_bw))
        self._on_manual_demod_pick()   # a hand-drag pauses Auto demod

    def _apply_auto_demod(self, hz: int) -> None:
        """When Auto is enabled, set demod mode + IF bandwidth for `hz`."""
        cb = getattr(self, "_auto_demod_cb", None)
        if not (cb and cb.isChecked()):
            return
        try:
            from core.auto_demod import suggest_demod, nearest_bw_label
            s = suggest_demod(hz)
            self._demod_combo.setCurrentText(s.mode)   # sets a default BW
            labels = [self._demod_bw.itemText(i)
                      for i in range(self._demod_bw.count())]
            bw = nearest_bw_label(s.bandwidth_hz, labels)
            if bw:
                self._demod_bw.setCurrentText(bw)
        except Exception:
            pass

    def _set_step(self, idx: int):
        self._step_idx = idx

    def _step_freq(self, direction: int):
        step = SDR_STEP_SIZES[self._step_idx]
        self._set_freq(self._center_hz + direction * step)

    def _tune_to_rig(self):
        if self.rig and self.rig.is_connected:
            self._set_freq(self.rig.state.freq_hz)

    # ── Display controls ──────────────────────────────────────────────────

    def _on_gain(self, val: int):
        self._gain_lbl.setText(f"{val} dB")
        self._manager.set_gain(float(val))

    def _on_floor_ceiling(self):
        self._floor_db   = self._floor_spin.value()
        self._ceiling_db = self._ceil_spin.value()
        self._auto_range = False
        self._update_axes()

    def _on_level_region(self):
        lo, hi = self._level_region.getRegion()
        self._floor_db   = lo
        self._ceiling_db = hi
        self._floor_spin.blockSignals(True)
        self._ceil_spin.blockSignals(True)
        self._floor_spin.setValue(lo)
        self._ceil_spin.setValue(hi)
        self._floor_spin.blockSignals(False)
        self._ceil_spin.blockSignals(False)

    def _auto_range_set(self):
        if self._latest_fft is not None:
            noise  = np.percentile(self._latest_fft, 10)
            peak   = np.percentile(self._latest_fft, 99)
            margin = (peak - noise) * 0.1
            self._floor_db   = noise - margin
            self._ceiling_db = peak  + margin
            self._floor_spin.setValue(self._floor_db)
            self._ceil_spin.setValue(self._ceiling_db)
            self._update_axes()

    def _on_palette(self, name: str):
        self._palette = name
        if getattr(self, "_legend", None) is not None:
            self._legend.set_palette(name)
        if HAS_PG:
            cmap = _make_colormap(name)
            if cmap:
                self._wf_img.setColorMap(cmap)

    def _on_ref_level(self, value: float):
        self._y_ref_db = value
        unit = "dBFS" if value == 0.0 else "dBm"
        self._ref_unit_lbl.setText(unit)
        if HAS_PG:
            self._spec_plot.setLabel(
                "left", unit, color="#444", **{"font-size": "9px"})
        self._update_axes()

    def _on_squelch_toggle(self, enabled: bool):
        self._squelch_enabled = enabled
        self._squelch_slider.setEnabled(enabled)
        if HAS_PG:
            self._squelch_line.setVisible(enabled)
        if not enabled:
            self._squelch_open = True
            self._squelch_ind.setStyleSheet("")

    def _on_squelch_slider(self, value: int):
        self._squelch_db = float(value)
        self._squelch_lbl.setText(f"{value:+d} dB")
        if HAS_PG and self._squelch_enabled:
            self._squelch_line.setValue(self._squelch_db)

    # Mode→default BW mapping (matches _demod_bw addItems order)
    _DEMOD_DEFAULT_BW = {
        "AM":     "10 kHz",
        "NFM":    "10 kHz",
        "WFM":    "200 kHz",
        "USB":    "2.5 kHz",
        "LSB":    "2.5 kHz",
        "CW":     "500 Hz",
        "Raw IQ": "200 kHz",
    }

    def _on_demod_mode_change(self, mode: str) -> None:
        """Auto-select sensible default BW when the demod mode changes."""
        default = self._DEMOD_DEFAULT_BW.get(mode)
        if default and hasattr(self, "_demod_bw"):
            self._demod_bw.setCurrentText(default)

    @property
    def _bw_hz(self) -> int:
        """Current IF bandwidth in Hz from the BW combo."""
        try:
            txt = self._demod_bw.currentText().strip()
            parts = txt.split()
            val = float(parts[0])
            unit = parts[1] if len(parts) > 1 else "Hz"
            if unit == "kHz":
                return int(val * 1_000)
            if unit == "MHz":
                return int(val * 1_000_000)
            return int(val)
        except Exception:
            return 10_000

    # ── Scheduled recording ───────────────────────────────────────────────

    def _check_sqtrig(self) -> None:
        """Squelch-triggered recording: auto-start/stop based on squelch state."""
        import time
        if not (hasattr(self, "_sqtrig_cb") and self._sqtrig_cb.isChecked()):
            return
        if not self._squelch_enabled:
            return
        now  = time.time()
        tail = self._sqtrig_tail.value()
        if self._squelch_open:
            # Signal present → start recording if not already, clear close ts
            self._sqtrig_close_ts = None
            if not self._recorder.is_recording:
                if self._sqtrig_open_ts is None:
                    self._sqtrig_open_ts = now
                self._toggle_record()   # start
        else:
            # No signal
            self._sqtrig_open_ts = None
            if self._recorder.is_recording:
                if self._sqtrig_close_ts is None:
                    self._sqtrig_close_ts = now
                elif now - self._sqtrig_close_ts >= tail:
                    self._toggle_record()   # stop after tail
                    self._sqtrig_close_ts = None

    def _arm_scheduled_record(self) -> None:
        """Arm a timed recording to start at the selected UTC time."""
        t   = self._sched_time.time()
        self._sched_armed   = True
        self._sched_dur_min = self._sched_dur.value()
        self._sched_stop_at = None
        hhmm = f"{t.hour():02d}:{t.minute():02d}"
        self._sched_status.setText(f"Armed → starts {hhmm} UTC")

    def _check_schedule(self) -> None:
        """Called every 10 s; fires the recording when wall-clock hits target."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        if self._sched_armed and not self._recorder.is_recording:
            t   = self._sched_time.time()
            if now.hour == t.hour() and now.minute == t.minute():
                self._sched_armed = False
                from datetime import timedelta
                stop = now + timedelta(minutes=self._sched_dur_min)
                self._sched_stop_at = stop.strftime("%H:%M")
                self._toggle_record()
                self._sched_status.setText(
                    f"Recording → stops ~{self._sched_stop_at} UTC")
        elif self._sched_stop_at and self._recorder.is_recording:
            t_str = now.strftime("%H:%M")
            if t_str >= self._sched_stop_at:
                self._toggle_record()
                self._sched_stop_at = None
                self._sched_status.setText("Scheduled recording complete")

    def _on_nr_toggle(self, enabled: bool):
        self._nr_enabled = enabled
        self._nr_slider.setEnabled(enabled)

    def _on_nr_slider(self, value: int):
        self._nr_level = value
        self._nr_lbl.setText(f"{value}%")

    def _on_nb_toggle(self, enabled: bool):
        self._nb_enabled = enabled
        self._nb_slider.setEnabled(enabled)

    def _on_nb_slider(self, value: int):
        self._nb_strength = value / 100.0
        self._nb_lbl.setText(f"{value}%")

    def _on_agc_toggle(self, enabled: bool):
        """Enable/disable hardware AGC; manual gain is inert while AGC is on."""
        try:
            self._manager.set_agc(enabled)
        except Exception:
            pass
        if hasattr(self, "_gain_slider"):
            self._gain_slider.setEnabled(not enabled)

    @property
    def _lo_hz(self) -> int:
        """LO offset in Hz — read live from config so Settings changes apply immediately."""
        try:
            return int(self.cfg.get("sdr.lo_offset_hz", 0) or 0)
        except Exception:
            return 0

    def _on_peak_hold(self, enabled: bool):
        self._peak_hold = enabled
        if HAS_PG:
            self._peak_curve.setVisible(enabled)
        if not enabled:
            self._peak_data = np.full(FFT_SIZE, -100.0)

    def _on_span(self, idx: int):
        spans_hz = [
            100_000, 500_000, 1_000_000, 2_400_000,
            5_000_000, 10_000_000, 20_000_000]
        if idx < len(spans_hz):
            self._span_hz = spans_hz[idx]
            if self._current:
                self._span_hz = min(
                    self._span_hz,
                    self._current.max_span)
            self._manager.set_sample_rate(self._span_hz)
            self._update_axes()
            self._draw_band_segments()

    # ── Wheel events ──────────────────────────────────────────────────────

    def _wheel_waterfall(self, event: QWheelEvent):
        # Read BOTH axes: a tilt-wheel / trackpad reports horizontal scroll on
        # x() with y()==0, which previously fell through to the "scroll down"
        # branch and always *decreased* frequency. Now horizontal scroll pans
        # frequency in the natural direction (right = higher, left = lower).
        dx   = event.angleDelta().x()
        dy   = event.angleDelta().y()
        mods = event.modifiers()
        if mods & Qt.KeyboardModifier.ControlModifier:
            # Ctrl+scroll = zoom span (either axis)
            d = dy if dy != 0 else dx
            if d > 0:
                self._zoom_in()
            elif d < 0:
                self._zoom_out()
            event.accept()
            return
        # Horizontal scroll always pans frequency: right = up, left = down.
        if dx > 0:
            self._step_freq(1)
        elif dx < 0:
            self._step_freq(-1)
        # Vertical scroll: pan frequency (up = higher), or adjust IF bandwidth
        # when the "↕=BW" toggle is on (up = wider, down = narrower).
        if dy != 0:
            if getattr(self, "_scroll_vert_bw", False):
                self._step_bandwidth(1 if dy > 0 else -1)
            else:
                self._step_freq(1 if dy > 0 else -1)
        event.accept()

    def _step_bandwidth(self, direction: int):
        """Step the demod IF bandwidth combo (up = wider; combo is ascending)."""
        combo = getattr(self, "_demod_bw", None)
        if combo is None:
            return
        new = combo.currentIndex() + (1 if direction > 0 else -1)
        if 0 <= new < combo.count():
            combo.setCurrentIndex(new)

    def _zoom_in(self):
        idx = self._span_combo.currentIndex()
        if idx > 0:
            self._span_combo.setCurrentIndex(idx - 1)

    def _zoom_out(self):
        idx = self._span_combo.currentIndex()
        if idx < self._span_combo.count() - 1:
            self._span_combo.setCurrentIndex(idx + 1)

    # ── Click to tune ─────────────────────────────────────────────────────

    def _on_wf_click(self, event):
        if not HAS_PG:
            return
        try:
            pos = self._wf_plot.plotItem.vb\
                .mapSceneToView(event.scenePos())
            # Displayed freq = hw_freq + lo_offset; reverse to get hw freq
            hz = int(pos.x() * 1e6) - self._lo_hz
            if hz <= 0:
                return
            if event.button() == Qt.MouseButton.RightButton:
                self._show_sigid_menu(hz, event.screenPos())
            else:
                self._set_freq(hz)
        except Exception:
            pass

    def _on_spec_click(self, event):
        if not HAS_PG:
            return
        try:
            pos = self._spec_plot.plotItem.vb\
                .mapSceneToView(event.scenePos())
            hz = int(pos.x() * 1e6) - self._lo_hz
            if hz <= 0:
                return
            if event.button() == Qt.MouseButton.RightButton:
                self._show_sigid_menu(hz, event.screenPos())
            else:
                self._set_freq(hz)
        except Exception:
            pass

    def _show_sigid_menu(self, freq_hz: int, screen_pos) -> None:
        """Context menu on right-click: identify signal, tune, clear."""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtCore import QPointF
        menu = QMenu(self)
        mhz = freq_hz / 1e6
        id_act = menu.addAction(f"Identify Signal at {mhz:.3f} MHz")
        tune_act = menu.addAction(f"Tune to {mhz:.3f} MHz")
        menu.addSeparator()
        clr_act = menu.addAction("Clear annotations at this frequency")
        clr_all = menu.addAction("Clear all annotations")
        # Use demod bandwidth if the user has set it, else span/100
        try:
            bw_txt = self._demod_bw.currentText().split()[0]
            bw_hz = int(float(bw_txt) * 1000)
        except Exception:
            bw_hz = max(2500, self._span_hz // 100)
        chosen = menu.exec(
            screen_pos.toPoint()
            if hasattr(screen_pos, "toPoint")
            else self.mapToGlobal(self.rect().center()))
        if chosen == id_act:
            self._identify_signal(bw_hz, freq_hz)
        elif chosen == tune_act:
            self._set_freq(freq_hz)
        elif chosen == clr_act:
            self._clear_sigid_annotations(freq_hz)
        elif chosen == clr_all:
            self._clear_sigid_annotations()

    # ── SDR samples → FFT ─────────────────────────────────────────────────

    def _on_samples(self, iq: np.ndarray,
                     sample_rate: int, center_hz: int):
        """Called from SDR RX thread with IQ samples."""
        self._sample_rate = sample_rate
        self._center_hz   = center_hz
        # Noise blanker — clamp impulsive samples in the time domain first.
        if self._nb_enabled:
            try:
                from core.dsp_nb import noise_blank
                iq = noise_blank(iq, self._nb_strength)
            except Exception:
                pass
        # FFT
        window  = np.hanning(len(iq))
        fft_out = np.fft.fftshift(
            np.abs(np.fft.fft(iq * window, FFT_SIZE)))
        fft_db  = 20 * np.log10(
            fft_out / FFT_SIZE + 1e-10)

        # Noise reduction — spectral averaging (smooths noise floor)
        if self._nr_enabled and self._nr_level > 0:
            win = 1 + int(self._nr_level / 100 * 15)  # 1–16 samples
            kernel = np.ones(win) / win
            fft_db = np.convolve(fft_db, kernel, mode='same')

        with self._fft_lock:
            self._latest_fft = fft_db
            # Update waterfall
            self._wf_data = np.roll(
                self._wf_data, -1, axis=0)
            row = np.interp(
                np.linspace(0, len(fft_db)-1,
                            FFT_SIZE // 2),
                np.arange(len(fft_db)), fft_db)
            self._wf_data[-1, :] = row
            # Peak hold
            if self._peak_hold:
                self._peak_data = np.maximum(
                    self._peak_data, fft_db)

        # Record if active
        if self._recorder.is_recording:
            self._recorder.write_samples(iq)

        # Record demodulated audio to WAV if armed (§14.7)
        arec = self._audio_rec
        if arec is not None and arec.is_recording:
            arec.feed(iq, sample_rate, center_hz)

        # Squelch gate — update open/closed state from peak FFT power
        if self._squelch_enabled:
            self._squelch_open = float(np.max(fft_db)) >= self._squelch_db
        # Route to digital if enabled and squelch open
        if self._route_to_digital and self._decoder_cb and self._squelch_open:
            try:
                self._decoder_cb(
                    iq, sample_rate, center_hz)
            except Exception:
                pass

    # ── Plot updates ──────────────────────────────────────────────────────

    @pyqtSlot()
    def _update_plots(self):
        # Survey pump runs off the plot timer (main thread), independent of
        # plotting, so the RX thread is never loaded and it works headless-ish.
        if self._survey_enabled:
            self._survey_tick()
        if not HAS_PG or self._latest_fft is None:
            return

        with self._fft_lock:
            fft   = self._latest_fft.copy()
            wf    = self._wf_data.copy()
            peak  = self._peak_data.copy()

        half  = self._span_hz / 2
        lo_off = self._lo_hz
        freqs = np.linspace(
            (self._center_hz + lo_off - half) / 1e6,
            (self._center_hz + lo_off + half) / 1e6,
            len(fft))

        # Spectrum (apply reference level offset for dBm display)
        ref = self._y_ref_db
        self._spec_curve.setData(freqs, fft + ref)

        # Peak hold
        if self._peak_hold:
            self._peak_curve.setData(freqs, peak + ref)

        # Auto-range
        if self._auto_range:
            self._floor_db   = np.percentile(fft, 5) - 5
            self._ceiling_db = np.max(fft) + 5
            if getattr(self, "_legend", None) is not None:
                self._legend.set_range(
                    self._floor_db + self._y_ref_db,
                    self._ceiling_db + self._y_ref_db)

        # Waterfall
        self._wf_img.setImage(
            wf.T,
            autoLevels=False,
            levels=(self._floor_db, self._ceiling_db))

        # Squelch indicator (safe to update on UI thread)
        if self._squelch_enabled:
            if self._squelch_open:
                self._squelch_ind.setStyleSheet("color:#3fbe6f;")
                self._squelch_ind.setToolTip(self.tr("Squelch OPEN — signal above threshold"))
            else:
                self._squelch_ind.setStyleSheet("color:#cc4444;")
                self._squelch_ind.setToolTip(self.tr("Squelch CLOSED — signal below threshold"))

        # Recording status
        if self._recorder.is_recording:
            elapsed = self._recorder.elapsed
            self._rec_status.setText(
                f"● REC  {elapsed:.0f}s")
            self._rec_status.setStyleSheet(
                "color:#cc4444;"
                "font-family:'Courier New';")

    def _update_axes(self):
        if not HAS_PG:
            return
        lo_off = self._lo_hz
        half   = self._span_hz / 2
        lo_mhz = (self._center_hz + lo_off - half) / 1e6
        hi_mhz = (self._center_hz + lo_off + half) / 1e6
        self._spec_plot.setXRange(lo_mhz, hi_mhz, padding=0)
        self._spec_plot.setYRange(
            self._floor_db + self._y_ref_db,
            self._ceiling_db + self._y_ref_db, padding=0)
        self._wf_img.setRect(
            QRectF(lo_mhz, 0, hi_mhz - lo_mhz, WF_ROWS))
        self._wf_plot.setXRange(lo_mhz, hi_mhz, padding=0)
        self._cf_line.setValue((self._center_hz + self._lo_hz) / 1e6)
        # IF passband indicator — ±BW/2 around the centre.  Block the region's
        # change signal so this programmatic update doesn't re-enter
        # _on_passband_drag.
        if getattr(self, "_passband", None) is not None:
            half_bw = self._bw_hz / 2
            cf_mhz  = (self._center_hz + self._lo_hz) / 1e6
            self._passband.blockSignals(True)
            self._passband.setRegion(
                (cf_mhz - half_bw / 1e6, cf_mhz + half_bw / 1e6))
            self._passband.blockSignals(False)
        # Waterfall colour legend — mirror the floor/ceiling (+ ref offset)
        if getattr(self, "_legend", None) is not None:
            self._legend.set_range(
                self._floor_db + self._y_ref_db,
                self._ceiling_db + self._y_ref_db)

    def _draw_band_segments(self):
        if not HAS_PG:
            return
        for item in self._seg_items:
            try:
                self._spec_plot.removeItem(item)
            except Exception:
                pass
        self._seg_items.clear()

        half = self._span_hz / 2
        lo   = int(self._center_hz - half)
        hi   = int(self._center_hz + half)

        from core.band_plan import segments_in_range
        for seg in segments_in_range(lo, hi):
            sl = max(seg.freq_lo, lo) / 1e6
            sh = min(seg.freq_hi, hi) / 1e6
            region = pg.LinearRegionItem(
                values=[sl, sh],
                movable=False,
                brush=pg.mkBrush(seg.color))
            region.setToolTip(seg.tooltip)
            region.setZValue(-10)
            self._spec_plot.addItem(region)
            self._seg_items.append(region)

    # ── SquelchPanel persistence ───────────────────────────────────────────

    def save_state(self) -> dict:
        return {
            "center_hz":       self._center_hz,
            "span":            self._span_combo.currentText(),
            "gain":            self._gain_slider.value(),
            "ppm":             self._ppm_spin.value(),
            "palette":         self._palette,
            "floor_db":        self._floor_db,
            "ceil_db":         self._ceiling_db,
            "peak_hold":       self._peak_hold,
            "y_ref_db":        self._y_ref_db,
            "squelch_enabled": self._squelch_enabled,
            "squelch_db":      self._squelch_db,
            "nr_enabled":      self._nr_enabled,
            "nr_level":        self._nr_level,
            "nb_enabled":      self._nb_enabled,
            "nb_strength":     self._nb_strength,
            "agc":             self._agc_cb.isChecked(),
            "demod_mode":      self._demod_combo.currentText(),
            "demod_bw":        self._demod_bw.currentText(),
            "demod_auto":      self._auto_demod_cb.isChecked(),
            "wheel_vert_bw":   getattr(self, "_scroll_vert_bw", False),
            "survey_enabled":  self._survey_enabled,
        }

    def restore_state(self, state: dict) -> None:
        if "center_hz" in state:
            self._set_freq(int(state["center_hz"]))
        if "span" in state:
            self._span_combo.setCurrentText(state["span"])
        if "gain" in state:
            self._gain_slider.setValue(int(state["gain"]))
        if "ppm" in state:
            self._ppm_spin.setValue(int(state["ppm"]))
        if "palette" in state:
            self._palette_combo.setCurrentText(state["palette"])
        if "floor_db" in state and "ceil_db" in state:
            self._floor_spin.setValue(float(state["floor_db"]))
            self._ceil_spin.setValue(float(state["ceil_db"]))
        if "peak_hold" in state:
            self._peak_cb.setChecked(bool(state["peak_hold"]))
        if "y_ref_db" in state:
            self._ref_spin.setValue(float(state["y_ref_db"]))
        if "squelch_db" in state:
            self._squelch_slider.setValue(int(state["squelch_db"]))
        if "squelch_enabled" in state:
            self._squelch_cb.setChecked(bool(state["squelch_enabled"]))
        if "nr_level" in state:
            self._nr_slider.setValue(int(state["nr_level"]))
        if "nr_enabled" in state:
            self._nr_cb.setChecked(bool(state["nr_enabled"]))
        if "demod_mode" in state:
            self._demod_combo.setCurrentText(state["demod_mode"])
        if "demod_bw" in state:
            self._demod_bw.setCurrentText(state["demod_bw"])
        if "demod_auto" in state:
            self._auto_demod_cb.setChecked(bool(state["demod_auto"]))
        if "nb_strength" in state:
            self._nb_slider.setValue(int(float(state["nb_strength"]) * 100))
        if "nb_enabled" in state:
            self._nb_cb.setChecked(bool(state["nb_enabled"]))
        if "agc" in state:
            self._agc_cb.setChecked(bool(state["agc"]))
        if "wheel_vert_bw" in state:
            self._wheel_bw_cb.setChecked(bool(state["wheel_vert_bw"]))
        if "survey_enabled" in state and hasattr(self, "_survey_btn"):
            self._survey_btn.setChecked(bool(state["survey_enabled"]))

    # IQ Recorder, Scanner, Signal ID, ADS-B, and public API methods
    # are in the mixin classes: _SDRRecordingMixin, _SDRScannerMixin,
    # _SDRSignalIDMixin (see imports above).


def _sep(border: str = "#2a2a2a") -> QFrame:
    """Horizontal separator line."""
    from PyQt6.QtWidgets import QFrame
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"color:{border};")
    return f


def _vsep(border: str = "#2a2a2a") -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setStyleSheet(f"color:{border};")
    f.setFixedWidth(1)
    return f


def _small_font():
    from PyQt6.QtGui import QFont
    f = QFont("Segoe UI")
    f.setPointSize(8)
    return f
