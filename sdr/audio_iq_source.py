from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- sdr/audio_iq_source.py
Use a rig's audio output as an SDR input source.

Three modes:

1. MONO AUDIO (IC-7100 USB, any soundcard)
   Left channel only → power spectrum of demodulated audio.
   Good for digital decode routing and audio monitoring.
   Sample rate: 8–48 kHz, bandwidth ~3–15 kHz.

2. IQ STEREO (software-defined radios with I/Q audio output)
   Left channel = I (in-phase), Right channel = Q (quadrature).
   Gives a true complex IQ stream → full waterfall around 0 Hz.
   Used by: FUNcube Dongle, some SDRs in "IQ mode".
   Sample rate: typically 48–192 kHz.

3. IF PANADAPTER (rig IF tap → SDR dongle)
   This mode is NOT handled here — the IF goes into the
   RTLTCPDevice or SoapyDevice at the IF frequency (e.g.
   IC-7100 second IF = 36.135 MHz). The SDR tab handles it
   transparently when you tune to the IF frequency.

Usage:
    src = AudioIQSource()
    src.set_device("USB Audio CODEC")   # rig audio device
    src.set_mode("mono")                # or "iq_stereo"
    src.set_sample_rate(48000)
    src.on_samples = my_callback        # same signature as SoapySDR
    src.start()
    ...
    src.stop()
