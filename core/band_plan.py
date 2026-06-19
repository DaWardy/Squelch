# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
#
# This program is free software: you can redistribute it
# and/or modify it under the terms of the GNU General
# Public License as published by the Free Software
# Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General
# Public License along with this program. If not, see
# <https://www.gnu.org/licenses/>.

from __future__ import annotations
"""Squelch -- core/band_plan.py
FCC Part 97 amateur radio band plan.
Segments colored by mode type and license privilege.
Used by spectrum widget for visual band overlays.
"""

from dataclasses import dataclass
from core.constants import BAND_EDGES_R2 as BAND_EDGES


# ── Segment types ─────────────────────────────────────────────────────────

class SegType:
    CW          = "CW"
    CW_DIGITAL  = "CW+Digital"
    DIGITAL     = "Digital"
    PHONE       = "Phone"
    AM          = "AM"
    IMAGE       = "Image/SSTV"
    BEACON      = "Beacons"
    SATELLITE   = "Satellite"
    REPEATER    = "Repeater"
    SIMPLEX     = "Simplex"
    CALLING     = "Calling"
    GUARD       = "Guard/EmComm"
    MIXED       = "Mixed"
    NOVICE      = "Novice/Tech"
    # Non-amateur service types
    FRS        = "FRS"
    GMRS_CHAN  = "GMRS"
    CB         = "CB"
    MURS       = "MURS"
    ISM        = "ISM/Unlicensed"
    WIFI       = "Wi-Fi/BT"


# Segment colors (RGBA hex strings for pyqtgraph)
SEG_COLORS = {
    SegType.CW:          "#6633cc80",   # purple
    SegType.CW_DIGITAL:  "#3355cc80",   # blue
    SegType.DIGITAL:     "#3388cc80",   # light blue
    SegType.PHONE:       "#33aa5580",   # green
    SegType.AM:          "#cc880080",   # orange
    SegType.IMAGE:       "#cc550080",   # red-orange
    SegType.BEACON:      "#ccaa2280",   # amber
    SegType.SATELLITE:   "#22aabb80",   # teal
    SegType.REPEATER:    "#55aa5580",   # medium green
    SegType.SIMPLEX:     "#44aa8880",   # seafoam
    SegType.CALLING:     "#ffaa0080",   # bright amber
    SegType.GUARD:       "#ff444480",   # red
    SegType.MIXED:       "#66886680",   # muted green
    SegType.NOVICE:      "#44668880",   # muted blue
    # Service band colors
    SegType.FRS:         "#ffaa4480",   # warm orange
    SegType.GMRS_CHAN:   "#ff884480",   # deeper orange
    SegType.CB:          "#ddaa2280",   # golden amber
    SegType.MURS:        "#aa88dd80",   # muted purple
    SegType.ISM:         "#88bb3380",   # olive green
    SegType.WIFI:        "#44aadd80",   # bright blue
}

# License class privileges
class License:
    TECHNICIAN = "Technician"
    GENERAL    = "General"
    EXTRA      = "Extra"
    ALL        = "All"
    NOVICE     = "Novice"
    # Service band license types (non-amateur)
    NONE       = "None required"
    GMRS_LIC   = "GMRS License"


@dataclass
class BandSegment:
    freq_lo:    int           # Hz
    freq_hi:    int           # Hz
    seg_type:   str           # SegType constant
    license:    str           # License constant
    mode_notes: str           # human readable
    tooltip:    str           # shown on hover
    color:      str = ""      # auto-filled from SEG_COLORS

    def __post_init__(self):
        if not self.color:
            self.color = SEG_COLORS.get(self.seg_type, "#44444480")

    @property
    def center_hz(self) -> int:
        return (self.freq_lo + self.freq_hi) // 2

    @property
    def width_hz(self) -> int:
        return self.freq_hi - self.freq_lo

    @property
    def label(self) -> str:
        """Short label for display on spectrum."""
        return self.seg_type


@dataclass
class Band:
    name:     str         # e.g. "20m"
    freq_lo:  int         # Hz
    freq_hi:  int         # Hz
    segments: list        # list of BandSegment
    notes:    str = ""
    category: str = "Amateur"  # "Amateur", "CB", "FRS/GMRS", "MURS", "ISM/Unlicensed"

    def segment_at(self, freq_hz: int) -> BandSegment | None:
        for s in self.segments:
            if s.freq_lo <= freq_hz <= s.freq_hi:
                return s
        return None

    def in_band(self, freq_hz: int) -> bool:
        return self.freq_lo <= freq_hz <= self.freq_hi


# ── FCC Band Plan ─────────────────────────────────────────────────────────
# Source: FCC Part 97 and ARRL Band Plan
# https://www.arrl.org/band-plan

