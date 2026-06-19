# Squelch — core/guest_op.py
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
from __future__ import annotations
"""
Guest Operator support.

Guest Operator mode is for a student or visiting operator getting on the air
at someone else's station. Unlike Demo mode, it does NOT block transmit — the
guest is operating for real (typically under supervision). It:

  * tracks the guest operator's callsign separately from the station owner,
  * supplies that callsign to the modes for correct identification,
  * generates a plain-language CONTACT SCRIPT the operator can read aloud when
    making a voice contact — invaluable for a nervous first-time student.

US identification note (FCC §97.119): the *station* must identify with the
station callsign at least every 10 minutes and at the end of a contact. When a
guest operates, the licensed control operator is responsible. Squelch keeps
both calls so logs and IDs are correct; it does not give legal advice.
"""
import re
from dataclasses import dataclass

# NATO phonetic alphabet for reading a callsign aloud
_PHONETIC = {
    "A": "Alpha", "B": "Bravo", "C": "Charlie", "D": "Delta",
    "E": "Echo", "F": "Foxtrot", "G": "Golf", "H": "Hotel",
    "I": "India", "J": "Juliet", "K": "Kilo", "L": "Lima",
    "M": "Mike", "N": "November", "O": "Oscar", "P": "Papa",
    "Q": "Quebec", "R": "Romeo", "S": "Sierra", "T": "Tango",
    "U": "Uniform", "V": "Victor", "W": "Whiskey", "X": "X-ray",
    "Y": "Yankee", "Z": "Zulu",
    "0": "Zero", "1": "One", "2": "Two", "3": "Three", "4": "Four",
    "5": "Five", "6": "Six", "7": "Seven", "8": "Eight", "9": "Niner",
    "/": "stroke",
}


def phonetic(callsign: str) -> str:
    """Spell a callsign in NATO phonetics: 'W1AW' -> 'Whiskey One Alpha Whiskey'."""
    out = []
    for ch in (callsign or "").upper():
        out.append(_PHONETIC.get(ch, ch))
    return " ".join(out)


@dataclass
class GuestSession:
    guest_call:   str = ""     # the guest/student operator's callsign
    station_call: str = ""     # the station owner's callsign
    supervised:   bool = True   # operating under a control operator?

    @property
    def active(self) -> bool:
        return bool(self.guest_call)


def voice_contact_script(guest_call: str, station_call: str,
                         your_grid: str = "",
                         supervised: bool = True) -> str:
    """Build a readable voice-contact script for a guest/student operator.

    Returns a short, friendly walkthrough the operator can read aloud while
    making an SSB/FM contact, with the callsign in phonetics.
    """
    gc   = (guest_call or "").upper()
    sc   = (station_call or "").upper()
    gp   = phonetic(gc)
    parts = []

    parts.append("=== VOICE CONTACT SCRIPT ===")
    if sc and sc != gc:
        parts.append(
            f"You are operating station {sc} as guest operator {gc}.")
    else:
        parts.append(f"You are operating as {gc}.")
    parts.append("")

    parts.append("1) CALLING CQ (looking for any contact):")
    parts.append(f'   "CQ CQ CQ, this is {gp} calling CQ and standing by."')
    parts.append("   (Say the callsign twice if the band is busy.)")
    parts.append("")

    parts.append("2) SOMEONE ANSWERS — they give their call. Reply:")
    parts.append(
        f'   "[their call], this is {gp}. Thanks for the call. '
        'You are 5 and 9. ' +
        (f'My grid is {your_grid.upper()}. ' if your_grid else "") +
        'My name is [your name]. How copy? Over."')
    parts.append("")

    parts.append("3) NORMAL EXCHANGE — signal report, name, location.")
    parts.append('   Listen, then respond to what they say. Keep it friendly.')
    parts.append("")

    parts.append("4) ENDING THE CONTACT (identify at the end):")
    if sc and sc != gc:
        parts.append(
            f'   "Thanks for the QSO. 73! This is {gc} operating {sc}, '
            'clear."')
    else:
        parts.append(f'   "Thanks for the QSO. 73! This is {gc}, clear."')
    parts.append("")

    parts.append("REMINDERS:")
    parts.append("  - Listen first; make sure the frequency is clear.")
    parts.append("  - Identify at least every 10 minutes and at the end.")
    if supervised:
        parts.append("  - Your control operator is supervising — ask anytime.")
    parts.append('  - "73" means best regards. "Over" = your turn. '
                 '"Clear" = done.')
    return "\n".join(parts)


_CALL_RE = re.compile(r"[^A-Z0-9/]")


def operating_callsign(cfg) -> str:
    """The callsign to identify with for ANY mode (FT8, FT4, JS8, PSK, RTTY,
    CW, SSB, Winlink...).  Priority order:

      1. Guest operator (supervised student) — guest.callsign
      2. Event / portable override — station.event_callsign
         (e.g. W1AW/5 for portable, W100AW for a special-event station)
      3. Normal station callsign — cfg.callsign

    Strips any character outside [A-Z0-9/] before returning — FCC §97.119
    requires a valid callsign; injected chars would corrupt OTA identification.
    """
    try:
        if cfg.get("guest.active", False):
            gc = (cfg.get("guest.callsign", "") or "").strip().upper()
            if gc:
                return _CALL_RE.sub("", gc)
    except Exception:
        pass
    try:
        ec = (cfg.get("station.event_callsign", "") or "").strip().upper()
        if ec:
            return _CALL_RE.sub("", ec)
    except Exception:
        pass
    try:
        raw = (cfg.callsign or "").upper()
        return _CALL_RE.sub("", raw)
    except Exception:
        return ""
