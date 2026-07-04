# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/encoder.py

Frame builder + modulator: bits → complex-baseband IQ (ROADMAP Phase 4,
ENC-BUILD). The inverse of the decode chain —

    payload ─▶ build_frame (preamble + sync + payload + CRC)
            ─▶ modulate (OOK / FSK / PSK) ─▶ IQ

`build_frame()` assembles the same frame structure `core/framing.inspect_frame`
parses, and `modulate()` produces IQ that `core/bitslicer.slice_bits` recovers —
so an encode→decode round-trip returns the original payload (validated by the
tests). The resulting IQ is what you hand to a TX-capable radio; keying goes
through `SoapyManager.transmit_iq()`, which is the **AUTH-LAYER chokepoint**
(default-deny, per-band, logged) — this module never keys anything itself.

Pure numpy, no Qt, no hardware. This is a clean-signal reference modulator for
protocol research and the Phase-5 TX chain, not a production waveform shaper
(no pulse shaping / filtering yet).
"""

import logging
from dataclasses import dataclass, field

import numpy as np

from core.bitslicer import OOK, FSK, PSK, bits_to_bytes
from core.framing import compute_crc, CRC_ALGOS, _normalize_pattern

log = logging.getLogger(__name__)

_DEFAULT_SPS = 40


@dataclass
class EncodeResult:
    """A modulated frame."""
    iq:                 np.ndarray = field(default_factory=lambda: np.zeros(0, np.complex64))
    bits:               list = field(default_factory=list)
    family:             str = ""
    samples_per_symbol: int = 0
    symbol_rate:        float = 0.0


# ── frame assembly ────────────────────────────────────────────────────────────

def alternating_preamble(n_bits: int, first: int = 0) -> list:
    """`n_bits` of 0101… (or 1010… when first=1)."""
    return [(first + i) & 1 for i in range(max(0, n_bits))]


def _int_to_bits(value: int, width: int) -> list:
    return [(value >> i) & 1 for i in range(width - 1, -1, -1)]


def build_frame(payload, *, preamble_bits: int = 32, sync_word=None,
                crc: str | None = None) -> list:
    """Assemble preamble + sync + payload + CRC into a bit list.

    payload  — bits (list[0/1]), bytes, or a hex string.
    sync_word — bits / bytes / hex, or None.
    crc      — a CRC_ALGOS name (CRC computed over the payload only), or None.
    """
    bits: list = []
    if preamble_bits:
        bits += alternating_preamble(preamble_bits)
    if sync_word is not None:
        bits += _normalize_pattern(sync_word)
    payload_bits = _normalize_pattern(payload)
    bits += payload_bits
    if crc:
        crc_val = compute_crc(bits_to_bytes(payload_bits), crc)
        bits += _int_to_bits(crc_val, CRC_ALGOS[crc][1])
    return bits


# ── modulation ────────────────────────────────────────────────────────────────

def _resolve_sps(fs: float, samples_per_symbol, symbol_rate) -> int:
    if samples_per_symbol and samples_per_symbol >= 2:
        return int(round(samples_per_symbol))
    if symbol_rate and symbol_rate > 0:
        return max(2, int(round(fs / symbol_rate)))
    return _DEFAULT_SPS


def modulate(bits, fs: float, *, family: str = OOK,
             samples_per_symbol=None, symbol_rate=None,
             carrier_hz: float = 0.0, fsk_dev_hz: float | None = None,
             amplitude: float = 1.0) -> np.ndarray:
    """Modulate a bit list to complex-baseband IQ.

    OOK — bit 1 = carrier on, bit 0 = off. FSK — bit 1 = +deviation, bit 0 =
    −deviation (continuous phase). PSK — coherent BPSK, bit 1 = phase 0, bit 0
    = phase π. Defaults produce signals the bit-slicer recovers exactly (OOK/
    FSK) or up to the inherent 180° BPSK ambiguity (PSK).
    """
    b = np.array([1 if x else 0 for x in bits], dtype=float)
    if b.size == 0 or fs <= 0:
        return np.zeros(0, dtype=np.complex64)
    sps = _resolve_sps(fs, samples_per_symbol, symbol_rate)
    sym = np.repeat(b, sps)
    t = np.arange(sym.size) / fs
    fam = (family or OOK).upper()
    if fam == FSK:
        dev = fsk_dev_hz if fsk_dev_hz else fs / 8.0
        inst_f = carrier_hz + np.where(sym > 0.5, dev, -dev)
        iq = amplitude * np.exp(1j * np.cumsum(2 * np.pi * inst_f / fs))
    elif fam == PSK:
        ph = np.where(sym > 0.5, 0.0, np.pi) + 2 * np.pi * carrier_hz * t
        iq = amplitude * np.exp(1j * ph)
    else:                                   # OOK / ASK (and fallback)
        env = np.where(sym > 0.5, amplitude, 0.0)
        iq = env * np.exp(2j * np.pi * carrier_hz * t)
    return iq.astype(np.complex64)


# ── one-shot encode ───────────────────────────────────────────────────────────

def encode_iq(payload, fs: float, *, family: str = OOK,
              preamble_bits: int = 32, sync_word=None, crc: str | None = None,
              samples_per_symbol=None, symbol_rate=None,
              carrier_hz: float = 0.0, fsk_dev_hz: float | None = None,
              amplitude: float = 1.0) -> EncodeResult:
    """Build a frame and modulate it in one call → EncodeResult (IQ + metadata).

    Hand `result.iq` to `SoapyManager.transmit_iq()` to key it — that call is
    the authorization chokepoint; this function only synthesises samples.
    """
    bits = build_frame(payload, preamble_bits=preamble_bits,
                       sync_word=sync_word, crc=crc)
    sps = _resolve_sps(fs, samples_per_symbol, symbol_rate)
    iq = modulate(bits, fs, family=family, samples_per_symbol=sps,
                  carrier_hz=carrier_hz, fsk_dev_hz=fsk_dev_hz,
                  amplitude=amplitude)
    return EncodeResult(
        iq=iq, bits=bits, family=(family or OOK).upper(),
        samples_per_symbol=sps,
        symbol_rate=round(fs / sps, 3) if sps else 0.0)
