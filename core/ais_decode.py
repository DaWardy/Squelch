# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/ais_decode.py

AIS (Automatic Identification System) decoder — marine vessel position/ID
messages on 161.975 / 162.025 MHz (VHF ch 87B/88B). A very common "decode a
signal in the wild" target for the workbench.

Two entry points:
  * `decode_ais_nmea(payload, fill_bits)` — the 6-bit-ASCII "armored" payload of
    an AIVDM/AIVDO sentence (what other tools emit as text) → `AISMessage`.
    Verified against published NMEA test sentences.
  * `parse_ais_fields(bits)` — a raw AIS payload bit list (e.g. from the RF
    path: bitslicer → NRZI → HDLC de-frame) → `AISMessage`. Same field layout.

Decodes the common position reports — types 1/2/3 (Class A) and 18 (Class B):
message type, MMSI, latitude, longitude, speed-over-ground, course, heading.
Pure Python, never raises (returns an AISMessage with valid=False on bad input).
"""

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class AISMessage:
    type:       int   = 0
    repeat:     int   = 0
    mmsi:       int   = 0
    lat:        float = 0.0     # degrees (+N), 91.0 = not available
    lon:        float = 0.0     # degrees (+E), 181.0 = not available
    sog:        float = 0.0     # knots (speed over ground)
    cog:        float = 0.0     # degrees (course over ground)
    heading:    int   = 511     # degrees true, 511 = not available
    nav_status: int   = 15      # 15 = not defined
    valid:      bool  = False
    note:       str   = ""

    @property
    def has_position(self) -> bool:
        return self.valid and abs(self.lat) <= 90.0 and abs(self.lon) <= 180.0


def _armored_to_bits(payload: str) -> list:
    """AIS 6-bit ASCII "armor" → bit list (MSB first per char)."""
    bits: list = []
    for ch in payload:
        v = ord(ch) - 48
        if v > 40:
            v -= 8
        if v < 0 or v > 63:
            continue
        for i in range(5, -1, -1):
            bits.append((v >> i) & 1)
    return bits


def _u(bits, start: int, length: int) -> int:
    """Unsigned big-endian integer from bits[start:start+length]."""
    v = 0
    for b in bits[start:start + length]:
        v = (v << 1) | (b & 1)
    return v


def _s(bits, start: int, length: int) -> int:
    """Two's-complement signed integer from a bit slice."""
    v = _u(bits, start, length)
    if v >= (1 << (length - 1)):
        v -= (1 << length)
    return v


def parse_ais_fields(bits) -> AISMessage:
    """Parse an AIS payload bit list → AISMessage (types 1/2/3/18). Never raises."""
    msg = AISMessage()
    try:
        if len(bits) < 38:
            msg.note = "payload too short"
            return msg
        msg.type = _u(bits, 0, 6)
        msg.repeat = _u(bits, 6, 2)
        msg.mmsi = _u(bits, 8, 30)
        if msg.type in (1, 2, 3) and len(bits) >= 137:
            msg.nav_status = _u(bits, 38, 4)
            msg.sog = _u(bits, 50, 10) / 10.0
            msg.lon = _s(bits, 61, 28) / 600000.0
            msg.lat = _s(bits, 89, 27) / 600000.0
            msg.cog = _u(bits, 116, 12) / 10.0
            msg.heading = _u(bits, 128, 9)
            msg.valid = True
        elif msg.type == 18 and len(bits) >= 133:
            msg.sog = _u(bits, 46, 10) / 10.0
            msg.lon = _s(bits, 57, 28) / 600000.0
            msg.lat = _s(bits, 85, 27) / 600000.0
            msg.cog = _u(bits, 112, 12) / 10.0
            msg.heading = _u(bits, 124, 9)
            msg.valid = True
        else:
            # still expose type + MMSI for other message types
            msg.valid = msg.mmsi > 0
            msg.note = f"type {msg.type} not fully parsed"
    except Exception as exc:                        # pragma: no cover
        log.debug("parse_ais_fields failed: %s", exc)
        msg.note = f"error: {exc}"
    return msg


def decode_ais_nmea(payload: str, fill_bits: int = 0) -> AISMessage:
    """Decode the armored payload field of an AIVDM/AIVDO sentence.

    `payload` is the 6th comma-field (e.g. '15M67FC000G?ufbE`FepT@3n00Sa');
    `fill_bits` is the field just before the checksum. Never raises."""
    try:
        bits = _armored_to_bits(payload)
        if fill_bits and 0 < fill_bits < len(bits):
            bits = bits[:len(bits) - fill_bits]
        return parse_ais_fields(bits)
    except Exception as exc:                         # pragma: no cover
        log.debug("decode_ais_nmea failed: %s", exc)
        return AISMessage(note=f"error: {exc}")
