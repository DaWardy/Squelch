# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/authorization.py

Transmit authorization (ROADMAP Phase 5, AUTH-LAYER) — the compliance gate.

Squelch can drive TX-capable SDRs and rigs, so transmit is **default-deny**:
the operator must (1) accept a legal-use acknowledgment and (2) opt specific
bands in. A frequency is only transmittable if it falls in an authorized band.

A buried **unrestricted override** exists for emergencies, or for operators who
hold authorization across the spectrum (e.g. licensed/agency use). It is off by
default, must be explicitly enabled behind disclaimers in the UI, and every
keying should be logged by the caller (core.netlog). **Legal responsibility
rests with the operator** — `can_transmit()` returns a decision; it does not
and cannot grant legal authority.

This module is the pure decision core. The UI/FSM wiring (settings panel,
AppState block, transmit_iq gate) consumes `can_transmit()`.
"""

import logging
from dataclasses import dataclass, field

from core.band_plan import band_at_freq, SERVICE_BANDS

log = logging.getLogger(__name__)

# Config keys
_CFG_ACK         = "tx.auth.acknowledged"
_CFG_BANDS       = "tx.auth.allowed_bands"
_CFG_UNRESTRICT  = "tx.auth.unrestricted"


@dataclass
class AuthDecision:
    """Result of a transmit-permission check."""
    allowed: bool
    reason:  str
    band:    str = ""          # resolved band name, when known

    def __bool__(self) -> bool:
        return self.allowed


@dataclass
class AuthorizationProfile:
    """Operator's transmit authorization. Default-deny: nothing allowed until
    the legal acknowledgment is accepted and bands are opted in."""
    acknowledged: bool = False
    allowed_bands: set = field(default_factory=set)   # band names, e.g. "20m"
    unrestricted: bool = False                         # buried emergency override

    # ── persistence ────────────────────────────────────────────────────────

    @classmethod
    def from_cfg(cls, cfg) -> "AuthorizationProfile":
        try:
            ack = bool(cfg.get(_CFG_ACK, False))
            bands = cfg.get(_CFG_BANDS, []) or []
            unrestricted = bool(cfg.get(_CFG_UNRESTRICT, False))
            return cls(acknowledged=ack,
                       allowed_bands=set(bands),
                       unrestricted=unrestricted)
        except Exception:
            return cls()

    def save(self, cfg) -> None:
        cfg.set(_CFG_ACK, bool(self.acknowledged))
        cfg.set(_CFG_BANDS, sorted(self.allowed_bands))
        cfg.set(_CFG_UNRESTRICT, bool(self.unrestricted))

    # ── mutators ─────────────────────────────────────────────────────────────

    def allow_band(self, name: str) -> None:
        if name:
            self.allowed_bands.add(name)

    def deny_band(self, name: str) -> None:
        self.allowed_bands.discard(name)


def resolve_band(freq_hz: int):
    """Return the Band for a frequency (amateur first, then service), or None."""
    b = band_at_freq(int(freq_hz or 0))
    if b is not None:
        return b
    for sb in SERVICE_BANDS:
        if sb.freq_lo <= freq_hz <= sb.freq_hi:
            return sb
    return None


def can_transmit(freq_hz: int, profile: AuthorizationProfile) -> AuthDecision:
    """Decide whether TX is permitted at `freq_hz` under `profile`.

    Order: legal acknowledgment → unrestricted override → per-band allow-list.
    Default-deny throughout. The caller is responsible for logging the keying
    and for the legality of the operation.
    """
    freq_hz = int(freq_hz or 0)

    if not profile.acknowledged:
        return AuthDecision(False, "Legal-use acknowledgment not accepted")

    if profile.unrestricted:
        band = resolve_band(freq_hz)
        return AuthDecision(
            True, "Unrestricted override enabled — operator responsibility",
            band.name if band else "")

    if freq_hz <= 0:
        return AuthDecision(False, "Invalid frequency")

    band = resolve_band(freq_hz)
    if band is None:
        return AuthDecision(
            False, "Frequency is not within a known/authorized band")
    if band.name in profile.allowed_bands:
        return AuthDecision(True, f"Band {band.name} authorized", band.name)
    return AuthDecision(
        False, f"Band {band.name} not in the authorized list", band.name)
