from __future__ import annotations
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
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- ui/tabs/help_tab.py
Searchable help system with setup guides,
keyboard shortcuts, and EmComm reference.
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QListWidget, QListWidgetItem,
    QTextEdit, QLineEdit, QPushButton, QFrame,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QDesktopServices
from PyQt6.QtCore import QUrl

log = logging.getLogger(__name__)

# ── Help content ──────────────────────────────────────────────────────────

HELP_ARTICLES = [
    # (title, category, content)
    ("Getting Started", "Setup",
     """# Getting Started with Squelch

## First Launch
On first launch, Squelch asks for your callsign and location.
Enter your FCC callsign and either a Maidenhead grid square (e.g. DM79rr),
a ZIP code, or a city name. All formats resolve to a Maidenhead grid.

## Top Bar
The top bar shows:
  • Your callsign (click to edit)
  • Operator profile selector
  • Your Maidenhead grid (click to edit or search)
  • UTC/Local clock toggle (click to switch)
  • Rig connection status

## Tabs
Each tab handles a specific function:
  Rig       — IC-7100 and other rig CAT control
  Modes     — FT8/FT4/WSPR/JS8 digital modes
  Log       — QSO logging with ADIF export
  Band Cond — Solar data and propagation
  SDR       — Software defined radio
  Digital   — P25/DMR/NXDN decode
  Local RF  — Repeaters and local resources
  Map       — Station map with gray line
  Winlink   — Email over radio
  Help      — This help system

## Your Data
All settings and logs are saved in:
  Windows: C:\\Users\\YourName\\AppData\\Roaming\\Squelch\\
  Linux:   ~/.config/squelch/

This location is preserved across Squelch updates.
"""),

    ("IC-7100 Setup", "Rig Control",
     """# IC-7100 CAT Control Setup

## Hardware Connection
The IC-7100 connects to your PC via USB using the built-in
USB audio/serial interface. No external interface is needed.

**Driver:** Silicon Labs CP210x
Download: silabs.com/developers/usb-to-uart-bridge-vcp-drivers

## IC-7100 Menu Settings
Set these in the radio's menu before connecting:

  Menu 066 (CI-V Baud Rate):   19200
  Menu 067 (CI-V Address):     94h (default — do not change)
  Menu 071 (CI-V Transceive):  ON
  Menu 072 (CI-V USB Baud):    19200
  Menu 073 (CI-V USB Echo):    OFF

## For Digital Modes (FT8/FT4)
  Menu 040 (DATA OFF MOD):     USB
  Menu 035 (USB Connector):    1: USB
  Set rig mode to USB-D (not plain USB)

## Squelch Settings (Rig Tab)
  Model:  ICOM IC-7100
  Port:   COM port showing CP210x (Device Manager → Ports)
  Baud:   19200

## VB-Cable for Audio
Install VB-Cable (vb-audio.com/Cable) for audio routing.
In WSJT-X:
  Input:  CABLE Output (VB-Audio Virtual Cable)
  Output: CABLE Input (VB-Audio Virtual Cable)

## Troubleshooting
  No COM port: Install CP210x driver, replug USB
  CAT fails:   Check Menu 072 baud rate matches Squelch
  No audio:    Check Menu 035 USB connector setting
  ALC high:    Reduce audio level in WSJT-X
"""),

    ("FT8 Operation", "Digital Modes",
     """# FT8 / FT4 / WSPR Operation

## Overview
Squelch works alongside WSJT-X for FT8 operation.
WSJT-X handles the waterfall and decode engine.
Squelch handles logging, callsign lookup, and band data.

## Workflow
1. Select FT8 in the Modes tab
   → WSJT-X launches automatically
2. In WSJT-X: pick your TX frequency on the waterfall
   (find a clear spot — avoid occupied signals)
3. Enable Auto Seq in WSJT-X
4. Decodes appear in both WSJT-X and Squelch
5. Squelch logs completed QSOs automatically

## Band Selection
Standard FT8 frequencies by band:
  160m: 1.840 MHz     17m: 18.100 MHz
  80m:  3.573 MHz     15m: 21.074 MHz
  40m:  7.074 MHz     12m: 24.915 MHz
  30m: 10.136 MHz     10m: 28.074 MHz
  20m: 14.074 MHz      6m: 50.313 MHz

## Propagation Tips
• Check Band Conditions tab before operating
• Gray line (dawn/dusk) offers best DX propagation
• SFI > 120: HF is good, try 10m-20m
• K-index > 4: aurora may disrupt higher bands
• Low SFI: try 40m-80m for regional contacts

## Logging
Squelch logs QSOs to:
  Windows: %APPDATA%\\Squelch\\logs\\squelch_log.db
ADIF export: Log tab → Export ADIF
"""),

    ("SignaLink USB Setup", "Rig Control",
     """# SignaLink USB Setup

## What It Does
The SignaLink USB is a USB audio interface that connects
your radio to your PC for digital mode operation.
Works with any rig that has a mic/speaker or accessory port.

## Installation
1. Download the jumper configuration for your rig:
   tigertronics.com/sl_wiretable.htm

2. Install the jumpers per the diagram for your radio

3. Connect to rig's accessory/data port (or mic/speaker)

4. Connect to PC via USB cable

5. The SignaLink appears as "USB Audio CODEC" in Windows

## WSJT-X Settings
  Settings → Audio:
    Input:  USB Audio CODEC
    Output: USB Audio CODEC
  Settings → Radio:
    PTT Method: RTS

## Level Adjustment
  TX: Adjust the TX knob on the SignaLink front panel
      Target: ALC meter barely moving on the radio
      Aim for 25-30W output on a 100W radio
  RX: Adjust RX knob so signal appears well on waterfall
      but does not clip (no red overload indicator)

## Troubleshooting
  No TX: Check jumper config for your specific rig
  ALC high: Turn TX knob down on SignaLink
  RFI: Add ferrite choke to USB cable
  Ground loop: Use audio isolation transformer
"""),

    ("QRZ-1 Explorer", "Rig Control",
     """# Explorer QRZ-1 Setup

## What It Is
The QRZ-1 Explorer is a VHF/UHF handheld radio based on
the TYT TH-UV88 platform. It has no CAT control.
Use it for voice and digital modes via audio interface.

## Programming Cable
Standard Kenwood K1 type cable (3.5mm + 2.5mm)
This is the same cable used for Baofeng radios.

## Programming with CHIRP
1. Download CHIRP: chirpmyradio.com
2. Open CHIRP → Radio → Download From Radio
3. Select: TYT → TH-UV88
4. Select your COM port → OK

Note: CHIRP may not correctly program CTCSS tones.
Use RT Systems RPS-QRZ1 software for reliable CTCSS programming.

## Digital Mode Setup (VOX)
1. Enable VOX: Menu → VOX → ON
2. Set VOX level: 2 or 3
3. Set VOX delay: Minimum
4. Connect K1 audio cable to PC soundcard
5. In WSJT-X: PTT Method → VOX

## Antenna Connector
SMA-Female (opposite of Baofeng SMA-Male)
You may need an SMA-F to SMA-M adapter for some antennas.

## CTCSS Note
If programmed tones don't work after CHIRP:
Re-upload using RT Systems RPS-QRZ1 software.
"""),

    ("SDR Setup", "SDR",
     """# SDR Setup Guide

## What You Need
SoapySDR is required for the SDR waterfall and spectrum.
Not needed if you only use the IC-7100 USB audio.

## Windows Installation
1. Download PothosSDR bundle (includes all drivers):
   downloads.myriadrf.org/builds/PothosSDR/
   Run as Administrator. Reboot.

2. Install Python binding:
   pip install soapysdr

## RTL-SDR (Extra Step Required)
RTL-SDR ships with a DVB-T driver that won't work.
Replace it using Zadig (zadig.akeo.ie):
  Options → List All Devices
  Select: Bulk-In, Interface (Interface 0)
  Driver: WinUSB → Replace Driver

Recommended: RTL-SDR Blog V3 (~$30 at rtl-sdr.com)

## Verify Detection
Run in terminal:
  SoapySDRUtil --find

Should list your device. If not, check driver installation.

## Linux / DragonOS
  sudo apt install soapysdr-tools python3-soapysdr
  sudo apt install soapyrtlsdr rtl-sdr    # for RTL-SDR
  sudo apt install soapyhackrf hackrf      # for HackRF

## ADS-B Setup
dump1090-fa enables aircraft tracking:
  Windows: github.com/flightaware/dump1090/releases
  Linux:   sudo apt install dump1090-fa
  Connect RTL-SDR, launch dump1090-fa,
  then click "Open ADS-B Map" in the SDR tab.
"""),

    ("Gray Line", "Propagation",
     """# Gray Line Propagation

## What Is the Gray Line?
The gray line (solar terminator) is the boundary between
day and night on Earth. It moves continuously as Earth rotates.

## Why It Matters for Ham Radio
During the gray line, the ionosphere is in a transitional state
that creates exceptional propagation conditions — especially on
the lower HF bands (160m, 80m, 40m).

Signals can travel long distances along the gray line with
unusually low path loss. DX contacts that are impossible
during full day or night often work during the gray line.

## Gray Line Indicators in Squelch
• Band Conditions tab: gray line status bar at top
• Map tab: day/night overlay with gray line boundary
• Both update every 60 seconds

## Status Meanings
  ☀ Gray line — sunset in X min    Excellent — you're IN it
  🌅 Gray line — sunrise in X min  Excellent — sunrise gray line
  ☀ Daytime                        Normal day conditions
  🌙 Nighttime                      Night-side propagation

## Best Practices
• Set an alarm for your local sunrise/sunset times
• Monitor 40m and 80m during gray line
• East-West paths are enhanced most
• Long-path DX (going the "wrong way around") often
  opens during gray line
• Watch for stations you normally can't hear

## Golden Hour
The 30 minutes before sunrise and after sunset are the
"golden hour" — often the best DX propagation of the day.
"""),

    ("Winlink / VARA", "Winlink",
     """# Winlink and VARA Setup

## What Is Winlink?
Winlink is an email-over-radio system used by amateur
radio operators and served agencies for emergency
communications. Messages travel via RF to gateway
stations connected to the internet.

Works without internet on the user end — essential for
EmComm when infrastructure is down.

## VARA HF
VARA HF is a high-performance HF modem (soundcard-based).
Free version works, paid license unlocks full speed.

Download: rosmodem.wordpress.com

Setup in Squelch:
1. Install VARA HF
2. Launch from Winlink tab → launch bar
3. Click "Connect HF" in Squelch
4. Compose your message, click Send

## VARA FM
VARA FM is for VHF/UHF operation via local gateways.
Better range than packet, excellent for ARES/RACES.

## Pat (Open Source Client)
Pat is a free, cross-platform Winlink client.
Download: github.com/la5nta/pat/releases

Pat handles the actual message transfer.
Squelch launches Pat and pre-fills your callsign/location.

## EmComm Templates
The Winlink tab includes ARES/EmComm templates:
  ICS-213  General message between stations/EOC
  ICS-214  Activity log for each operational period
  Radiogram NTS traffic (welfare/priority messages)
  Welfare  Let family know you're safe

## Winlink Wednesday
Every Wednesday, send a check-in to WW@winlink.org
to verify your system works before you need it.
Use the "Winlink Wednesday Check-in" template.
"""),

    ("EmComm / ARES", "Emergency Comms",
     """# Emergency Communications Guide

## ARES Basics
The Amateur Radio Emergency Service (ARES) is a field
organization of licensed amateurs who have voluntarily
registered their qualifications to provide communications
for public service events and emergency response.

## Net Protocols
When checking in to a net:
  1. Wait for net control to call for check-ins
  2. Give your callsign phonetically on first contact
  3. Give your location (grid square or city/county)
  4. State your traffic (message count) or "no traffic"
  5. Follow net control's instructions

## Message Handling
Priority order (highest to lowest):
  EMERGENCY  Life/death situations
  PRIORITY   Urgent but not life-threatening
  WELFARE    Health/welfare of individuals
  ROUTINE    Normal traffic

## Tactical vs Formal Traffic
  Tactical:  Quick exchange using tactical callsigns
             (EOC, SHELTER, COMMAND, etc.)
  Formal:    ARRL Radiogram format for official traffic

## ICS Integration
Modern EmComm uses the Incident Command System (ICS):
  ICS-213: General message (point-to-point)
  ICS-214: Activity log (submit to EOC each period)
  ICS-309: Communications log

Squelch includes templates for ICS-213 and ICS-214
in the Winlink tab.

## Go-Kit Checklist
  ☐ Radio + antenna (HF and VHF/UHF)
  ☐ Power supply + battery backup
  ☐ PC running Squelch
  ☐ SignaLink or audio interface
  ☐ Winlink account verified (winlink.org)
  ☐ VARA HF + VARA FM installed and tested
  ☐ Pat or RMS Express ready
  ☐ Frequency list for served agency
  ☐ Paper forms (backup if no PC)
"""),

    ("Yaesu FT-991A Setup", "Rig Control",
     """# Yaesu FT-991A CAT Control Setup

## USB Connection
The FT-991A has a built-in USB audio and CAT interface.
Connect via USB cable — no external interface needed.
Driver installs automatically on Windows 10/11.

## Radio Menu Settings
Press MENU on the radio:

  CAT RATE:       38400 bps (recommended)
  CAT TOT:        10 msec
  CAT RTS:        Enable
  RS232 BAUD:     38400
  DATA IN SEL:    USB  (for digital modes)
  DATA PTT SEL:   DTR  (if using hamlib PTT)

## Squelch Settings (Rig Tab)
  Model:  Yaesu FT-991A
  Port:   COM port for FT-991A (check Device Manager)
  Baud:   38400

## Hamlib Model
Hamlib model number: 135 (FT-991)
The FT-991A uses the same Hamlib model as FT-991.

## For FT8/Digital Modes
  Set radio to USB-D mode (not plain USB)
  DATA IN SEL: USB
  Audio input:  USB Audio CODEC (from FT-991A)
  Audio output: USB Audio CODEC (to FT-991A)

## Troubleshooting
  CAT not responding: Check baud rate matches menu setting
  No audio:          Check DATA IN SEL = USB
  TX but no signal:  Reduce audio level, check ALC
"""),

    ("Kenwood TS-2000 Setup", "Rig Control",
     """# Kenwood TS-2000 CAT Control Setup

## Interface Required
The TS-2000 uses a DE-9 (DB-9) serial port for CAT.
You need a USB-to-serial adapter (FTDI or Prolific chip).
Or use the built-in serial port if your PC has one.

## Recommended Interface
  Signalink USB with Kenwood cable OR
  West Mountain Radio RIGblaster OR
  Any FTDI-based USB-Serial adapter + null modem cable

## Radio Menu Settings
  Menu 54 (PC COM RATE):  9600 or 57600
  Make note of what you set — must match Squelch

## Squelch Settings (Rig Tab)
  Model:  Kenwood TS-2000
  Port:   COM port for your USB-serial adapter
  Baud:   9600 (or match your Menu 54 setting)

## Hamlib Model
Hamlib model number: 202 (TS-2000)

## For FT8/Digital Modes
  Connect audio via Signalink or soundcard interface
  Set radio to USB mode for 20m/17m/15m/12m/10m
  Set radio to LSB mode for 80m/40m
  Audio input:  SignaLink (USB Audio CODEC)
  Audio output: SignaLink (USB Audio CODEC)

## Troubleshooting
  No COM port: Check USB-serial driver installed
  CAT errors:  Verify baud rate matches Menu 54
  ALC high:    Reduce TX level on Signalink
"""),

    ("Yaesu FT-817/818 Setup", "Rig Control",
     """# Yaesu FT-817/818 CAT Control Setup

## Interface Required
The FT-817/818 uses a mini-DIN 8-pin data port.
You need an interface cable — recommended options:

  West Mountain Radio RIGblaster Nomic
  Yaesu CT-39A cable + USB-serial adapter
  SignaLink USB with Yaesu cable

## Radio Menu Settings
  Menu 14 (CAT RATE):   4800, 9600, 19200, or 38400
  Menu 16 (CAT TOT):    10 msec
  Menu 17 (CAT RTS):    Enable

## Squelch Settings (Rig Tab)
  Model:  Yaesu FT-817/818
  Port:   COM port for your interface
  Baud:   4800 (default) or match your menu setting

## Note on Power
The FT-817/818 runs 5W max. When using digital modes:
  Reduce power to 2.5W to avoid overheating
  Use a fan if operating for extended periods

## Battery Operation
FT-817/818 can run from internal battery (~5Wh NiMH)
For portable/SOTA operation this is ideal.
"""),

    ("Generic CAT Setup Guide", "Rig Control",
     """# Generic CAT Control Setup

## What is CAT Control?
CAT (Computer Aided Transceiver) control lets Squelch:
  - Read and set frequency
  - Change mode (USB/LSB/CW/FM)
  - Control PTT (push-to-talk)
  - Read S-meter and other data

## Finding Your Hamlib Model Number
Run in terminal:
  rigctl -l | grep -i "your rig name"
Or visit: hamlib.org/hams.html

Enter the number in Squelch → Rig tab → Model (manual)

## Common Interface Types

  USB direct:   IC-7100, FT-991A, IC-7300 — plug-in USB
  USB-Serial:   TS-2000, older rigs — need adapter cable
  Audio only:   Baofeng, UV-5R, QRZ-1 — no CAT available

## COM Port (Windows)
  Device Manager → Ports (COM & LPT)
  Look for: CP210x, FTDI, Prolific, CH340
  Note the COM number (e.g. COM5)

## Troubleshooting Checklist
  1. Is the driver installed? (Device Manager, no yellow !)
  2. Does the baud rate match the radio's menu?
  3. Is another program using the COM port? (close it)
  4. Is CAT enabled in the radio menu?
  5. Is the cable correct for your radio model?
  6. Try a different USB port / cable

## PTT Control Options
  CAT PTT:  Hamlib controls PTT via CAT command
  RTS:      Serial port RTS line (most interfaces)
  DTR:      Serial port DTR line
  VOX:      Audio level triggers PTT (SignaLink default)
  None:     Manual PTT (push radio button yourself)
"""),

    ("Keyboard Shortcuts", "Reference",
     """# Keyboard Shortcuts

## Global
  F1         Open Help (this tab)
  Ctrl+,     Open Settings
  Ctrl+L     Jump to Log tab
  Ctrl+M     Jump to Modes tab
  Ctrl+R     Jump to Rig tab
  Ctrl+B     Jump to Band Conditions
  Ctrl+D     Jump to Digital Monitor
  Ctrl+W     Jump to Winlink
  Alt+F4     Exit (Windows)

## Log Tab
  Ctrl+N     New manual QSO entry
  Ctrl+E     Export ADIF
  Ctrl+F     Search log

## Rig Tab
  Ctrl+Up    Frequency up (step)
  Ctrl+Down  Frequency down (step)
  Space      PTT (hold) — when rig connected

## Modes Tab
  F5         Send CQ (FT8)
  F6         Halt TX
  F7         Toggle Auto Seq

## General
  Ctrl+Z     Undo (in text fields)
  Ctrl+A     Select all
  Escape     Close dialogs

Note: Some shortcuts require the rig to be connected
and the appropriate tab to be active.
"""),

    ("APRS Setup", "Digital Modes",
     """# APRS Setup Guide

## What is APRS?
APRS (Automatic Packet Reporting System) is a
digital system for real-time position reporting,
weather data, messaging, and object tracking.
Used by emergency communications, portable ops,
and vehicle tracking.

## APRS-IS (Internet Gateway)
Squelch connects to the worldwide APRS-IS network
for receive-only monitoring. No radio required.

  Local RF tab → APRS-IS panel → Connect
  Station location must be set in the top bar
  Receives packets within 150 km of your location

## APRS Beacon (Internet)
When connected to APRS-IS, you can send a beacon:
  Local RF tab → APRS-IS panel → Beacon Now
  Configurable: symbol, comment, path, interval
  Settings → Station → Beacon comment

## RF APRS (with Radio)
For RF APRS you need a TNC (Terminal Node Controller):
  Direwolf: software TNC for PC soundcard (free)
  github.com/wb2osz/direwolf

  Hardware TNC: Mobilinkd, TNC-Pi, etc.
  Connect to IC-7100 data port or Baofeng audio jack

## Direwolf Setup
  Download: github.com/wb2osz/direwolf/releases
  Configure direwolf.conf with your callsign
  Set ADEVICE to your audio device
  Start Direwolf before launching Squelch

## Common APRS Symbols
  House (default): fixed home station
  Car: mobile vehicle
  Portable: /- (backpack/portable)
  Yaesu walker: moving on foot
  Emergency: priority station

## APRS Paths
  WIDE1-1,WIDE2-1: standard path (3 hops)
  WIDE1-1: one hop (VHF local)
  Direct: no digipeating (IGate direct only)

## Map Integration
Connected APRS stations appear on the Squelch map.
Gray markers show nearby APRS stations.
"""),

    ("SOTA and POTA", "Operating",
     """# SOTA and POTA — Portable Operations

## SOTA (Summits on the Air)
summits on the air (sota.org.uk) awards for
operating from designated mountain summits.

## How SOTA Works
  Activators: operate from a summit, earn points
  Chasers:   work the activator, earn 1 point each

Points depend on summit difficulty (1-10 points).
Chase the gray line for maximum DX contacts.

## POTA (Parks on the Air)
pota.app — operate from national/state parks.
No points per contact — 10 QSOs = activation.
Over 30,000 parks across 100+ programs worldwide.

## Finding Active Spots in Squelch
  Modes tab → SOTA/POTA Spots panel
  Click ▶ Start to begin fetching spots
  Updates every 5 minutes automatically
  Double-click a spot to tune the rig

## Frequency Conventions
  CW:  7.030-7.032 MHz, 14.060 MHz
  SSB: 7.285 MHz, 14.285-14.290 MHz
  FT8: standard FT8 frequencies (7.074, 14.074 etc)

## Making the Contact
  Activator sends: "CQ SOTA [callsign] [summit ref]"
  Chaser responds: "[callsign]"
  Quick exchange: signal report + summit reference

## Portable Setup Tips
  FT-817/818 or IC-705 for HF portable
  End-fed half-wave antenna (EFHW) — easy portable
  LiPo battery bank for power
  Squelch portable mode: use QRZ-1 + Baofeng
  Log contacts in Squelch — upload ADIF to SOTA/POTA

## Digital Modes for Portable
  FT8 works great portable — low power, long distance
  WSJT-X + Squelch auto-logs all SOTA/POTA contacts
  5 watts FT8 can reach coast to coast
"""),

    ("Propagation Reference", "Reference",
     """# Propagation Quick Reference

## Solar Flux Index (SFI)
Measures solar radio emission at 10.7cm wavelength.
  < 70:   Poor — HF propagation weak or absent
  70-90:  Fair — lower bands (40m, 80m) usable
  90-120: Good — all HF bands usable
  > 120:  Excellent — 10m, 12m may open
  > 150:  Outstanding — 10m often worldwide

## K-index (Geomagnetic Activity)
Measures geomagnetic disturbances (0-9 scale).
  0-1:  Quiet — excellent for all bands
  2-3:  Unsettled — generally good
  4:    Active — higher bands may be degraded
  5-6:  Minor storm — 160m-40m may be affected
  7-9:  Major storm — avoid high bands, try 80m/160m

## A-index
24-hour average of geomagnetic activity.
  0-7:   Quiet — excellent conditions
  8-15:  Unsettled
  16-29: Active
  30-49: Minor storm
  > 50:  Major storm

## Band Propagation by Time
  Dawn:    40m, 80m, 160m open well; listen for DX
  Morning: 20m-15m open; 10m may open
  Midday:  15m, 10m peak; 20m good
  Afternoon: 20m-40m good; 10m closing
  Dusk:   40m opens; listen on 15m-20m
  Night:  80m, 160m; 40m for continental; 20m long path

## Best Bands for DX
  Worldwide DX: 20m (most reliable)
  Long distance: 15m, 10m (when solar flux high)
  Regional:     40m evening, 80m night
  Local/State:  2m FM, 70cm
"""),
]