"""

import logging
from typing import Callable, Optional

log = logging.getLogger(__name__)

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import sounddevice as sd
    HAS_SD = True
except ImportError:
    HAS_SD = False


class AudioIQSource:
    """
    Soundcard-based IQ source.
    Works with any audio input device — USB rig audio,
    FUNcube Dongle, Softrock, panadapter audio output, etc.
    """

    MODES = {
        "mono":      "Mono audio → power spectrum of RX audio",
        "iq_stereo": "Stereo I/Q → full complex waterfall (L=I, R=Q)",
    }

    def __init__(self):
        self._device      = None   # None = system default
        self._mode        = "mono"
        self._sample_rate = 48000
        self._blocksize   = 2048
        self._stream      = None
        self._running     = False
        self._center_hz   = 0      # for IQ mode, DC offset
        self._on_samples: Optional[Callable] = None

    # ── Configuration ─────────────────────────────────────────────────

    def set_device(self, name: str):
        """Set audio input device by name substring."""
        self._device = name if name != "Default" else None

    def set_mode(self, mode: str):
        """
        Set input mode:
          "mono"      — rig USB audio, any mono source
          "iq_stereo" — L=I, R=Q (FUNcube, Softrock, etc.)
        """
        if mode not in self.MODES:
            raise ValueError(
                f"Unknown mode: {mode}. "
                f"Options: {list(self.MODES)}")
        self._mode = mode

    def set_sample_rate(self, rate: int):
        self._sample_rate = int(rate)

    def set_center_hz(self, hz: int):
        """
        Center frequency hint.
        In mono mode: the rig's current tuned frequency.
        In IQ stereo: the SDR's center frequency.
        Passed through to the samples callback so the
        waterfall can label its X axis correctly.
        """
        self._center_hz = int(hz)

    @property
    def on_samples(self) -> Optional[Callable]:
        return self._on_samples

    @on_samples.setter
    def on_samples(self, cb: Callable):
        self._on_samples = cb

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def display_name(self) -> str:
        dev  = self._device or "Default Audio"
        mode = "IQ Stereo" if self._mode == "iq_stereo" \
               else "Mono Audio"
        return f"{dev} ({mode}, {self._sample_rate}Hz)"

    # ── Lifecycle ─────────────────────────────────────────────────────

    def start(self) -> bool:
        if not HAS_SD:
            log.warning(
                "sounddevice not installed — "
                "pip install sounddevice")
            return False
        if not HAS_NUMPY:
            log.warning("numpy not installed")
            return False

        channels = 2 if self._mode == "iq_stereo" else 1
        try:
            # Resolve device index
            dev_idx = self._resolve_device(channels)

            self._stream = sd.InputStream(
                device     = dev_idx,
                samplerate = self._sample_rate,
                channels   = channels,
                dtype      = "float32",
                blocksize  = self._blocksize,
                callback   = self._audio_callback)
            self._stream.start()
            self._running = True
            log.info(
                f"AudioIQSource started: "
                f"{self.display_name}")
            return True
        except Exception as e:
            log.warning(f"AudioIQSource start: {e}")
            return False

    def stop(self):
        self._running = False
        try:
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None
        except Exception:
            pass

    # ── Audio callback ────────────────────────────────────────────────

    def _audio_callback(self, indata, frames,
                         time_info, status):
        """Called by sounddevice for each audio block."""
        if status:
            log.debug(f"AudioIQ status: {status}")
        if self._on_samples is None:
            return

        try:
            if self._mode == "iq_stereo":
                # Stereo: L=I, R=Q → complex64
                if indata.shape[1] >= 2:
                    samples = (indata[:, 0] +
                               1j * indata[:, 1]
                               ).astype(np.complex64)
                else:
                    # Fallback to mono if stereo not available
                    samples = indata[:, 0].astype(
                        np.complex64)
            else:
                # Mono: real audio → treat as real-valued IQ
                # (imaginary part = 0; Hilbert would be ideal
                # but adds complexity and latency)
                mono = indata[:, 0].astype(np.float32)
                samples = mono.astype(np.complex64)

            self._on_samples(
                samples,
                self._sample_rate,
                self._center_hz)

        except Exception as e:
            log.debug(f"AudioIQ callback: {e}")

    # ── Device resolution ─────────────────────────────────────────────

    def _resolve_device(self,
                         channels: int) -> Optional[int]:
        """
        Find sounddevice index for the requested device name.
        Returns None for system default.
        """
        if not self._device:
            return None
        try:
            devices = sd.query_devices()
            name_lower = self._device.lower()
            for i, d in enumerate(devices):
                if d["max_input_channels"] >= channels:
                    if name_lower in d["name"].lower():
                        log.debug(
                            f"AudioIQ device: {d['name']}")
                        return i
            log.warning(
                f"AudioIQ: device not found: "
                f"'{self._device}' — using default")
        except Exception as e:
            log.debug(f"AudioIQ device lookup: {e}")
        return None

    @staticmethod
    def enumerate_inputs() -> list[dict]:
        """List all available audio input devices."""
        if not HAS_SD:
            return []
        try:
            result = []
            for i, d in enumerate(sd.query_devices()):
                if d["max_input_channels"] > 0:
                    result.append({
                        "index":    i,
                        "name":     d["name"],
                        "channels": d["max_input_channels"],
                        "default_sr": int(
                            d["default_samplerate"]),
                    })
            return result
        except Exception:
            return []


# ── Rig audio hints ────────────────────────────────────────────────────────

# Known rig USB audio device name substrings
RIG_AUDIO_HINTS = {
    "IC-7100":   ["USB Audio CODEC", "CP210"],
    "IC-7300":   ["USB Audio CODEC"],  # also IQ capable
    "IC-7610":   ["USB Audio CODEC"],  # true IQ via USB
    "FT-991A":   ["USB Audio CODEC", "FT-991"],
    "TS-2000":   ["USB Audio CODEC", "USB-IF"],
    "FUNcube":   ["FUNcube", "Fun Cube"],
    "RSP2Pro":   [],  # uses SoapySDR, not audio
    "Generic":   ["Line In", "Microphone", "Stereo Mix"],
}

IQ_CAPABLE_RIGS = {
    "IC-7300":  "USB IQ output available — set in menu",
    "IC-7610":  "Native IQ via USB at up to 192 kHz",
    "IC-705":   "USB IQ output available",
    "FUNcube Dongle": "Native IQ stereo, 192 kHz",
}


def find_rig_audio_device(rig_model: str) -> Optional[str]:
    """
    Try to find the audio input device for a given rig.
    Returns device name string or None.
    """
    if not HAS_SD:
        return None
    hints = RIG_AUDIO_HINTS.get(rig_model, [])
    if not hints:
        return None  # rig uses SoapySDR or has no audio path
    try:
        for d in sd.query_devices():
            if d["max_input_channels"] < 1:
                continue
            name = d["name"].lower()
            for hint in hints:
                if hint.lower() in name:
                    return d["name"]
    except Exception:
        pass
    return None