BANDS: list[Band] = [

    Band("160m", 1_800_000, 2_000_000, [
        BandSegment(1_800_000, 1_838_000, SegType.CW,      License.ALL,
                    "CW only",
                    "1.800-1.838 MHz\nCW only\nAll license classes"),
        BandSegment(1_838_000, 1_840_000, SegType.DIGITAL, License.ALL,
                    "Digital modes",
                    "1.838-1.840 MHz\nDigital modes\nAll license classes"),
        BandSegment(1_840_000, 2_000_000, SegType.PHONE,   License.ALL,
                    "Phone (LSB) + CW",
                    "1.840-2.000 MHz\nPhone (LSB) and CW\nAll license classes\n"
                    "Common calling: 1.860 MHz"),
    ]),

    Band("80m", 3_500_000, 4_000_000, [
        BandSegment(3_500_000, 3_525_000, SegType.CW,      License.EXTRA,
                    "CW — Extra only",
                    "3.500-3.525 MHz\nCW only\nExtra class only"),
        BandSegment(3_525_000, 3_600_000, SegType.CW,      License.GENERAL,
                    "CW — General+",
                    "3.525-3.600 MHz\nCW only\nGeneral and Extra\n"
                    "3.570-3.600: Digital modes"),
        BandSegment(3_600_000, 3_700_000, SegType.PHONE,   License.EXTRA,
                    "Phone (LSB) — Extra only",
                    "3.600-3.700 MHz\nPhone (LSB)\nExtra class only"),
        BandSegment(3_700_000, 3_800_000, SegType.PHONE,   License.GENERAL,
                    "Phone (LSB) — General+",
                    "3.700-3.800 MHz\nPhone (LSB)\nGeneral and Extra\n"
                    "3.733 MHz: SSTV calling"),
        BandSegment(3_800_000, 4_000_000, SegType.PHONE,   License.ALL,
                    "Phone (LSB) — All classes",
                    "3.800-4.000 MHz\nPhone (LSB)\nAll license classes\n"
                    "3.885 MHz: AM calling\n3.990 MHz: Net calling"),
    ]),

    Band("60m", 5_330_500, 5_405_000, [
        BandSegment(5_330_500, 5_332_000, SegType.MIXED,   License.GENERAL,
                    "Ch 1 — USB/CW/Digital",
                    "Channel 1: 5.3305 MHz\nUSB Phone, CW, Digital\nMax 100W PEP\nGeneral+"),
        BandSegment(5_346_500, 5_348_000, SegType.MIXED,   License.GENERAL,
                    "Ch 2 — USB/CW/Digital",
                    "Channel 2: 5.3465 MHz\nUSB Phone, CW, Digital"),
        BandSegment(5_357_000, 5_358_500, SegType.MIXED,   License.GENERAL,
                    "Ch 3 — USB/CW/Digital",
                    "Channel 3: 5.3570 MHz\nUSB Phone, CW, Digital"),
        BandSegment(5_371_500, 5_373_000, SegType.MIXED,   License.GENERAL,
                    "Ch 4 — USB/CW/Digital",
                    "Channel 4: 5.3715 MHz\nUSB Phone, CW, Digital"),
        BandSegment(5_403_500, 5_405_000, SegType.MIXED,   License.GENERAL,
                    "Ch 5 — USB/CW/Digital",
                    "Channel 5: 5.4035 MHz\nUSB Phone, CW, Digital"),
    ]),

    Band("40m", 7_000_000, 7_300_000, [
        BandSegment(7_000_000, 7_025_000, SegType.CW,      License.EXTRA,
                    "CW — Extra only",
                    "7.000-7.025 MHz\nCW only\nExtra class only"),
        BandSegment(7_025_000, 7_075_000, SegType.CW,      License.GENERAL,
                    "CW — General+",
                    "7.025-7.075 MHz\nCW only\nGeneral and Extra\n"
                    "7.040 MHz: RTTY/Digital calling"),
        BandSegment(7_075_000, 7_100_000, SegType.DIGITAL, License.GENERAL,
                    "Digital — General+",
                    "7.075-7.100 MHz\nDigital modes\nGeneral and Extra\n"
                    "7.074 MHz: FT8"),
        BandSegment(7_100_000, 7_125_000, SegType.PHONE,   License.EXTRA,
                    "Phone (LSB) — Extra only",
                    "7.100-7.125 MHz\nPhone (LSB)\nExtra class only"),
        BandSegment(7_125_000, 7_175_000, SegType.PHONE,   License.GENERAL,
                    "Phone (LSB) — General+",
                    "7.125-7.175 MHz\nPhone (LSB)\nGeneral and Extra"),
        BandSegment(7_175_000, 7_300_000, SegType.PHONE,   License.ALL,
                    "Phone (LSB) — All classes",
                    "7.175-7.300 MHz\nPhone (LSB)\nAll license classes\n"
                    "7.200 MHz: Calling frequency\n7.290 MHz: AM calling"),
    ]),

    Band("30m", 10_100_000, 10_150_000, [
        BandSegment(10_100_000, 10_130_000, SegType.CW,     License.GENERAL,
                    "CW only",
                    "10.100-10.130 MHz\nCW only\nGeneral and Extra\n"
                    "WARC band — no contests"),
        BandSegment(10_130_000, 10_150_000, SegType.DIGITAL, License.GENERAL,
                    "Digital modes",
                    "10.130-10.150 MHz\nDigital modes\nGeneral and Extra\n"
                    "10.130 MHz: RTTY\n10.138.7 MHz: WSPR\n"
                    "No phone — WARC band"),
    ]),

    Band("20m", 14_000_000, 14_350_000, [
        BandSegment(14_000_000, 14_025_000, SegType.CW,     License.EXTRA,
                    "CW — Extra only",
                    "14.000-14.025 MHz\nCW only\nExtra class only"),
        BandSegment(14_025_000, 14_070_000, SegType.CW,     License.GENERAL,
                    "CW — General+",
                    "14.025-14.070 MHz\nCW only\nGeneral and Extra"),
        BandSegment(14_070_000, 14_100_000, SegType.DIGITAL, License.GENERAL,
                    "Digital modes",
                    "14.070-14.100 MHz\nDigital modes\nGeneral and Extra\n"
                    "14.074 MHz: FT8\n14.080 MHz: FT4\n"
                    "14.095.6 MHz: WSPR"),
        BandSegment(14_100_000, 14_112_000, SegType.BEACON,  License.ALL,
                    "Beacons",
                    "14.100-14.112 MHz\nBeacons — NCDXF/IARU\n"
                    "14.100 MHz: WWV time signals"),
        BandSegment(14_112_000, 14_150_000, SegType.PHONE,   License.EXTRA,
                    "Phone (USB) — Extra only",
                    "14.112-14.150 MHz\nPhone (USB)\nExtra class only"),
        BandSegment(14_150_000, 14_225_000, SegType.PHONE,   License.GENERAL,
                    "Phone (USB) — General+",
                    "14.150-14.225 MHz\nPhone (USB)\nGeneral and Extra"),
        BandSegment(14_225_000, 14_350_000, SegType.PHONE,   License.ALL,
                    "Phone (USB) — All classes",
                    "14.225-14.350 MHz\nPhone (USB)\nAll license classes\n"
                    "14.225 MHz: SSTV calling\n14.286 MHz: AM calling\n"
                    "14.300 MHz: Maritime/distress"),
    ]),

    Band("17m", 18_068_000, 18_168_000, [
        BandSegment(18_068_000, 18_100_000, SegType.CW,      License.GENERAL,
                    "CW only",
                    "18.068-18.100 MHz\nCW only\nGeneral and Extra\n"
                    "WARC band — no contests"),
        BandSegment(18_100_000, 18_110_000, SegType.DIGITAL, License.GENERAL,
                    "Digital modes",
                    "18.100-18.110 MHz\nDigital modes\n"
                    "18.100 MHz: FT8\n18.104.6 MHz: WSPR"),
        BandSegment(18_110_000, 18_168_000, SegType.PHONE,   License.GENERAL,
                    "Phone (USB)",
                    "18.110-18.168 MHz\nPhone (USB)\nGeneral and Extra\n"
                    "WARC band — no contests"),
    ]),

    Band("15m", 21_000_000, 21_450_000, [
        BandSegment(21_000_000, 21_025_000, SegType.CW,      License.EXTRA,
                    "CW — Extra only",
                    "21.000-21.025 MHz\nCW only\nExtra class only"),
        BandSegment(21_025_000, 21_070_000, SegType.CW,      License.GENERAL,
                    "CW — General+",
                    "21.025-21.070 MHz\nCW only\nGeneral and Extra"),
        BandSegment(21_070_000, 21_110_000, SegType.DIGITAL, License.GENERAL,
                    "Digital modes",
                    "21.070-21.110 MHz\nDigital modes\n"
                    "21.074 MHz: FT8\n21.094.6 MHz: WSPR"),
        BandSegment(21_110_000, 21_150_000, SegType.MIXED,   License.ALL,
                    "CW + Phone — All classes",
                    "21.110-21.150 MHz\nCW and Phone\nAll license classes"),
        BandSegment(21_150_000, 21_225_000, SegType.PHONE,   License.EXTRA,
                    "Phone (USB) — Extra only",
                    "21.150-21.225 MHz\nPhone (USB)\nExtra class only"),
        BandSegment(21_225_000, 21_275_000, SegType.PHONE,   License.GENERAL,
                    "Phone (USB) — General+",
                    "21.225-21.275 MHz\nPhone (USB)\nGeneral and Extra"),
        BandSegment(21_275_000, 21_450_000, SegType.PHONE,   License.ALL,
                    "Phone (USB) — All classes",
                    "21.275-21.450 MHz\nPhone (USB)\nAll license classes\n"
                    "21.340 MHz: SSTV calling"),
    ]),

    Band("12m", 24_890_000, 24_990_000, [
        BandSegment(24_890_000, 24_920_000, SegType.CW,      License.GENERAL,
                    "CW only",
                    "24.890-24.920 MHz\nCW only\nGeneral and Extra\n"
                    "WARC band"),
        BandSegment(24_920_000, 24_930_000, SegType.DIGITAL, License.GENERAL,
                    "Digital modes",
                    "24.920-24.930 MHz\nDigital modes\n"
                    "24.915 MHz: FT8"),
        BandSegment(24_930_000, 24_990_000, SegType.PHONE,   License.GENERAL,
                    "Phone (USB)",
                    "24.930-24.990 MHz\nPhone (USB)\nGeneral and Extra\n"
                    "WARC band"),
    ]),

    Band("10m", 28_000_000, 29_700_000, [
        BandSegment(28_000_000, 28_070_000, SegType.CW,      License.GENERAL,
                    "CW only",
                    "28.000-28.070 MHz\nCW only\nGeneral and Extra"),
        BandSegment(28_070_000, 28_150_000, SegType.DIGITAL, License.GENERAL,
                    "Digital modes",
                    "28.070-28.150 MHz\nDigital modes\n"
                    "28.074 MHz: FT8\n28.124.6 MHz: WSPR\n"
                    "28.180 MHz: FT4"),
        BandSegment(28_150_000, 28_300_000, SegType.CW,      License.GENERAL,
                    "CW + beacons",
                    "28.150-28.300 MHz\nCW + Beacons\n"
                    "28.200 MHz: NCDXF beacon network"),
        BandSegment(28_300_000, 28_500_000, SegType.PHONE,   License.GENERAL,
                    "Phone (USB) — General+",
                    "28.300-28.500 MHz\nPhone (USB)\nGeneral and Extra"),
        BandSegment(28_500_000, 29_700_000, SegType.PHONE,   License.ALL,
                    "Phone (USB) — All classes",
                    "28.500-29.700 MHz\nPhone (USB)\nAll license classes\n"
                    "28.385 MHz: SSB calling\n29.000 MHz: AM\n"
                    "29.600 MHz: FM simplex calling\n"
                    "29.520-29.580 MHz: FM repeater inputs\n"
                    "29.620-29.680 MHz: FM repeater outputs"),
    ]),

    Band("6m", 50_000_000, 54_000_000, [
        BandSegment(50_000_000, 50_100_000, SegType.CW,      License.ALL,
                    "CW only",
                    "50.000-50.100 MHz\nCW only\n"
                    "50.060-50.080 MHz: Beacons"),
        BandSegment(50_100_000, 50_300_000, SegType.PHONE,   License.ALL,
                    "Phone (USB)",
                    "50.100-50.300 MHz\nPhone (USB)\n"
                    "50.125 MHz: SSB calling\n50.110 MHz: DX calling"),
        BandSegment(50_300_000, 50_600_000, SegType.MIXED,   License.ALL,
                    "All modes",
                    "50.300-50.600 MHz\nAll modes\n"
                    "50.313 MHz: FT8\n50.323 MHz: FT4"),
        BandSegment(50_600_000, 51_000_000, SegType.DIGITAL, License.ALL,
                    "Digital / non-voice",
                    "50.600-51.000 MHz\nDigital and non-voice"),
        BandSegment(51_000_000, 51_100_000, SegType.SIMPLEX, License.ALL,
                    "Pacific DX window",
                    "51.000-51.100 MHz\nPacific DX window"),
        BandSegment(51_120_000, 51_980_000, SegType.REPEATER, License.ALL,
                    "Repeater outputs",
                    "51.120-51.980 MHz\nFM repeater outputs\n600 kHz split"),
        BandSegment(52_020_000, 52_980_000, SegType.REPEATER, License.ALL,
                    "Repeater inputs",
                    "52.020-52.980 MHz\nFM repeater inputs"),
        BandSegment(52_525_000, 52_525_000, SegType.CALLING,  License.ALL,
                    "FM simplex calling",
                    "52.525 MHz\nFM simplex calling frequency"),
        BandSegment(53_000_000, 54_000_000, SegType.MIXED,   License.ALL,
                    "All modes",
                    "53.000-54.000 MHz\nAll modes"),
    ]),

    Band("2m", 144_000_000, 148_000_000, [
        BandSegment(144_000_000, 144_100_000, SegType.CW,     License.ALL,
                    "CW / EME",
                    "144.000-144.100 MHz\nCW and EME\n"
                    "144.010 MHz: Moonbounce calling"),
        BandSegment(144_100_000, 144_200_000, SegType.PHONE,  License.ALL,
                    "Phone (USB) weak signal",
                    "144.100-144.200 MHz\nSSB weak signal\n"
                    "144.200 MHz: National calling frequency"),
        BandSegment(144_200_000, 144_275_000, SegType.PHONE,  License.ALL,
                    "Phone (USB)",
                    "144.200-144.275 MHz\nSSB Phone"),
        BandSegment(144_275_000, 144_300_000, SegType.BEACON, License.ALL,
                    "Beacons",
                    "144.275-144.300 MHz\nBeacon subband"),
        BandSegment(144_300_000, 144_500_000, SegType.MIXED,  License.ALL,
                    "All modes",
                    "144.300-144.500 MHz\nAll modes\n"
                    "144.390 MHz: APRS"),
        BandSegment(144_500_000, 144_600_000, SegType.MIXED,  License.ALL,
                    "Linear transponders",
                    "144.500-144.600 MHz\nLinear transponder outputs"),
        BandSegment(144_600_000, 144_900_000, SegType.DIGITAL, License.ALL,
                    "Digital modes",
                    "144.600-144.900 MHz\nDigital modes\n"
                    "144.800 MHz: APRS (EU)"),
        BandSegment(144_900_000, 145_100_000, SegType.MIXED,  License.ALL,
                    "Experimental / FM simplex",
                    "144.900-145.100 MHz\n"
                    "146.520 MHz: National FM simplex calling"),
        BandSegment(145_100_000, 145_500_000, SegType.REPEATER, License.ALL,
                    "FM repeater outputs",
                    "145.100-145.500 MHz\nFM repeater outputs\n600 kHz split"),
        BandSegment(146_000_000, 146_400_000, SegType.REPEATER, License.ALL,
                    "FM repeater inputs",
                    "146.000-146.400 MHz\nFM repeater inputs"),
        BandSegment(146_400_000, 146_600_000, SegType.SIMPLEX, License.ALL,
                    "FM simplex",
                    "146.400-146.600 MHz\nFM simplex\n"
                    "146.520 MHz: National FM calling"),
        BandSegment(146_600_000, 147_000_000, SegType.REPEATER, License.ALL,
                    "FM repeater outputs",
                    "146.600-147.000 MHz\nFM repeater outputs"),
        BandSegment(147_000_000, 147_400_000, SegType.REPEATER, License.ALL,
                    "FM repeater inputs",
                    "147.000-147.400 MHz\nFM repeater inputs"),
        BandSegment(147_400_000, 148_000_000, SegType.MIXED,  License.ALL,
                    "FM simplex",
                    "147.400-148.000 MHz\nFM simplex"),
    ]),

    Band("70cm", 420_000_000, 450_000_000, [
        BandSegment(420_000_000, 426_000_000, SegType.MIXED,    License.ALL,
                    "All modes",
                    "420-426 MHz\nAll modes\nATV, weak signal"),
        BandSegment(426_000_000, 432_000_000, SegType.MIXED,    License.ALL,
                    "All modes",
                    "426-432 MHz\nAll modes"),
        BandSegment(432_000_000, 432_100_000, SegType.CW,       License.ALL,
                    "CW / EME",
                    "432.000-432.100 MHz\nCW and EME\n"
                    "432.010 MHz: EME calling"),
        BandSegment(432_100_000, 432_300_000, SegType.PHONE,    License.ALL,
                    "Phone (USB) weak signal",
                    "432.100-432.300 MHz\nSSB weak signal\n"
                    "432.100 MHz: National calling"),
        BandSegment(433_000_000, 435_000_000, SegType.MIXED,    License.ALL,
                    "All modes",
                    "433-435 MHz\nAll modes\n"
                    "433.920 MHz: ISM/LoRa"),
        BandSegment(435_000_000, 438_000_000, SegType.SATELLITE, License.ALL,
                    "Satellite",
                    "435-438 MHz\nSatellite uplink/downlink"),
        BandSegment(438_000_000, 444_000_000, SegType.MIXED,    License.ALL,
                    "All modes / ATV",
                    "438-444 MHz\nAll modes, ATV"),
        BandSegment(442_000_000, 445_000_000, SegType.REPEATER, License.ALL,
                    "FM repeater outputs",
                    "442-445 MHz\nFM repeater outputs\n5 MHz split"),
        BandSegment(445_000_000, 447_000_000, SegType.SIMPLEX,  License.ALL,
                    "FM simplex",
                    "445-447 MHz\nFM simplex\n"
                    "446.000 MHz: National FM calling"),
        BandSegment(447_000_000, 450_000_000, SegType.REPEATER, License.ALL,
                    "FM repeater inputs",
                    "447-450 MHz\nFM repeater inputs"),
    ]),

    Band("1.25m", 222_000_000, 225_000_000, [
        BandSegment(222_000_000, 222_025_000, SegType.CW,      License.ALL,
                    "CW / EME",
                    "222.000-222.025 MHz\nCW and weak signal\n"
                    "Secondary US allocation — must accept primary-user interference"),
        BandSegment(222_025_000, 222_150_000, SegType.MIXED,   License.ALL,
                    "Weak signal SSB/CW/Digital",
                    "222.025-222.150 MHz\nSSB, CW, digital weak signal\n"
                    "222.100 MHz: National calling frequency (SSB)"),
        BandSegment(222_150_000, 223_380_000, SegType.MIXED,   License.ALL,
                    "All modes",
                    "222.150-223.380 MHz\nAll modes\n"
                    "222.340 MHz: Packet calling\n223.500 MHz: FM simplex calling"),
        BandSegment(223_380_000, 223_520_000, SegType.CALLING, License.ALL,
                    "FM simplex calling area",
                    "223.380-223.520 MHz\n223.500 MHz: National FM simplex calling"),
        BandSegment(223_520_000, 225_000_000, SegType.REPEATER, License.ALL,
                    "FM repeater outputs",
                    "223.520-225.000 MHz\nFM repeater outputs\n1.6 MHz split"),
    ], notes="222-225 MHz — USA only; secondary allocation (Technician+)"),

    Band("33cm", 902_000_000, 928_000_000, [
        BandSegment(902_000_000, 902_250_000, SegType.CW,      License.ALL,
                    "CW / EME / weak signal",
                    "902.000-902.250 MHz\nCW, EME, weak signal\n"
                    "902.100 MHz: National calling (CW/SSB)"),
        BandSegment(902_250_000, 906_000_000, SegType.MIXED,   License.ALL,
                    "All modes",
                    "902.250-906.000 MHz\nAll modes\n"
                    "Heavily shared with ISM Part 15 devices"),
        BandSegment(906_000_000, 909_000_000, SegType.DIGITAL, License.ALL,
                    "Packet / digital",
                    "906-909 MHz\nPacket, AX.25, digital nodes"),
        BandSegment(909_000_000, 921_000_000, SegType.MIXED,   License.ALL,
                    "All modes / ATV / experimental",
                    "909-921 MHz\nAll modes, ATV, experimental\n"
                    "Heavy ISM sharing in 915 MHz region"),
        BandSegment(921_000_000, 928_000_000, SegType.REPEATER, License.ALL,
                    "FM repeater outputs",
                    "921-928 MHz\nFM repeater outputs\n25 MHz split"),
    ], notes="902-928 MHz — 33cm band; primary shared with ISM (Technician+)"),

    Band("23cm", 1_240_000_000, 1_300_000_000, [
        BandSegment(1_240_000_000, 1_246_000_000, SegType.IMAGE,    License.ALL,
                    "ATV / fast-scan TV",
                    "1240-1246 MHz\nAmateur Television (ATV)\nFast-scan TV transmissions"),
        BandSegment(1_246_000_000, 1_252_000_000, SegType.MIXED,    License.ALL,
                    "Weak signal / all modes",
                    "1246-1252 MHz\nSSB, CW, digital, all modes\n"
                    "1296.100 MHz: National calling (SSB)"),
        BandSegment(1_252_000_000, 1_258_000_000, SegType.IMAGE,    License.ALL,
                    "ATV",
                    "1252-1258 MHz\nAmateur Television"),
        BandSegment(1_260_000_000, 1_270_000_000, SegType.SATELLITE, License.ALL,
                    "Satellite uplink",
                    "1260-1270 MHz\nSatellite uplink\nPrimary for satellite service"),
        BandSegment(1_270_000_000, 1_276_000_000, SegType.REPEATER, License.ALL,
                    "FM repeaters",
                    "1270-1276 MHz\nFM repeater outputs"),
        BandSegment(1_282_000_000, 1_288_000_000, SegType.REPEATER, License.ALL,
                    "FM repeaters",
                    "1282-1288 MHz\nFM repeater outputs"),
        BandSegment(1_294_000_000, 1_300_000_000, SegType.PHONE,    License.ALL,
                    "FM simplex",
                    "1294-1300 MHz\nFM simplex\n1294.500 MHz: National calling"),
    ], notes="1240-1300 MHz — 23cm band; secondary allocation in USA (Technician+)"),

    Band("13cm", 2_300_000_000, 2_450_000_000, [
        BandSegment(2_300_000_000, 2_310_000_000, SegType.MIXED,    License.ALL,
                    "2300-2310 MHz",
                    "2300-2310 MHz\n13cm lower allocation\nAll modes\n"
                    "2304.100 MHz: National calling (SSB)"),
        BandSegment(2_390_000_000, 2_417_000_000, SegType.MIXED,    License.ALL,
                    "2390-2417 MHz",
                    "2390-2417 MHz\n13cm upper allocation\nAll modes\n"
                    "Shares spectrum with ISM 2.4 GHz (2400-2483.5 MHz)"),
        BandSegment(2_417_000_000, 2_450_000_000, SegType.IMAGE,    License.ALL,
                    "ATV / 2417-2450 MHz",
                    "2417-2450 MHz\nAmateur Television (ATV)\n"
                    "Heavy ISM 2.4 GHz device sharing"),
    ], notes="2300-2310 + 2390-2450 MHz — 13cm band; gap between sub-bands (Technician+)"),
]


