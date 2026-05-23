from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- dsp/blocks/sources.py
Signal source blocks: hardware SDR, IQ file, tone generator.
"""

import logging
import time
from pathlib import Path

from dsp.block import SourceBlock, PortDef, PortType, ParamDef
from dsp.registry import register

log = logging.getLogger(__name__)

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


@register
class SoapySource(SourceBlock):
    """
    Receive IQ samples from any SoapySDR-compatible device
    (RTL-SDR, USRP B200/B210, HackRF, SDRplay, Airspy…).
    """
    key         = "soapy_source"
    name        = "SDR Source (SoapySDR)"
    category    = "Sources"
    description = "IQ samples from RTL-SDR, USRP, HackRF, etc."
    color       = "#1a3a5a"

    outputs = [PortDef("out", PortType.CF32,
                       help="Complex IQ samples")]
    params  = [
        ParamDef("freq_hz",     "Center Frequency",
                 "float",  144_390_000.0,
                 units="Hz",
                 help="Center frequency in Hz (e.g. 144390000)"),
        ParamDef("sample_rate", "Sample Rate",
                 "int",    2_048_000,
                 choices=[250_000, 1_024_000, 2_048_000,
                          3_200_000, 10_000_000,
                          20_000_000, 56_000_000],
                 units="SPS",
                 help="Samples per second"),
        ParamDef("gain",        "Gain",
                 "float",  30.0,
                 min_val=0.0, max_val=70.0,
                 units="dB"),
        ParamDef("ppm",         "PPM Correction",
                 "int",    0,
                 min_val=-100, max_val=100,
                 units="ppm",
                 help="Frequency correction for cheap dongles"),
        ParamDef("device",      "Device Args",
                 "str",    "",
                 help="SoapySDR driver args, e.g. 'driver=rtlsdr'"),
        ParamDef("agc",         "Automatic Gain",
                 "bool",   False),
    ]

    def __init__(self):
        super().__init__()
        self._dev    = None
        self._stream = None
        self._buf    = None

    def start(self) -> bool:
        if not HAS_NUMPY:
            self._error = "numpy not installed"
            return False
        try:
            import SoapySDR
            from SoapySDR import (SOAPY_SDR_RX,
                                   SOAPY_SDR_CF32)
            args = self.get("device", "") or ""
            freq = self.get("freq_hz",     144_390_000.0)
            sr   = self.get("sample_rate", 2_048_000)
            gain = self.get("gain",        30.0)
            ppm  = self.get("ppm",         0)

            self._dev = SoapySDR.Device(args)
            self._dev.setSampleRate(SOAPY_SDR_RX, 0, sr)
            self._dev.setFrequency(SOAPY_SDR_RX, 0, freq)
            self._dev.setGain(SOAPY_SDR_RX, 0, gain)
            if ppm:
                try:
                    self._dev.setFrequencyCorrection(
                        SOAPY_SDR_RX, 0, ppm)
                except Exception:
                    pass

            self._stream = self._dev.setupStream(
                SOAPY_SDR_RX, SOAPY_SDR_CF32)
            self._dev.activateStream(self._stream)
            self._buf    = np.zeros(
                self.CHUNK, dtype=np.complex64)
            self._running = True
            log.info(
                f"SoapySource started: "
                f"{freq/1e6:.3f}MHz {sr/1e6:.2f}MSPS")
            return True
        except Exception as e:
            self._error = str(e)
            log.warning(f"SoapySource start: {e}")
            return False

    def stop(self):
        self._running = False
        try:
            if self._dev and self._stream:
                self._dev.deactivateStream(self._stream)
                self._dev.closeStream(self._stream)
                self._stream = None
            if self._dev:
                self._dev = None
        except Exception:
            pass

    def generate(self, n_samples: int) -> dict:
        if not self._dev or not self._stream:
            return {}
        try:
            import SoapySDR
            sr = self._dev.readStream(
                self._stream, [self._buf],
                min(n_samples, self.CHUNK),
                timeoutUs=100_000)
            if sr.ret > 0:
                return {"out": self._buf[:sr.ret].copy()}
        except Exception as e:
            log.debug(f"SoapySource read: {e}")
        return {}

    def on_param_change(self, name: str, value):
        if not self._dev or not self._running:
            return
        try:
            import SoapySDR
            SOAPY_SDR_RX = SoapySDR.SOAPY_SDR_RX
            if name == "freq_hz":
                self._dev.setFrequency(
                    SOAPY_SDR_RX, 0, value)
            elif name == "gain":
                self._dev.setGain(
                    SOAPY_SDR_RX, 0, value)
            elif name == "ppm":
                try:
                    self._dev.setFrequencyCorrection(
                        SOAPY_SDR_RX, 0, value)
                except Exception:
                    pass
        except Exception as e:
            log.debug(f"SoapySource param: {e}")


@register
class IQFileSource(SourceBlock):
    """
    Read IQ samples from a .iq / .bin / .wav recording.
    Loops when end of file is reached (if loop=True).
    """
    key         = "iq_file_source"
    name        = "IQ File Source"
    category    = "Sources"
    description = "Read IQ samples from a recording file"
    color       = "#1a3a2a"

    outputs = [PortDef("out", PortType.CF32)]
    params  = [
        ParamDef("filename",    "File Path",
                 "str",    "",
                 help="Path to .iq / .bin / .s8 / .f32 file"),
        ParamDef("sample_rate", "Sample Rate",
                 "int",    2_048_000, units="SPS"),
        ParamDef("format",      "Sample Format",
                 "choice", "CF32",
                 choices=["CF32", "CS16", "CS8", "CU8"],
                 help="CF32=float32 (RTL-SDR raw=CU8)"),
        ParamDef("loop",        "Loop",
                 "bool",   True),
        ParamDef("repeat_delay","Repeat Delay",
                 "float",  0.0, units="s"),
    ]

    def __init__(self):
        super().__init__()
        self._data  = None
        self._pos   = 0

    def start(self) -> bool:
        if not HAS_NUMPY:
            return False
        filename = self.get("filename", "")
        if not filename or not Path(filename).exists():
            self._error = f"File not found: {filename}"
            return False
        try:
            fmt = self.get("format", "CF32")
            raw = np.fromfile(filename,
                              dtype=_fmt_dtype(fmt))
            if fmt == "CU8":
                raw = raw.astype(np.float32) / 127.5 - 1.0
                self._data = raw[0::2] + 1j * raw[1::2]
                self._data = self._data.astype(np.complex64)
            elif fmt == "CS16":
                raw = raw.astype(np.float32) / 32768.0
                self._data = raw[0::2] + 1j * raw[1::2]
                self._data = self._data.astype(np.complex64)
            elif fmt == "CS8":
                raw = raw.astype(np.float32) / 128.0
                self._data = raw[0::2] + 1j * raw[1::2]
                self._data = self._data.astype(np.complex64)
            else:   # CF32
                self._data = raw.view(np.complex64)
            self._pos     = 0
            self._running = True
            log.info(
                f"IQFileSource: {filename} "
                f"({len(self._data)} samples)")
            return True
        except Exception as e:
            self._error = str(e)
            log.warning(f"IQFileSource start: {e}")
            return False

    def generate(self, n_samples: int) -> dict:
        if self._data is None:
            return {}
        end = self._pos + n_samples
        if end > len(self._data):
            if self.get("loop", True):
                chunk = np.concatenate([
                    self._data[self._pos:],
                    self._data[:end - len(self._data)]])
                self._pos = end - len(self._data)
                delay = self.get("repeat_delay", 0.0)
                if delay:
                    time.sleep(delay)
            else:
                chunk = self._data[self._pos:]
                self._running = False
                self._pos = len(self._data)
        else:
            chunk = self._data[self._pos:end]
            self._pos = end
        # Simulate real-time playback rate
        sr     = self.get("sample_rate", 2_048_000)
        sleep  = n_samples / sr
        time.sleep(sleep)
        return {"out": chunk}


@register
class ToneSource(SourceBlock):
    """
    Generate a complex tone at a given offset frequency.
    Useful for testing signal chains without hardware.
    e_g. center=146.52MHz, offset=+500Hz → CTCSS-like tone
    """
    key         = "tone_source"
    name        = "Tone Source (Test)"
    category    = "Sources"
    description = "Complex tone for testing — no hardware needed"
    color       = "#2a1a3a"

    outputs = [PortDef("out", PortType.CF32)]
    params  = [
        ParamDef("sample_rate",    "Sample Rate",
                 "int",   2_048_000, units="SPS"),
        ParamDef("freq_offset",    "Tone Frequency",
                 "float", 1000.0,
                 min_val=-1_000_000, max_val=1_000_000,
                 units="Hz",
                 help="Offset from center frequency"),
        ParamDef("amplitude",      "Amplitude",
                 "float", 0.5,
                 min_val=0.0, max_val=1.0),
        ParamDef("noise_floor",    "Noise Floor",
                 "float", 0.01,
                 min_val=0.0, max_val=1.0,
                 help="Add AWGN noise at this level"),
    ]

    def __init__(self):
        super().__init__()
        self._phase = 0.0

    def start(self) -> bool:
        if not HAS_NUMPY:
            return False
        self._running = True
        self._phase   = 0.0
        return True

    def generate(self, n: int) -> dict:
        if not HAS_NUMPY:
            return {}
        sr    = self.get("sample_rate",   2_048_000)
        freq  = self.get("freq_offset",   1000.0)
        amp   = self.get("amplitude",     0.5)
        noise = self.get("noise_floor",   0.01)

        t        = (np.arange(n) + self._phase) / sr
        samples  = amp * np.exp(1j * 2 * np.pi * freq * t)
        self._phase = (self._phase + n) % sr

        if noise > 0:
            samples += noise * (
                np.random.randn(n) +
                1j * np.random.randn(n))

        samples  = samples.astype(np.complex64)
        # Simulate real-time rate
        time.sleep(n / sr)
        return {"out": samples}


def _fmt_dtype(fmt: str) -> str:
    return {"CF32": "float32",
            "CS16": "int16",
            "CS8":  "int8",
            "CU8":  "uint8"}.get(fmt, "float32")
