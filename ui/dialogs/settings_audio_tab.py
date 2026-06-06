from __future__ import annotations
"""SettingsDialog audio tab — extracted from settings_dialog.py."""
from PyQt6.QtWidgets import (QWidget, QFormLayout, QScrollArea, QFrame,
    QLabel, QLineEdit, QComboBox, QSpinBox, QCheckBox, QHBoxLayout,
    QVBoxLayout, QPushButton, QGroupBox, QDoubleSpinBox)
from PyQt6.QtCore import Qt

def _scrolled() -> QWidget:
    """Return a plain widget (most tabs don't need scrolling)."""
    return QWidget()


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(
        "color:#1a1a1a;margin:4px 0;")
    return f


def _section(form: QFormLayout, title: str):
    lbl = QLabel(title)
    lbl.setStyleSheet(
        "color:#3fbe6f;"
        "font-weight:bold;margin-top:8px;")
    form.addRow(lbl)


def _flatten(d: dict, prefix: str = "") -> dict:
    result = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result.update(_flatten(v, key))
        else:
            result[key] = v
    return result



class _SettingsAudioTab:
    """Mixed into SettingsDialog."""

    def _tab_audio(self) -> QWidget:
        w = _scrolled()
        f = QFormLayout(w)
        f.setSpacing(10)
        f.setContentsMargins(16, 16, 16, 16)

        _section(f, "Digital Mode Audio (FT8/FT4/WSPR)")

        # Refresh device list
        self._refresh_audio_btn = QPushButton(
            "↺ Refresh Device List")
        self._refresh_audio_btn.setFixedWidth(180)
        self._refresh_audio_btn.clicked.connect(
            self._refresh_audio_devices)
        f.addRow("", self._refresh_audio_btn)

        self._audio_input = QComboBox()
        self._audio_input.setEditable(True)
        self._audio_input.setToolTip(
            "Input from radio to PC (e.g. VB-Cable / SignaLink)")
        f.addRow("Audio Input:", self._audio_input)

        self._audio_output = QComboBox()
        self._audio_output.setEditable(True)
        self._audio_output.setToolTip(
            "Output from PC to radio")
        f.addRow("Audio Output:", self._audio_output)

        self._audio_sample_rate = QComboBox()
        self._audio_sample_rate.addItems([
            "48000 Hz (recommended)",
            "44100 Hz",
            "96000 Hz",
        ])
        f.addRow("Sample Rate:", self._audio_sample_rate)

        f.addRow(_sep())
        _section(f, "Digital Voice Audio (DSD+ / OP25)")

        self._digital_input = QComboBox()
        self._digital_input.setEditable(True)
        self._digital_input.setToolTip(
            "Audio from SDR or rig for P25/DMR decode")
        f.addRow("Decode Input:", self._digital_input)

        self._digital_output = QComboBox()
        self._digital_output.setEditable(True)
        self._digital_output.setToolTip(
            "Speaker output for decoded voice")
        f.addRow("Voice Output:", self._digital_output)

        # Populate with known devices
        self._refresh_audio_devices()

        return w

