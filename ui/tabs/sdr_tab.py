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
"""Squelch -- ui/tabs/sdr_tab.py
Full SDR tab.
Waterfall + spectrum, device selector, dynamic RX/TX controls,
IQ recorder/player, scanner, audio routing, signal routing to
Digital tab.
"""

import logging
import threading
import time
import numpy as np
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QSplitter, QPushButton, QLabel, QComboBox,
    QGroupBox, QSlider, QSpinBox, QDoubleSpinBox,
    QFrame, QProgressBar, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox,
    QSizePolicy, QScrollArea, QLineEdit, QButtonGroup
,
    QDialog
,
    QDialogButtonBox
,
    QFileDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QWheelEvent, QDesktopServices, QFont
from PyQt6.QtCore import QUrl

from ui.widgets.launch_bar import LaunchBar
from network.signal_id import get_identifier
from sdr.soapy_device import (
    SoapyManager, SDRDevice, get_sdr_manager, HAS_SOAPY)
from sdr.iq_recorder import (
    IQRecorder, IQPlayer, list_recordings, Recording)
from core.band_plan import band_at_freq, BAND_EDGES
from core.validator import frequency_hz_soft
from core.constants import BAND_EDGES_R2 as BAND_EDGES, FFT_SIZE

log = logging.getLogger(__name__)

try:
    import pyqtgraph as pg
    HAS_PG = True
    pg.setConfigOptions(antialias=False, useOpenGL=False)
except ImportError:
    HAS_PG = False

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


