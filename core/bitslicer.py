# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/bitslicer.py

Generic OOK/ASK · FSK · PSK bit-slicer from complex-baseband IQ (ROADMAP
Phase 4, DEC-GENERIC). Given a chunk of IQ centred on a digital signal, recover
the raw symbol stream — the front half of "decode arbitrary protocol":

    IQ ─▶ soft signal (envelope / inst-freq / phase-diff)
       ─▶ binarize ─▶ estimate symbols-per-symbol ─▶ sample ─▶ bits

It pairs with the modulation classifier (core/modulation_classify.py): when the
modulation is not given, we ask the classifier, then slice accordingly. The
recovered bits feed the protocol framing inspector (Phase 4 DEC-FRAMING) and,
eventually, the encode→TX chain — which is already gated by AUTH-LAYER.

Pure DSP: numpy only, no Qt, no hardware. Clean synthetic signals slice
exactly; noisy/low-SNR captures are best-effort with a rough confidence. This
is a *symbol* slicer, not a protocol decoder — it makes no assumptions about
framing, bit order, or line coding (BPSK is recovered coherently and carries a
180° phase ambiguity, so its output may be bit-inverted). Never raises:
bad/empty input returns an empty result.
"""

import logging
from dataclasses import dataclass, field

import numpy as np

log = logging.getLogger(__name__)

# Slicing families (which soft signal + threshold to use).
OOK = "OOK"          # amplitude on/off (ASK) — level threshold on the envelope
FSK = "FSK"          # 2-level frequency — sign threshold on inst. frequency
PSK = "PSK"          # phase — sign of the differential phase product (DBPSK)

# Plausible samples-per-symbol search bounds for auto estimation.
_MIN_SPS = 2
_MAX_SPS = 4096


@dataclass
class SliceResult:
    """Recovered symbol stream and how it was sliced."""
    bits:               list = field(default_factory=list)   # list[int] 0/1
    family:             str   = ""        # OOK / FSK / PSK
    samples_per_symbol: float = 0.0
    symbol_rate:        float = 0.0       # baud = fs / sps
    n_symbols:          int   = 0
    confidence:         float = 0.0       # rough 0..1 eye-opening measure

    def as_hex(self) -> str:
        return bits_to_hex(self.bits)


# ── soft-signal extraction ────────────────────────────────────────────────────

def _soft_signal(iq: np.ndarray, family: str):
    """Return (soft_real_signal, kind) for the chosen slicing family.

    kind == 'level' → threshold at a data-driven level (OOK envelope);
    kind == 'zero'  → threshold at zero / the median (FSK, PSK).
    """
    iq = np.asarray(iq, dtype=np.complex64)
    if family == OOK:
        return np.abs(iq).astype(np.float64), "level"
    if family == FSK:
        # instantaneous frequency = derivative of the unwrapped phase
        ph = np.unwrap(np.angle(iq))
        inst_f = np.diff(ph, prepend=ph[:1])
        return inst_f.astype(np.float64), "zero"
    if family == PSK:
        # coherent BPSK: square to strip the ±π modulation, derotate by the
        # residual carrier phase, then the real part holds a level per symbol
        # (+A / −A). Sign → symbol. NOTE 180° ambiguity — the output may be
        # bit-inverted (no absolute phase reference; resolved by framing).
        sq = iq * iq
        theta = 0.5 * float(np.angle(np.mean(sq))) if sq.size else 0.0
        soft = np.real(iq * np.exp(-1j * theta))
        return soft.astype(np.float64), "zero"
    return np.abs(iq).astype(np.float64), "level"


def _binarize(soft: np.ndarray, kind: str) -> np.ndarray:
    """Soft real signal → 0/1 per sample."""
    if soft.size == 0:
        return np.zeros(0, dtype=np.int8)
    if kind == "level":
        lo, hi = float(soft.min()), float(soft.max())
        thr = (lo + hi) / 2.0
    else:                                   # 'zero' → split at the median
        thr = float(np.median(soft))
    return (soft > thr).astype(np.int8)


# ── symbol-rate (samples-per-symbol) estimation ───────────────────────────────

def _run_lengths(binary: np.ndarray) -> np.ndarray:
    """Lengths of maximal runs of equal values."""
    if binary.size == 0:
        return np.zeros(0, dtype=int)
    change = np.nonzero(np.diff(binary))[0] + 1
    edges = np.concatenate([[0], change, [binary.size]])
    return np.diff(edges)


def estimate_sps(binary: np.ndarray) -> float:
    """Estimate samples-per-symbol from a binarised stream.

    The shortest pulses are single symbols; longer runs are integer multiples.
    A low percentile of the run lengths is a noise-robust "one symbol" width
    (a lone glitch won't drag it, unlike the raw minimum).
    """
    runs = _run_lengths(binary)
    if runs.size == 0:
        return 0.0
    # ignore the first/last runs (partial symbols at the capture edges)
    core = runs[1:-1] if runs.size >= 3 else runs
    sps = float(np.percentile(core, 10))
    return max(float(_MIN_SPS), min(sps, float(_MAX_SPS)))


# ── symbol sampling ───────────────────────────────────────────────────────────

def _sample_symbols(binary: np.ndarray, sps: float,
                    phase: float = 0.5) -> list:
    """Sample the binarised stream once per symbol at the symbol centre."""
    if binary.size == 0 or sps < 1.0:
        return []
    n = int(binary.size / sps)
    out = []
    for k in range(n):
        idx = int((k + phase) * sps)
        if idx >= binary.size:
            break
        out.append(int(binary[idx]))
    return out


def _eye_confidence(soft: np.ndarray, binary: np.ndarray, sps: float,
                    kind: str) -> float:
    """Rough 0..1: separation of the two symbol clusters vs their spread."""
    if soft.size == 0 or sps < 1.0:
        return 0.0
    ones = soft[binary == 1]
    zeros = soft[binary == 0]
    if ones.size == 0 or zeros.size == 0:
        return 0.0
    sep = abs(float(ones.mean()) - float(zeros.mean()))
    spread = float(ones.std()) + float(zeros.std()) + 1e-9
    return float(max(0.0, min(1.0, sep / (sep + spread))))


# ── public API ────────────────────────────────────────────────────────────────

def _family_from_modulation(iq: np.ndarray, fs: float) -> str:
    """Ask the modulation classifier and map its label to a slicing family."""
    try:
        from core.modulation_classify import (
            classify_modulation, OOK as M_OOK, FSK as M_FSK, PSK as M_PSK)
        label = classify_modulation(iq, fs).modulation
        return {M_OOK: OOK, M_FSK: FSK, M_PSK: PSK}.get(label, OOK)
    except Exception:                       # pragma: no cover
        return OOK


def slice_bits(iq, fs: float, *, family: str | None = None,
               samples_per_symbol: float | None = None,
               symbol_rate: float | None = None,
               phase: float = 0.5) -> SliceResult:
    """Recover a symbol stream from IQ.

    family              — OOK/FSK/PSK; auto-detected from the modulation
                          classifier when omitted.
    samples_per_symbol  — override the estimator (deterministic slicing).
    symbol_rate         — alternative to sps: sps = fs / symbol_rate.
    phase               — 0..1 sampling instant within each symbol (0.5 = centre).
    """
    iq = np.asarray(iq, dtype=np.complex64)
    if iq.size < 4 or fs <= 0:
        return SliceResult()
    fam = (family or _family_from_modulation(iq, fs)).upper()
    if fam not in (OOK, FSK, PSK):
        fam = OOK
    soft, kind = _soft_signal(iq, fam)
    binary = _binarize(soft, kind)

    if samples_per_symbol and samples_per_symbol >= 1.0:
        sps = float(samples_per_symbol)
    elif symbol_rate and symbol_rate > 0:
        sps = float(fs) / float(symbol_rate)
    else:
        sps = estimate_sps(binary)
    if sps < 1.0:
        return SliceResult(family=fam)

    bits = _sample_symbols(binary, sps, phase)
    return SliceResult(
        bits=bits, family=fam,
        samples_per_symbol=round(sps, 3),
        symbol_rate=round(float(fs) / sps, 3) if sps else 0.0,
        n_symbols=len(bits),
        confidence=round(_eye_confidence(soft, binary, sps, kind), 3),
    )


# ── bit packing ───────────────────────────────────────────────────────────────

def bits_to_bytes(bits, msb_first: bool = True) -> bytes:
    """Pack a 0/1 list into bytes (trailing partial byte dropped)."""
    b = [1 if x else 0 for x in bits]
    n = len(b) - (len(b) % 8)
    out = bytearray()
    for i in range(0, n, 8):
        octet = b[i:i + 8]
        if not msb_first:
            octet = octet[::-1]
        val = 0
        for bit in octet:
            val = (val << 1) | bit
        out.append(val)
    return bytes(out)


def bits_to_hex(bits, msb_first: bool = True) -> str:
    return bits_to_bytes(bits, msb_first).hex()