# Build search index
_SEARCH_INDEX = {}
for title, cat, content in HELP_ARTICLES:
    key = f"{cat}/{title}"
    words = (title + " " + cat + " " +
             content).lower().split()
    _SEARCH_INDEX[key] = words


class HelpTab(QWidget):
    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.cfg = config
        self._current_article = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._window = None    # pop-out window ref

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(
            "QSplitter::handle{background:#1a1a1a;width:3px;}")

        # Left: article list + search
        left = self._build_nav()
        left.setMaximumWidth(260)
        left.setMinimumWidth(180)
        splitter.addWidget(left)

        # Right: article content
        right = self._build_content()
        splitter.addWidget(right)
        splitter.setSizes([220, 700])

        root.addWidget(splitter, 1)

    def _build_nav(self) -> QWidget:
        w   = QWidget()
        w.setStyleSheet("background:#0a0a0a;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)

        # Search
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍 Search help…")
        self._search.setStyleSheet(
            "background:#141414;color:#aaa;"
            "border:1px solid #1a1a1a;border-radius:3px;"
            "padding:4px 8px;font-size:13px;")
        self._search.textChanged.connect(self._do_search)
        lay.addWidget(self._search)

        # Article list
        self._list = QListWidget()
        self._list.setStyleSheet(
            "QListWidget{background:#0a0a0a;color:#aaa;"
            "border:none;font-size:13px;}"
            "QListWidget::item{padding:4px 6px;}"
            "QListWidget::item:selected{"
            "background:#1a3a1a;color:#3fbe6f;}"
            "QListWidget::item:hover{"
            "background:#141414;}")
        self._list.currentItemChanged.connect(
            self._on_article_select)
        lay.addWidget(self._list, 1)

        self._populate_list(HELP_ARTICLES)
        return w

    def _build_content(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._content = QTextEdit()
        self._content.setReadOnly(True)
        self._content.setStyleSheet(
            "background:#0d0d0d;color:#bbb;"
            "font-size:12px;font-family:'Segoe UI',sans-serif;"
            "border:none;padding:16px;line-height:1.5;")
        lay.addWidget(self._content, 1)

        # Show welcome on first open
        self._show_welcome()
        return w

    def _populate_list(self, articles):
        self._list.clear()
        current_cat = None
        for title, cat, _ in articles:
            if cat != current_cat:
                # Category header
                header = QListWidgetItem(f"── {cat} ──")
                header.setFlags(
                    Qt.ItemFlag.NoItemFlags)
                header.setForeground(
                    __import__("PyQt6.QtGui",
                    fromlist=["QColor"]).QColor("#3fbe6f"))
                self._list.addItem(header)
                current_cat = cat
            item = QListWidgetItem(f"  {title}")
            item.setData(Qt.ItemDataRole.UserRole, title)
            self._list.addItem(item)

    def _on_article_select(self, item):
        if not item:
            return
        title = item.data(Qt.ItemDataRole.UserRole)
        if not title:
            return
        for t, cat, content in HELP_ARTICLES:
            if t == title:
                self._show_article(t, cat, content)
                break

    def _show_article(self, title, cat, content):
        # Simple Markdown-like rendering
        html = self._render_content(title, cat, content)
        self._content.setHtml(html)
        self._current_article = title

    def _render_content(self, title, cat, content) -> str:
        lines = content.strip().splitlines()
        html  = [
            "<style>"
            "body{font-family:'Segoe UI',sans-serif;"
            "font-size:12px;color:#bbb;line-height:1.6;}"
            "h1{color:#3fbe6f;font-size:18px;margin-bottom:4px;}"
            "h2{color:#aaa;font-size:14px;margin-top:16px;}"
            "code{background:#141414;color:#44aaff;"
            "font-family:'Courier New';padding:1px 4px;}"
            "pre{background:#141414;color:#aaa;"
            "font-family:'Courier New';font-size:13px;"
            "padding:10px;border-left:3px solid #3fbe6f;}"
            "p{margin:4px 0;}"
            "</style>"
            f"<p style='color:#555;font-size:12px'>"
            f"{cat}</p>"
        ]
        in_pre = False
        pre_lines = []

        for line in lines:
            if line.startswith("## "):
                if in_pre:
                    html.append(
                        "<pre>" +
                        "\n".join(pre_lines) +
                        "</pre>")
                    pre_lines = []
                    in_pre = False
                html.append(
                    f"<h2>{line[3:]}</h2>")
            elif line.startswith("# "):
                html.append(
                    f"<h1>{line[2:]}</h1>")
            elif line.startswith("  "):
                # Indented — treat as code block
                if not in_pre:
                    in_pre = True
                pre_lines.append(line)
            else:
                if in_pre:
                    html.append(
                        "<pre>" +
                        "\n".join(pre_lines) +
                        "</pre>")
                    pre_lines = []
                    in_pre = False
                if line.strip():
                    # Inline code: backtick
                    import re
                    line = re.sub(
                        r'`([^`]+)`',
                        r'<code>\1</code>',
                        line)
                    html.append(f"<p>{line}</p>")
                else:
                    html.append("<br>")

        if in_pre:
            html.append(
                "<pre>" +
                "\n".join(pre_lines) +
                "</pre>")

        return "\n".join(html)

    def _show_welcome(self):
        self._content.setHtml("""
<style>
body{font-family:'Segoe UI';color:#bbb;font-size:12px;
     line-height:1.6;}
h1{color:#3fbe6f;font-size:20px;}
h2{color:#aaa;font-size:14px;margin-top:16px;}
.cat{color:#3fbe6f;font-size:13px;}
</style>
<h1>Squelch Help</h1>
<p>Select a topic from the left, or search for what you need.</p>
<h2>Quick Links</h2>
<p>
<span class='cat'>Setup:</span> Getting Started &nbsp;|&nbsp;
IC-7100 Setup &nbsp;|&nbsp; SDR Setup
</p>
<p>
<span class='cat'>Operating:</span> FT8 Operation &nbsp;|&nbsp;
Gray Line &nbsp;|&nbsp; EmComm / ARES
</p>
<p>
<span class='cat'>Reference:</span> Propagation Reference &nbsp;|&nbsp;
Keyboard Shortcuts
</p>
<br>
<p style='color:#555;font-size:13px;'>
Squelch v0.7.1-alpha &nbsp;|&nbsp;
github.com/dawardy/squelch &nbsp;|&nbsp;
GPL v3
</p>
""")

    def _do_search(self, query: str):
        query = query.strip().lower()
        if not query:
            self._populate_list(HELP_ARTICLES)
            return

        words   = query.split()
        results = []
        for title, cat, content in HELP_ARTICLES:
            key = f"{cat}/{title}"
            idx = _SEARCH_INDEX.get(key, [])
            score = sum(
                1 for w in words if w in idx)
            if score > 0:
                results.append((score, title, cat, content))

        results.sort(reverse=True)
        filtered = [(t, c, ct)
                    for _, t, c, ct in results]
        self._populate_list(filtered)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._current_article:
            self._show_welcome()