# ── Non-Amateur Service Bands ─────────────────────────────────────────────
# CB (Part 95), FRS/GMRS (Part 95), MURS (Part 95), ISM/Unlicensed (Part 15)

SERVICE_BANDS: list[Band] = [

    Band("CB (11m)", 26_965_000, 27_405_000, [
        BandSegment(26_965_000, 27_045_000, SegType.CB,    License.NONE,
                    "Channels 1-8 — AM",
                    "CB Channels 1-8\n26.965-27.045 MHz\n"
                    "AM only, 4W max\nNo license required since 1984"),
        BandSegment(27_045_000, 27_085_000, SegType.GUARD, License.NONE,
                    "Channel 9 — Emergency",
                    "CB Channel 9: 27.065 MHz\nEmergency / motorist assistance\n"
                    "Monitored by REACT and some law enforcement"),
        BandSegment(27_085_000, 27_165_000, SegType.CB,    License.NONE,
                    "Channels 10-17 — AM",
                    "CB Channels 10-17\n27.085-27.165 MHz\nAM only"),
        BandSegment(27_165_000, 27_205_000, SegType.CALLING, License.NONE,
                    "Channel 19 — Highway calling",
                    "CB Channel 19: 27.185 MHz\nHighway trucker calling frequency\n"
                    "Most widely monitored CB frequency\nAM only"),
        BandSegment(27_205_000, 27_305_000, SegType.CB,    License.NONE,
                    "Channels 20-35 — AM",
                    "CB Channels 20-35\n27.205-27.305 MHz\nAM only"),
        BandSegment(27_305_000, 27_405_000, SegType.CB,    License.NONE,
                    "Channels 36-40 — AM/SSB",
                    "CB Channels 36-40\n27.305-27.405 MHz\n"
                    "SSB (USB) allowed — commonly used for long-range contacts\n"
                    "AM also permitted\nCh.36-38: often used for SSB"),
    ], notes="Citizens Band — 40 channels, AM (+ SSB on 36-40), no license (USA)",
       category="CB"),

    Band("MURS", 151_820_000, 154_600_000, [
        BandSegment(151_820_000, 151_940_000, SegType.MURS, License.NONE,
                    "MURS Ch.1-3 (151 MHz)",
                    "MURS Channels 1-3\n"
                    "151.820, 151.880, 151.940 MHz\n"
                    "2W max, 11.25 kHz bandwidth\nNo license required"),
        BandSegment(154_570_000, 154_600_000, SegType.MURS, License.NONE,
                    "MURS Ch.4-5 (154 MHz)",
                    "MURS Channels 4-5\n"
                    "154.570, 154.600 MHz\n"
                    "2W max, 20 kHz bandwidth\nNo license required"),
    ], notes="Multi-Use Radio Service — 5 channels, 2W max, no license (USA)",
       category="MURS"),

    Band("FRS / GMRS", 462_550_000, 467_725_000, [
        BandSegment(462_550_000, 462_725_000, SegType.FRS,      License.NONE,
                    "FRS Ch.1-7, 15-22 (462 MHz)",
                    "FRS/GMRS Shared — 462 MHz channels\n"
                    "Ch.1-7: 462.5625-462.7125 MHz (FRS 2W / GMRS up to 5W)\n"
                    "Ch.15-22: 462.550-462.725 MHz (FRS 2W / GMRS up to 50W)\n"
                    "FRS: no license\nGMRS: FCC license required (no test)"),
        BandSegment(467_562_500, 467_712_500, SegType.FRS,      License.NONE,
                    "FRS Ch.8-14 (467 MHz)",
                    "FRS Only — 467 MHz channels\n"
                    "Ch.8-14: 467.5625-467.7125 MHz\n"
                    "0.5W max — FRS only, not GMRS\nNo license required"),
        BandSegment(467_550_000, 467_725_000, SegType.GMRS_CHAN, License.GMRS_LIC,
                    "GMRS repeater inputs (467 MHz)",
                    "GMRS Repeater Inputs — 467 MHz\n"
                    "Inputs for GMRS repeaters\nCorresponds to 462 MHz outputs\n"
                    "GMRS license required"),
    ], notes="FRS (22 channels, no license) + GMRS (license required, no test) — 462/467 MHz",
       category="FRS/GMRS"),

    Band("ISM 27 MHz", 26_957_000, 27_283_000, [
        BandSegment(26_957_000, 27_283_000, SegType.ISM, License.NONE,
                    "ISM 27 MHz — RC, home devices",
                    "ISM 27 MHz band: 26.957-27.283 MHz\n"
                    "RC models (27.145 MHz), garage door openers,\n"
                    "baby monitors, older cordless phones\n"
                    "Note: overlaps with CB 11m band (26.965-27.405 MHz)"),
    ], notes="ISM 27 MHz — unlicensed devices (RC, home electronics)", category="ISM/Unlicensed"),

    Band("ISM 433 MHz", 433_050_000, 434_790_000, [
        BandSegment(433_050_000, 434_790_000, SegType.ISM, License.NONE,
                    "ISM 433 MHz — sensors, keyfobs, LoRa",
                    "ISM 433 MHz: 433.050-434.790 MHz\n"
                    "EU/worldwide unlicensed: keyfobs, sensors, LoRa 433\n"
                    "433.920 MHz: ISM calling frequency\n"
                    "NOT an ISM band in the USA\n"
                    "Note: overlaps with amateur 70cm band (420-450 MHz)"),
    ], notes="ISM 433 MHz — EU/worldwide unlicensed (NOT US ISM)", category="ISM/Unlicensed"),

    Band("ISM 900 MHz", 902_000_000, 928_000_000, [
        BandSegment(902_000_000, 915_000_000, SegType.ISM, License.NONE,
                    "LoRa/LoRaWAN, Wi-Fi HaLow (lower)",
                    "ISM 902-915 MHz\nLoRa, LoRaWAN (915 band), Wi-Fi HaLow\n"
                    "Zigbee 915, Z-Wave 908 MHz\n"
                    "Note: overlaps with amateur 33cm band (902-928 MHz)"),
        BandSegment(915_000_000, 928_000_000, SegType.ISM, License.NONE,
                    "ISM 915-928 MHz — smart devices",
                    "ISM 915-928 MHz\nSmart meters (AMI), RFID tags,\n"
                    "medical telemetry, baby monitors, wireless microphones\n"
                    "LPWAN (Sigfox, NB-IoT sub-GHz)"),
    ], notes="ISM 902-928 MHz — unlicensed USA; overlaps amateur 33cm band", category="ISM/Unlicensed"),

    Band("ISM 2.4 GHz", 2_400_000_000, 2_483_500_000, [
        BandSegment(2_400_000_000, 2_412_000_000, SegType.WIFI, License.NONE,
                    "Wi-Fi Ch.1 / Bluetooth",
                    "2400-2412 MHz\nWi-Fi channel 1\nBluetooth Classic / BLE lower"),
        BandSegment(2_412_000_000, 2_472_000_000, SegType.WIFI, License.NONE,
                    "Wi-Fi 2.4 GHz Ch.1-13",
                    "2412-2472 MHz\nWi-Fi 802.11b/g/n/ax — channels 1-13\n"
                    "2.437 GHz: channel 6 (US default)\n"
                    "Zigbee, Z-Wave 2.4 GHz, Wi-Fi calling"),
        BandSegment(2_472_000_000, 2_483_500_000, SegType.ISM, License.NONE,
                    "Bluetooth / BLE / Zigbee upper",
                    "2472-2483.5 MHz\nBluetooth Classic + BLE upper channels\n"
                    "Zigbee, IEEE 802.15.4 channels 25-26"),
    ], notes="ISM 2.4 GHz — Wi-Fi, Bluetooth, BLE, Zigbee (worldwide)", category="ISM/Unlicensed"),

    Band("UNII 5 GHz", 5_150_000_000, 5_925_000_000, [
        BandSegment(5_150_000_000, 5_250_000_000, SegType.WIFI, License.NONE,
                    "UNII-1 — indoor only",
                    "5.150-5.250 GHz\nUNII-1: indoor only\n"
                    "Wi-Fi 802.11a/n/ac/ax channels 36-48\nMax 200 mW EIRP"),
        BandSegment(5_250_000_000, 5_350_000_000, SegType.WIFI, License.NONE,
                    "UNII-2A — DFS required",
                    "5.250-5.350 GHz\nUNII-2A: outdoor allowed\n"
                    "Wi-Fi channels 52-64\nDFS (Dynamic Frequency Selection) required"),
        BandSegment(5_470_000_000, 5_725_000_000, SegType.WIFI, License.NONE,
                    "UNII-2C — DFS",
                    "5.470-5.725 GHz\nUNII-2C: Wi-Fi with DFS\n"
                    "Channels 100-144\nRadar avoidance required"),
        BandSegment(5_725_000_000, 5_850_000_000, SegType.ISM, License.NONE,
                    "UNII-3 / ISM 5.8 GHz",
                    "5.725-5.850 GHz\nISM 5.8 GHz + UNII-3\n"
                    "Wi-Fi channels 149-165\nCordless phones (5.8 GHz DECT),\n"
                    "backhaul microwave links"),
        BandSegment(5_850_000_000, 5_925_000_000, SegType.WIFI, License.NONE,
                    "UNII-4",
                    "5.850-5.925 GHz\nUNII-4: expanded Wi-Fi (post-2020)\n"
                    "Previously DSRC vehicle communications band"),
    ], notes="UNII/ISM 5 GHz — Wi-Fi 5 GHz (802.11a/n/ac/ax)", category="ISM/Unlicensed"),

    Band("Wi-Fi 6 GHz", 5_925_000_000, 7_125_000_000, [
        BandSegment(5_925_000_000, 6_425_000_000, SegType.WIFI, License.NONE,
                    "UNII-5 — Wi-Fi 6E low",
                    "5.925-6.425 GHz\nUNII-5: Wi-Fi 6E/7 indoor\n"
                    "Channels 1-93 (20/40/80/160 MHz)\nMax 30 dBm EIRP indoor"),
        BandSegment(6_425_000_000, 6_525_000_000, SegType.WIFI, License.NONE,
                    "UNII-6",
                    "6.425-6.525 GHz\nUNII-6: restricted power\n"
                    "Standard power access points"),
        BandSegment(6_525_000_000, 6_875_000_000, SegType.WIFI, License.NONE,
                    "UNII-7 — Wi-Fi 6E upper",
                    "6.525-6.875 GHz\nUNII-7: higher power outdoor allowed\n"
                    "Wi-Fi 6E channels — 160 MHz wide channels available"),
        BandSegment(6_875_000_000, 7_125_000_000, SegType.WIFI, License.NONE,
                    "UNII-8 — Wi-Fi 7",
                    "6.875-7.125 GHz\nUNII-8: Wi-Fi 7 (802.11be)\n"
                    "320 MHz channels enabled in this range"),
    ], notes="6 GHz Wi-Fi (Wi-Fi 6E / Wi-Fi 7) — USA unlicensed (FCC 2020)", category="ISM/Unlicensed"),
]

