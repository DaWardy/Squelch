from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/tabs/sdr_toolbar.py

Top-toolbar construction for the SDR tab, extracted from sdr_tab.py
(HOUSE-CS complexity split): the device/connect group, frequency entry,
step-size buttons, the extras (TX indicator, screenshot, → Monitor export,
rig-audio, rig-tune), and the screenshot save.

`_SDRToolbarMixin` is mixed into `SDRTab`. Every button connects to a handler
that stays on SDRTab or one of its other mixins (resolved via self); this mixin
only builds the widgets (self._dev_combo, self._freq_edit, self._step_btns,
self._connect_btn, self._sdr_status, self._tx_indicator, …).

_vsep / SDR_STEP_SIZES / SDR_STEP_LABELS are module-level in ui.tabs.sdr_tab —
imported lazily inside the methods to avoid an import cycle.
"""

from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QComboBox, QPushButton, QLineEdit,
)


class _SDRToolbarMixin:
    """Builds the SDR tab's top toolbar (device / freq / step / extras)."""

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
        from ui.tabs.sdr_tab import _vsep
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
        from ui.tabs.sdr_tab import _vsep
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
        # AdjustToContents + a minimum so the unit text (e.g. "MHz") is never
        # clipped to "MI…" by a too-narrow fixed width.
        self._freq_unit.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._freq_unit.setMinimumWidth(64)
        lay.addWidget(self._freq_unit)
        lay.addWidget(_vsep())

    def _toolbar_add_step_group(self, lay) -> None:
        """Tuning-step selector — a compact dropdown (HDSDR-style) rather than
        a row of nine buttons that ate toolbar width."""
        from ui.tabs.sdr_tab import SDR_STEP_LABELS
        lay.addWidget(QLabel(self.tr("Step:")))
        self._step_combo = QComboBox()
        self._step_combo.addItems(SDR_STEP_LABELS)
        self._step_combo.setCurrentIndex(self._step_idx)
        self._step_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._step_combo.setToolTip(self.tr(
            "Tuning step for the ◄ ► keys and the mouse wheel"))
        self._step_combo.currentIndexChanged.connect(self._set_step)
        lay.addWidget(self._step_combo)

    def _toolbar_add_extras(self, lay) -> None:
        """TX indicator (hidden until TX hardware detected) + rig-tune + audio buttons."""
        self._tx_indicator = QLabel("● TX")
        self._tx_indicator.setStyleSheet(
            "color:#cc4444;font-family:'Courier New';")
        self._tx_indicator.hide()
        lay.addWidget(self._tx_indicator)
        lay.addStretch()
        shot_btn = QPushButton(self.tr("📸"))
        shot_btn.setFixedWidth(32)
        shot_btn.setToolTip(self.tr(
            "Save spectrum+waterfall screenshot to Desktop"))
        shot_btn.clicked.connect(self._save_screenshot)
        lay.addWidget(shot_btn)
        rflab_btn = QPushButton(self.tr("→ Monitor"))
        rflab_btn.setFixedWidth(76)
        rflab_btn.setToolTip(self.tr(
            "Export signal bookmarks to Monitor frequency watchlist"))
        rflab_btn.clicked.connect(self._export_to_rf_lab)
        lay.addWidget(rflab_btn)
        audio_btn = QPushButton(self.tr("🎙 Rig Audio"))
        audio_btn.setFixedWidth(96)
        audio_btn.setToolTip(self.tr(
            "Use rig or soundcard audio as SDR input\n"
            "Works without SoapySDR — IC-7100, FT-991A, any USB rig\n"
            "IQ Stereo mode: IC-7300/7610/705, FUNcube Dongle"))
        audio_btn.clicked.connect(self._open_audio_source_dialog)
        lay.addWidget(audio_btn)
        if self.rig:
            rig_btn = QPushButton(self.tr("← Rig Freq"))
            rig_btn.setFixedWidth(90)
            rig_btn.setToolTip(self.tr("Tune SDR to current rig frequency"))
            rig_btn.clicked.connect(self._tune_to_rig)
            lay.addWidget(rig_btn)

    def _save_screenshot(self) -> None:
        """Grab the visible SDR tab and save as a timestamped PNG."""
        from pathlib import Path
        from PyQt6.QtCore import QDateTime
        ts = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
        fname = f"squelch_sdr_{ts}.png"
        out_dir = next(
            (p for p in (Path.home() / "Desktop", Path.home() / "Downloads")
             if p.exists()),
            Path.home())
        out = out_dir / fname
        pixmap = self.grab()
        if pixmap.save(str(out)):
            try:
                self.window().statusBar().showMessage(
                    f"Screenshot saved: {out}", 5000)
            except Exception:
                pass
        else:
            try:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self, "Screenshot failed",
                    f"Could not save to {out}")
            except Exception:
                pass