class SDRTab(QWidget):
    def __init__(self, config, rig=None, parent=None):
        super().__init__(parent)
        self.cfg        = config
        self.rig        = rig
        self._manager   = get_sdr_manager()
        # Location manager for receiver.json
        try:
            from core.location import LocationManager
            self.location_mgr = LocationManager(config)
        except Exception:
            self.location_mgr = None
        self._recorder  = IQRecorder(
            Path(config.get(
                "paths.iq_recordings", "recordings")))
        self._player    = IQPlayer()
        self._devices:  list[SDRDevice] = []
        self._current:  SDRDevice = None

        # Spectrum state
        self._center_hz  = 100_000_000
        self._span_hz    = 2_400_000
        self._step_idx   = 4   # 12.5 kHz default
        self._floor_db   = -100.0
        self._ceiling_db = -20.0
        self._auto_range = True
        self._palette    = "Jet"
        self._peak_hold  = False
        self._wf_data    = np.full(
            (WF_ROWS, FFT_SIZE // 2), -100.0)
        self._peak_data  = np.full(FFT_SIZE, -100.0)
        self._fft_lock   = threading.Lock()
        self._latest_fft: np.ndarray = None

        # Scanner
        self._scan_running = False
        self._scan_timer   = QTimer(self)
        self._scan_timer.timeout.connect(self._scan_step)

        # Signal routing
        self._route_to_digital = False
        self._decoder_cb = None

        self._build()

        # Wire manager callbacks
        self._manager.on_samples(self._on_samples)

        # UI refresh timer
        self._ui_timer = QTimer(self)
        self._ui_timer.setInterval(100)
        self._ui_timer.timeout.connect(self._update_plots)
        self._ui_timer.start()

        # Enumerate devices
        QTimer.singleShot(500, self._enumerate_devices)

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build(self):
        try:
            outer = QVBoxLayout(self)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(0)

            if not HAS_SOAPY:
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
            # Always show something — never blank
            lay = QVBoxLayout(self)
            lay.setContentsMargins(40, 40, 40, 40)
            title = QLabel("SDR Tab — Load Error")
            title.setStyleSheet(
                "color:#cc4444;font-size:14px;font-weight:bold;")
            lay.addWidget(title)
            err_lbl = QLabel(
                f"The SDR tab failed to load:\n\n{e}\n\n"
                "This is usually caused by a missing dependency.\n"
                "Check logs/squelch.log for details.")
            err_lbl.setWordWrap(True)
            err_lbl.setStyleSheet("color:#888;font-size:13px;")
            lay.addWidget(err_lbl)
            lay.addStretch()

    def _build_no_soapy(self, layout):
        """Shown when SoapySDR is not installed."""
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(40, 40, 40, 40)
        l.setSpacing(10)

        title = QLabel("〰️  SDR — Setup Required")
        title.setStyleSheet(
            "color:#3fbe6f;font-size:16px;"
            "font-weight:bold;")
        l.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#1a1a1a;")
        l.addWidget(sep)

        msg = QLabel(
            "SoapySDR is not installed. "
            "Install it to enable the spectrum waterfall, "
            "IQ recording, signal identification, and ADS-B tracking.\n\n"
            "Not required if using IC-7100 USB audio — "
            "the Rig tab spectrum works without SoapySDR.")
        msg.setWordWrap(True)
        msg.setStyleSheet("color:#aaa;font-size:12px;")
        l.addWidget(msg)

        # Install steps
        steps = [
            ("Windows — all hardware:",
             "1. Install PothosSDR bundle "
             "(includes SoapySDR + drivers):\n"
             "   https://downloads.myriadrf.org/builds/PothosSDR/\n"
             "2. Reboot\n"
             "3. pip install soapysdr\n"
             "4. Run installer.py to verify"),
            ("RTL-SDR on Windows — extra step required:",
             "Replace default driver with WinUSB using Zadig:\n"
             "   https://zadig.akeo.ie/\n"
             "Select your RTL-SDR dongle → WinUSB → Replace Driver"),
            ("Linux / DragonOS:",
             "sudo apt install soapysdr-tools soapyrtlsdr\n"
             "See README.md for all hardware types"),
        ]
        for label, detail in steps:
            lbl = QLabel(f"  ▸  {label}")
            lbl.setStyleSheet(
                "color:#3fbe6f;font-size:13px;"
                "font-weight:bold;margin-top:6px;")
            l.addWidget(lbl)
            det = QLabel(f"     {detail}")
            det.setStyleSheet("color:#666;font-size:12px;")
            det.setWordWrap(True)
            l.addWidget(det)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color:#1a1a1a;margin-top:8px;")
        l.addWidget(sep2)

        # dump1090 section — works without SoapySDR
        dump_title = QLabel("  ADS-B Aircraft Tracking")
        dump_title.setStyleSheet(
            "color:#aaa;font-size:12px;font-weight:bold;")
        l.addWidget(dump_title)

        dump_msg = QLabel(
            "  dump1090-fa enables ADS-B aircraft tracking "
            "and is used to place your station marker on the "
            "aircraft map. It does not require SoapySDR.\n"
            "  Install: github.com/flightaware/dump1090")
        dump_msg.setWordWrap(True)
        dump_msg.setStyleSheet("color:#666;font-size:12px;")
        l.addWidget(dump_msg)

        # ADS-B map button — works when dump1090 is running
        self._adsb_map_btn = QPushButton(
            "🗺  Open ADS-B Aircraft Map")
        self._adsb_map_btn.setFixedWidth(240)
        self._adsb_map_btn.setFixedHeight(30)
        self._adsb_map_btn.setStyleSheet("""
            QPushButton{
              background:#1a2a1a;color:#3fbe6f;
              border:1px solid #3fbe6f;border-radius:4px;
              font-size:13px;padding:4px 12px;}
            QPushButton:hover{background:#2a3a2a;}
            QPushButton:disabled{color:#333;
              border-color:#222;background:#111;}
        """)
        self._adsb_map_btn.setToolTip(
            "Opens dump1090-fa aircraft map at\n"
            "http://localhost:8080\n"
            "Your station location is shown on the map.")
        self._adsb_map_btn.clicked.connect(
            self._open_adsb_map)
        l.addWidget(self._adsb_map_btn)

        # Check if dump1090 is running
        self._check_dump1090_status()

        btn_row = QHBoxLayout()
        guide_btn = QPushButton("Open SDR Setup Guide")
        guide_btn.setFixedWidth(180)
        guide_btn.clicked.connect(self._open_sdr_guide)
        btn_row.addWidget(guide_btn)
        btn_row.addStretch()
        l.addLayout(btn_row)

        l.addStretch()
        # Ensure widget fills available space
        w.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding)
        layout.addWidget(w)
        layout.setStretchFactor(w, 1)

    def _build_no_pyqtgraph(self, layout):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(40, 40, 40, 40)
        title = QLabel("〰️  SDR — Missing Dependency")
        title.setStyleSheet(
            "color:#3fbe6f;font-size:14px;font-weight:bold;")
        l.addWidget(title)
        msg = QLabel(
            "pyqtgraph is required for the SDR waterfall.\n\n"
            "Run: pip install pyqtgraph\n"
            "Or:  python installer.py")
        msg.setWordWrap(True)
        msg.setStyleSheet("color:#888;font-size:12px;")
        l.addWidget(msg)
        l.addStretch()
        layout.addWidget(w)

    def _build_full(self, layout):
        """Full SDR UI with waterfall."""

        # ── Launch bar ───────────────────────────────────────────────────
        self._launch_bar = LaunchBar("sdr", self.cfg)
        layout.addWidget(self._launch_bar)

        # ── Top toolbar ───────────────────────────────────────────────────
        toolbar = self._build_toolbar()
        layout.addWidget(toolbar)

        # ── Main splitter: waterfall | controls ───────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(
            "QSplitter::handle{background:#1a1a1a;width:3px;}")

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

    def _build_toolbar(self) -> QWidget:
        bar = QFrame()
        bar.setFixedHeight(44)
        bar.setStyleSheet(
            "background:#111;border-bottom:1px solid #1a1a1a;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(8)

        # Device selector
        dev_lbl = QLabel(self.tr("Device:"))
        dev_lbl.setStyleSheet("color:#666;font-size:12px;")
        lay.addWidget(dev_lbl)

        self._dev_combo = QComboBox()
        self._dev_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._dev_combo.setMinimumWidth(160)
        self._dev_combo.addItem(self.tr("— Scanning… —"))
        self._dev_combo.currentIndexChanged.connect(
            self._on_device_select)
        lay.addWidget(self._dev_combo)

        self._connect_btn = QPushButton(self.tr("Connect"))
        self._connect_btn.setFixedWidth(80)
        self._connect_btn.setStyleSheet(
            "background:#1a3a1a;color:#3fbe6f;"
            "border:1px solid #3fbe6f;border-radius:4px;")
        self._connect_btn.clicked.connect(self._connect_sdr)
        lay.addWidget(self._connect_btn)

        self._sdr_status = QLabel("● Disconnected")
        self._sdr_status.setStyleSheet(
            "color:#555;font-size:13px;"
            "font-family:'Courier New';")
        lay.addWidget(self._sdr_status)
        lay.addWidget(_vsep())

        # Frequency display
        self._freq_edit = QLineEdit(
            f"{self._center_hz/1e6:.4f}")
        self._freq_edit.setFixedWidth(110)
        self._freq_edit.setStyleSheet(
            "background:#1a1a1a;color:#3fbe6f;"
            "font-size:14px;font-family:'Courier New';"
            "border:1px solid #333;border-radius:3px;"
            "padding:2px 6px;")
        self._freq_edit.returnPressed.connect(
            self._on_freq_enter)
        lay.addWidget(self._freq_edit)

        self._freq_unit = QComboBox()
        self._freq_unit.addItems(["MHz", "kHz", "Hz"])
        self._freq_unit.setFixedWidth(55)
        lay.addWidget(self._freq_unit)
        lay.addWidget(_vsep())

        # Step sizes
        step_lbl = QLabel("Step:")
        step_lbl.setStyleSheet("color:#666;font-size:12px;")
        lay.addWidget(step_lbl)

        self._step_btns = []
        self._step_grp  = QButtonGroup(self)
        self._step_grp.setExclusive(True)
        for i, (hz, lbl) in enumerate(
                zip(SDR_STEP_SIZES, SDR_STEP_LABELS)):
            btn = QPushButton(lbl)
            btn.setCheckable(True)
            btn.setChecked(i == self._step_idx)
            btn.setFixedHeight(22)
            btn.setStyleSheet("""
                QPushButton{font-size:13px;border:1px solid #222;
                  border-radius:3px;background:#111;
                  color:#666;padding:0 4px;}
                QPushButton:checked{background:#1a3a1a;
                  color:#3fbe6f;border-color:#3fbe6f;}
                QPushButton:hover{background:#1e2e1e;color:#aaa;}
            """)
            btn.clicked.connect(
                lambda _, idx=i: self._set_step(idx))
            self._step_btns.append(btn)
            self._step_grp.addButton(btn)
            lay.addWidget(btn)

        lay.addWidget(_vsep())

        # TX indicator (only shown for TX-capable hardware)
        self._tx_indicator = QLabel("● TX")
        self._tx_indicator.setStyleSheet(
            "color:#cc4444;font-size:13px;"
            "font-family:'Courier New';")
        self._tx_indicator.hide()
        lay.addWidget(self._tx_indicator)

        lay.addStretch()

        # Tune to rig button
        if self.rig:
            rig_btn = QPushButton(
                self.tr("← Rig Freq"))
            rig_btn.setFixedWidth(90)
            rig_btn.setToolTip(
                self.tr("Tune SDR to current rig frequency"))
            rig_btn.clicked.connect(self._tune_to_rig)
            lay.addWidget(rig_btn)

        return bar

    def _build_waterfall(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Spectrum plot
        self._spec_plot = pg.PlotWidget(
            background="#080808")
        self._spec_plot.setFixedHeight(120)
        self._spec_plot.showGrid(
            x=False, y=True, alpha=0.15)
        self._spec_plot.setMenuEnabled(False)
        self._spec_plot.setMouseEnabled(x=False, y=False)
        self._spec_plot.getAxis("left").setWidth(40)
        self._spec_plot.setLabel(
            "left", "dBFS",
            color="#444", **{"font-size": "9px"})
        self._spec_curve = self._spec_plot.plot(
            pen=pg.mkPen("#3fbe6f", width=1))
        self._peak_curve = self._spec_plot.plot(
            pen=pg.mkPen("#ff8800", width=1,
                          style=Qt.PenStyle.DotLine))
        self._peak_curve.hide()

        # Center frequency marker
        self._cf_line = pg.InfiniteLine(
            angle=90, movable=False,
            pen=pg.mkPen("#ff4444", width=1,
                          style=Qt.PenStyle.DashLine))
        self._spec_plot.addItem(self._cf_line)

        # Floor/ceiling draggable region
        self._level_region = pg.LinearRegionItem(
            values=[self._floor_db, self._ceiling_db],
            orientation='horizontal',
            movable=True,
            brush=pg.mkBrush(255, 255, 255, 8))
        self._level_region.sigRegionChanged.connect(
            self._on_level_region)
        self._spec_plot.addItem(self._level_region)

        # Waterfall image
        self._wf_plot = pg.PlotWidget(
            background="#080808")
        self._wf_plot.setMenuEnabled(False)
        self._wf_plot.hideAxis("left")
        self._wf_plot.getAxis("bottom").setStyle(
            tickFont=_small_font())

        self._wf_img = pg.ImageItem()
        cmap = _make_colormap(self._palette)
        if cmap:
            self._wf_img.setColorMap(cmap)
        self._wf_plot.addItem(self._wf_img)

        # Click waterfall to tune / right-click to identify
        self._wf_plot.scene().sigMouseClicked.connect(
            self._on_wf_click)
        # Load Artemis DB in background
        import threading
        threading.Thread(
            target=get_identifier().load_db,
            daemon=True).start()
        self._spec_plot.scene().sigMouseClicked.connect(
            self._on_spec_click)

        # Scroll/zoom on waterfall
        self._wf_plot.wheelEvent = self._wheel_waterfall
        self._spec_plot.wheelEvent = self._wheel_waterfall

        # Band segments overlay
        self._seg_items = []

        # Splitter between spectrum and waterfall
        # User can resize each independently
        from PyQt6.QtWidgets import QSplitter
        wf_splitter = QSplitter(Qt.Orientation.Vertical)
        wf_splitter.setStyleSheet(
            "QSplitter::handle{"
            "background:#2a2a2a;height:4px;"
            "border-top:1px solid #333;}")

        spec_container = QWidget()
        sc_lay = QVBoxLayout(spec_container)
        sc_lay.setContentsMargins(0, 0, 0, 0)
        sc_lay.addWidget(self._spec_plot)

        wf_container = QWidget()
        wc_lay = QVBoxLayout(wf_container)
        wc_lay.setContentsMargins(0, 0, 0, 0)
        wc_lay.addWidget(self._wf_plot)

        wf_splitter.addWidget(spec_container)
        wf_splitter.addWidget(wf_container)
        # Default: spectrum 30%, waterfall 70%
        wf_splitter.setSizes([120, 280])
        wf_splitter.setChildrenCollapsible(False)

        lay.addWidget(wf_splitter)
        return w

    def _build_controls(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea{border:none;background:transparent;}")

        inner = QWidget()
        lay   = QVBoxLayout(inner)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)
        scroll.setWidget(inner)

        # ── Gain ──────────────────────────────────────────
        gain_grp = QGroupBox(self.tr("Gain"))
        gl = QGridLayout(gain_grp)
        gl.setSpacing(4)

        gl.addWidget(QLabel(self.tr("RF Gain:")), 0, 0)
        self._gain_slider = QSlider(
            Qt.Orientation.Horizontal)
        self._gain_slider.setRange(0, 60)
        self._gain_slider.setValue(30)
        self._gain_slider.valueChanged.connect(
            self._on_gain)
        gl.addWidget(self._gain_slider, 0, 1)
        self._gain_lbl = QLabel("30 dB")
        self._gain_lbl.setStyleSheet(
            "color:#3fbe6f;font-size:12px;"
            "font-family:'Courier New';")
        self._gain_lbl.setFixedWidth(45)
        gl.addWidget(self._gain_lbl, 0, 2)

        gl.addWidget(QLabel(self.tr("PPM Corr:")), 1, 0)
        self._ppm_spin = QSpinBox()
        self._ppm_spin.setRange(-100, 100)
        self._ppm_spin.setValue(0)
        self._ppm_spin.setSuffix(" ppm")
        self._ppm_spin.setFixedWidth(80)
        self._ppm_spin.valueChanged.connect(
            lambda v: self._manager.set_ppm(v))
        gl.addWidget(self._ppm_spin, 1, 1, 1, 2)
        lay.addWidget(gain_grp)

        # ── Display ───────────────────────────────────────
        disp_grp = QGroupBox(self.tr("Display"))
        dl = QGridLayout(disp_grp)
        dl.setSpacing(4)

        dl.addWidget(QLabel(self.tr("Floor:")), 0, 0)
        self._floor_spin = QDoubleSpinBox()
        self._floor_spin.setRange(-160, 0)
        self._floor_spin.setValue(-100)
        self._floor_spin.setSuffix(" dB")
        self._floor_spin.setSingleStep(5)
        self._floor_spin.setFixedWidth(90)
        self._floor_spin.valueChanged.connect(
            self._on_floor_ceiling)
        dl.addWidget(self._floor_spin, 0, 1)

        dl.addWidget(QLabel(self.tr("Ceiling:")), 1, 0)
        self._ceil_spin = QDoubleSpinBox()
        self._ceil_spin.setRange(-120, 20)
        self._ceil_spin.setValue(-20)
        self._ceil_spin.setSuffix(" dB")
        self._ceil_spin.setSingleStep(5)
        self._ceil_spin.setFixedWidth(90)
        self._ceil_spin.valueChanged.connect(
            self._on_floor_ceiling)
        dl.addWidget(self._ceil_spin, 1, 1)

        auto_btn = QPushButton(self.tr("Auto"))
        auto_btn.setFixedHeight(24)
        auto_btn.setToolTip(
            self.tr("Auto-set floor and ceiling"))
        auto_btn.clicked.connect(self._auto_range_set)
        dl.addWidget(auto_btn, 0, 2, 2, 1)

        dl.addWidget(QLabel(self.tr("Palette:")), 2, 0)
        self._palette_combo = QComboBox()
        self._palette_combo.addItems(list(PALETTES.keys()))
        self._palette_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._palette_combo.currentTextChanged.connect(
            self._on_palette)
        dl.addWidget(self._palette_combo, 2, 1, 1, 2)

        self._peak_cb = QCheckBox(self.tr("Peak hold"))
        self._peak_cb.toggled.connect(self._on_peak_hold)
        dl.addWidget(self._peak_cb, 3, 0, 1, 3)
        lay.addWidget(disp_grp)

        # ── Span ──────────────────────────────────────────
        span_grp = QGroupBox(self.tr("Span"))
        sl = QHBoxLayout(span_grp)
        self._span_combo = QComboBox()
        spans = ["100 kHz","500 kHz","1 MHz","2.4 MHz",
                 "5 MHz","10 MHz","20 MHz"]
        self._span_combo.addItems(spans)
        self._span_combo.setCurrentText("2.4 MHz")
        self._span_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._span_combo.currentIndexChanged.connect(
            self._on_span)
        sl.addWidget(self._span_combo)
        lay.addWidget(span_grp)

        # ── Demodulator ───────────────────────────────────
        demod_grp = QGroupBox(self.tr("Demodulator"))
        deml = QGridLayout(demod_grp)
        deml.setSpacing(4)

        deml.addWidget(QLabel(self.tr("Mode:")), 0, 0)
        self._demod_combo = QComboBox()
        self._demod_combo.addItems([
            "AM", "NFM", "WFM", "USB", "LSB", "CW",
            "Raw IQ"])
        self._demod_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        deml.addWidget(self._demod_combo, 0, 1)

        deml.addWidget(QLabel(self.tr("BW:")), 1, 0)
        self._demod_bw = QComboBox()
        self._demod_bw.addItems([
            "200 Hz","500 Hz","1 kHz","2.5 kHz",
            "5 kHz","10 kHz","15 kHz","200 kHz"])
        self._demod_bw.setCurrentText("10 kHz")
        self._demod_bw.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        deml.addWidget(self._demod_bw, 1, 1)

        # Route to Digital tab
        self._route_cb = QCheckBox(
            self.tr("Route to Digital tab"))
        self._route_cb.setToolTip(
            self.tr(
                "Pipe demodulated audio to the Digital "
                "Monitor tab for P25/DMR/NXDN decode"))
        self._route_cb.toggled.connect(
            lambda c: setattr(
                self, '_route_to_digital', c))
        deml.addWidget(self._route_cb, 2, 0, 1, 2)
        lay.addWidget(demod_grp)

        # ── TX controls (hidden for RX-only devices) ──────
        self._tx_grp = QGroupBox(self.tr("Transmit"))
        txl = QVBoxLayout(self._tx_grp)
        tx_warn = QLabel(
            self.tr(
                "⚠ Ensure you have appropriate\n"
                "license before transmitting."))
        tx_warn.setStyleSheet(
            "color:#eeaa22;font-size:12px;")
        txl.addWidget(tx_warn)

        tx_btn = QPushButton(self.tr("TX IQ File…"))
        tx_btn.clicked.connect(self._tx_iq_file)
        txl.addWidget(tx_btn)
        self._tx_grp.hide()   # shown only for TX hardware
        lay.addWidget(self._tx_grp)

        lay.addStretch()
        return scroll

    def _build_bottom_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(90)
        bar.setStyleSheet(
            "background:#0d0d0d;"
            "border-top:1px solid #1a1a1a;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(8)

        # ── IQ Recorder ───────────────────────────────────
        rec_grp = QGroupBox(self.tr("IQ Recorder"))
        rl = QVBoxLayout(rec_grp)
        rl.setSpacing(2)

        rec_btn_row = QHBoxLayout()
        self._rec_btn = QPushButton("⏺ Record")
        self._rec_btn.setFixedHeight(26)
        self._rec_btn.setStyleSheet(
            "background:#3a1a1a;color:#cc4444;"
            "border:1px solid #cc4444;border-radius:4px;")
        self._rec_btn.clicked.connect(self._toggle_record)

        self._play_btn = QPushButton("▶ Play")
        self._play_btn.setFixedHeight(26)
        self._play_btn.clicked.connect(self._toggle_play)
        self._stop_btn = QPushButton("■ Stop")
        self._stop_btn.setFixedHeight(26)
        self._stop_btn.clicked.connect(self._stop_playback)
        self._stop_btn.setEnabled(False)

        rec_btn_row.addWidget(self._rec_btn)
        rec_btn_row.addWidget(self._play_btn)
        rec_btn_row.addWidget(self._stop_btn)
        rl.addLayout(rec_btn_row)

        self._rec_status = QLabel(self.tr("Idle"))
        self._rec_status.setStyleSheet(
            "color:#555;font-size:12px;"
            "font-family:'Courier New';")
        rl.addWidget(self._rec_status)

        self._play_bar = QProgressBar()
        self._play_bar.setRange(0, 100)
        self._play_bar.setValue(0)
        self._play_bar.setFixedHeight(6)
        self._play_bar.setTextVisible(False)
        rl.addWidget(self._play_bar)
        lay.addWidget(rec_grp)

        # ── Scanner ───────────────────────────────────────
        scan_grp = QGroupBox(self.tr("Scanner"))
        scl = QGridLayout(scan_grp)
        scl.setSpacing(3)

        scl.addWidget(QLabel(self.tr("From:")), 0, 0)
        self._scan_from = QLineEdit("100.0")
        self._scan_from.setFixedWidth(70)
        scl.addWidget(self._scan_from, 0, 1)
        scl.addWidget(QLabel("MHz"), 0, 2)

        scl.addWidget(QLabel(self.tr("To:")), 0, 3)
        self._scan_to = QLineEdit("108.0")
        self._scan_to.setFixedWidth(70)
        scl.addWidget(self._scan_to, 0, 4)
        scl.addWidget(QLabel("MHz"), 0, 5)

        scl.addWidget(QLabel(self.tr("Dwell:")), 1, 0)
        self._scan_dwell = QDoubleSpinBox()
        self._scan_dwell.setRange(0.1, 10.0)
        self._scan_dwell.setValue(1.0)
        self._scan_dwell.setSuffix(" s")
        self._scan_dwell.setFixedWidth(70)
        scl.addWidget(self._scan_dwell, 1, 1, 1, 2)

        scan_btns = QHBoxLayout()
        self._scan_start = QPushButton(self.tr("▶ Scan"))
        self._scan_start.setFixedHeight(24)
        self._scan_start.setStyleSheet(
            "background:#1a3a1a;color:#3fbe6f;"
            "border:1px solid #3fbe6f;border-radius:3px;"
            "font-size:12px;")
        self._scan_start.clicked.connect(self._start_scan)
        self._scan_stop = QPushButton(self.tr("■ Stop"))
        self._scan_stop.setFixedHeight(24)
        self._scan_stop.setEnabled(False)
        self._scan_stop.clicked.connect(self._stop_scan)
        scan_btns.addWidget(self._scan_start)
        scan_btns.addWidget(self._scan_stop)
        scl.addLayout(scan_btns, 1, 3, 1, 3)
        lay.addWidget(scan_grp)

        # ── Recordings list ───────────────────────────────
        lib_grp = QGroupBox(self.tr("Recordings"))
        ll = QVBoxLayout(lib_grp)
        self._rec_combo = QComboBox()
        self._rec_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._rec_combo.setMinimumWidth(200)
        ll.addWidget(self._rec_combo)
        self._load_rec_btn = QPushButton(
            self.tr("Load selected"))
        self._load_rec_btn.setFixedHeight(24)
        self._load_rec_btn.clicked.connect(
            self._load_recording)
        ll.addWidget(self._load_rec_btn)
        lay.addWidget(lib_grp)

        lay.addStretch()
        self._refresh_recordings()
        return bar

    # ── Device management ─────────────────────────────────────────────────

    def _enumerate_devices(self):
        def _do():
            devs = SoapyManager.enumerate()
            QTimer.singleShot(0,
                lambda d=devs: self._populate_devices(d))
        threading.Thread(target=_do, daemon=True).start()

    def _populate_devices(self, devices: list[SDRDevice]):
        self._devices = devices
        self._dev_combo.clear()
        if not devices:
            self._dev_combo.addItem(
                self.tr("No SDR devices found"))
            return
        for dev in devices:
            self._dev_combo.addItem(dev.display_name)
        self._dev_combo.setCurrentIndex(0)

    def _on_device_select(self, idx: int):
        if 0 <= idx < len(self._devices):
            dev = self._devices[idx]
            # Show TX controls only for TX hardware
            self._tx_grp.setVisible(dev.can_tx)
            self._tx_indicator.setVisible(dev.can_tx)
            # Adjust span to hardware limits
            self._span_hz = dev.recommended_span
            self._manager.set_sample_rate(
                dev.recommended_span)

    def _connect_sdr(self):
        idx = self._dev_combo.currentIndex()
        if not self._devices or idx >= len(self._devices):
            return
        if self._connect_btn.text() == self.tr("Disconnect"):
            self._manager.stop_rx()
            self._manager.close()
            self._connect_btn.setText(self.tr("Connect"))
            self._sdr_status.setText("● Disconnected")
            self._sdr_status.setStyleSheet(
                "color:#555;font-size:13px;"
                "font-family:'Courier New';")
            return

        dev = self._devices[idx]
        self._connect_btn.setEnabled(False)
        self._connect_btn.setText(self.tr("Connecting…"))

        def _do():
            ok = self._manager.open(dev)
            QTimer.singleShot(0,
                lambda o=ok, d=dev: self._on_connected(o, d))
        threading.Thread(target=_do, daemon=True).start()

    def _on_connected(self, ok: bool, dev: SDRDevice):
        self._connect_btn.setEnabled(True)
        if ok:
            self._connect_btn.setText(
                self.tr("Disconnect"))
            self._sdr_status.setText(
                f"● {dev.display_name}")
            self._sdr_status.setStyleSheet(
                "color:#3fbe6f;font-size:13px;"
                "font-family:'Courier New';")
            self._current = dev
            self._manager.start_rx()
            self._update_axes()
            self._draw_band_segments()
        else:
            self._connect_btn.setText(self.tr("Connect"))
            self._sdr_status.setText("● Error")
            self._sdr_status.setStyleSheet(
                "color:#cc4444;font-size:13px;"
                "font-family:'Courier New';")

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
        if HAS_PG:
            self._cf_line.setValue(hz)

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
        if HAS_PG:
            cmap = _make_colormap(name)
            if cmap:
                self._wf_img.setColorMap(cmap)

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
            sr = max(self._span_hz,
                     self._span_hz)
            self._manager.set_sample_rate(sr)
            self._update_axes()
            self._draw_band_segments()

    # ── Wheel events ──────────────────────────────────────────────────────

    def _wheel_waterfall(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        mods  = event.modifiers()
        if mods & Qt.KeyboardModifier.ControlModifier:
            # Ctrl+scroll = zoom span
            if delta > 0:
                self._zoom_in()
            else:
                self._zoom_out()
        else:
            # Scroll = pan frequency
            if delta > 0:
                self._step_freq(1)
            else:
                self._step_freq(-1)
        event.accept()

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
            # Map pixel position to frequency
            half  = self._span_hz / 2
            lo    = self._center_hz - half
            hi    = self._center_hz + half
            frac  = pos.x() / FFT_SIZE
            hz    = int(lo + frac * (hi - lo))
            if hz > 0:
                self._set_freq(hz)
        except Exception:
            pass

    def _on_spec_click(self, event):
        if not HAS_PG:
            return
        try:
            pos = self._spec_plot.plotItem.vb\
                .mapSceneToView(event.scenePos())
            hz = int(pos.x())
            if hz > 0:
                self._set_freq(hz)
        except Exception:
            pass

    # ── SDR samples → FFT ─────────────────────────────────────────────────

    def _on_samples(self, iq: np.ndarray,
                     sample_rate: int, center_hz: int):
        """Called from SDR RX thread with IQ samples."""
        # FFT
        window  = np.hanning(len(iq))
        fft_out = np.fft.fftshift(
            np.abs(np.fft.fft(iq * window, FFT_SIZE)))
        fft_db  = 20 * np.log10(
            fft_out / FFT_SIZE + 1e-10)

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

        # Route to digital if enabled
        if self._route_to_digital and self._decoder_cb:
            try:
                self._decoder_cb(
                    iq, sample_rate, center_hz)
            except Exception:
                pass

    # ── Plot updates ──────────────────────────────────────────────────────

    @pyqtSlot()
    def _update_plots(self):
        if not HAS_PG or self._latest_fft is None:
            return

        with self._fft_lock:
            fft   = self._latest_fft.copy()
            wf    = self._wf_data.copy()
            peak  = self._peak_data.copy()

        half  = self._span_hz / 2
        freqs = np.linspace(
            self._center_hz - half,
            self._center_hz + half,
            len(fft))

        # Spectrum
        self._spec_curve.setData(freqs, fft)

        # Peak hold
        if self._peak_hold:
            self._peak_curve.setData(freqs, peak)

        # Auto-range
        if self._auto_range:
            self._floor_db   = np.percentile(fft, 5) - 5
            self._ceiling_db = np.max(fft) + 5

        # Waterfall
        self._wf_img.setImage(
            wf.T,
            autoLevels=False,
            levels=(self._floor_db, self._ceiling_db))

        # Recording status
        if self._recorder.is_recording:
            elapsed = self._recorder.elapsed
            self._rec_status.setText(
                f"● REC  {elapsed:.0f}s")
            self._rec_status.setStyleSheet(
                "color:#cc4444;font-size:12px;"
                "font-family:'Courier New';")

    def _update_axes(self):
        if not HAS_PG:
            return
        half = self._span_hz / 2
        lo   = self._center_hz - half
        hi   = self._center_hz + half
        self._spec_plot.setXRange(lo, hi, padding=0)
        self._spec_plot.setYRange(
            self._floor_db, self._ceiling_db, padding=0)
        self._wf_plot.setXRange(
            0, FFT_SIZE // 2, padding=0)
        self._cf_line.setValue(self._center_hz)

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
            sl = max(seg.freq_lo, lo)
            sh = min(seg.freq_hi, hi)
            region = pg.LinearRegionItem(
                values=[sl, sh],
                movable=False,
                brush=pg.mkBrush(seg.color))
            region.setToolTip(seg.tooltip)
            region.setZValue(-10)
            self._spec_plot.addItem(region)
            self._seg_items.append(region)

    # ── IQ Recorder ──────────────────────────────────────────────────────

    def _toggle_record(self):
        if self._recorder.is_recording:
            rec = self._recorder.stop()
            self._rec_btn.setText("⏺ Record")
            self._rec_btn.setStyleSheet(
                "background:#3a1a1a;color:#cc4444;"
                "border:1px solid #cc4444;border-radius:4px;")
            self._rec_status.setText(
                self.tr("Recording saved"))
            self._rec_status.setStyleSheet(
                "color:#3fbe6f;font-size:12px;"
                "font-family:'Courier New';")
            self._refresh_recordings()
        else:
            hw = (self._current.display_name
                  if self._current else "")
            stem = self._recorder.start(
                self._center_hz,
                self._manager._sample_rate,
                hardware=hw)
            if stem:
                self._rec_btn.setText("■ Stop")
                self._rec_btn.setStyleSheet(
                    "background:#cc2222;color:#fff;"
                    "border:1px solid #ff4444;"
                    "border-radius:4px;")

    def _toggle_play(self):
        if self._player.is_playing:
            self._player.pause()
            self._play_btn.setText("▶ Play")
        else:
            self._player.play()
            self._play_btn.setText("⏸ Pause")
            self._stop_btn.setEnabled(True)

    def _stop_playback(self):
        self._player.stop()
        self._play_btn.setText("▶ Play")
        self._stop_btn.setEnabled(False)
        self._play_bar.setValue(0)

    def _load_recording(self):
        idx = self._rec_combo.currentIndex()
        recs = list_recordings(
            Path(self.cfg.get(
                "paths.iq_recordings", "recordings")))
        if 0 <= idx < len(recs):
            rec = recs[idx]
            if self._player.load(rec):
                self._player.on_samples(
                    self._on_samples)
                self._player.on_progress(
                    self._on_play_progress)
                self._player.on_end(
                    lambda: QTimer.singleShot(
                        0, self._stop_playback))
                self._set_freq(rec.center_hz)
                self._rec_status.setText(
                    f"Loaded: {rec.name}")
            else:
                QMessageBox.warning(
                    self, self.tr("Load Failed"),
                    self.tr("Recording file not found."))

    def _on_play_progress(self, pos_s: float,
                           dur_s: float):
        if dur_s > 0:
            pct = int(pos_s / dur_s * 100)
            QTimer.singleShot(0,
                lambda p=pct: self._play_bar.setValue(p))

    def _refresh_recordings(self):
        recs = list_recordings(
            Path(self.cfg.get(
                "paths.iq_recordings", "recordings")))
        self._rec_combo.clear()
        for r in recs:
            self._rec_combo.addItem(r.display_name)

    # ── Scanner ───────────────────────────────────────────────────────────

    def _start_scan(self):
        try:
            lo = int(float(
                self._scan_from.text()) * 1_000_000)
            hi = int(float(
                self._scan_to.text()) * 1_000_000)
        except ValueError:
            QMessageBox.warning(
                self, self.tr("Scanner"),
                self.tr("Invalid frequency range."))
            return
        self._scan_lo  = lo
        self._scan_hi  = hi
        self._scan_cur = lo
        self._scan_running = True
        interval = int(
            self._scan_dwell.value() * 1000)
        self._scan_timer.setInterval(interval)
        self._scan_timer.start()
        self._scan_start.setEnabled(False)
        self._scan_stop.setEnabled(True)

    def _stop_scan(self):
        self._scan_running = False
        self._scan_timer.stop()
        self._scan_start.setEnabled(True)
        self._scan_stop.setEnabled(False)

    def _scan_step(self):
        if not self._scan_running:
            return
        step = SDR_STEP_SIZES[self._step_idx]
        self._scan_cur += step
        if self._scan_cur > self._scan_hi:
            self._scan_cur = self._scan_lo
        self._set_freq(self._scan_cur)

    # ── TX ────────────────────────────────────────────────────────────────

    def _tx_iq_file(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Select IQ File"),
            str(Path(self.cfg.get(
                "paths.iq_recordings", "recordings"))),
            "SigMF Data (*.sigmf-data);;All (*)")
        if path:
            QMessageBox.information(
                self, self.tr("TX IQ"),
                self.tr(
                    "IQ file TX will be available in "
                    "a future update.\n"
                    "File selected: " +
                    Path(path).name))

    # ── Signal routing to Digital tab ────────────────────────────────────

    def set_decoder_callback(self, cb):
        """Set callback for routed IQ samples."""
        self._decoder_cb = cb

    # ── Help ──────────────────────────────────────────────────────────────

    def _identify_signal(self, bandwidth_hz: int,
                           freq_hz: int):
        """Identify signal at clicked frequency."""
        def _done(matches):
            from PyQt6.QtWidgets import QDialog, QVBoxLayout
            from PyQt6.QtWidgets import QTableWidget
            from PyQt6.QtWidgets import QTableWidgetItem
            from PyQt6.QtWidgets import QHeaderView
            from PyQt6.QtWidgets import QDialogButtonBox
            from PyQt6.QtCore import QTimer

            def _show(m=matches):
                if not m:
                    bw_k = bandwidth_hz / 1e3
                    fq_m = freq_hz / 1e6
                    QMessageBox.information(
                        self, self.tr("Signal ID"),
                        f"No match found for "
                        f"{bw_k:.1f} kHz bandwidth "
                        f"at {fq_m:.3f} MHz.\n\n"
                        "Try adjusting bandwidth selection.")
                    return

                dlg = QDialog(self)
                dlg.setWindowTitle(
                    self.tr("Signal Identification"))
                dlg.setMinimumWidth(500)
                lay = QVBoxLayout(dlg)

                bw_k = bandwidth_hz / 1e3
                fq_m = freq_hz / 1e6
                nm   = len(m)
                lbl = QLabel(
                    f"Bandwidth: {bw_k:.1f} kHz  "
                    f"Frequency: {fq_m:.3f} MHz\n"
                    f"Top {nm} matches from "
                    f"Artemis database:")
                lbl.setStyleSheet("color:#aaa;font-size:12px;")
                lay.addWidget(lbl)

                tbl = QTableWidget(len(m), 4)
                tbl.setHorizontalHeaderLabels([
                    "Signal", "Modulation",
                    "Bandwidth", "Confidence"])
                tbl.horizontalHeader().setSectionResizeMode(
                    0, QHeaderView.ResizeMode.Stretch)
                tbl.setEditTriggers(
                    QTableWidget.EditTrigger.NoEditTriggers)
                tbl.setStyleSheet(
                    "font-size:12px;font-family:'Courier New';")

                for row, match in enumerate(m):
                    tbl.setItem(row, 0,
                        QTableWidgetItem(match.name))
                    tbl.setItem(row, 1,
                        QTableWidgetItem(match.modulation))
                    tbl.setItem(row, 2,
                        QTableWidgetItem(
                            f"{match.bandwidth_hz/1e3:.1f} kHz"))
                    tbl.setItem(row, 3,
                        QTableWidgetItem(
                            f"{match.confidence*100:.0f}%"))

                lay.addWidget(tbl)
                btns = QDialogButtonBox(
                    QDialogButtonBox.StandardButton.Ok)
                btns.accepted.connect(dlg.accept)
                lay.addWidget(btns)
                dlg.exec()

            QTimer.singleShot(0, _show)

        get_identifier().identify_async(
            bandwidth_hz, freq_hz, _done)

    def _open_adsb_map(self):
        """Open dump1090 aircraft map in browser."""
        # Write receiver.json first so station shows on map
        if self.cfg:
            try:
                self.location_mgr.write_dump1090_receiver_json()
            except Exception:
                pass
        QDesktopServices.openUrl(
            QUrl("http://localhost:8080"))

    def _check_dump1090_status(self):
        """Check if dump1090 is running and update button."""
        import threading
        def _check():
            running = False
            try:
                # Checking local-only service (localhost)
                # Not user-supplied URL - safe to connect
                import urllib.request
                urllib.request.urlopen(  # nosec B310
                    "http://localhost:8080/data/aircraft.json",
                    timeout=1)
                running = True
            except Exception:
                pass
            QTimer.singleShot(0,
                lambda r=running: self._update_dump1090_btn(r))
        threading.Thread(target=_check, daemon=True).start()

    def _update_dump1090_btn(self, running: bool):
        if hasattr(self, '_adsb_map_btn'):
            if running:
                self._adsb_map_btn.setText(
                    "🗺  Open ADS-B Aircraft Map  ●")
                self._adsb_map_btn.setEnabled(True)
                self._adsb_map_btn.setToolTip(
                    "dump1090-fa is running\n"
                    "Your station marker is shown on the map.\n"
                    "Opens http://localhost:8080")
            else:
                self._adsb_map_btn.setText(
                    "🗺  Open ADS-B Map (dump1090 not running)")
                self._adsb_map_btn.setEnabled(False)
                self._adsb_map_btn.setToolTip(
                    "dump1090-fa is not running.\n"
                    "Configure path in Settings → Paths & Executables\n"
                    "then launch from the Paths dialog.")

    def _open_sdr_guide(self):
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(
            "https://github.com/dawardy/squelch"
            "/blob/main/README.md#sdr-setup"))

    # ── Public API ────────────────────────────────────────────────────────

    def set_center_freq_from_rig(self, hz: int):
        """Called by rig tab when VFO changes."""
        if self._current:
            self._set_freq(hz)


def _vsep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setStyleSheet("color:#1e1e1e;")
    f.setFixedWidth(1)
    return f


def _small_font():
    from PyQt6.QtGui import QFont
    f = QFont("Segoe UI")
    f.setPointSize(8)
    return f
