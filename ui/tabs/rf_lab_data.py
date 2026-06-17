from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- ui/tabs/rf_lab_data.py
Pure-data constants for the RF Lab Emergency Monitor.
No Qt imports — safe to import in tests without PyQt6.
"""

# (freq_hz, name, category, description)
BUILTIN_FREQS: list[tuple[int, str, str, str]] = [
    # NOAA Weather Radio
    (162_400_000, "NOAA WX-1",   "Weather", "NOAA Weather Radio 162.400 MHz"),
    (162_425_000, "NOAA WX-2",   "Weather", "NOAA Weather Radio 162.425 MHz"),
    (162_450_000, "NOAA WX-3",   "Weather", "NOAA Weather Radio 162.450 MHz"),
    (162_475_000, "NOAA WX-4",   "Weather", "NOAA Weather Radio 162.475 MHz"),
    (162_500_000, "NOAA WX-5",   "Weather", "NOAA Weather Radio 162.500 MHz"),
    (162_525_000, "NOAA WX-6",   "Weather", "NOAA Weather Radio 162.525 MHz"),
    (162_550_000, "NOAA WX-7",   "Weather", "NOAA Weather Radio 162.550 MHz"),
    # Aviation
    (121_500_000, "GUARD 121.5", "Aviation", "International aviation distress/guard frequency"),
    (243_000_000, "MIL GUARD",   "Aviation", "Military UHF guard frequency (243.0 MHz)"),
    (122_750_000, "CTAF 122.75", "Aviation", "Air-to-air common traffic advisory"),
    # Marine
    (156_800_000, "Marine Ch.16","Marine",   "International maritime distress and calling"),
    (156_300_000, "Marine Ch.6", "Marine",   "Intership safety channel"),
    (161_975_000, "AIS Ch.87B",  "Marine",   "AIS (Automatic Identification System) channel A"),
    (162_025_000, "AIS Ch.88B",  "Marine",   "AIS channel B"),
    # Public Safety / EMS
    (155_340_000, "EMS Simplex", "EMS",      "Common EMS simplex interoperability"),
    (155_475_000, "Fire Disp.",  "EMS",      "Common fire dispatch (varies by region)"),
    (460_525_000, "EMS UHF",     "EMS",      "UHF EMS simplex interop (varies by region)"),
    # ISS / Space
    (145_800_000, "ISS Voice",   "Space",    "ISS amateur radio downlink voice"),
    (145_825_000, "ISS Packet",  "Space",    "ISS APRS/packet downlink"),
    # FM Broadcast (reference / education)
    (88_000_000,  "FM Band Lo",  "Broadcast","FM broadcast band start (88.0 MHz)"),
    (108_000_000, "FM Band Hi",  "Broadcast","FM broadcast band end (108.0 MHz)"),
]

CATEGORY_COLORS: dict[str, str] = {
    "Weather":   "#00aaff",
    "Aviation":  "#ffcc00",
    "Marine":    "#44cc88",
    "EMS":       "#ff6644",
    "Space":     "#cc88ff",
    "Broadcast": "#aaaaaa",
    "Custom":    "#3fbe6f",
}
