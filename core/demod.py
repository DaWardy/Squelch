# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/demod.py

The demodulator engine (ROADMAP §14.4 core) — turn IQ into audio. Squelch could
*see* signals (waterfall, survey) but not *listen* to them; this is the missing
DSP. It also underpins multiple receivers: a `MultiVFO` runs one demodulator per
channel over the same IQ stream (SDR Console's signature feature).

`demodulate(iq, sample_rate, mode, offset_hz=…, bandwidth_hz=…, audio_rate=…)`
does the whole chain: frequency-shift the wanted signal to baseband → low-pass to
the channel bandwidth → decimate to the audio rate → demodulate for the mode:

  * AM  — envelope (magnitude), DC removed
  * FM  — instantaneous-frequency (phase difference); NBFM/WFM by bandwidth
  * USB/LSB — real part of the single-sideband-selected baseband
  * CW  — SSB with a BFO offset so the carrier lands at an audible tone

Pure numpy (a windowed-sinc FIR for the anti-alias low-pass; no scipy). Returns a
float32 audio array in ~[-1, 1]. Never raises — returns silence on bad input, so
a receiver loop can't die on one frame.
"""

import logging
from dataclasses import dataclass, field

import numpy as np

log = logging.getLogger(__name__)

AUDIO_RATE = 48_000
MODES = ("AM", "FM", "NBFM", "WFM", "USB", "LSB", "CW")
_DEFAULT_BW = {"AM": 10_000, "FM": 12_500, "NBFM": 12_500, "WFM": 180_000,
               "USB": 2_700, "LSB": 2_700, "CW": 500}
CW_BFO_HZ = 700          # CW beat-note pitch


# ── building blocks ─────────────────────────────────────────────────────────
def frequency_shift(iq: np.ndarray, sample_rate: float, offset_hz: float) -> np.ndarray:
    """Shift `iq` so a signal at +offset_hz moves to baseband (0 Hz)."""
    n = len(iq)
    if n == 0:
        return iq
    ph = np.exp(-2j * np.pi * (offset_hz / float(sample_rate)) * np.arange(n))
    return (iq * ph).astype(np.complex64)


def _lowpass_fir(cutoff_hz: float, sample_rate: float, taps: int = 129) -> np.ndarray:
    """A windowed-sinc low-pass kernel (normalised to unity DC gain)."""
    cutoff = max(1.0, min(float(cutoff_hz), sample_rate / 2 - 1))
    t = np.arange(taps) - (taps - 1) / 2.0
    h = np.sinc(2 * cutoff / sample_rate * t) * np.hamming(taps)
    s = h.sum()
    return h / (s if s else 1.0)


def lowpass_decimate(iq: np.ndarray, sample_rate: float, cutoff_hz: float,
                     target_rate: float) -> tuple:
    """Low-pass to `cutoff_hz`, then decimate toward `target_rate`.

    Returns (filtered_decimated_iq, new_sample_rate)."""
    if len(iq) == 0:
        return iq, sample_rate
    h = _lowpass_fir(cutoff_hz, sample_rate)
    filt = np.convolve(iq, h, mode="same")
    factor = max(1, int(sample_rate // max(1.0, target_rate)))
    return filt[::factor].astype(np.complex64), sample_rate / factor


# ── per-mode demodulators (operate on baseband, channel-rate IQ) ─────────────
def demod_am(bb: np.ndarray) -> np.ndarray:
    audio = np.abs(bb)
    return audio - np.mean(audio)          # strip the DC (carrier) term


def demod_fm(bb: np.ndarray, sample_rate: float, deviation_hz: float) -> np.ndarray:
    if len(bb) < 2:
        return np.zeros(len(bb), dtype=np.float32)
    dphase = np.angle(bb[1:] * np.conj(bb[:-1]))     # inst. frequency
    gain = sample_rate / (2 * np.pi * max(1.0, deviation_hz))
    audio = np.concatenate([[0.0], dphase * gain])
    return audio.astype(np.float32)


def demod_ssb(bb: np.ndarray, upper: bool = True) -> np.ndarray:
    """SSB: carrier is at baseband 0; keep one sideband (reject the other via an
    FFT mask) and take the real part as audio. `upper` → USB (+freqs)."""
    n = len(bb)
    if n == 0:
        return np.zeros(0, dtype=np.float32)
    spec = np.fft.fft(bb)
    freqs = np.fft.fftfreq(n)
    if upper:
        spec[freqs < 0] = 0
    else:
        spec[freqs > 0] = 0
    return np.fft.ifft(spec).real.astype(np.float32)


# ── one-stop chain ───────────────────────────────────────────────────────────
def demodulate(iq, sample_rate: float, mode: str = "FM", *,
               offset_hz: float = 0.0, bandwidth_hz: float = 0.0,
               audio_rate: float = AUDIO_RATE) -> np.ndarray:
    """IQ → audio for one channel. Never raises (returns silence on failure)."""
    try:
        iq = np.asarray(iq, dtype=np.complex64)
        if iq.size == 0:
            return np.zeros(0, dtype=np.float32)
        m = (mode or "FM").upper()
        if m == "NFM":
            m = "NBFM"                              # SDR-tab combo alias
        bw = float(bandwidth_hz) or float(_DEFAULT_BW.get(m, 12_500))
        # Shift the wanted carrier to baseband (0 Hz). Audio frequency is then
        # (RF − carrier), which is what SSB/CW recovery expects.
        bb = frequency_shift(iq, sample_rate, offset_hz)
        # AM/FM keep ±bw/2 around the carrier; SSB/CW keep the audio passband ±bw
        # (SSB then rejects the opposite sideband; CW's BFO tone is added after).
        cutoff = bw / 2.0 if m in ("AM", "FM", "NBFM", "WFM") else bw
        bb, rate = lowpass_decimate(bb, sample_rate, cutoff, audio_rate)
        audio = _demod_by_mode(bb, rate, m, bw)
        # normalise to a safe range
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if peak > 1e-9:
            audio = audio / peak * 0.9
        return audio.astype(np.float32)
    except Exception as exc:                        # pragma: no cover
        log.debug("demodulate failed: %s", exc)
        return np.zeros(0, dtype=np.float32)


def _demod_by_mode(bb, rate, m, bw):
    if m == "AM":
        return demod_am(bb)
    if m in ("FM", "NBFM", "WFM"):
        dev = 75_000 if m == "WFM" else max(2_500, bw / 2.0)
        return demod_fm(bb, rate, dev)
    if m == "LSB":
        return demod_ssb(bb, upper=False)
    if m == "CW":
        # Re-inject a BFO so the (now-baseband) carrier beats at CW_BFO_HZ.
        n = len(bb)
        bfo = np.exp(2j * np.pi * (CW_BFO_HZ / rate) * np.arange(n))
        return (bb * bfo).real.astype(np.float32)
    return demod_ssb(bb, upper=True)               # USB and default


# ── multiple receivers (the §14.4 engine) ────────────────────────────────────
@dataclass
class VFOChannel:
    """One receiver: an absolute frequency, a mode, and a bandwidth."""
    freq_hz:      int
    mode:         str = "FM"
    bandwidth_hz: int = 0
    label:        str = ""


@dataclass
class MultiVFO:
    """Several demodulators over one shared IQ stream (SDR-Console matrix core)."""
    audio_rate: float = AUDIO_RATE
    channels: list = field(default_factory=list)

    def add(self, freq_hz: int, mode: str = "FM", bandwidth_hz: int = 0,
            label: str = "") -> VFOChannel:
        ch = VFOChannel(int(freq_hz), mode, int(bandwidth_hz), label)
        self.channels.append(ch)
        return ch

    def remove(self, index: int) -> bool:
        if 0 <= index < len(self.channels):
            del self.channels[index]
            return True
        return False

    def process(self, iq, sample_rate: float, center_hz: int) -> dict:
        """Demodulate every channel that falls within the IQ's span.

        Returns {label-or-index: audio}. A channel outside [center ± rate/2] is
        skipped. Never raises."""
        out: dict = {}
        try:
            lo = center_hz - sample_rate / 2.0
            hi = center_hz + sample_rate / 2.0
            for i, ch in enumerate(self.channels):
                if not (lo <= ch.freq_hz <= hi):
                    continue
                key = ch.label or f"vfo{i}"
                out[key] = demodulate(
                    iq, sample_rate, ch.mode,
                    offset_hz=ch.freq_hz - center_hz,
                    bandwidth_hz=ch.bandwidth_hz,
                    audio_rate=self.audio_rate)
        except Exception as exc:                    # pragma: no cover
            log.debug("MultiVFO.process failed: %s", exc)
        return out
