from __future__ import annotations
"""Spot-tuning helpers — pure Python, no Qt dependency.

Used by ModesTab and testable without a display.
"""


def infer_rig_mode(mode_str: str, freq_hz: int) -> str:
    """Map a DX-spot / SOTA-POTA mode string to a Hamlib rig-mode string.

    Falls back to USB (≥10 MHz) or LSB (<10 MHz) when mode is unrecognised.
    """
    m = (mode_str or "").upper().strip()
    if m in ("CW", "CW-R"):
        return "CW"
    if m in ("FT8", "FT4", "JS8", "WSPR", "PSK", "PSK31", "PSK63",
             "PKTUSB", "DIGI", "VARA"):
        return "PKTUSB"
    if m in ("RTTY", "RTTY-R", "PKTLSB"):
        return "PKTLSB"
    if m == "AM":
        return "AM"
    if m == "FM":
        return "FM"
    if m in ("LSB", "USB"):
        return m
    # SSB without polarity or unknown → infer from frequency
    return "USB" if freq_hz >= 10_000_000 else "LSB"
