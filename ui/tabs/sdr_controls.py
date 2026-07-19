from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/tabs/sdr_controls.py

RX control-panel group builders for the SDR tab, extracted from sdr_tab.py
(HOUSE-CS complexity split): the Gain, Display, Span, and Demodulator group
boxes. These are pure widget construction — every control's valueChanged/
toggled signal connects to a handler that stays on SDRTab (resolved via self),
so the streaming/plot core is untouched.

`_SDRControlsMixin` is mixed into `SDRTab`. It creates the control widgets as
instance attributes (self._gain_slider, self._demod_bw, self._squelch_slider,
self._nr_slider, self._nb_slider, self._tx_grp, …) that the host's handlers
read/update. Initial values come from host state (self._squelch_db,
self._nr_level, self._nb_strength, self._center_hz) and self.cfg.

PALETTES is a module constant of ui.tabs.sdr_tab — imported lazily inside
_build_display_group to avoid an import cycle.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGroupBox, QGridLayout, QHBoxLayout, QVBoxLayout, QLabel,
    QSlider, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox, QPushButton,
)

from core.themes import get_theme as _sdr_get_theme


class _SDRControlsMixin:
    """Gain / Display / Span / Demodulator control-group builders."""

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
        self._agc_cb = QCheckBox(self.tr("AGC"))
        self._agc_cb.setToolTip(self.tr(
            "Hardware automatic gain control.\n"
            "OFF (default) = manual gain — recommended for weak-signal and\n"
            "digital decode/TX. ON lets the device ride gain automatically\n"
            "(manual gain is then ignored)."))
        self._agc_cb.toggled.connect(self._on_agc_toggle)
        gl.addWidget(self._agc_cb, 0, 3)
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
        from ui.tabs.sdr_tab import PALETTES
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
        dl.addWidget(QLabel(self.tr("Ref:")), 4, 0)
        self._ref_spin = QDoubleSpinBox()
        self._ref_spin.setRange(-200.0, 100.0)
        self._ref_spin.setValue(0.0)
        self._ref_spin.setSuffix(" dB")
        self._ref_spin.setSingleStep(1.0)
        self._ref_spin.setFixedWidth(90)
        self._ref_spin.setToolTip(self.tr(
            "Reference level offset (0 = dBFS).\n"
            "Set to your system's noise figure + gain\n"
            "to display approximate dBm on the Y axis."))
        self._ref_spin.valueChanged.connect(self._on_ref_level)
        dl.addWidget(self._ref_spin, 4, 1)
        self._ref_unit_lbl = QLabel("dBFS")
        self._ref_unit_lbl.setFixedWidth(40)
        dl.addWidget(self._ref_unit_lbl, 4, 2)
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
        self._wheel_bw_cb = QCheckBox(self.tr("↕=BW"))
        self._wheel_bw_cb.setToolTip(self.tr(
            "Mouse-wheel mapping on the spectrum / waterfall:\n"
            "  • Horizontal scroll: pan frequency (right = up, left = down)\n"
            "  • Vertical scroll: pan frequency (up = higher)\n"
            "  • Ctrl + scroll: zoom the span\n"
            "When checked, vertical scroll instead changes the IF bandwidth\n"
            "(up = wider, down = narrower)."))
        self._wheel_bw_cb.toggled.connect(
            lambda c: setattr(self, "_scroll_vert_bw", c))
        sl.addWidget(self._wheel_bw_cb)
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
        self._demod_combo.currentTextChanged.connect(self._on_demod_mode_change)
        deml.addWidget(self._demod_combo, 0, 1)
        self._auto_demod_cb = QCheckBox(self.tr("Auto"))
        self._auto_demod_cb.setToolTip(self.tr(
            "Auto-pick demod mode + bandwidth from the tuned frequency\n"
            "(WFM broadcast, AM airband/SW, NFM voice, SSB/CW on HF)"))
        self._auto_demod_cb.toggled.connect(
            lambda c: self._apply_auto_demod(self._center_hz) if c else None)
        deml.addWidget(self._auto_demod_cb, 0, 2)
        deml.addWidget(QLabel(self.tr("BW:")), 1, 0)
        self._demod_bw = QComboBox()
        self._demod_bw.addItems([
            "200 Hz", "500 Hz", "1 kHz", "2.5 kHz",
            "5 kHz", "10 kHz", "15 kHz", "200 kHz"])
        # Editable so any CUSTOM bandwidth works — type a value ("3.2 kHz") or
        # drag a passband edge; _bw_hz parses arbitrary "N Hz/kHz/MHz" text.
        self._demod_bw.setEditable(True)
        self._demod_bw.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._demod_bw.setCurrentText("10 kHz")
        self._demod_bw.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        deml.addWidget(self._demod_bw, 1, 1)
        # Manual override: hand-picking a mode/BW pauses Auto. activated[] fires
        # only on user interaction, not on programmatic setCurrentText, so
        # auto-applied changes don't trip it.
        self._demod_combo.activated.connect(self._on_manual_demod_pick)
        self._demod_bw.activated.connect(self._on_manual_demod_pick)
        # Redraw the passband indicator whenever the IF bandwidth changes
        # (manual pick, mode-default, auto-demod or restore) — previously the
        # passband only moved on tune, so BW changes were invisible.
        self._demod_bw.currentTextChanged.connect(self._on_bw_change)
        self._route_cb = QCheckBox(self.tr("Route to Digital tab"))
        self._route_cb.setToolTip(self.tr(
            "Pipe demodulated audio to the Digital "
            "Monitor tab for P25/DMR/NXDN decode"))
        self._route_cb.toggled.connect(
            lambda c: setattr(self, '_route_to_digital', c))
        deml.addWidget(self._route_cb, 2, 0, 1, 2)
        # Squelch row
        self._squelch_cb = QCheckBox(self.tr("Squelch"))
        self._squelch_cb.setToolTip(self.tr(
            "Suppress routing when signal is below threshold.\n"
            "Orange dashed line on spectrum shows threshold level."))
        self._squelch_cb.toggled.connect(self._on_squelch_toggle)
        deml.addWidget(self._squelch_cb, 3, 0)
        self._squelch_lbl = QLabel(f"{int(self._squelch_db):+d} dB")
        self._squelch_lbl.setFixedWidth(52)
        self._squelch_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        deml.addWidget(self._squelch_lbl, 3, 1)
        self._squelch_slider = QSlider(Qt.Orientation.Horizontal)
        self._squelch_slider.setRange(-120, 0)
        self._squelch_slider.setValue(int(self._squelch_db))
        self._squelch_slider.setEnabled(False)
        self._squelch_slider.valueChanged.connect(self._on_squelch_slider)
        deml.addWidget(self._squelch_slider, 4, 0, 1, 2)
        self._squelch_ind = QLabel("●")
        self._squelch_ind.setFixedWidth(16)
        self._squelch_ind.setToolTip(self.tr("Green = squelch open  Red = squelch closed"))
        deml.addWidget(self._squelch_ind, 3, 2)
        # Noise reduction row
        self._nr_cb = QCheckBox(self.tr("NR"))
        self._nr_cb.setToolTip(self.tr(
            "Spectral averaging noise reduction.\n"
            "Smooths the spectrum display noise floor.\n"
            "Higher values = stronger smoothing."))
        self._nr_cb.toggled.connect(self._on_nr_toggle)
        deml.addWidget(self._nr_cb, 5, 0)
        self._nr_lbl = QLabel(f"{self._nr_level}%")
        self._nr_lbl.setFixedWidth(36)
        self._nr_lbl.setAlignment(Qt.AlignmentFlag.AlignRight |
                                   Qt.AlignmentFlag.AlignVCenter)
        deml.addWidget(self._nr_lbl, 5, 1)
        self._nr_slider = QSlider(Qt.Orientation.Horizontal)
        self._nr_slider.setRange(0, 100)
        self._nr_slider.setValue(self._nr_level)
        self._nr_slider.setEnabled(False)
        self._nr_slider.valueChanged.connect(self._on_nr_slider)
        deml.addWidget(self._nr_slider, 6, 0, 1, 2)
        # Noise blanker row (time-domain impulse removal on IQ)
        self._nb_cb = QCheckBox(self.tr("NB"))
        self._nb_cb.setToolTip(self.tr(
            "Noise blanker — removes short impulsive noise (ignition,\n"
            "power-line arcs) from the IQ before demod. Higher = more\n"
            "aggressive. Leave off if it distorts strong signals."))
        self._nb_cb.toggled.connect(self._on_nb_toggle)
        deml.addWidget(self._nb_cb, 7, 0)
        self._nb_lbl = QLabel(f"{int(self._nb_strength * 100)}%")
        self._nb_lbl.setFixedWidth(36)
        self._nb_lbl.setAlignment(Qt.AlignmentFlag.AlignRight |
                                  Qt.AlignmentFlag.AlignVCenter)
        deml.addWidget(self._nb_lbl, 7, 1)
        self._nb_slider = QSlider(Qt.Orientation.Horizontal)
        self._nb_slider.setRange(0, 100)
        self._nb_slider.setValue(int(self._nb_strength * 100))
        self._nb_slider.setEnabled(False)
        self._nb_slider.valueChanged.connect(self._on_nb_slider)
        deml.addWidget(self._nb_slider, 8, 0, 1, 2)
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
