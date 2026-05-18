from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- dsp/blocks/demodulators.py
Demodulator blocks: WFM, NFM, AM, SSB (USB/LSB).
All accept complex IQ input, output float32 audio.
"""

import logging
from dsp.block import SyncBlock, DecimBlock, PortDef, PortType, ParamDef
from dsp.registry import register

log = logging.getLogger(__name__)

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


@register
class WFMDemod(SyncBlock):
    category    = "Demodulators"
    """
    Wideband FM demodulator. Demodulates broadcast FM radio.
    Input: CF32 IQ at ≥200 kSPS
    Output: F32 audio at input_rate / decimation
    Typical use: 2MSPS in → decimation 40 → 50kHz audio
    """
    key         = "wfm_demod"
    name        = "WFM Demodulator"
    description = "Wideband FM — broadcast radio, APRS, NOAA weather"
    color       = "#3a2a1a"

    inputs  = [PortDef("in",  PortType.CF32,
                       help="IQ at ≥200 kSPS")]
    outputs = [PortDef("out", PortType.F32,
                       help="Demodulated audio")]
    params  = [
        ParamDef("decimation",  "Decimation",
                 "int",  10, min_val=1, max_val=256,
                 help="Reduce rate before audio output"),
        ParamDef("deemphasis",  "De-emphasis (μs)",
                 "choice", 75,
                 choices=[0, 50, 75],
                 help="75μs = Americas/Korea, 50μs = rest of world"),
        ParamDef("tau",         "Deviation (Hz)",
                 "float", 75000.0,
                 help="FM deviation, typically 75kHz for WFM"),
    ]

    def __init__(self):
        super().__init__()
        self._prev = complex(0)
        self._de_buf = None

    def process(self, x):
        if not HAS_NUMPY:
            return np.zeros(1, dtype=np.float32)
        decim    = self.get("decimation", 10)
        tau_us   = self.get("deemphasis", 75)
        tau_hz   = self.get("tau",        75000.0)

        # FM discriminator: phase difference
        delayed  = np.empty_like(x)
        delayed[0] = self._prev
        delayed[1:] = x[:-1]
        self._prev = x[-1]

        # Instantaneous frequency via angle diff
        disc = np.angle(x * np.conj(delayed))

        # Normalize by deviation
        sr   = 2_048_000  # assume standard for now
        disc = disc * (sr / (2 * np.pi * tau_hz))

        # Decimate
        audio = disc[::decim].astype(np.float32)

        # De-emphasis filter (simple IIR)
        if tau_us > 0:
            audio = self._deemphasis(audio, tau_us, sr // decim)

        return audio

    def _deemphasis(self, x, tau_us, sr):
        """Apply de-emphasis IIR filter."""
        alpha = 1.0 - np.exp(-1.0 / (sr * tau_us * 1e-6))
        y     = np.empty_like(x)
        s     = 0.0
        for i, xi in enumerate(x):
            s    = alpha * xi + (1 - alpha) * s
            y[i] = s
        return y


@register
class NFMDemod(SyncBlock):
    category    = "Demodulators"
    """
    Narrowband FM demodulator. Works for VHF/UHF voice,
    CTCSS squelch detection, APRS, digital voice.
    Input: CF32 at ≥25 kSPS
    Output: F32 audio
    """
    key         = "nfm_demod"
    name        = "NFM Demodulator"
    description = "Narrowband FM — VHF/UHF voice, APRS, CTCSS"
    color       = "#3a2a2a"

    inputs  = [PortDef("in",  PortType.CF32)]
    outputs = [PortDef("out", PortType.F32)]
    params  = [
        ParamDef("decimation",  "Decimation",
                 "int",   5, min_val=1, max_val=64),
        ParamDef("squelch_db",  "Squelch (dB)",
                 "float", -60.0, min_val=-90.0, max_val=0.0,
                 units="dB",
                 help="Open squelch when power > threshold"),
        ParamDef("deviation",   "Deviation (Hz)",
                 "float", 5000.0,
                 help="NFM deviation, typically 5kHz"),
    ]

    def __init__(self):
        super().__init__()
        self._prev = complex(0)

    def _power_db(self, x) -> float:
        if not HAS_NUMPY or len(x) == 0:
            return -100.0
        pwr = float(np.mean(np.abs(x)**2))
        if pwr <= 0:
            return -100.0
        return 10.0 * np.log10(pwr)

    def process(self, x):
        if not HAS_NUMPY:
            return np.zeros(1, dtype=np.float32)
        decim   = self.get("decimation",  5)
        sql_db  = self.get("squelch_db",  -60.0)
        dev     = self.get("deviation",   5000.0)

        # Squelch check
        if self._power_db(x) < sql_db:
            n = len(x) // decim or 1
            return np.zeros(n, dtype=np.float32)

        # FM discriminator
        prev_arr = np.empty_like(x)
        prev_arr[0]  = self._prev
        prev_arr[1:] = x[:-1]
        self._prev   = x[-1]
        disc  = np.angle(x * np.conj(prev_arr))
        sr    = 48_000 * decim   # rough SR estimate
        disc  = disc * (sr / (2 * np.pi * dev))
        return disc[::decim].astype(np.float32)


@register
class AMDemod(SyncBlock):
    category    = "Demodulators"
    """
    Amplitude modulation envelope detector.
    Works for AM broadcast, SSB with carrier, NOAA weather.
    Input: CF32 IQ
    Output: F32 audio (magnitude)
    """
    key         = "am_demod"
    name        = "AM Demodulator"
    description = "AM envelope detector — AM broadcast, ATC, weather"
    color       = "#3a3a1a"

    inputs  = [PortDef("in",  PortType.CF32)]
    outputs = [PortDef("out", PortType.F32)]
    params  = [
        ParamDef("decimation",  "Decimation",
                 "int",   10, min_val=1, max_val=256),
        ParamDef("normalize",   "Normalize",
                 "bool",  True,
                 help="Normalize output amplitude to ±1"),
    ]

    def process(self, x):
        if not HAS_NUMPY:
            return np.zeros(1, dtype=np.float32)
        decim = self.get("decimation", 10)
        norm  = self.get("normalize",  True)
        # Envelope detection
        mag   = np.abs(x).astype(np.float32)
        if norm:
            peak = np.max(mag)
            if peak > 0:
                mag = mag / peak
        return mag[::decim]


@register
class SSBDemod(SyncBlock):
    category    = "Demodulators"
    """
    Single-sideband demodulator (USB or LSB).
    Standard for HF amateur, aviation, marine voice.
    Input: CF32 IQ centered on carrier
    Output: F32 audio
    """
    key         = "ssb_demod"
    name        = "SSB Demodulator"
    description = "USB/LSB demodulator — HF voice, aviation, marine"
    color       = "#3a2a3a"

    inputs  = [PortDef("in",  PortType.CF32)]
    outputs = [PortDef("out", PortType.F32)]
    params  = [
        ParamDef("mode",       "Sideband",
                 "choice", "USB",
                 choices=["USB", "LSB"]),
        ParamDef("decimation", "Decimation",
                 "int",   10, min_val=1, max_val=64),
        ParamDef("bw_hz",      "Bandwidth (Hz)",
                 "float", 2700.0,
                 min_val=500.0, max_val=8000.0,
                 help="Audio bandwidth (typical: 2.7 kHz)"),
    ]

    def process(self, x):
        if not HAS_NUMPY:
            return np.zeros(1, dtype=np.float32)
        mode  = self.get("mode",       "USB")
        decim = self.get("decimation", 10)

        if mode == "LSB":
            # Flip spectrum for LSB
            audio = np.real(
                np.conj(x)).astype(np.float32)
        else:
            audio = np.real(x).astype(np.float32)

        return audio[::decim]


@register
class CWDecoder(SyncBlock):
    category    = "Demodulators"
    """
    Simple CW (Morse code) audio decoder.
    Detects tone on/off transitions and decodes to text.
    Connect after an NFM or AM demodulator.
    Input: F32 audio
    Output: F32 audio (passthrough) + emits text via callback
    """
    key         = "cw_decoder"
    name        = "CW Decoder"
    description = "Morse code decoder — outputs decoded text"
    color       = "#1a2a3a"

    inputs  = [PortDef("in",  PortType.F32)]
    outputs = [PortDef("out", PortType.F32,
                       help="Passthrough audio")]
    params  = [
        ParamDef("threshold",  "Tone Threshold",
                 "float", 0.1, min_val=0.01, max_val=1.0,
                 help="Amplitude threshold for tone detection"),
        ParamDef("freq_hz",    "Tone Frequency",
                 "float", 700.0, min_val=200.0, max_val=2000.0,
                 units="Hz"),
        ParamDef("wpm",        "Expected WPM",
                 "int",   20, min_val=5, max_val=60,
                 help="Expected Morse speed (auto-adapts)"),
    ]

    # Morse table
    _MORSE = {
        ".-": "A", "-...": "B", "-.-.": "C", "-..": "D",
        ".": "E", "..-.": "F", "--.": "G", "....": "H",
        "..": "I", ".---": "J", "-.-": "K", ".-..": "L",
        "--": "M", "-.": "N", "---": "O", ".--.": "P",
        "--.-": "Q", ".-.": "R", "...": "S", "-": "T",
        "..-": "U", "...-": "V", ".--": "W", "-..-": "X",
        "-.--": "Y", "--..": "Z",
        "-----": "0", ".----": "1", "..---": "2",
        "...--": "3", "....-": "4", ".....": "5",
        "-....": "6", "--...": "7", "---..": "8",
        "----.": "9",
        ".-.-.-": ".", "--..--": ",", "..--..": "?",
        ".----.": "'",
    }

    def __init__(self):
        super().__init__()
        self._symbol    = ""
        self._in_tone   = False
        self._tone_len  = 0
        self._space_len = 0
        self._on_text:  list = []

    def on_decoded(self, cb):
        self._on_text.append(cb)

    def _emit(self, char: str):
        for cb in self._on_text:
            try:
                cb(char)
            except Exception:
                pass

    def process(self, x):
        if not HAS_NUMPY or len(x) == 0:
            return x
        threshold = self.get("threshold", 0.1)
        wpm       = self.get("wpm",       20)
        dot_len   = int(48000 / (wpm * 2.4))  # samples per dot

        for sample in x:
            tone = abs(float(sample)) > threshold
            if tone:
                self._tone_len  += 1
                if self._space_len > dot_len * 6 and self._symbol:
                    # Word space
                    self._emit(" ")
                    self._symbol = ""
                elif self._space_len > dot_len * 2 and self._symbol:
                    # Character space — decode symbol
                    c = self._MORSE.get(self._symbol, "?")
                    self._emit(c)
                    self._symbol = ""
                self._space_len = 0
            else:
                if self._tone_len > 0:
                    self._symbol += ("-"
                        if self._tone_len > dot_len * 2
                        else ".")
                    self._tone_len = 0
                self._space_len += 1

        return x   # passthrough
