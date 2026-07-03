# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- core/tx_license.py

License-class TX-privilege decisions (pure logic; no Qt, no hardware).

Answers two operator-facing questions the UI needs before keying up:

  1. Given the operator's license class and a frequency, may they transmit
     there under amateur privileges? (Extra ⊇ General ⊇ Technician ⊇ Novice;
     a segment tagged "Extra" is Extra-only, "All" is any class.)
  2. Does this TX need a first-time out-of-band acknowledgment? — True whenever
     the frequency is outside the amateur bands, the class doesn't cover the
     amateur segment, or the operator picked the "Other / Emergency" override.

This is the decision layer only. Persisting the one-time acknowledgment and
gating the actual transmit_iq()/AppState path is the caller's job (see
core/authorization.py for the per-band allow-list gate this complements).
"""

from __future__ import annotations

from dataclasses import dataclass

from core.band_plan import License, band_at_freq, segment_at_freq

# The TX license-class dropdown, in privilege order, plus the deliberate
# non-amateur override the operator must consciously choose.
OTHER_EMERGENCY = "Other / Emergency"
LICENSE_CHOICES = [
    License.TECHNICIAN,
    License.GENERAL,
    License.EXTRA,
    OTHER_EMERGENCY,
]

# Higher rank = broader privileges. "All" means any class may use the segment.
_RANK = {
    License.ALL:        0,
    License.NOVICE:     1,
    License.TECHNICIAN: 2,
    License.GENERAL:    3,
    License.EXTRA:      4,
}


def license_rank(license_class: str) -> int:
    """Privilege rank for a class (unknown/override classes rank 0)."""
    return _RANK.get(license_class, 0)


def is_amateur_freq(freq_hz: int) -> bool:
    """True if the frequency falls in an amateur band (not a service band)."""
    b = band_at_freq(int(freq_hz or 0))
    return bool(b) and getattr(b, "category", "Amateur") == "Amateur"


@dataclass
class TxLicenseDecision:
    """Outcome of a license-class TX-privilege check for one frequency."""
    freq_hz:       int
    license_class: str
    in_amateur:    bool          # frequency is in an amateur band
    license_ok:    bool          # operator's class covers the amateur segment
    needs_ack:     bool          # first-time out-of-band / override warning due
    label:         str = ""      # short human-readable summary


def tx_privilege(freq_hz: int, license_class: str) -> TxLicenseDecision:
    """Decide amateur TX privilege at *freq_hz* for *license_class*.

    Never raises. The "Other / Emergency" class is treated as a non-amateur
    override: it is not checked against amateur privileges and always needs the
    acknowledgment.
    """
    freq_hz = int(freq_hz or 0)
    in_amateur = is_amateur_freq(freq_hz)

    if license_class == OTHER_EMERGENCY:
        return TxLicenseDecision(
            freq_hz, license_class, in_amateur, license_ok=False,
            needs_ack=True,
            label="Other / Emergency — outside normal amateur privileges")

    if not in_amateur:
        return TxLicenseDecision(
            freq_hz, license_class, in_amateur=False, license_ok=False,
            needs_ack=True,
            label="Outside the amateur bands — TX requires acknowledgment")

    seg = segment_at_freq(freq_hz)
    required = seg.license if seg else License.EXTRA   # unknown ⇒ strictest
    license_ok = license_rank(license_class) >= license_rank(required)
    if license_ok:
        return TxLicenseDecision(
            freq_hz, license_class, in_amateur=True, license_ok=True,
            needs_ack=False,
            label=f"OK — {license_class} privileges")
    return TxLicenseDecision(
        freq_hz, license_class, in_amateur=True, license_ok=False,
        needs_ack=True,
        label=f"Segment requires {required} — above {license_class}")


def allowed_segments(license_class: str):
    """Amateur BandSegments the class may transmit in (for TX-freq filtering).

    Empty for the "Other / Emergency" override (it isn't an amateur class).
    """
    if license_class == OTHER_EMERGENCY:
        return []
    from core.band_plan import BANDS
    rank = license_rank(license_class)
    out = []
    for band in BANDS:
        for seg in getattr(band, "segments", []):
            if license_rank(seg.license) <= rank:
                out.append(seg)
    return out
