from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/tabs/sdr_audio_source.py

Rig-audio-as-SDR-input support for the SDR tab, extracted from sdr_tab.py
(HOUSE-CS complexity split): the "Rig Audio Input" dialog (mono / IQ-stereo
mode + device + sample-rate selection) and starting an AudioIQSource that
feeds the waterfall via the host's _on_samples callback.

`_SDRAudioSourceMixin` is mixed into `SDRTab`. It relies on host-class state:
  * self.cfg          — Config (rig model + freq for center sync)
  * self._on_samples  — the streaming/plot callback (stays on the host)
  * self._sdr_status  — status label widget
  * self._audio_src / self._audio_center_update  — audio-source runtime state

HAS_AUDIO_SRC is a module flag of ui.tabs.sdr_tab — imported lazily inside the
methods to avoid an import cycle; find_rig_audio_device is only reached when
audio support is present, so it is imported locally alongside AudioIQSource.
"""

import logging

from PyQt6.QtWidgets import QMessageBox

log = logging.getLogger(__name__)


class _SDRAudioSourceMixin:
    """Configure and start rig USB audio (mono / IQ stereo) as the SDR input."""

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
        from sdr.audio_iq_source import AudioIQSource, find_rig_audio_device
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
        from ui.tabs.sdr_tab import HAS_AUDIO_SRC
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
        from ui.tabs.sdr_tab import HAS_AUDIO_SRC
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
