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
"""Squelch -- core/rig_presets.py
Radio configuration presets. Auto-populates rig tab settings
and drives the help system radio setup pages.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RigPreset:
    name:              str
    hamlib_model:      int | None
    baud:              int
    ptt_method:        str          # CAT, VOX, RTS, DTR
    data_mode:         str          # PKTUSB, PKTLSB, USB
    civ_address:       str          = ""
    usb_hints:         list         = field(default_factory=list)
    audio_notes:       str          = ""
    notes:             str          = ""
    radio_menu_steps:  list         = field(default_factory=list)
    troubleshooting:   list         = field(default_factory=list)
    supports_cat:      bool         = True
    supports_aprs:     bool         = False
    supports_gps:      bool         = False
    supports_dstar:    bool         = False
    student_friendly:  bool         = False
    category:          str          = "HF"   # HF, VHF, Portable, Student


PRESETS: dict[str, RigPreset] = {

    # ── ICOM ─────────────────────────────────────────────────────────────

    "ICOM IC-7100": RigPreset(
        name          = "ICOM IC-7100",
        hamlib_model  = 370,
        baud          = 19200,
        ptt_method    = "CAT",
        data_mode     = "PKTUSB",
        civ_address   = "88",
        usb_hints     = ["CP210", "IC-7100"],
        supports_aprs = True,
        supports_gps  = True,
        supports_dstar= True,
        category      = "HF",
        audio_notes   = (
            "The IC-7100 provides CAT control and audio over a single USB "
            "cable. It appears as 'USB Audio CODEC' in Windows Sound settings. "
            "Set as default recording device for digital mode audio input."
        ),
        notes = (
            "The IC-7100 is the primary supported rig for Squelch. "
            "Built-in APRS, GPS, and D-STAR. Single USB cable for "
            "CAT + audio. Excellent for portable and mobile operation."
        ),
        radio_menu_steps = [
            "Press MENU on the radio",
            "Select: Connectors",
            "CI-V Baud Rate    → 19200",
            "CI-V Address      → 88 (default, do not change)",
            "USB Send          → DTR",
            "USB Mod           → WLAN (or ACC for external audio)",
            "Press MENU to exit and save",
        ],
        troubleshooting = [
            "Not connecting: verify CI-V Baud Rate matches Squelch (19200)",
            "No audio RX: check 'USB Audio CODEC' in Windows Sound → Recording",
            "No audio TX: check 'USB Audio CODEC' in Windows Sound → Playback",
            "PTT not keying: verify USB Send = DTR in radio menu",
            "Wrong frequency shown: verify CI-V Address = 88",
            "APRS not working: Menu → APRS → set to ON",
        ],
    ),

    "ICOM IC-7300": RigPreset(
        name          = "ICOM IC-7300",
        hamlib_model  = 373,
        baud          = 19200,
        ptt_method    = "CAT",
        data_mode     = "PKTUSB",
        civ_address   = "94",
        usb_hints     = ["CP210", "IC-7300"],
        category      = "HF",
        notes = (
            "The IC-7300 has a built-in real-time spectrum scope. "
            "Squelch's SDR waterfall is redundant if you have an IC-7300 "
            "but can still be used for wider band monitoring."
        ),
        audio_notes   = (
            "Appears as 'USB Audio CODEC' in Windows. "
            "Single USB cable for CAT + audio."
        ),
        radio_menu_steps = [
            "MENU → Connectors → CI-V Baud Rate → 19200",
            "MENU → Connectors → CI-V Address   → 94",
            "MENU → Connectors → USB Send       → DTR",
            "MENU → Connectors → MOD Input      → USB",
        ],
        troubleshooting = [
            "Not connecting: check CI-V address is 94, not 88",
            "Audio issues: check USB Audio CODEC in Windows Sound",
        ],
    ),

    "ICOM IC-7610": RigPreset(
        name          = "ICOM IC-7610",
        hamlib_model  = 376,
        baud          = 19200,
        ptt_method    = "CAT",
        data_mode     = "PKTUSB",
        civ_address   = "98",
        usb_hints     = ["CP210", "IC-7610"],
        category      = "HF",
        notes         = "Dual-watch SDR receiver. High-end HF/50MHz transceiver.",
        radio_menu_steps = [
            "MENU → Connectors → CI-V Baud Rate → 19200",
            "MENU → Connectors → CI-V Address   → 98",
            "MENU → Connectors → USB Send       → DTR",
        ],
        troubleshooting = [
            "Not connecting: check CI-V address is 98",
        ],
    ),

    "ICOM IC-9700": RigPreset(
        name          = "ICOM IC-9700",
        hamlib_model  = 369,
        baud          = 19200,
        ptt_method    = "CAT",
        data_mode     = "PKTFM",
        civ_address   = "A2",
        usb_hints     = ["CP210", "IC-9700"],
        supports_dstar= True,
        category      = "VHF",
        notes         = "VHF/UHF/1.2GHz SDR-based transceiver. Excellent for satellite.",
        radio_menu_steps = [
            "MENU → Connectors → CI-V Baud Rate → 19200",
            "MENU → Connectors → CI-V Address   → A2",
            "MENU → Connectors → USB Send       → DTR",
        ],
        troubleshooting = [
            "Not connecting: CI-V address is A2 (hex), not decimal",
        ],
    ),

    "ICOM IC-705": RigPreset(
        name          = "ICOM IC-705",
        hamlib_model  = 388,
        baud          = 19200,
        ptt_method    = "CAT",
        data_mode     = "PKTUSB",
        civ_address   = "A4",
        usb_hints     = ["CP210", "IC-705"],
        supports_dstar= True,
        supports_gps  = True,
        category      = "Portable",
        notes = (
            "Portable SDR-based HF/VHF/UHF transceiver. "
            "Built-in GPS and D-STAR. Excellent for POTA/SOTA. "
            "5W max output."
        ),
        radio_menu_steps = [
            "MENU → Connectors → CI-V Baud Rate → 19200",
            "MENU → Connectors → CI-V Address   → A4",
            "MENU → Connectors → USB Send       → DTR",
            "MENU → Connectors → USB MOD Level  → 50%",
        ],
        troubleshooting = [
            "Not connecting: CI-V address is A4 (hex)",
            "Low audio: increase USB MOD level in menu",
        ],
    ),

    # ── YAESU ────────────────────────────────────────────────────────────

    "Yaesu FT-991A": RigPreset(
        name          = "Yaesu FT-991A",
        hamlib_model  = 1035,
        baud          = 38400,
        ptt_method    = "CAT",
        data_mode     = "PKTUSB",
        usb_hints     = ["CP210", "FT-991", "FTDI"],
        category      = "HF",
        audio_notes   = (
            "Appears as two audio devices in Windows: "
            "'USB Audio CODEC' for main audio and a second device "
            "for data. Use the main USB Audio CODEC for Squelch."
        ),
        notes = "All-band HF/VHF/UHF. C4FM/Fusion digital voice built in.",
        radio_menu_steps = [
            "Press F + MENU to enter menu",
            "Menu 031 → CAT RATE     → 38400",
            "Menu 032 → CAT TOT      → 10",
            "Menu 033 → CAT RTS      → Enable",
            "Menu 062 → DATA MODE    → PSK",
            "Menu 064 → DATA IN/OUT  → REAR",
            "Menu 065 → DATA PTT SEL → DTR",
        ],
        troubleshooting = [
            "Not connecting: verify baud rate is 38400 in both radio and Squelch",
            "Menu numbering differs between firmware versions — check your manual",
            "PTT issues: Menu 065 DATA PTT SEL must be DTR",
        ],
    ),

    "Yaesu FT-DX10": RigPreset(
        name          = "Yaesu FT-DX10",
        hamlib_model  = 1062,
        baud          = 38400,
        ptt_method    = "CAT",
        data_mode     = "PKTUSB",
        usb_hints     = ["CP210", "FT-DX10"],
        category      = "HF",
        notes         = "Mid-range HF transceiver with SDR receiver.",
        radio_menu_steps = [
            "MENU → CAT RATE → 38400",
            "MENU → CAT PTT  → DTR",
            "MENU → DATA MOD → USB",
        ],
        troubleshooting = [
            "Not connecting: verify 38400 baud in menu",
        ],
    ),

    "Yaesu FT-817/818": RigPreset(
        name          = "Yaesu FT-817/818",
        hamlib_model  = 1033,
        baud          = 9600,
        ptt_method    = "CAT",
        data_mode     = "PKTUSB",
        usb_hints     = ["FTDI"],
        category      = "Portable",
        notes = (
            "Ultra-portable HF/VHF/UHF. 5W max. Very popular for "
            "SOTA, POTA, and portable digital ops. Requires FTDI "
            "USB-serial cable (not included)."
        ),
        audio_notes = (
            "Requires a separate USB-serial cable for CAT control "
            "and a separate audio interface cable for digital modes. "
            "SignaLink USB or Digirig recommended."
        ),
        radio_menu_steps = [
            "Press F and hold MENU to enter menu mode",
            "Menu 14 → CAT RATE → 9600",
            "Menu 15 → CAT TOT  → 100",
            "Menu 16 → CAT RTS  → Enable",
        ],
        troubleshooting = [
            "Baud rate: FT-817 maximum is 9600, do not set higher",
            "CAT cable: must be FTDI-based, not CH340",
            "Audio: use DATA port on rear for cleanest signal",
        ],
    ),

    "Yaesu FT-891": RigPreset(
        name          = "Yaesu FT-891",
        hamlib_model  = 1039,
        baud          = 38400,
        ptt_method    = "CAT",
        data_mode     = "PKTUSB",
        usb_hints     = ["FTDI", "FT-891"],
        category      = "Portable",
        notes         = "Compact HF/50MHz mobile transceiver. Popular for vehicle installs.",
        radio_menu_steps = [
            "MENU → CAT RATE → 38400",
            "MENU → DATA MOD → USB",
            "MENU → DATA PTT → DTR",
        ],
        troubleshooting = [
            "Not connecting: check baud rate is 38400",
        ],
    ),

    # ── KENWOOD ───────────────────────────────────────────────────────────

    "Kenwood TS-590S": RigPreset(
        name          = "Kenwood TS-590S",
        hamlib_model  = 229,
        baud          = 115200,
        ptt_method    = "CAT",
        data_mode     = "PKTUSB",
        usb_hints     = ["FTDI", "CP210", "TS-590"],
        category      = "HF",
        notes         = "Excellent HF transceiver with built-in USB audio.",
        audio_notes   = (
            "Built-in USB audio interface. Appears as 'USB Audio CODEC' "
            "or 'TS-590S' in Windows Sound settings."
        ),
        radio_menu_steps = [
            "MENU → 59 → PC BAUD RATE → 115200",
            "MENU → 60 → PC FLOW CTRL → RTS/CTS",
            "MENU → 62 → USB AUDIO    → ON",
        ],
        troubleshooting = [
            "High baud rate: TS-590S supports 115200, keep it there",
            "Audio: enable USB Audio in menu 62",
        ],
    ),

    "Kenwood TS-890S": RigPreset(
        name          = "Kenwood TS-890S",
        hamlib_model  = 243,
        baud          = 115200,
        ptt_method    = "CAT",
        data_mode     = "PKTUSB",
        usb_hints     = ["FTDI", "CP210", "TS-890"],
        category      = "HF",
        notes         = "High-end HF/50MHz with built-in SDR panadapter.",
        radio_menu_steps = [
            "MENU → PC BAUD RATE → 115200",
            "MENU → USB AUDIO    → ON",
        ],
        troubleshooting = [
            "Not connecting: verify 115200 baud",
        ],
    ),

    "Kenwood TS-2000": RigPreset(
        name          = "Kenwood TS-2000",
        hamlib_model  = 202,
        baud          = 9600,
        ptt_method    = "CAT",
        data_mode     = "PKTUSB",
        usb_hints     = ["FTDI"],
        category      = "HF",
        notes = (
            "All-band HF/VHF/UHF/SAT transceiver. "
            "Requires USB-serial adapter. Popular shack radio."
        ),
        radio_menu_steps = [
            "MENU A → 58 → COM RATE → 9600",
        ],
        troubleshooting = [
            "Older rig: 9600 baud maximum, do not set higher",
            "Requires FTDI USB-serial adapter",
        ],
    ),

    # ── ELECRAFT ─────────────────────────────────────────────────────────

    "Elecraft K3/K3S": RigPreset(
        name          = "Elecraft K3/K3S",
        hamlib_model  = 1351,
        baud          = 38400,
        ptt_method    = "CAT",
        data_mode     = "PKTUSB",
        usb_hints     = ["FTDI", "Elecraft", "K3"],
        category      = "HF",
        notes = (
            "Contest-grade HF transceiver. "
            "Excellent receiver performance. "
            "Requires USB-serial adapter or optional KXV3 module."
        ),
        radio_menu_steps = [
            "CONFIG → RS232 → BAUD → 38400",
            "CONFIG → RS232 → DATA → 8N1",
        ],
        troubleshooting = [
            "K3 requires optional KXV3 for USB audio",
            "K3S has built-in USB — use that port",
        ],
    ),

    "Elecraft KX3": RigPreset(
        name          = "Elecraft KX3",
        hamlib_model  = 1353,
        baud          = 38400,
        ptt_method    = "CAT",
        data_mode     = "PKTUSB",
        usb_hints     = ["FTDI", "KX3"],
        category      = "Portable",
        notes = (
            "Ultra-portable QRP transceiver. 10W max. "
            "Excellent for SOTA/POTA. "
            "Requires KXUSB cable for CAT control."
        ),
        radio_menu_steps = [
            "MENU → BAUD → 38400",
        ],
        troubleshooting = [
            "Requires Elecraft KXUSB cable",
            "Audio: use headphone jack with interface cable",
        ],
    ),

    "Elecraft K4": RigPreset(
        name          = "Elecraft K4",
        hamlib_model  = 1356,
        baud          = 38400,
        ptt_method    = "CAT",
        data_mode     = "PKTUSB",
        usb_hints     = ["FTDI", "K4"],
        category      = "HF",
        notes         = "Flagship Elecraft HF transceiver with built-in SDR.",
        radio_menu_steps = [
            "CONFIG → SERIAL → BAUD → 38400",
        ],
        troubleshooting = [
            "Built-in USB audio — no separate interface needed",
        ],
    ),

    # ── BUDGET / STUDENT ─────────────────────────────────────────────────

    "Xiegu G90": RigPreset(
        name          = "Xiegu G90",
        hamlib_model  = None,
        baud          = 19200,
        ptt_method    = "CAT",
        data_mode     = "PKTUSB",
        usb_hints     = ["CP210", "G90"],
        category      = "Portable",
        student_friendly = True,
        notes = (
            "Affordable portable HF transceiver with built-in ATU. "
            "20W output. Popular budget option for new HF operators. "
            "Use Hamlib model 1 (Generic) or community-provided model."
        ),
        audio_notes = (
            "Requires separate audio interface cable. "
            "Digirig Mobile recommended for clean digital audio."
        ),
        radio_menu_steps = [
            "Menu → CAT Baud → 19200",
            "Menu → DATA Mode → USB",
        ],
        troubleshooting = [
            "Hamlib model: use 'Generic' or search Hamlib list for G90",
            "Audio: use rear DATA port, not front headphone jack",
        ],
    ),

    "Xiegu X6100": RigPreset(
        name          = "Xiegu X6100",
        hamlib_model  = None,
        baud          = 19200,
        ptt_method    = "CAT",
        data_mode     = "PKTUSB",
        usb_hints     = ["CP210", "X6100"],
        category      = "Portable",
        student_friendly = True,
        notes = (
            "Portable HF transceiver with built-in SDR panadapter "
            "and Android-based interface. 10W output. "
            "Can run some apps natively but Squelch runs on connected PC."
        ),
        radio_menu_steps = [
            "Settings → CAT → Baud Rate → 19200",
        ],
        troubleshooting = [
            "Hamlib model: use Generic or X6100 community model",
        ],
    ),

    "Baofeng UV-5R / UV-82": RigPreset(
        name          = "Baofeng UV-5R / UV-82",
        hamlib_model  = None,
        baud          = 0,
        ptt_method    = "VOX",
        data_mode     = "FM",
        usb_hints     = [],
        supports_cat  = False,
        category      = "Student",
        student_friendly = True,
        notes = (
            "No CAT control — audio interface only. "
            "Works for digital modes (FT8, WSPR, PSK31, SSTV) "
            "via VOX PTT and audio cable. "
            "Frequency must be set manually on the radio. "
            "Ideal low-cost student station."
        ),
        audio_notes = (
            "Requires a Kenwood K1 audio cable (2.5mm + 3.5mm) "
            "to connect to PC sound card. "
            "Digirig Mobile or similar interface recommended for "
            "best audio quality and PTT control. "
            "VOX PTT: set Baofeng VOX to level 2-3."
        ),
        radio_menu_steps = [
            "Set radio to NFM mode",
            "Set desired frequency manually on the radio",
            "Tone squelch (CTCSS) → OFF for digital operation",
            "VOX → ON, set level to 2 or 3",
            "Connect K1 cable to PC sound card",
        ],
        troubleshooting = [
            "No TX: verify VOX is on and level is 2-3",
            "Distorted audio: reduce PC output volume",
            "Interference: keep cable away from radio antenna",
            "PTT cable: Digirig gives cleaner PTT than VOX",
        ],
    ),

    # ── MANUAL ───────────────────────────────────────────────────────────

    # ── USB Audio Interface Adapters ──────────────────────────────────
    "SignaLink USB": RigPreset(
        name          = "SignaLink USB",
        hamlib_model  = None,
        baud          = 0,
        ptt_method    = "RTS",
        data_mode     = "USB",
        usb_hints     = ["SignaLink", "USB Audio CODEC"],
        supports_cat  = False,
        category      = "Audio Interface",
        student_friendly = False,
        notes = (
            "USB audio interface for any rig with an accessory port. "
            "Works with IC-7100, FT-991A, TS-590S, and most HF rigs. "
            "PTT via internal VOX or RTS line. "
            "Provides audio isolation and level control. "
            "No CAT — use Hamlib directly to the rig for frequency control."
        ),
        audio_notes = (
            "SignaLink USB appears as a USB Audio CODEC device. "
            "Set WSJT-X audio input/output to SignaLink. "
            "PTT: set WSJT-X PTT Method to CAT (via Hamlib) or RTS. "
            "Internal jumpers set audio levels — see SignaLink manual."
        ),
        radio_menu_steps = [
            "Connect SignaLink USB to rig accessory/data port",
            "Connect SignaLink to PC via USB",
            "Install jumpers per rig (download from tigertronics.com)",
            "Set rig to USB-D or DATA mode",
            "In WSJT-X: Settings → Audio → select SignaLink USB",
            "In WSJT-X: Settings → Radio → PTT Method → RTS or CAT",
            "Adjust TX level knob on SignaLink for ~30W output",
        ],
        troubleshooting = [
            "No audio: verify SignaLink shows in Windows sound devices",
            "No TX: check jumper configuration for your specific rig",
            "ALC riding: turn TX knob down on SignaLink",
            "RFI: ensure USB cable is ferrite-choked",
        ],
    ),

    "RigBlaster Advantage": RigPreset(
        name          = "RigBlaster Advantage",
        hamlib_model  = None,
        baud          = 0,
        ptt_method    = "RTS",
        data_mode     = "USB",
        usb_hints     = ["RigBlaster", "USB Audio"],
        supports_cat  = False,
        category      = "Audio Interface",
        student_friendly = False,
        notes = (
            "USB audio interface by West Mountain Radio. "
            "Works with most HF rigs via mic/speaker/accessory ports. "
            "Also supports CW keying. No CAT."
        ),
        audio_notes = (
            "Appears as a USB audio device in Windows. "
            "PTT via RTS line on USB serial port. "
            "CW keying via DTR line."
        ),
        radio_menu_steps = [
            "Connect RigBlaster to rig mic/speaker ports",
            "Connect to PC via USB",
            "Set rig to USB or DATA mode",
            "Select RigBlaster audio in WSJT-X",
            "PTT Method → RTS",
        ],
        troubleshooting = [
            "No PTT: verify COM port assigned to RigBlaster",
            "Audio level: adjust in Windows sound settings",
        ],
    ),

    "Generic USB Audio (VOX PTT)": RigPreset(
        name          = "Generic USB Audio (VOX PTT)",
        hamlib_model  = None,
        baud          = 0,
        ptt_method    = "VOX",
        data_mode     = "USB",
        usb_hints     = ["USB Audio", "CODEC"],
        supports_cat  = False,
        category      = "Audio Interface",
        student_friendly = True,
        notes = (
            "Any USB sound card or audio interface with VOX PTT. "
            "Cheap CM108-based adapters work for light use. "
            "Use dedicated interface (SignaLink, RigBlaster) for "
            "serious digital operation — better audio isolation "
            "and level control."
        ),
        audio_notes = (
            "Enable VOX on rig. Set VOX delay to minimum (50ms). "
            "VOX level: adjust so TX keys on audio, drops quickly. "
            "Watch ALC — keep TX audio low enough that ALC stays low."
        ),
        radio_menu_steps = [
            "Connect USB audio adapter to rig mic/speaker",
            "Enable VOX on rig (check menu)",
            "Set VOX delay to minimum",
            "Select USB audio device in WSJT-X/Fldigi",
            "PTT Method → VOX in WSJT-X",
            "Start with low TX output and increase carefully",
        ],
        troubleshooting = [
            "TX not releasing: VOX delay too long — decrease",
            "TX not keying: increase audio level or VOX sensitivity",
            "ALC distorting: reduce WSJT-X pwr slider",
            "Ground loop hum: use audio isolation transformer",
        ],
    ),

    "Explorer QRZ-1": RigPreset(
        name          = "Explorer QRZ-1",
        hamlib_model  = None,
        baud          = 0,
        ptt_method    = "VOX",
        data_mode     = "FM",
        usb_hints     = [],
        supports_cat  = False,
        category      = "Student",
        student_friendly = True,
        notes = (
            "VHF/UHF handheld — no CAT control. "
            "Audio interface only for digital modes. "
            "Based on TYT TH-UV88 hardware. "
            "Use standard Kenwood/Baofeng K1 cable for programming and audio."
        ),
        audio_notes = (
            "Connect via K1 audio cable for digital modes. "
            "Set VOX to level 2-3 for TX. "
            "For programming: use CHIRP with TYT TH-UV88 driver, "
            "or RT Systems RPS-QRZ1 software for reliable CTCSS. "
            "Note: CHIRP may not program CTCSS correctly — "
            "use RT Systems software to re-upload after CHIRP programming."
        ),
        radio_menu_steps = [
            "Set radio to NFM mode",
            "Set frequency manually on radio",
            "CTCSS/Tone Squelch → OFF for digital operation",
            "VOX → ON, level 2 or 3",
            "Connect K1 cable to PC sound card",
            "For programming: use CHIRP (TYT TH-UV88 driver)",
            "  or RT Systems RPS-QRZ1 software",
        ],
        troubleshooting = [
            "No TX: verify VOX on and level 2-3",
            "CTCSS not working after CHIRP: re-upload with RT Systems software",
            "Programming cable: standard Kenwood K1 type (not CH341 if possible)",
            "Antenna connector: SMA-F (opposite of Baofeng SMA-M)",
        ],
    ),

    "Manual / Other": RigPreset(
        name          = "Manual / Other",
        hamlib_model  = None,
        baud          = 9600,
        ptt_method    = "CAT",
        data_mode     = "PKTUSB",
        usb_hints     = [],
        category      = "HF",
        notes = (
            "Select this option if your radio is not in the list. "
            "You will need to enter the Hamlib model number manually. "
            "Full list of supported radios: "
            "https://hamlib.sourceforge.net/manuals/hamlib.html"
        ),
        radio_menu_steps = [
            "Consult your radio manual for CAT/CI-V settings",
            "Set baud rate to match Squelch settings",
            "Enable CAT control if required by your radio",
            "Set PTT method to CAT, RTS, or DTR per your radio",
        ],
        troubleshooting = [
            "Find your Hamlib model number at hamlib.sourceforge.net",
            "Try common baud rates: 9600, 19200, 38400, 115200",
            "Check radio manual for CI-V or RS-232 settings",
        ],
    ),
}


# ── Lookup helpers ────────────────────────────────────────────────────────

def get_preset(name: str) -> RigPreset | None:
    return PRESETS.get(name)

def preset_names() -> list[str]:
    """
    Ordered list for UI dropdown.
    Sorted by manufacturer group then alphabetically within group.
    Manufacturer order reflects market share / primary support priority.
    """
    groups = {
        "ICOM":     [],
        "Yaesu":    [],
        "Kenwood":  [],
        "Elecraft":  [],
        "Xiegu":    [],
        "Baofeng":  [],
        "Manual":   [],
    }
    for name in PRESETS:
        if name.startswith("ICOM"):
            groups["ICOM"].append(name)
        elif name.startswith("Yaesu"):
            groups["Yaesu"].append(name)
        elif name.startswith("Kenwood"):
            groups["Kenwood"].append(name)
        elif name.startswith("Elecraft"):
            groups["Elecraft"].append(name)
        elif name.startswith("Xiegu"):
            groups["Xiegu"].append(name)
        elif name.startswith("Baofeng"):
            groups["Baofeng"].append(name)
        else:
            groups["Manual"].append(name)

    result = []
    for group in ["ICOM", "Yaesu", "Kenwood", "Elecraft",
                  "Xiegu", "Baofeng", "Manual"]:
        result.extend(sorted(groups[group]))
    return result

def detect_from_port(description: str) -> RigPreset | None:
    """Try to identify rig from USB port description string."""
    desc = description.upper()
    for preset in PRESETS.values():
        if any(h.upper() in desc for h in preset.usb_hints):
            return preset
    return None

def student_presets() -> list[str]:
    return [n for n, p in PRESETS.items() if p.student_friendly]

# Type hint
try:
    from typing import Optional
except ImportError:
    pass
