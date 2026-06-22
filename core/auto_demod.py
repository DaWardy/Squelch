# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/auto_demod.py

Automatic demodulator + bandwidth selection by frequency.

As the SDR tunes across the spectrum, this picks the right demodulation mode
and IF bandwidth for where it lands — WFM for the FM broadcast band, AM for
airband and AM/SW broadcast, NFM for VHF/UHF voice & weather, SSB/CW for the
HF amateur segments, etc. Pure and unit-tested; the SDR tab applies the result
when "Auto" is enabled.

Modes are exactly the SDR tab's set: AM / NFM / WFM / USB / LSB / CW.
"""

from dataclasses import dataclass

from core.band_plan import band_at_freq, segment_at_freq, suggested_mode, SegType


@dataclass
class DemodSuggestion:
    mode:         str        # AM/NFM/WFM/USB/LSB/CW
    bandwidth_hz: int
    label:        str        # human description, e.g. "FM Broadcast"
    confidence:   float      # 0..1


# Default IF bandwidth (Hz) per demod mode.
_MODE_BW = {
    "WFM": 200_000, "NFM": 15_000, "AM": 10_000,
    "USB": 2_500,   "LSB": 2_500,  "CW": 500,
}

# Rig-style mode (band_plan.suggested_mode) → SDR demod mode.
_RIG_TO_SDR = {
    "FM": "NFM", "FMN": "NFM", "DV": "NFM",
    "AM": "AM",
    "USB": "USB", "PKTUSB": "USB", "DIGU": "USB", "RTTY": "USB",
    "LSB": "LSB", "PKTLSB": "LSB", "DIGL": "LSB",
    "CW": "CW", "CWR": "CW",
}

# Fixed broadcast / non-amateur ranges band_plan does not cover.
# (freq_lo, freq_hi, mode, label) — checked before band_plan.
_FIXED_RANGES = [
    (530_000,      1_710_000,  "AM",  "AM Broadcast"),
    (88_000_000,   108_000_000, "WFM", "FM Broadcast"),
    (108_000_000,  137_000_000, "AM",  "Airband"),
    (137_000_000,  138_000_000, "NFM", "Weather satellite / VHF"),
]


def _sw_broadcast(freq_hz: int) -> bool:
    """Rough HF shortwave broadcast coverage (2.3–26.1 MHz, excl. amateur)."""
    return 2_300_000 <= freq_hz <= 26_100_000


def suggest_demod(freq_hz: int) -> DemodSuggestion:
    """Best demod mode + IF bandwidth for a frequency."""
    freq_hz = int(freq_hz or 0)
    if freq_hz <= 0:
        return DemodSuggestion("NFM", _MODE_BW["NFM"], "Unknown", 0.0)

    # 1) Fixed broadcast / airband ranges (most specific, high confidence).
    for lo, hi, mode, label in _FIXED_RANGES:
        if lo <= freq_hz <= hi:
            return DemodSuggestion(mode, _MODE_BW[mode], label, 0.9)

    # 2) Amateur bands — use the band-plan segment to pick mode.
    band = band_at_freq(freq_hz)
    if band is not None:
        return _amateur_suggestion(freq_hz, band)

    # 3) Service bands & other knowns via the allocation classifier.
    svc = _service_suggestion(freq_hz)
    if svc is not None:
        return svc

    # 4) Fallbacks: HF shortwave = AM; other HF = USB/LSB; VHF+ = NFM.
    if _sw_broadcast(freq_hz):
        return DemodSuggestion("AM", 9_000, "Shortwave Broadcast", 0.5)
    if freq_hz < 30_000_000:
        mode = "USB" if freq_hz >= 10_000_000 else "LSB"
        return DemodSuggestion(mode, _MODE_BW[mode], "HF (SSB)", 0.3)
    return DemodSuggestion("NFM", _MODE_BW["NFM"], "VHF/UHF (NFM)", 0.3)


def _amateur_suggestion(freq_hz: int, band) -> DemodSuggestion:
    seg = segment_at_freq(freq_hz)
    rig_mode = suggested_mode(freq_hz)
    mode = _RIG_TO_SDR.get(rig_mode, "NFM")
    # CW segments are narrow regardless of what suggested_mode says.
    if seg is not None and seg.seg_type == SegType.CW:
        mode = "CW"
    label = f"{band.name} amateur"
    return DemodSuggestion(mode, _MODE_BW[mode], label, 0.6)


def _service_suggestion(freq_hz: int):
    try:
        from core.signal_classify import classify_by_allocation
    except Exception:
        return None
    c = classify_by_allocation(freq_hz)
    if not c.is_known:
        return None
    mode = _RIG_TO_SDR.get(c.modulation, c.modulation if c.modulation in _MODE_BW else "NFM")
    if mode not in _MODE_BW:
        mode = "NFM"
    return DemodSuggestion(mode, _MODE_BW[mode], c.label, min(c.confidence, 0.8))


# ── bandwidth-label matching (for the SDR tab's fixed BW combo) ───────────────

def parse_bw_label(label: str) -> int:
    """'2.5 kHz' → 2500. Returns 0 on bad input."""
    try:
        parts = str(label).split()
        val = float(parts[0])
        unit = parts[1].lower() if len(parts) > 1 else "hz"
        mult = {"hz": 1, "khz": 1_000, "mhz": 1_000_000}.get(unit, 1)
        return int(val * mult)
    except Exception:
        return 0


def nearest_bw_label(bw_hz: int, labels) -> str:
    """Pick the label from `labels` whose bandwidth is closest to bw_hz."""
    best, best_d = "", None
    for lab in labels:
        hz = parse_bw_label(lab)
        if hz <= 0:
            continue
        d = abs(hz - bw_hz)
        if best_d is None or d < best_d:
            best, best_d = lab, d
    return best
