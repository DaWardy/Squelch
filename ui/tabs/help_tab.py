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
import logging
from core.themes import get_theme as _ht_get_theme
from ui.panel import SquelchPanel
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QListWidget, QListWidgetItem,
    QTextEdit, QLineEdit, QPushButton, QFrame,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QDesktopServices

log = logging.getLogger(__name__)

# ── Help content ──────────────────────────────────────────────────────────

HELP_ARTICLES = [
    # (title, category, content)
    ("Software Dependencies", "Setup",
     """# Software Dependencies

Every package Squelch uses, where it comes from, and why.

## Python Runtime
  Python 3.9+     python.org
                  Python Software Foundation (US non-profit)
                  PSF License — permissive, BSD-like
                  250M+ downloads/month

## UI Framework
  PyQt6           pypi.org/project/PyQt6
                  Riverbank Computing (UK) / Qt Group (Finland)
                  GPL v3 — matches Squelch license
                  Powers all windows, widgets, and dialogs

## Signal Processing
  numpy           pypi.org/project/numpy
                  NumFOCUS (US non-profit)
                  BSD 3-Clause
                  300M+ downloads/month — most audited math library

  SoapySDR        github.com/pothosware/SoapySDR
                  Pothosware / Josh Blum (USA)
                  Boost License (permissive)
                  Standard SDR hardware abstraction layer

  pyqtgraph       pypi.org/project/pyqtgraph
                  Community / Luke Campagnola (USA/Canada)
                  MIT License
                  Waterfall and spectrum display

  sgp4            pypi.org/project/sgp4
                  Brandon Rhodes (USA)
                  MIT License — pure Python, easy to audit
                  Satellite orbital mechanics

## Networking
  requests        pypi.org/project/requests
                  Python Software Foundation (USA)
                  Apache 2.0
                  400M+ downloads/month — most downloaded Python package
                  Used for: NOAA solar data, Winlink API,
                  RepeaterBook, geocoding, Celestrak TLEs

  defusedxml      pypi.org/project/defusedxml
                  Christian Heimes / CPython core developer (Germany)
                  PSF License
                  SECURITY-CRITICAL: prevents XML injection attacks
                  in QRZ and FLRig XML parsing

## Audio
  sounddevice     pypi.org/project/sounddevice
                  Matthias Geier (Germany)
                  MIT License
                  Rig audio input and digital mode audio output

## What Squelch does NOT do
  No telemetry    — Squelch never phones home
  No analytics    — No usage tracking of any kind
  No ads          — No advertising SDKs
  No auto-update  — Never downloads or executes code from internet
  No cloud        — All data stays on your machine

## Verifying your install
  In the Squelch folder:
    venv/Scripts/pip list
    venv/Scripts/pip show <package>

  Full audit including transitive dependencies:
    venv/Scripts/pip install pipdeptree
    venv/Scripts/pipdeptree

## Full dependency documentation
  See DEPENDENCIES.md in the Squelch folder
  for country of origin, estimated user counts,
  and audit links for every package.
"""),

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
Cabrillo export: Log tab → Export Cabrillo (contest submissions)
CSV export: Log tab → Export CSV (spreadsheet)

## Uploading to LoTW (Logbook of the World)
1. Install TQSL from tqsl.arrl.org and set up your certificate
2. Add your LoTW callsign and password in Settings → APIs → LoTW
3. Log tab → Upload LoTW queue — uploads pending QSOs via TQSL
   Confirmations typically arrive within 24–48 hours.

## Uploading to QRZ Logbook
1. Log in to qrz.com, go to Logbook → Settings → Enable API
2. Copy your API key (free — no subscription required for logbook)
3. Add the key in Settings → APIs → QRZ.com → Logbook API Key
4. Log tab → Upload QRZ queue — syncs pending QSOs to your QRZ logbook

## Uploading to ClubLog
1. Create a free account at clublog.org
2. Add your ClubLog email and password in Settings → APIs → ClubLog
3. Log tab → Upload ClubLog — uploads your full log as ADIF
   ClubLog processes uploads within a few minutes.

## Uploading to eQSL.cc
1. Create a free account at eqsl.cc
2. Add your eQSL username and password in Settings → APIs → eQSL.cc
3. Log tab → Upload eQSL — uploads your full log as ADIF
   Duplicates are silently accepted (re-upload safe).

## Uploading to HRDLog.net
1. Create a free account at hrdlog.net
2. Go to hrdlog.net → Settings → API Key to generate your key
3. Add your callsign and API key in Settings → APIs → HRDLog.net
4. Log tab → Upload HRDLog — uploads your full log as ADIF

## Awards Progress (Log tab)
Squelch tracks DXCC, WAS (50 states), and Maidenhead grid squares
worked and confirmed. Progress bars at the top of the Log tab update
automatically as you log QSOs and receive LoTW/QRZ confirmations.
"""),

    ("SignaLink USB Setup", "Audio & Hardware",
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

    ("QRZ-1 Explorer", "Audio & Hardware",
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

    ("SDRplay RSP Setup (RSP2Pro, RSPdx, RSPduo)", "SDR",
     """# SDRplay RSP Setup on Windows

## About the RSP Lineup

SDRplay makes a family of wide-coverage receivers with
genuine 12-bit or 14-bit ADCs — a real step above RTL-SDR.

  RSP1A  1 kHz - 2 GHz  1 antenna port   best value
  RSP2   1 kHz - 2 GHz  3 antenna ports  notch filters
  RSP2Pro 1 kHz - 2 GHz 3 antenna ports  RSP2 + shielding
  RSPdx  1 kHz - 2 GHz  3 antenna ports  improved filters
  RSPduo 1 kHz - 2 GHz  2 tuners         dual independent RX

All share the same install path and Squelch settings.

## Step 1 — Install SDRplay API  (REQUIRED first)

  https://www.sdrplay.com/softwarehome/

Download the API installer for Windows.
Run it before installing PothosSDR.
This step is mandatory — SoapySDRplay does not work
without the SDRplay hardware API.

The installer is free, no account required (~30 MB).

## Step 2 — Install PothosSDR Bundle

  https://downloads.myriadrf.org/builds/PothosSDR/

PothosSDR includes SoapySDRplay, which is the
bridge between the SDRplay API and Squelch.
Run the installer, accept defaults, reboot.

Order matters: SDRplay API first, then PothosSDR.

## Step 3 — Install Python Binding

  pip install soapysdr

Verify with Squelch installer:
  python installer.py

Look for: SoapySDR X.X.X — 1 device(s) found

## EASIER PATH — conda / miniforge (recommended for most)

Many users find conda simpler than PothosSDR — it installs SoapySDR
and the device drivers together, no CMake or reboot dance:

  1. Install Miniforge: github.com/conda-forge/miniforge
  2. Then, for your hardware (install only what you have):
       conda install -c conda-forge soapysdr-module-rtlsdr   (RTL-SDR)
       conda install -c conda-forge soapysdr-module-hackrf   (HackRF)
       conda install -c conda-forge soapysdr-module-sdrplay  (SDRplay)
       conda install -c conda-forge soapysdr-module-lms7     (LimeSDR)

Note the package names are 'soapysdr-module-NAME', not 'soapyNAME'.
RTL-SDR and HackRF are the most reliable on Windows via conda; UHD
(Ettus) and Airspy modules may be Linux-only on conda-forge — for
those on Windows, use the PothosSDR bundle below.

The Squelch installer can do this for you: run 'python installer.py'
and pick your hardware from the SDR Drivers step.

## Squelch SDR Tab — RSP2Pro Specific Settings

When Squelch detects your RSP2Pro, it shows these controls:

### Antenna Port
  Antenna A  —  main 50Ω SMA input
  Antenna B  —  50Ω SMA + Bias-Tee DC supply
  Hi-Z       —  high impedance input
                 USE THIS for HF below 30 MHz with
                 a long wire or magnetic loop antenna

### MW/FM Broadcast Notch
  Attenuates the 150 kHz - 30 MHz MW/LW band and
  76-108 MHz FM band.
  Enable if you see FM stations leaking into your HF band.
  Safe to leave enabled for most HF monitoring.

### Bias-Tee (Port B only)
  Supplies 4.7V DC via the Antenna B SMA connector.
  Powers external LNAs like the Nooelec LaNA.
  ONLY use with Antenna B selected.
  Do NOT enable with a passive antenna — it will
  draw through your feedline impedance.

### IF Bandwidth
  Selects the IF filter before the ADC:
    200 kHz   — CW/SSB, one signal at a time
    600 kHz   — NFM, channelized VHF monitoring
    1.536 MHz — AM broadcast, ATC
    5 MHz     — general HF/VHF monitoring (recommended start)
    8 MHz     — maximum coverage (RSPdx only)

### AGC vs Manual IF Gain Reduction
  AGC on:   RSP adjusts gain automatically
  AGC off:  You set IF Gain Reduction manually
            Higher number = less gain (for strong signals)
            Lower number = more gain (for weak signals)
            Start at 40 dB and adjust

### I/Q Imbalance Correction
  Reduces mirror images in the spectrum.
  Leave enabled — no downside.

## Hi-Z Port — HF Long Wire

The Hi-Z port is unique to the RSP2/Pro/RSPduo.
It presents a high impedance input that is matched
to long-wire or magnetic loop antennas on HF.

Ideal bands via Hi-Z:
  LW/MW:    153 kHz - 1.7 MHz
  Shortwave: 2 MHz - 30 MHz
  Not for VHF/UHF — use port A or B above 60 MHz

## RSPduo: Dual-Tuner Mode

The RSPduo has two completely independent tuners.
Both can operate simultaneously at different frequencies:
  Tuner 1: any frequency in 1 kHz - 2 GHz
  Tuner 2: any frequency in 1 kHz - 2 GHz

Example: monitor 14.074 MHz FT8 AND 144 MHz FM
at the same time with a single RSPduo.

In Squelch, select "Tuner 1 50ohm" for the first
frequency and "Tuner 2 50ohm" for the second.
(Full dual-tuner support in a future Squelch update.)

## Troubleshooting

  "No device found" in Squelch:
    Was SDRplay API installed BEFORE PothosSDR?
    If no: reinstall PothosSDR after the API.
    Check sdrplay.com/api to verify API version.

  Broadcast interference on HF:
    Enable MW/FM notch filter.
    Reduce sample rate to narrow the captured band.

  Weak signals:
    Switch to Hi-Z port for HF below 30 MHz.
    Disable AGC, reduce IFGR to 20-30 dB.

  High noise floor:
    Enable MW/FM notch.
    Reduce sample rate.
    Check for USB 3.0 noise (try a different USB port).
"""),

    ("HackRF One Setup", "SDR",
     """# HackRF One Setup on Windows

## Why HackRF is different from RTL-SDR

HackRF is a Software Defined Radio transceiver (TX + RX)
covering 1 MHz to 6 GHz. It costs more than an RTL-SDR
but covers a much wider frequency range and can transmit.

Key difference: HackRF does NOT need Zadig.
It uses its own WinUSB driver that the PothosSDR
installer handles automatically.

## Step 1 — Install PothosSDR Bundle

  https://downloads.myriadrf.org/builds/PothosSDR/

This single installer includes:
  SoapySDR
  SoapyHackRF driver
  hackrf_info.exe and other tools

Run the installer, accept defaults, reboot.

## Step 2 — Install Python binding

  pip install soapysdr

Then verify with Squelch installer:
  python installer.py

Look for: HackRF or SoapySDR: N device(s) found

## Step 3 — Configure in Squelch SDR Tab

When HackRF is detected, the SDR tab shows
HackRF-specific controls:

  RF Amp (+14 dB):
    Enables HackRF's internal amplifier.
    Try without it first — amp adds noise.
    Enable only for very weak signals.

  Bias-Tee:
    Supplies DC power through the antenna port.
    Powers external LNAs (e.g. SAWbird for L-band).
    WARNING: do NOT enable with a direct antenna.

  LNA Gain (0-40 dB, 8 dB steps):
    First gain stage. Start at 16-24 dB.

  VGA Gain (0-62 dB, 2 dB steps):
    Second gain stage. Start at 30 dB.
    Reduce if signals look distorted or noisy.

## Typical Starting Settings

  Frequency:   your band of interest
  Sample Rate: 10 MHz (good balance of CPU vs coverage)
  LNA Gain:    24 dB
  VGA Gain:    30 dB
  RF Amp:      Off (enable if needed)

## HackRF Limitations

  Half-duplex: TX and RX cannot happen simultaneously.
  Transmitting with Squelch requires careful setup —
  the PTT watchdog is your safety net.

## Transmitting (advanced)

  Enable TX in Settings only if you hold an amateur
  license. The TX power range is roughly 0-10 dBm
  (-30 to +20 with amp depending on frequency).
  HackRF is low power — use an external amplifier
  for any meaningful range.
"""),

    ("USRP B200 mini / B210 Setup", "SDR",
     """# USRP B200 mini / B210 Setup on Windows

## What makes the B200/B210 special

The Ettus USRP B-Series are professional-grade
SDR platforms used in research and commercial deployments.

  B200 mini:  70 MHz - 6 GHz, 1 channel, ~56 MSPS
  B210:       70 MHz - 6 GHz, 2 channels, simultaneous TX+RX

They connect via USB 3.0 (USB 2.0 supported at lower rates).
No Zadig needed — UHD installs the driver automatically.

## Step 1 — Install UHD (two options)

Option A — PothosSDR bundle (easier):
  https://downloads.myriadrf.org/builds/PothosSDR/
  Includes UHD, SoapySDR, and SoapyUHD driver.
  Reboot after install.

Option B — Ettus UHD installer (latest UHD):
  https://files.ettus.com/binaries/uhd/
  Download the Windows .exe installer.
  Reboot after install.
  Then install SoapyUHD separately.

## Step 2 — Install Python binding

  pip install soapysdr

Verify:
  uhd_find_devices
  → Should show: USRP Device N: B200 ...

  python installer.py
  → Look for: SoapySDR N device(s) found

## Step 3 — First run (FPGA image download)

On first connection, UHD downloads the FPGA bitstream.
This takes 30-60 seconds and requires internet.
Subsequent connections are immediate.

If you see: "Unable to find an appropriate image"
Run: uhd_images_downloader.py

## Step 4 — Configure in Squelch SDR Tab

  Clock Source:
    internal — onboard TCXO, ±2.5 ppm
    external — 10 MHz ref on REF IN jack (best)
    gpsdo    — GPS-disciplined oscillator (best accuracy)

  Subdev Spec:
    A:A         — B200 mini, or B210 single channel
    A:A A:B     — B210 both channels (MIMO)

  RX Antenna:
    RX2  — dedicated receive port (recommended)
    TX/RX — shared transmit/receive port

## Recommended Settings

  Clock: internal (or external if you have a 10 MHz ref)
  Subdev: A:A (B200 mini), A:A A:B (B210 MIMO)
  Antenna: RX2
  Sample Rate: 8-16 MHz for most use cases
  Gain: 40-60 dB (total), adjust for signal level

## B210 MIMO Operation

With subdev A:A A:B, the B210 provides:
  CH1 (A:A): independent frequency, gain, antenna
  CH2 (A:B): independent frequency, gain, antenna

Both channels sample simultaneously and share a
phase-coherent clock — useful for direction finding
and two-band monitoring.

## USB 3.0 Required for High Sample Rates

  USB 2.0: up to ~8-10 MSPS
  USB 3.0: up to 61.44 MSPS

Use a dedicated USB 3.0 port directly on the motherboard,
not a USB hub. Drop-outs at high rates = USB bandwidth issue.
"""),

    ("RTL-TCP Quick Start", "SDR",
     """# RTL-SDR via rtl_tcp — No CMake Required

## Why rtl_tcp?

SoapySDR on Windows requires CMake and Visual Studio
build tools — a painful process for most ham operators.

rtl_tcp is a much simpler path:
  No compilation. No CMake. No Visual Studio.
  Just download, install one driver, and run.

## Step 1 — Download rtlsdr-release.zip

  github.com/rtlsdrblog/rtl-sdr-blog/releases  (official RTL-SDR Blog drivers)

Download the latest Windows .zip file.
Extract anywhere — it's portable, no installer needed.
The folder contains rtl_tcp.exe and several DLLs.

## Step 2 — Install WinUSB driver with Zadig

  zadig.akeo.ie

Plug in your RTL-SDR dongle.
Open Zadig.
  Options → List All Devices (check this)
  Select: "Bulk-In, Interface (Interface 0)"
  Or: "RTL2832U" or "RTL2838UHIDIR"
  Driver target: WinUSB
  Click: Replace Driver

This replaces the default driver with one that lets
software stream raw IQ data. Without this step,
rtl_tcp will not see the dongle.

Do this once per dongle, per PC.

## Step 3 — Run rtl_tcp.exe

Double-click rtl_tcp.exe. You should see:
  Found 1 device(s)
  Found Realtek RTL2832U ...
  Listening...

Default: localhost:1234, 2.048 MSPS, auto gain.

Custom options:
  rtl_tcp.exe -f 144390000   Center at 144.39 MHz
  rtl_tcp.exe -g 30          Manual gain 30 dB
  rtl_tcp.exe -p 0           PPM correction 0

## Step 4 — Open Squelch

Squelch auto-detects rtl_tcp on localhost:1234.
The SDR tab shows the waterfall immediately.

If Squelch was open when you started rtl_tcp,
close and reopen the SDR tab, or restart Squelch.

## Supported Features via rtl_tcp

  ✅ Waterfall display and spectrum
  ✅ Frequency tuning and gain control
  ✅ PPM correction
  ✅ IQ recording and playback
  ✅ Route to Digital Monitor (P25/DMR)

  ⚠ Scanner requires manual rtl_tcp restart to change freq
     (SoapySDR/PothosSDR path supports seamless scanning)

## Upgrading to Full SoapySDR Later

When you want more features (USRP, HackRF, scanner):

  1. Install PothosSDR: downloads.myriadrf.org/builds/PothosSDR/
  2. Reboot
  3. pip install soapysdr
  4. Squelch automatically uses SoapySDR instead of rtl_tcp

No settings to change — Squelch prefers SoapySDR when available.

## Troubleshooting

  "No devices found" in rtl_tcp.exe:
    Zadig driver not installed, or wrong device selected.
    Unplug/replug dongle and try again.

  Squelch doesn't detect rtl_tcp:
    Make sure rtl_tcp.exe is running BEFORE opening the SDR tab.
    Check Windows Firewall isn't blocking localhost:1234.

  Waterfall but no signal:
    Try gain: rtl_tcp.exe -g 40
    Or enable AGC: rtl_tcp.exe -g 0 -E agc
"""),

    ("RTL-SDR Quick Start (miniforge/conda)", "SDR",
     """## RTL-SDR + Miniforge — Quickest Path to SDR on Windows

This is the simplest way to get your RTL-SDR Blog dongle working in Squelch
on Windows without installing PothosSDR or building anything from source.

## What you need
- RTL-SDR Blog V3/V4 dongle (or any RTL2832U-based dongle)
- Miniforge3 already installed (which you have if you're using this installer)

## Step 1 — Install the Zadig USB driver
Zadig replaces the default Windows USB driver so SoapySDR can claim the device.

  1. Download Zadig: https://zadig.akeo.ie  (open source, safe)
  2. Plug in your RTL-SDR.
  3. Run Zadig → Options → List All Devices.
  4. Select "Bulk-In, Interface (Interface 0)" or "RTL2838UHIDIR".
  5. Driver: WinUSB (or libusbK). Click "Install Driver".

You only need to do this once per computer.

## Step 2 — Install the SoapySDR RTL-SDR module
In a Miniforge/Anaconda Prompt:

  conda install -c conda-forge soapysdr soapysdr-module-rtlsdr

Wait for it to finish. Verify with:

  python -c "import SoapySDR; print(SoapySDR.Device.enumerate())"

You should see something like: [{'driver': 'rtlsdr', 'label': 'Generic RTL2832U ...'}]
If you see [], the driver isn't loaded — run Zadig again and confirm WinUSB is selected.

## Step 3 — Launch Squelch
Squelch automatically finds SoapySDR in your conda environment (no manual
setup needed as of v0.11.17). Open the SDR tab and click Connect.

If the device doesn't appear:
  1. Check logs/squelch.log — search for "SDR: found" to see the enumerate result.
  2. Run: python -c "import SoapySDR; print(SoapySDR.Device.enumerate())" in
     the Squelch venv (not conda) to isolate the issue.
  3. If SoapySDR loads but shows [] there, try:
     venv/Scripts/pip install soapysdr  (Windows)
     (installs it directly into the venv as a fallback)

## SDRplay RSP2Pro / RSP1A / RSPdx
Install the SDRplay API FIRST from sdrplay.com/softwarehome, then:

  conda install -c conda-forge soapysdr soapysdr-module-sdrplay

The order matters — SoapySDR must detect the SDRplay API during install.
""", ),
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

    ("IC-7100 Detailed Setup", "Rig Control",
     """## Icom IC-7100 — Squelch Setup

The IC-7100 connects via USB (it presents as a virtual COM port). No USB-to-serial
adapter is needed.

## Step 1 — Install USB driver (Windows)
Install the Silicon Labs CP210x driver from:
  https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers

After installing, check Device Manager — you should see:
  Ports (COM & LPT) → Silicon Labs CP210x USB to UART Bridge (COMx)

Note the COM port number.

## Step 2 — Configure Squelch
1. Open Settings (Ctrl+,) → Rig tab.
2. Rig model: select ICOM IC-7100.
3. Port: select the COM port from Step 1.
4. Baud rate: 19200 (IC-7100 default; match your radio's CI-V baud setting).
5. Click Connect.

## Step 3 — Check the radio
On the IC-7100, verify CI-V baud rate:
  Menu → Connectors → CI-V Baud Rate → 19200 (or Auto).
  Menu → Connectors → CI-V USB → On.

## Troubleshooting
- "rigctld not found": install Hamlib and run python installer.py.
- "Permission denied": on Linux, run: sudo usermod -aG dialout $USER then reboot.
- "Timeout": try baud 9600 and match on the radio.
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

## View / Layout
  Ctrl+Shift+W  Enter Workspace Mode (floating panel layout)
  Ctrl+Shift+R  Toggle RF Lab / Education Mode
  Ctrl+W        Toggle Spectrum / Waterfall (SDR/Rig tab)
  Ctrl+Shift+1  Workspace preset 1
  Ctrl+Shift+2  Workspace preset 2
  Ctrl+Shift+3  Workspace preset 3
  Ctrl+Shift+4  Workspace preset 4

## SDR
  📸 button     Save spectrum+waterfall screenshot to Desktop

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
    ("Local RF — Where the data comes from", "Local RF",
     """## Local RF — Repeater data sources

Squelch's Local RF tab can populate its repeater table from three sources,
in order of preference:

### 1. CHIRP CSV import  (recommended, no setup)
The fastest, fully-offline path. If you already use CHIRP to program
your radio, you already have the data.

In CHIRP:
  1. Radio → Query Source → RepeaterBook → Proximity Query
  2. Enter your ZIP/grid and radius
  3. File → Export → save as .csv

In Squelch:
  4. Local RF tab → "📂 Import CHIRP CSV"
  5. Pick the file you just exported

No API key, no token, no network calls. The data is CHIRP's standard
radio-independent CSV format — works with exports from any source CHIRP
supports (RepeaterBook, RadioReference, DMR-MARC, etc.).

### 2. RepeaterBook with an approved API token
RepeaterBook now requires per-developer API tokens (as of March 2026).
Squelch is GPL non-commercial and tokens are free for non-commercial use.

Apply: repeaterbook.com/api/token_request.php
Paste the token: Settings → APIs → RepeaterBook → API token

Once configured, the "🔍 Search" button uses the official RepeaterBook
export API and filters by distance from your location.

### 3. (currently unavailable) hearham.com
hearham.com was added as a free fallback. As of this build their API
returns HTTP 403 to our requests, so it is currently non-functional.

### Why no scraping?
RepeaterBook's policy explicitly forbids secondary API use, bulk
extraction, or building another directory from their data. We respect
that. CHIRP is a blessed partner with their own approval — when you
export from CHIRP, that's CHIRP's authorized data delivered through you,
your file, your own software. Perfectly clean.
"""),

    ("TX Macros (F1–F8)", "Digital Modes",
     """# TX Macros — F1 through F8

## Overview
The Digital tab has a row of eight macro buttons (F1–F8) that let
you send pre-written messages with a single click or keypress.
Macros are useful for contest exchanges, standard calling sequences,
and any repetitive text.

## Sending a Macro
Click any F-button, or press the matching function key while the
Digital tab is active. The macro text is expanded and sent
immediately via the active TX bridge (Fldigi or JS8Call).

## Editing Macros
Right-click any macro button to open the edit dialog.
  Label — short name shown on the button
  Text  — message to send

## Variable Substitution
The following variables are expanded at send time:
  {mycall}    — your callsign (respects Guest Operator mode)
  {theircall} — last worked/decoded station
  {freq}      — current VFO frequency in MHz
  {mode}      — current operating mode
  {serial}    — QSO serial number (auto-incremented)
  {name}      — operator name from callsign lookup

## Default Macros
  F1: CQ — CQ CQ CQ DE {mycall} {mycall} K
  F2: Exch — {mycall} 599 001
  F3: TU — TU {mycall} K
  F4: QSL — QSL TU 73 DE {mycall} SK
  F5: AGN? — AGN? {theircall} DE {mycall}
  F6: QRZ? — QRZ? DE {mycall}
  F7: 73 — 73 DE {mycall} SK
  F8: (empty — fill with your own text)

Macros are saved in config and persist across sessions.
"""),

    ("Guest Operator Mode", "Station Setup",
     """# Guest Operator Mode

## What It Does
Guest Operator mode lets a visitor or student transmit under
their own callsign from your station. TX remains enabled.
All transmissions automatically use the guest's callsign,
satisfying FCC §97.119 station identification requirements.

## How to Activate
1. Go to Operate → Guest Operator… (or press Ctrl+G)
2. Enter the guest's callsign
3. Check "Operating under a control operator" if the station
   licensee is present and supervising
4. Click Start / Update

A blue banner appears at the top of the window:
  GUEST OPERATOR: [CALLSIGN] operating [station]

## What Changes in Guest Mode
  • All TX modes (FT8/FT4/WSPR, Fldigi, Winlink, APRS beacon,
    PSKReporter submissions) use the guest callsign
  • QSO log entries record the guest's callsign as the operator
  • Macro {mycall} expands to the guest callsign
  • DX cluster spot matching uses the guest callsign

## Ending a Guest Session
Operate → Guest Operator → End Guest Session, or close the dialog.
The blue banner disappears and TX returns to the station callsign.

## Demo Mode vs Guest Mode
Demo Mode (Operate → Demo Mode) disables all TX at the AppState
level — no RF is emitted regardless of buttons pressed. Use it
for classroom demonstrations where the rig must not transmit.
Guest Mode keeps TX enabled but changes whose callsign is used.
These modes are independent and can be combined.
"""),

    ("Signal Identification", "SDR",
     """# Signal Identification

## Overview
Squelch can identify unknown signals on the spectrum by comparing
their frequency and bandwidth against the Artemis signal database
(a crowd-sourced reference of ~500 known signal types).

## How to Use
1. Open the SDR tab
2. Right-click on a signal in the spectrum or waterfall
3. Select "Identify Signal at X.XXX MHz"
4. The Signal ID panel opens on the right side of the waterfall
   showing the best matches with:
     • Signal name and category (Amateur / Aviation / Military /
       Marine / Utility / Broadcast / Satellite)
     • Confidence bar (green ≥ 70%, yellow 40–70%, red < 40%)
     • Modulation type and bandwidth
     • Link to SigID Wiki for more details

## Annotating the Waterfall
From the Signal ID panel, click "Annotate" to paint a coloured
region on the spectrum at the matched frequency and bandwidth.
Colour coding matches category (green = amateur, red = military,
blue = aviation, etc.). Clear annotations via right-click →
Clear annotation / Clear all annotations.

## Bookmarks
Click "Bookmark" in the Signal ID panel to save the identification
to a local log (assets/signal_bookmarks.json). The bookmark log
shows at the bottom of the Signal ID panel with timestamp,
frequency, name, and modulation.

## Tips
  • Select a larger frequency region for wider signals (data links,
    FM broadcasts) before right-clicking
  • A 10–15 kHz BW selection works well for most narrowband modes
  • Confidence below 40% means several signals share that bandwidth;
    check the SigID Wiki link for the top match
  • The Artemis DB lookup is local and offline — no network call
"""),

    ("APRS Anomaly Detection", "Digital Modes",
     """# APRS Anomaly Detection

## Overview
Squelch analyses the live APRS stream and flags packets that
exhibit unusual or potentially significant behaviour. Alerts
appear in the status bar and are logged for later review.

## Detection Rules
  A1 — Rapid position jump: a station moves > 100 km in < 5 min.
       Could be a mis-keyed position, balloon, or spoofed packet.
  A2 — Unknown symbol code: packet uses an APRS symbol not in the
       standard table. May indicate a custom or non-standard client.
  A3 — Repeated identical packet: the same packet received 3+
       times within 10 minutes. Could be a loop, stuck digi, or TX
       equipment fault.
  A4 — High message rate: a station sends > 10 messages in
       2 minutes. May indicate automation, a looping script, or a
       malfunctioning device.
  A5 — Unrecognised packet type: packet header does not match any
       known APRS packet type (position, weather, message, object,
       status, telemetry, etc.).

## Status Bar Alerts
When a rule fires, the status bar briefly shows:
  ⚠ APRS [A1] W4ABC — rapid position jump (450 km in 2 min)

## Reviewing Anomalies
All anomaly events are written to the Squelch activity log.
Open Help → Network Activity to see recent events with timestamps.
"""),

    ("RF Lab / Education Mode", "SDR",
     """# RF Lab / Education Mode

## What It Is
RF Lab mode reconfigures the interface for SDR-only use —
ideal for students, instructors, and RF professionals who do
not need ham radio rig control or CAT. A ham radio licence
is not required in this mode.

TX capability for USRP and HackRF remains available via the
SDR tab's transmit controls.

## Enabling RF Lab Mode
  Option 1 — First-run wizard:
    On first launch, select "RF Lab / Education" from the
    Usage mode dropdown. Callsign and radio fields are
    disabled; only location is needed.

  Option 2 — After initial setup:
    View → RF Lab / Education Mode (checkable menu item)

The mode choice is saved across restarts. Toggle at any time.

## What Changes
In RF Lab mode, ham-specific tabs are hidden:
  Hidden: Rig Control, Modes, Log, Digital, Winlink, Local RF
  Visible: SDR, RF Lab, Band Conditions, Map, Help

To restore all tabs: View → RF Lab / Education Mode
(uncheck) to return to full Ham Radio layout.

## Emergency Monitor (RF Lab tab)
The RF Lab tab provides a frequency watchlist with 21
pre-loaded emergency and education frequencies:

  NOAA Weather Radio (7 channels: 162.400–162.550 MHz)
  Aviation:
    121.500 MHz — International distress / guard
    243.000 MHz — Military UHF guard
    122.750 MHz — Air-to-air (CTAF)
  Marine:
    156.800 MHz — Channel 16 (distress and calling)
    156.300 MHz — Channel 6 (intership safety)
    161.975 MHz — AIS channel A
    162.025 MHz — AIS channel B
  EMS / Public Safety:
    155.340 MHz — EMS simplex interoperability
    155.475 MHz — Fire dispatch (common, varies by region)
    460.525 MHz — UHF EMS simplex
  Space:
    145.800 MHz — ISS voice downlink
    145.825 MHz — ISS APRS / packet downlink
  FM Broadcast reference:
    88.0 MHz and 108.0 MHz (band edges)

## Click-to-Tune
Click the "Tune →" button on any frequency row to:
  1. Send that frequency to the SDR tab
  2. Automatically switch to the SDR tab
The SDR tab then shows the spectrum and waterfall at that
frequency (requires a connected SDR device).

## Adding Custom Frequencies
  RF Lab tab toolbar → + Add Custom
  Enter frequency (MHz), name, category, and description.
  Custom frequencies appear at the bottom of the list and
  survive restarts (saved in profile state).

  To remove a custom entry: select it → click Remove.
  Built-in frequencies cannot be removed.

## Filtering
  Category filter: show only Weather / Aviation / Marine /
    EMS / Space / Broadcast / Custom entries.
  Search box: filter by name prefix or frequency string.

## TX in RF Lab Mode
Transmitting is NOT available in RF Lab mode for traditional
rigs (no CAT connection). However, SDR devices with TX
capability (USRP B200/B210, HackRF One) can transmit via:
  SDR tab → TX controls (when hardware is detected)
This allows experiment and educational TX under appropriate
regulatory authorisation.

## Saving a Spectrum Screenshot
The SDR tab toolbar includes a 📸 button (far right of toolbar).
Clicking it grabs the entire visible SDR tab — spectrum plot,
waterfall, and controls — and saves a timestamped PNG:

  Filename: squelch_sdr_YYYYMMDD_HHmmss.png
  Saved to: Desktop (falls back to Downloads if Desktop is absent)
  Confirmation: "Screenshot saved: <path>" in the status bar

Use this to capture interesting signals for classroom handouts,
incident documentation, or offline analysis.
"""),

    ("Manual QSO Logging", "Logging",
     """# Manual QSO Logging

## Opening the Entry Form
Log tab toolbar → "+ Manual Entry"  (or Ctrl+N)

## Callsign Lookup
When you tab out of the Callsign field, Squelch automatically
looks up the callsign via QRZ XML API (subscription) or HamQTH
(free). If credentials are set in Settings → APIs, the lookup:
  • Fills the Name field (if empty)
  • Fills the Their Grid field (if empty)
  • Shows a "Looking up…" status while the request is in flight

To set up callsign lookup:
  QRZ: Settings → APIs → QRZ.com → enter username + password
       (XML data requires a QRZ subscription)
  HamQTH: Settings → APIs → HamQTH → enter callsign + password
           (free, no subscription needed)
Both services are tried; QRZ is primary, HamQTH is the fallback.

## Distance & Bearing (Path: label)
When a grid square is present (typed or auto-filled from lookup),
the Path: label shows:
  e.g.  5 571 km  ·  287°

This uses your station location (Settings → Station → Location)
and the worked station's Maidenhead grid square. The distance
also appears in the Dist km column of the QSO table.

## DXCC Awards Table
Log tab → Awards Progress → "DX Needed…" opens a searchable
table of all 340 DXCC entities showing:
  ✓ Confirmed — worked and LoTW-confirmed
  ✓ Worked    — logged but not yet confirmed
  — Needed    — never worked

Filter by entity name, prefix, or continent. Toggle "Show needed
only" to see your target list.
"""),

    ("Log Upload Services", "Reference",
     """# Log Upload Services

Squelch supports uploading your QSO log to five services.
All credentials are stored in the OS keyring (never in
config files). Set up credentials in Settings → APIs.

## LoTW — Logbook of the World (ARRL)
The gold standard for electronic QSL confirmation.
Confirmations count toward ARRL awards (DXCC, WAS, etc.).

Setup:
  1. Install TQSL from tqsl.arrl.org
  2. Apply for a LoTW certificate (may take a few days)
  3. Settings → APIs → LoTW: enter callsign and password
  4. Log tab → Upload LoTW queue

## QRZ Logbook
Uploads pending QSOs to your QRZ.com online logbook.
Requires a QRZ Logbook API key (free — no subscription).

Setup:
  1. qrz.com → Logbook → Settings → Enable API → copy key
  2. Settings → APIs → QRZ.com → Logbook API Key
  3. Log tab → Upload QRZ queue

## ClubLog
Popular DX logging site; used by many DXpeditions.
Provides callsign lookup for rare entities.

Setup:
  1. Create account at clublog.org
  2. Settings → APIs → ClubLog: email and password
  3. Log tab → Upload ClubLog

## eQSL.cc
Electronic QSL cards; popular in Europe and for awards.

Setup:
  1. Create account at eqsl.cc
  2. Settings → APIs → eQSL.cc: username and password
  3. Log tab → Upload eQSL

## HRDLog.net
Online logbook with real-time cluster and statistics.

Setup:
  1. Create account at hrdlog.net
  2. hrdlog.net → Settings → API Key
  3. Settings → APIs → HRDLog.net: callsign and API key
  4. Log tab → Upload HRDLog

## Automatic Upload
  Settings → APIs → LoTW → Auto-upload QSOs to LoTW:
  When enabled, each logged QSO is queued automatically.
  Other services: manual upload only (Log tab buttons).
"""),
]

# Build search index
_SEARCH_INDEX = {}
for title, cat, content in HELP_ARTICLES:
    key = f"{cat}/{title}"
    words = (title + " " + cat + " " +
             content).lower().split()
    _SEARCH_INDEX[key] = words


class HelpTab(SquelchPanel, QWidget):
    panel_id    = "help"
    panel_title = "Help"

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
        _t = _ht_get_theme(self.cfg.get("ui.theme", "Dark"))
        w   = QWidget()
        w.setStyleSheet(f"background:{_t.bg_primary};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)

        # Search
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍 Search help…")
        self._search.setStyleSheet(
            "background:#141414;"
            "border:1px solid #1a1a1a;border-radius:3px;"
            "padding:4px 8px;")
        self._search.textChanged.connect(self._do_search)
        lay.addWidget(self._search)

        # Article list
        self._list = QListWidget()
        self._list.setStyleSheet(
            "QListWidget{background:#0a0a0a;"
            "border:none;}"
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
            "background:#0d0d0d;"
            "font-family:'Segoe UI',sans-serif;"
            "border:none;padding:16px;line-height:1.5;")
        lay.addWidget(self._content, 1)

        # Show welcome on first open
        self._show_welcome()
        return w

    def _populate_list(self, articles):
        self._list.clear()
        # Sort by category so each section header appears exactly once
        sorted_arts = sorted(articles, key=lambda a: (a[1], a[0]))
        current_cat = None
        for title, cat, _ in sorted_arts:
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

    @staticmethod
    def _flush_pre(html: list, pre_lines: list) -> None:
        html.append("<pre>" + "\n".join(pre_lines) + "</pre>")
        pre_lines.clear()

    def _render_content_lines(self, lines: list, html: list) -> None:
        import re
        in_pre = False
        pre_lines: list = []
        for line in lines:
            if line.startswith("## "):
                if in_pre:
                    self._flush_pre(html, pre_lines); in_pre = False
                html.append(f"<h2>{line[3:]}</h2>")
            elif line.startswith("# "):
                html.append(f"<h1>{line[2:]}</h1>")
            elif line.startswith("  "):
                in_pre = True
                pre_lines.append(line)
            else:
                if in_pre:
                    self._flush_pre(html, pre_lines); in_pre = False
                if line.strip():
                    line = re.sub(r'`([^`]+)`', r'<code>\1</code>', line)
                    html.append(f"<p>{line}</p>")
                else:
                    html.append("<br>")
        if in_pre:
            self._flush_pre(html, pre_lines)

    def _render_content(self, title, cat, content) -> str:
        html = [
            "<style>"
            "body{font-family:'Segoe UI',sans-serif;line-height:1.6;}"
            "h1{color:#3fbe6f;margin-bottom:4px;}"
            "h2{margin-top:16px;}"
            "code{background:#141414;color:#44aaff;"
            "font-family:'Courier New';padding:1px 4px;}"
            "pre{background:#141414;font-family:'Courier New';"
            "padding:10px;border-left:3px solid #3fbe6f;}"
            "p{margin:4px 0;}"
            "</style>"
            f"<p style=''>{cat}</p>"
        ]
        self._render_content_lines(content.strip().splitlines(), html)
        return "\n".join(html)

    def _show_welcome(self):
        self._content.setHtml("""
<style>
body{font-family:'Segoe UI';
     line-height:1.6;}
h1{color:#3fbe6f;}
h2{margin-top:16px;}
.cat{color:#3fbe6f;}
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
<p style=''>
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
            # Substring match so "ic" finds "IC-7100", "ic-7300", etc.
            # A query word scores if it appears anywhere in any indexed token,
            # with a bonus for matching the title.
            title_l = title.lower()
            score = 0
            for w in words:
                if any(w in tok for tok in idx):
                    score += 1
                if w in title_l:
                    score += 2   # title hits rank higher
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