# Combined list for dialogs / reference tools
ALL_BANDS: list[Band] = BANDS + SERVICE_BANDS

# ── Quick lookup structures ───────────────────────────────────────────────
# _BAND_BY_NAME / _BANDS_SORTED cover amateur BANDS only (for VFO lookups).
# Use ALL_BANDS for reference dialogs that include service allocations.

_BAND_BY_NAME: dict[str, Band] = {b.name: b for b in BANDS}
_BANDS_SORTED: list[Band] = sorted(BANDS, key=lambda b: b.freq_lo)


def get_band(name: str) -> Band | None:
    return _BAND_BY_NAME.get(name)


def band_at_freq(freq_hz: int) -> Band | None:
    for b in _BANDS_SORTED:
        if b.freq_lo <= freq_hz <= b.freq_hi:
            return b
    return None


def segment_at_freq(freq_hz: int) -> BandSegment | None:
    band = band_at_freq(freq_hz)
    if band:
        return band.segment_at(freq_hz)
    return None


def suggested_mode(freq_hz: int) -> str:
    """
    Return the suggested operating mode for a given frequency.
    Used for auto-mode switching on VFO change.
    """
    band = band_at_freq(freq_hz)
    if not band:
        return "USB"

    seg = band.segment_at(freq_hz)
    seg_type = seg.seg_type if seg else SegType.PHONE

    # VHF/UHF FM bands
    if freq_hz >= 50_000_000:
        if seg_type in (SegType.REPEATER, SegType.SIMPLEX,
                        SegType.CALLING, SegType.MIXED):
            return "FM"
        if seg_type in (SegType.CW,):
            return "CW"
        if seg_type == SegType.PHONE:
            return "USB"
        return "FM"

    # HF
    if seg_type == SegType.CW:
        return "CW"
    if seg_type == SegType.DIGITAL:
        return "PKTUSB" if freq_hz >= 10_000_000 else "PKTLSB"
    if seg_type == SegType.BEACON:
        return "CW"
    if seg_type == SegType.AM:
        return "AM"
    if seg_type == SegType.IMAGE:
        return "USB" if freq_hz >= 10_000_000 else "LSB"

    # Phone — LSB below 10 MHz, USB above
    return "USB" if freq_hz >= 10_000_000 else "LSB"


