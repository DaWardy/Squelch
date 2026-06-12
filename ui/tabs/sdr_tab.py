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
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
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
    from sdr.audio_iq_source import (
        AudioIQSource, find_rig_audio_device,
        IQ_CAPABLE_RIGS)
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



from ui.tabs.sdr_setup_guide  import _SDRSetupGuideMixin
from ui.tabs.sdr_device_panels import _SDRDevicePanelsMixin
from ui.tabs.sdr_recording import _SDRRecordingMixin, _safe_recordings_path
from ui.tabs.sdr_scanner import _SDRScannerMixin
from ui.tabs.sdr_signal_id import _SDRSignalIDMixin


class SDRTab(SquelchPanel, _SDRSetupGuideMixin, _SDRDevicePanelsMixin,
             _SDRRecordingMixin, _SDRScannerMixin, _SDRSignalIDMixin, QWidget):
    panel_id    = "sdr"
    panel_title = "SDR"

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
        # Lazily-initialized RTL-TCP client (used when SoapySDR returns no
        # devices but rtl_tcp is running locally — common when the dongle
        # is already claimed by an rtl_tcp server).
        self._rtltcp_dev = None

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
        self._toolbar_add_device_group(lay)
        self._toolbar_add_freq_group(lay)
        self._toolbar_add_step_group(lay)
        self._toolbar_add_extras(lay)
        return bar

    def _toolbar_add_device_group(self, lay) -> None:
        lay.addWidget(QLabel(self.tr("Device:")))
        self._dev_combo = QComboBox()
        self._dev_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._dev_combo.setMinimumWidth(200)
        self._dev_combo.addItem(self.tr("— Scanning… —"))
        self._dev_combo.currentIndexChanged.connect(self._on_device_select)
        lay.addWidget(self._dev_combo)
        rescan_btn = QPushButton(self.tr("⟳"))
        rescan_btn.setFixedSize(26, 26)
        rescan_btn.setToolTip(self.tr("Rescan for SDR hardware"))
        rescan_btn.clicked.connect(self._enumerate_devices)
        lay.addWidget(rescan_btn)
        self._dev_type_lbl = QLabel("")
        self._dev_type_lbl.setStyleSheet(
            "color:#888;font-size:10px;font-family:'Courier New';")
        lay.addWidget(self._dev_type_lbl)
        self._connect_btn = QPushButton(self.tr("Connect"))
        self._connect_btn.setFixedWidth(80)
        self._connect_btn.setStyleSheet(
            "background:#1a3a1a;color:#3fbe6f;"
            "border:1px solid #3fbe6f;border-radius:4px;")
        self._connect_btn.clicked.connect(self._connect_sdr)
        lay.addWidget(self._connect_btn)
        self._sdr_status = QLabel("● Disconnected")
        self._sdr_status.setStyleSheet("font-family:'Courier New';")
        lay.addWidget(self._sdr_status)
        lay.addWidget(_vsep())

    def _toolbar_add_freq_group(self, lay) -> None:
        self._freq_edit = QLineEdit(f"{self._center_hz/1e6:.4f}")
        self._freq_edit.setFixedWidth(110)
        self._freq_edit.setStyleSheet(
            "background:#1a1a1a;color:#3fbe6f;"
            "font-family:'Courier New';"
            "border:1px solid #333;border-radius:3px;"
            "padding:2px 6px;")
        self._freq_edit.returnPressed.connect(self._on_freq_enter)
        lay.addWidget(self._freq_edit)
        self._freq_unit = QComboBox()
        self._freq_unit.addItems(["MHz", "kHz", "Hz"])
        self._freq_unit.setFixedWidth(55)
        lay.addWidget(self._freq_unit)
        lay.addWidget(_vsep())

    def _toolbar_add_step_group(self, lay) -> None:
        lay.addWidget(QLabel("Step:"))
        self._step_btns = []
        self._step_grp  = QButtonGroup(self)
        self._step_grp.setExclusive(True)
        for i, (hz, lbl) in enumerate(zip(SDR_STEP_SIZES, SDR_STEP_LABELS)):
            btn = QPushButton(lbl)
            btn.setCheckable(True)
            btn.setChecked(i == self._step_idx)
            btn.setFixedHeight(22)
            btn.setStyleSheet(
                "QPushButton{border:1px solid #222;border-radius:3px;"
                "background:#111;padding:0 4px;}"
                "QPushButton:checked{background:#1a3a1a;color:#3fbe6f;"
                "border-color:#3fbe6f;}"
                "QPushButton:hover{background:#1e2e1e;}")
            btn.clicked.connect(lambda _, idx=i: self._set_step(idx))
            self._step_btns.append(btn)
            self._step_grp.addButton(btn)
            lay.addWidget(btn)
        lay.addWidget(_vsep())

    def _toolbar_add_extras(self, lay) -> None:
        """TX indicator (hidden until TX hardware detected) + optional rig-tune button."""
        self._tx_indicator = QLabel("● TX")
        self._tx_indicator.setStyleSheet(
            "color:#cc4444;font-family:'Courier New';")
        self._tx_indicator.hide()
        lay.addWidget(self._tx_indicator)
        lay.addStretch()
        if self.rig:
            rig_btn = QPushButton(self.tr("← Rig Freq"))
            rig_btn.setFixedWidth(90)
            rig_btn.setToolTip(self.tr("Tune SDR to current rig frequency"))
            rig_btn.clicked.connect(self._tune_to_rig)
            lay.addWidget(rig_btn)

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
        wc_lay = QVBoxLayout(wf_container)
        wc_lay.setContentsMargins(0, 0, 0, 0)
        wc_lay.addWidget(self._wf_plot)
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
        self._spec_plot.getAxis("left").setWidth(40)
        self._spec_plot.setLabel(
            "left", "dBFS", color="#444", **{"font-size": "9px"})
        self._spec_curve = self._spec_plot.plot(
            pen=pg.mkPen("#3fbe6f", width=1))
        self._peak_curve = self._spec_plot.plot(
            pen=pg.mkPen("#ff8800", width=1, style=Qt.PenStyle.DotLine))
        self._peak_curve.hide()
        self._cf_line = pg.InfiniteLine(
            angle=90, movable=False,
            pen=pg.mkPen("#ff4444", width=1, style=Qt.PenStyle.DashLine))
        self._spec_plot.addItem(self._cf_line)
        self._level_region = pg.LinearRegionItem(
            values=[self._floor_db, self._ceiling_db],
            orientation='horizontal', movable=True,
            brush=pg.mkBrush(255, 255, 255, 8))
        self._level_region.sigRegionChanged.connect(self._on_level_region)
        self._spec_plot.addItem(self._level_region)
        self._spec_plot.scene().sigMouseClicked.connect(self._on_spec_click)
        self._spec_plot.wheelEvent = self._wheel_waterfall

    def _build_waterfall_plot(self) -> None:
        """Build self._wf_plot with image item and click/wheel handlers."""
        import threading
        self._wf_plot = pg.PlotWidget(background="#080808")
        self._wf_plot.setMenuEnabled(False)
        self._wf_plot.hideAxis("left")
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
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)
        scroll.setWidget(inner)
        lay.addWidget(self._build_gain_group())
        lay.addWidget(self._build_display_group())
        lay.addWidget(self._build_span_group())
        lay.addWidget(self._build_demod_group())
        lay.addStretch()
        return scroll

    def _build_gain_group(self) -> QGroupBox:
        gain_grp = QGroupBox(self.tr("Gain"))
        gl = QGridLayout(gain_grp)
        gl.setSpacing(4)
        gl.addWidget(QLabel(self.tr("RF Gain:")), 0, 0)
        self._gain_slider = QSlider(Qt.Orientation.Horizontal)
        self._gain_slider.setRange(0, 60)
        self._gain_slider.setValue(30)
        self._gain_slider.valueChanged.connect(self._on_gain)
        gl.addWidget(self._gain_slider, 0, 1)
        self._gain_lbl = QLabel("30 dB")
        self._gain_lbl.setStyleSheet(
            "color:#3fbe6f;font-family:'Courier New';")
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
        return gain_grp

    def _build_display_group(self) -> QGroupBox:
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
        self._floor_spin.valueChanged.connect(self._on_floor_ceiling)
        dl.addWidget(self._floor_spin, 0, 1)
        dl.addWidget(QLabel(self.tr("Ceiling:")), 1, 0)
        self._ceil_spin = QDoubleSpinBox()
        self._ceil_spin.setRange(-120, 20)
        self._ceil_spin.setValue(-20)
        self._ceil_spin.setSuffix(" dB")
        self._ceil_spin.setSingleStep(5)
        self._ceil_spin.setFixedWidth(90)
        self._ceil_spin.valueChanged.connect(self._on_floor_ceiling)
        dl.addWidget(self._ceil_spin, 1, 1)
        auto_btn = QPushButton(self.tr("Auto"))
        auto_btn.setFixedHeight(24)
        auto_btn.setToolTip(self.tr("Auto-set floor and ceiling"))
        auto_btn.clicked.connect(self._auto_range_set)
        dl.addWidget(auto_btn, 0, 2, 2, 1)
        dl.addWidget(QLabel(self.tr("Palette:")), 2, 0)
        self._palette_combo = QComboBox()
        self._palette_combo.addItems(list(PALETTES.keys()))
        self._palette_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._palette_combo.currentTextChanged.connect(self._on_palette)
        dl.addWidget(self._palette_combo, 2, 1, 1, 2)
        self._peak_cb = QCheckBox(self.tr("Peak hold"))
        self._peak_cb.toggled.connect(self._on_peak_hold)
        dl.addWidget(self._peak_cb, 3, 0, 1, 3)
        return disp_grp

    def _build_span_group(self) -> QGroupBox:
        span_grp = QGroupBox(self.tr("Span"))
        sl = QHBoxLayout(span_grp)
        self._span_combo = QComboBox()
        self._span_combo.addItems([
            "100 kHz", "500 kHz", "1 MHz", "2.4 MHz",
            "5 MHz", "10 MHz", "20 MHz"])
        self._span_combo.setCurrentText("2.4 MHz")
        self._span_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._span_combo.currentIndexChanged.connect(self._on_span)
        sl.addWidget(self._span_combo)
        return span_grp

    def _build_demod_group(self) -> QGroupBox:
        """Build demodulator group + TX sub-group (hidden for RX-only devices)."""
        demod_grp = QGroupBox(self.tr("Demodulator"))
        deml = QGridLayout(demod_grp)
        deml.setSpacing(4)
        deml.addWidget(QLabel(self.tr("Mode:")), 0, 0)
        self._demod_combo = QComboBox()
        self._demod_combo.addItems([
            "AM", "NFM", "WFM", "USB", "LSB", "CW", "Raw IQ"])
        self._demod_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        deml.addWidget(self._demod_combo, 0, 1)
        deml.addWidget(QLabel(self.tr("BW:")), 1, 0)
        self._demod_bw = QComboBox()
        self._demod_bw.addItems([
            "200 Hz", "500 Hz", "1 kHz", "2.5 kHz",
            "5 kHz", "10 kHz", "15 kHz", "200 kHz"])
        self._demod_bw.setCurrentText("10 kHz")
        self._demod_bw.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        deml.addWidget(self._demod_bw, 1, 1)
        self._route_cb = QCheckBox(self.tr("Route to Digital tab"))
        self._route_cb.setToolTip(self.tr(
            "Pipe demodulated audio to the Digital "
            "Monitor tab for P25/DMR/NXDN decode"))
        self._route_cb.toggled.connect(
            lambda c: setattr(self, '_route_to_digital', c))
        deml.addWidget(self._route_cb, 2, 0, 1, 2)
        # TX sub-group — hidden until TX-capable hardware is detected
        self._tx_grp = QGroupBox(self.tr("Transmit"))
        txl = QVBoxLayout(self._tx_grp)
        tx_warn = QLabel(self.tr(
            "⚠ Ensure you have appropriate\nlicense before transmitting."))
        tx_warn.setStyleSheet(
            f"color:{_sdr_get_theme(self.cfg.get('ui.theme','Dark')).warn_color};")
        txl.addWidget(tx_warn)
        tx_btn = QPushButton(self.tr("TX IQ File…"))
        tx_btn.clicked.connect(self._tx_iq_file)
        txl.addWidget(tx_btn)
        self._tx_grp.hide()
        deml.addWidget(self._tx_grp, 3, 0, 1, 2)
        return demod_grp

    def _build_bottom_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(90)
        bar.setStyleSheet(
            "background:#0d0d0d;"
            "border-top:1px solid #1a1a1a;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(8)
        lay.addWidget(self._build_recorder_group())
        lay.addWidget(self._build_scanner_group())
        lay.addWidget(self._build_recordings_group())
        lay.addStretch()
        self._refresh_recordings()
        return bar

    def _build_recorder_group(self) -> QGroupBox:
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
        self._rec_status.setStyleSheet("font-family:'Courier New';")
        rl.addWidget(self._rec_status)
        self._play_bar = QProgressBar()
        self._play_bar.setRange(0, 100)
        self._play_bar.setValue(0)
        self._play_bar.setFixedHeight(6)
        self._play_bar.setTextVisible(False)
        rl.addWidget(self._play_bar)
        return rec_grp

    def _build_scanner_group(self) -> QGroupBox:
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
            "border:1px solid #3fbe6f;border-radius:3px;")
        self._scan_start.clicked.connect(self._start_scan)
        self._scan_stop = QPushButton(self.tr("■ Stop"))
        self._scan_stop.setFixedHeight(24)
        self._scan_stop.setEnabled(False)
        self._scan_stop.clicked.connect(self._stop_scan)
        scan_btns.addWidget(self._scan_start)
        scan_btns.addWidget(self._scan_stop)
        scl.addLayout(scan_btns, 1, 3, 1, 3)
        return scan_grp

    def _build_recordings_group(self) -> QGroupBox:
        """Build the recordings library group (combo + load + browse buttons)."""
        lib_grp = QGroupBox(self.tr("Recordings"))
        ll = QVBoxLayout(lib_grp)
        self._rec_combo = QComboBox()
        self._rec_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._rec_combo.setMinimumWidth(200)
        ll.addWidget(self._rec_combo)
        self._load_rec_btn = QPushButton(self.tr("Load selected"))
        self._load_rec_btn.setFixedHeight(24)
        self._load_rec_btn.setToolTip(
            "Load the selected recording from Squelch's recordings folder")
        self._load_rec_btn.clicked.connect(self._load_recording)
        ll.addWidget(self._load_rec_btn)
        # Browse picks arbitrary .wav/.iq files outside the recordings folder
        self._browse_rec_btn = QPushButton(self.tr("Browse…"))
        self._browse_rec_btn.setFixedHeight(24)
        self._browse_rec_btn.setToolTip(
            "Open a .wav or .iq file from anywhere on disk")
        self._browse_rec_btn.clicked.connect(self._browse_recording)
        ll.addWidget(self._browse_rec_btn)
        return lib_grp

    # ── Device management ─────────────────────────────────────────────────

    def _enumerate_devices(self):
        """Enumerate SDR devices in background; always calls _populate_devices."""
        def _do():
            if not HAS_SOAPY:
                QTimer.singleShot(0, lambda: self._populate_devices([]))
                return
            try:
                log.info("SDR: enumerating devices via SoapySDR")
                devs = SoapyManager.enumerate()
                log.info(f"SDR: found {len(devs)} device(s)")
            except Exception as e:
                log.warning(f"SDR: enumerate failed: {e}")
                devs = []
            QTimer.singleShot(0, lambda d=devs: self._populate_devices(d))
        # Update status so user can see a scan is in progress
        if hasattr(self, "_dev_combo"):
            self._dev_combo.clear()
            self._dev_combo.addItem(self.tr("— Scanning… —"))
        threading.Thread(target=_do, daemon=True, name="SDREnum").start()

    def _populate_devices(self, devices: list):
        self._devices = devices
        self._dev_combo.clear()
        if hasattr(self, "_dev_type_lbl"):
            self._dev_type_lbl.setText("")
        # Fallback: RTL-TCP running but SoapySDR can't claim the device
        if not devices and HAS_RTLTCP and rtltcp_is_running():
            self._dev_combo.addItem(
                self.tr("RTL-TCP server  (127.0.0.1:1234)"))
            self._devices = [None]
            self._dev_combo.setCurrentIndex(0)
            if hasattr(self, "_dev_type_lbl"):
                self._dev_type_lbl.setText("RTL-TCP")
            log.info("SDR: SoapySDR found 0 devices, rtl_tcp running — using RTL-TCP")
            return
        if not devices:
            self._dev_combo.addItem(self.tr("No SDR devices found — click ⟳ to rescan"))
            if hasattr(self, "_dev_type_lbl"):
                self._dev_type_lbl.setText("none")
            return
        for dev in devices:
            self._dev_combo.addItem(dev.display_name)
        self._dev_combo.setCurrentIndex(0)
        # Show driver type for first device
        self._update_dev_type_label(0)

    def _update_dev_type_label(self, index: int) -> None:
        """Show driver/hardware type for selected device."""
        if not hasattr(self, "_dev_type_lbl"):
            return
        if not self._devices or index < 0 or index >= len(self._devices):
            self._dev_type_lbl.setText("")
            return
        dev = self._devices[index]
        if dev is None:
            self._dev_type_lbl.setText("RTL-TCP")
            return
        # SDRDevice has a 'driver' or 'hardware' attribute from SoapySDR
        driver = (getattr(dev, "driver", "")
                  or getattr(dev, "hardware", "")
                  or "").upper()
        # Map common driver keys to friendly names
        _DRIVER_NAMES = {
            "RTL":    "RTL-SDR",
            "RTLSDR": "RTL-SDR",
            "AIRSPY": "Airspy",
            "SDRPLAY": "SDRplay RSP",
            "RSP": "SDRplay RSP",
            "UHD": "USRP (UHD)",
            "HACKRF": "HackRF",
            "LIME": "LimeSDR",
            "XTRX": "XTRX",
            "AUDIO": "Audio IQ",
            "REMOTE": "SoapyRemote",
        }
        label = next((v for k, v in _DRIVER_NAMES.items()
                      if k in driver), driver or "Unknown")
        self._dev_type_lbl.setText(label)

    def _build_audio_mode_group(self):
        """Build Input Mode GroupBox; sets self._audio_mode_btns. Returns group."""
        from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QRadioButton, QButtonGroup
        grp = QGroupBox("Input Mode")
        lay = QVBoxLayout(grp)
        self._audio_mode_btns = QButtonGroup()
        rb_mono = QRadioButton("Mono Audio  —  rig USB audio, standard receive")
        rb_mono.setChecked(True)
        rb_mono.setToolTip(
            "Use the rig's demodulated audio output\n"
            "Bandwidth: ~3 kHz SSB, ~15 kHz FM\n"
            "Works with IC-7100, FT-991A, TS-2000, any USB rig")
        self._audio_mode_btns.addButton(rb_mono, 0)
        lay.addWidget(rb_mono)
        rb_iq = QRadioButton("IQ Stereo  —  L=I, R=Q (FUNcube, IC-7300 IQ mode)")
        rb_iq.setToolTip(
            "True complex IQ from a stereo source\n"
            "Bandwidth: up to 192 kHz depending on soundcard\n"
            "Supported: IC-7300/7610/705 (IQ mode), FUNcube Dongle, Softrock")
        self._audio_mode_btns.addButton(rb_iq, 1)
        lay.addWidget(rb_iq)
        return grp

    def _build_audio_device_form(self):
        """Build device + sample-rate form. Returns (layout, dev_combo, sr_combo)."""
        from PyQt6.QtWidgets import QFormLayout, QComboBox
        from sdr.audio_iq_source import AudioIQSource
        f = QFormLayout()
        dev_combo = QComboBox()
        dev_combo.addItem("Default (system default input)")
        try:
            for d in AudioIQSource.enumerate_inputs():
                dev_combo.addItem(
                    f"{d['name']}  ({d['channels']}ch, {d['default_sr']}Hz)")
        except Exception:
            pass
        rig_model = self.cfg.get("rig.selected_model", "") if self.cfg else ""
        rig_dev   = find_rig_audio_device(rig_model)
        if rig_dev:
            for i in range(dev_combo.count()):
                if rig_dev[:10].lower() in dev_combo.itemText(i).lower():
                    dev_combo.setCurrentIndex(i)
                    break
        dev_combo.setToolTip(
            "For IC-7100: USB Audio CODEC\n"
            "For IC-7300 IQ: USB Audio CODEC (stereo, 192kHz)")
        f.addRow("Audio Device:", dev_combo)
        sr_combo = QComboBox()
        sr_combo.addItems(["48000 Hz  (standard)", "96000 Hz",
                           "192000 Hz  (IQ mode, IC-7300)"])
        f.addRow("Sample Rate:", sr_combo)
        return f, dev_combo, sr_combo

    def _open_audio_source_dialog(self):
        """Open dialog to configure rig audio as SDR input."""
        if not HAS_AUDIO_SRC:
            QMessageBox.warning(
                self, "sounddevice Required",
                "pip install sounddevice\n\n"
                "sounddevice is needed to use rig audio input.")
            return

        from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QVBoxLayout)
        dlg = QDialog(self)
        dlg.setWindowTitle("Rig Audio Input")
        dlg.setMinimumWidth(420)
        root = QVBoxLayout(dlg)
        root.addWidget(self._build_audio_mode_group())
        form, dev_combo, sr_combo = self._build_audio_device_form()
        root.addLayout(form)
        iq_note = QLabel(
            "IQ-capable rigs:\n"
            "  IC-7300/7610/705: SET → Connectors → USB Send/Keying → IQ 192kHz\n"
            "  FUNcube Dongle Pro+: always IQ — just select it\n"
            "  Softrock / SDR-Kits: IQ Stereo with any soundcard")
        iq_note.setStyleSheet(
            "font-family:'Courier New';background:#0a0a0a;padding:8px;"
            "border:1px solid #1a1a1a;border-radius:3px;")
        iq_note.setWordWrap(True)
        root.addWidget(iq_note)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        root.addWidget(btns)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        mode_str = "iq_stereo" if self._audio_mode_btns.checkedId() == 1 else "mono"
        dev_name = dev_combo.currentText().split("  (")[0].strip()
        if dev_name.startswith("Default"):
            dev_name = "Default"
        sr = {0: 48000, 1: 96000, 2: 192000}[sr_combo.currentIndex()]
        self._start_audio_source(dev_name, mode_str, sr)

    def _start_audio_source(self, device: str,
                              mode: str,
                              sample_rate: int):
        """Start AudioIQSource and route into the waterfall."""
        if not HAS_AUDIO_SRC:
            return

        # Stop any existing source
        if hasattr(self, "_audio_src") and                 self._audio_src:
            self._audio_src.stop()

        from sdr.audio_iq_source import AudioIQSource
        src = AudioIQSource()
        src.set_device(device)
        src.set_mode(mode)
        src.set_sample_rate(sample_rate)

        # Sync center freq from rig if available
        center = 0
        if self.cfg:
            center = int(
                self.cfg.get("rig.freq_hz", 0) or 0)
        src.set_center_hz(center)
        src.on_samples = self._on_samples

        if src.start():
            self._audio_src   = src
            self._sdr_status.setText(
                f"● Audio: {device[:20]}")
            self._sdr_status.setStyleSheet(
                "color:#3fbe6f;"
                "font-weight:bold;")
            # Update center when rig tunes
            self._audio_center_update = True
            log.info(
                f"Audio source started: "
                f"{device} {mode} {sample_rate}Hz")
        else:
            QMessageBox.warning(
                self, "Audio Source Failed",
                f"Could not open audio device:\n{device}\n\n"
                "Check the device is connected and not in use.")
            self._audio_src = None

    def _on_device_select(self, idx: int):
        self._update_dev_type_label(idx)
        if 0 <= idx < len(self._devices):
            dev = self._devices[idx]
            if dev is None:
                return   # RTL-TCP sentinel — no SoapySDR device object
            # Show TX controls only for TX hardware
            self._tx_grp.setVisible(getattr(dev, "can_tx", False))
            self._tx_indicator.setVisible(getattr(dev, "can_tx", False))
            # Adjust span to hardware limits
            if hasattr(dev, "recommended_span"):
                self._span_hz = dev.recommended_span
                self._manager.set_sample_rate(dev.recommended_span)
            # Show device-specific settings panel
            self._build_device_panel(dev)

    def _build_device_panel(self, dev):
        """
        Show hardware-specific controls for the selected device.
        HackRF: amp, bias-tee, LNA/VGA split
        USRP B200/B210: clock source, subdev, channel
        RTL-SDR: direct sampling, bias-tee
        """
        from sdr.soapy_device import DEVICE_PROFILES
        profile = DEVICE_PROFILES.get(
            dev.driver.lower(), {})

        # Clear old panel
        if hasattr(self, "_dev_panel") and                 self._dev_panel:
            self._dev_panel.setVisible(False)
            self._dev_panel.deleteLater()
            self._dev_panel = None

        driver = dev.driver.lower()

        if driver == "hackrf":
            self._dev_panel = self._hackrf_panel()
        elif driver == "uhd":
            self._dev_panel = self._usrp_panel()
        elif driver == "rtlsdr":
            self._dev_panel = self._rtlsdr_panel()
        elif driver == "sdrplay":
            # Detect exact RSP model from device label
            from sdr.soapy_device import detect_rsp_model
            model = detect_rsp_model(dev.label)
            self._dev_panel = self._sdrplay_panel(model)
        else:
            self._dev_panel = None
            return

        # Insert into the controls layout
        if hasattr(self, "_controls_layout"):
            self._controls_layout.addWidget(
                self._dev_panel)





    # ── SDRplay control callbacks ──────────────────────────










    # ── Device control callbacks ───────────────────────────










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
                ""
                "font-family:'Courier New';")
            return

        dev = self._devices[idx]
        self._connect_btn.setEnabled(False)
        self._connect_btn.setText(self.tr("Connecting…"))

        # Sentinel from _populate_devices: connect to the local rtl_tcp
        # server instead of opening a SoapySDR device.
        if dev is None:
            def _do_rtltcp():
                ok = False
                try:
                    if not self._rtltcp_dev:
                        self._rtltcp_dev = RTLTCPDevice()
                    if self._rtltcp_dev.open():
                        self._rtltcp_dev.on_samples(self._on_samples)
                        self._rtltcp_dev.start_rx()
                        ok = True
                except Exception as e:
                    log.error(f"RTL-TCP connect failed: {e}")
                from types import SimpleNamespace
                fake = SimpleNamespace(
                    display_name="RTL-TCP @ 127.0.0.1:1234")
                QTimer.singleShot(0,
                    lambda o=ok, d=fake: self._on_connected(o, d))
            threading.Thread(target=_do_rtltcp, daemon=True).start()
            return

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
                "color:#3fbe6f;"
                "font-family:'Courier New';")
            self._current = dev
            self._manager.start_rx()
            self._update_axes()
            self._draw_band_segments()
        else:
            self._connect_btn.setText(self.tr("Connect"))
            self._sdr_status.setText("● Error")
            self._sdr_status.setStyleSheet(
                "color:#cc4444;"
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
                "color:#cc4444;"
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
