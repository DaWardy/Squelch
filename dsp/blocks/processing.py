from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- dsp/blocks/processing.py
Signal processing blocks: FFT, FIR filter, resampler, multiply, shift.
"""

import logging
from dsp.block import (SyncBlock, DecimBlock,
                        Block, PortDef, PortType,
                        ParamDef)
from dsp.registry import register

log = logging.getLogger(__name__)

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


@register
class FreqShift(SyncBlock):
    """
    Shift the center frequency of an IQ signal.
    Multiplies by exp(j*2*pi*f*t) to shift by f Hz.
    Use to move a signal of interest to DC (0 Hz offset).
    """
    key         = "freq_shift"
    name        = "Frequency Shift"
    description = "Shift IQ signal by N Hz (frequency translation)"
    color       = "#2a3a2a"

    inputs  = [PortDef("in",  PortType.CF32)]
    outputs = [PortDef("out", PortType.CF32)]
    params  = [
        ParamDef("shift_hz",    "Shift",
                 "float", 0.0, units="Hz",
                 help="Positive = shift up, negative = shift down"),
        ParamDef("sample_rate", "Sample Rate",
                 "int",   2_048_000, units="SPS"),
    ]

    def __init__(self):
        super().__init__()
        self._phase = 0.0

    def process(self, x):
        if not HAS_NUMPY:
            return x
        shift = self.get("shift_hz",    0.0)
        sr    = self.get("sample_rate", 2_048_000)
        n     = len(x)
        t     = (np.arange(n) + self._phase) / sr
        lo    = np.exp(1j * 2 * np.pi * shift * t
                       ).astype(np.complex64)
        self._phase = (self._phase + n) % sr
        return (x * lo).astype(np.complex64)


@register
class FIRFilter(SyncBlock):
    """
    FIR (Finite Impulse Response) low-pass filter.
    Useful for isolating a narrow signal before demodulation.
    Cutoff is relative to sample rate (e.g. 0.1 = 10% of SR).
    """
    key         = "fir_filter"
    name        = "FIR Low-Pass Filter"
    description = "Low-pass FIR filter — remove out-of-band noise"
    color       = "#2a3a3a"

    inputs  = [PortDef("in",  PortType.CF32)]
    outputs = [PortDef("out", PortType.CF32)]
    params  = [
        ParamDef("cutoff",  "Cutoff Frequency",
                 "float", 0.1, min_val=0.001, max_val=0.499,
                 units="× SR",
                 help="Fraction of sample rate (0.1 = 10%)"),
        ParamDef("taps",    "Taps (filter length)",
                 "int",   64,  min_val=8, max_val=512,
                 help="More taps = sharper rolloff, more CPU"),
        ParamDef("window",  "Window Function",
                 "choice", "hamming",
                 choices=["hamming", "blackman",
                          "hann", "rectangular"]),
    ]

    def __init__(self):
        super().__init__()
        self._coeffs    = None
        self._zi        = None

    def _build_filter(self):
        if not HAS_NUMPY:
            return
        try:
            from scipy import signal as sp_sig
            cutoff = self.get("cutoff", 0.1)
            taps   = self.get("taps",   64)
            win    = self.get("window", "hamming")
            self._coeffs = sp_sig.firwin(
                taps, cutoff,
                window=win).astype(np.float32)
        except ImportError:
            # scipy not available — use simple box filter
            n = max(8, self.get("taps", 64))
            self._coeffs = np.ones(n, dtype=np.float32) / n

    def start(self) -> bool:
        self._build_filter()
        return True

    def on_param_change(self, name, value):
        self._build_filter()

    def process(self, x):
        if not HAS_NUMPY or self._coeffs is None:
            return x
        try:
            from scipy.signal import lfilter
            real = lfilter(self._coeffs, [1.0], x.real)
            imag = lfilter(self._coeffs, [1.0], x.imag)
            return (real + 1j * imag).astype(np.complex64)
        except ImportError:
            return np.convolve(
                x, self._coeffs,
                mode="same").astype(np.complex64)


@register
class Decimator(DecimBlock):
    """
    Reduce sample rate by integer factor.
    A 2 MSPS stream decimated by 4 becomes 500 kSPS.
    Lower rate = less CPU for downstream blocks.
    """
    key         = "decimator"
    name        = "Decimator"
    description = "Reduce sample rate by integer factor"
    color       = "#3a2a3a"

    inputs  = [PortDef("in",  PortType.CF32)]
    outputs = [PortDef("out", PortType.CF32)]
    params  = [
        ParamDef("factor",     "Decimation Factor",
                 "int",  4, min_val=1, max_val=256,
                 help="Output rate = Input rate / factor"),
        ParamDef("filter",     "Anti-Alias Filter",
                 "bool", True,
                 help="Apply low-pass before decimating "
                      "(prevents aliasing)"),
    ]

    def process(self, x):
        if not HAS_NUMPY:
            return x
        factor = self.get("factor", 4)
        if factor <= 1:
            return x
        return x[::factor].astype(np.complex64)


@register
class MultiplyConst(SyncBlock):
    """
    Multiply IQ samples by a complex constant.
    Real multiplier = amplitude scaling.
    Complex multiplier = amplitude + phase shift.
    """
    key         = "multiply_const"
    name        = "Multiply Constant"
    description = "Scale amplitude or rotate phase"
    color       = "#3a3a2a"

    inputs  = [PortDef("in",  PortType.CF32)]
    outputs = [PortDef("out", PortType.CF32)]
    params  = [
        ParamDef("real",  "Real Part",
                 "float", 1.0, units="",
                 help="Amplitude scale factor"),
        ParamDef("imag",  "Imaginary Part",
                 "float", 0.0,
                 help="0 = no phase shift"),
    ]

    def process(self, x):
        if not HAS_NUMPY:
            return x
        k = complex(self.get("real", 1.0),
                    self.get("imag", 0.0))
        return (x * k).astype(np.complex64)


@register
class FFTBlock(SyncBlock):
    """
    Compute power spectrum via FFT.
    Output is power in dB, shape (fft_size,).
    Connect to a WaterfallSink or SpectrumSink.
    """
    key         = "fft"
    name        = "FFT Spectrum"
    description = "Power spectrum in dB — connect to waterfall or scope"
    color       = "#2a3a4a"

    inputs  = [PortDef("in",  PortType.CF32,
                       help="IQ samples")]
    outputs = [PortDef("out", PortType.F32,
                       help="Power spectrum in dB")]
    params  = [
        ParamDef("fft_size",  "FFT Size",
                 "choice", 2048,
                 choices=[256, 512, 1024, 2048, 4096, 8192]),
        ParamDef("window",    "Window",
                 "choice", "hann",
                 choices=["hann", "hamming",
                          "blackman", "rectangular"]),
        ParamDef("avg",       "Averaging (frames)",
                 "int",    4, min_val=1, max_val=64,
                 help="Smooth spectrum over N frames"),
    ]

    def __init__(self):
        super().__init__()
        self._avg_buf  = []

    def process(self, x):
        if not HAS_NUMPY:
            return np.zeros(1, dtype=np.float32)
        fft_size = self.get("fft_size", 2048)
        win_name = self.get("window",   "hann")
        avg_n    = self.get("avg",      4)
        n        = min(len(x), fft_size)
        chunk    = x[:n]

        # Window
        win_fn = {
            "hann":       np.hanning,
            "hamming":    np.hamming,
            "blackman":   np.blackman,
            "rectangular":np.ones,
        }.get(win_name, np.hanning)
        win    = win_fn(n).astype(np.float32)

        # Pad if needed
        if n < fft_size:
            chunk = np.pad(chunk, (0, fft_size - n))
            win   = np.pad(win,   (0, fft_size - n))

        fft = np.fft.fftshift(
            np.abs(np.fft.fft(chunk * win, fft_size)))
        pwr = (20 * np.log10(
            fft / fft_size + 1e-10)).astype(np.float32)

        # Running average
        self._avg_buf.append(pwr)
        if len(self._avg_buf) > avg_n:
            self._avg_buf.pop(0)
        return np.mean(self._avg_buf, axis=0).astype(
            np.float32)