def bands_in_range(freq_lo: int, freq_hi: int) -> list[Band]:
    """Return all bands that overlap a frequency range (for waterfall overlay)."""
    return [b for b in _BANDS_SORTED
            if b.freq_hi >= freq_lo and b.freq_lo <= freq_hi]


def segments_in_range(freq_lo: int, freq_hi: int) -> list[BandSegment]:
    """Return all segments visible in a frequency range."""
    result = []
    for band in bands_in_range(freq_lo, freq_hi):
        for seg in band.segments:
            if seg.freq_hi >= freq_lo and seg.freq_lo <= freq_hi:
                result.append(seg)
    return result


# ── Digital mode frequencies (for quick-set and markers) ─────────────────

DIGITAL_FREQS: dict[str, list[tuple[str, int]]] = {
    "FT8": [
        ("160m", 1_840_000), ("80m", 3_573_000), ("40m", 7_074_000),
        ("30m", 10_136_000), ("20m", 14_074_000), ("17m", 18_100_000),
        ("15m", 21_074_000), ("12m", 24_915_000), ("10m", 28_074_000),
        ("6m",  50_313_000),
    ],
    "FT4": [
        ("80m", 3_575_000), ("40m", 7_047_500), ("20m", 14_080_000),
        ("15m", 21_140_000), ("10m", 28_180_000),
    ],
    "WSPR": [
        ("160m", 1_836_600), ("80m", 3_568_600), ("40m", 7_038_600),
        ("30m", 10_138_700), ("20m", 14_095_600), ("17m", 18_104_600),
        ("15m", 21_094_600), ("12m", 24_924_600), ("10m", 28_124_600),
    ],
    "JS8": [
        ("40m", 7_078_000), ("20m", 14_078_000),
        ("15m", 21_078_000), ("10m", 28_078_000),
    ],
    "PSK31": [
        ("80m", 3_580_000), ("40m", 7_070_000), ("20m", 14_070_000),
        ("15m", 21_070_000), ("10m", 28_120_000),
    ],
}

# ── BAND_EDGES dict for compatibility with rig_tab and other modules ──────
# Amateur bands only — excludes SERVICE_BANDS intentionally (VFO / rig use).
BAND_EDGES: dict[str, tuple[int, int]] = {
    b.name: (b.freq_lo, b.freq_hi) for b in BANDS
}
