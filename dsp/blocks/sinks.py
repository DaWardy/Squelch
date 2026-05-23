from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- dsp/blocks/sinks.py
Signal sink blocks: audio out, file, waterfall display, null.
"""

import logging
from pathlib import Path
from typing import Callable

from dsp.block import SinkBlock, PortDef, PortType, ParamDef
from dsp.registry import register

log = logging.getLogger(__name__)

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


@register
class AudioSink(SinkBlock):
    """
    Play audio through sounddevice / system audio.
    Connect after an FM, AM, or SSB demodulator.
    Input: F32 mono or F32S stereo audio
    """
    key         = "audio_sink"
    name        = "Audio Sink (Speakers)"
    description = "Play demodulated audio through system speakers"
    color       = "#1a2a1a"

    inputs = [PortDef("in", PortType.F32,
                      help="Float audio samples")]
    params = [
        ParamDef("sample_rate", "Sample Rate",
                 "int",  48000,
                 choices=[8000, 11025, 22050,
                          44100, 48000, 96000],
                 units="Hz"),
        ParamDef("device",      "Output Device",
                 "str",  "Default",
                 help="Audio output device name"),
        ParamDef("volume",      "Volume",
                 "float", 0.8,
                 min_val=0.0, max_val=1.0),
        ParamDef("buffer_ms",   "Buffer (ms)",
                 "int",   100,
                 min_val=10, max_val=2000,
                 help="Audio buffer size in milliseconds"),
    ]

    def __init__(self):
        super().__init__()
        self._stream  = None
        self._buf     = []

    def start(self) -> bool:
        try:
            import sounddevice as sd
            sr     = self.get("sample_rate", 48000)
            device = self.get("device",      "Default")
            dev    = None if device == "Default" else device
            self._stream = sd.OutputStream(
                samplerate = sr,
                channels   = 1,
                dtype      = "float32",
                device     = dev,
                blocksize  = sr // 10)
            self._stream.start()
            self._running = True
            log.info(f"AudioSink started: {sr}Hz")
            return True
        except ImportError:
            self._error = ("sounddevice not installed. "
                           "pip install sounddevice")
            log.warning(self._error)
            return False
        except Exception as e:
            self._error = str(e)
            log.warning(f"AudioSink start: {e}")
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

    def consume(self, inputs: dict):
        data = inputs.get("in")
        if data is None or self._stream is None:
            return
        if not HAS_NUMPY:
            return
        vol = self.get("volume", 0.8)
        audio = np.clip(data * vol, -1.0, 1.0
                        ).astype(np.float32)
        try:
            self._stream.write(audio)
        except Exception as e:
            log.debug(f"AudioSink write: {e}")


@register
class IQFileSink(SinkBlock):
    """
    Write raw IQ samples to a file for later playback.
    Format: complex float32 interleaved (I, Q, I, Q…).
    """
    key         = "iq_file_sink"
    name        = "IQ File Sink"
    description = "Record IQ samples to a .iq file"
    color       = "#1a3a1a"

    inputs = [PortDef("in", PortType.CF32)]
    params = [
        ParamDef("filename",    "Output File",
                 "str",    "recording.iq",
                 help="Path to output file"),
        ParamDef("format",      "Sample Format",
                 "choice", "CF32",
                 choices=["CF32", "CS16", "CU8"],
                 help="CF32=float32 IQ (most compatible)"),
        ParamDef("max_gb",      "Max Size (GB)",
                 "float", 1.0, min_val=0.1, max_val=100.0),
    ]

    def __init__(self):
        super().__init__()
        self._file     = None
        self._written  = 0
        self._path_str = ""

    def start(self) -> bool:
        if not HAS_NUMPY:
            return False
        filename = self.get("filename", "recording.iq")
        try:
            self._path_str = filename
            Path(filename).parent.mkdir(
                parents=True, exist_ok=True)
            self._file    = open(filename, "wb")  # nosec B603
            self._written = 0
            self._running = True
            log.info(f"IQFileSink: recording to {filename}")
            return True
        except Exception as e:
            self._error = str(e)
            return False

    def stop(self):
        self._running = False
        if self._file:
            try:
                self._file.close()
            except Exception:
                pass
            self._file = None
            log.info(
                f"IQFileSink: {self._written/(1024**2):.1f}"
                f" MB written to {self._path_str}")

    def consume(self, inputs: dict):
        data = inputs.get("in")
        if data is None or self._file is None:
            return
        max_bytes = self.get("max_gb", 1.0) * 1024**3
        if self._written >= max_bytes:
            self.stop()
            return
        fmt = self.get("format", "CF32")
        if fmt == "CF32":
            out = data.astype(np.complex64)
        elif fmt == "CS16":
            raw = np.empty(len(data) * 2, dtype=np.int16)
            raw[0::2] = (data.real * 32767).clip(
                -32768, 32767).astype(np.int16)
            raw[1::2] = (data.imag * 32767).clip(
                -32768, 32767).astype(np.int16)
            out = raw
        else:  # CU8
            raw = np.empty(len(data) * 2, dtype=np.uint8)
            raw[0::2] = ((data.real + 1) * 127.5).clip(
                0, 255).astype(np.uint8)
            raw[1::2] = ((data.imag + 1) * 127.5).clip(
                0, 255).astype(np.uint8)
            out = raw
        b = out.tobytes()
        self._file.write(b)
        self._written += len(b)


@register
class WaterfallSink(SinkBlock):
    """
    Display live waterfall/spectrum.
    Feeds back into Squelch's SDR tab waterfall widget.
    Connect after an FFT block.
    Input: F32 power spectrum (dB, from FFT block)
    """
    key         = "waterfall_sink"
    name        = "Waterfall Sink (Display)"
    description = "Feed spectrum data to Squelch's waterfall display"
    color       = "#1a2a3a"

    inputs = [PortDef("in", PortType.F32,
                      help="Power spectrum from FFT block")]
    params = [
        ParamDef("floor_db",    "Floor (dB)",
                 "float", -100.0, units="dB"),
        ParamDef("ceiling_db",  "Ceiling (dB)",
                 "float", -20.0,  units="dB"),
    ]

    def __init__(self):
        super().__init__()
        self._on_spectrum: list[Callable] = []

    def on_spectrum(self, cb: Callable):
        """Register callback: cb(spectrum_array_db)."""
        self._on_spectrum.append(cb)

    def start(self) -> bool:
        self._running = True
        return True

    def consume(self, inputs: dict):
        data = inputs.get("in")
        if data is None:
            return
        for cb in self._on_spectrum:
            try:
                cb(data)
            except Exception:
                pass


@register
class NullSink(SinkBlock):
    """
    Discard all samples. Useful for completing a flowgraph
    when you don't need the output (e.g. just recording).
    """
    key         = "null_sink"
    name        = "Null Sink"
    description = "Discard samples — use to complete a graph"
    color       = "#1a1a1a"

    inputs = [PortDef("in", PortType.CF32,
                      optional=True)]
    params = [
        ParamDef("sample_rate", "Sample Rate",
                 "int", 2_048_000, units="SPS"),
    ]

    def start(self) -> bool:
        self._running = True
        return True

    def consume(self, inputs: dict):
        # NullSink discards all input - this is intentional
        return
