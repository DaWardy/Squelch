# Squelch

**Amateur Radio Operations Platform**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Version](https://img.shields.io/badge/version-0.11.41--alpha-orange)](https://github.com/dawardy/squelch/releases)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)

Squelch is a unified amateur radio operations platform for Windows
and Linux. It brings together rig control, digital modes, SDR,
logging, propagation data, and emergency communications tools
into a single application.

> **Alpha software.** Expect bugs. Report them at
> [github.com/dawardy/squelch/issues](https://github.com/dawardy/squelch/issues)

---

## What Works Now (v0.11.41-alpha)

| Feature | Status |
|---------|--------|
| IC-7100 CAT rig control | Built |
| FT8/FT4/WSPR decode list (via WSJT-X) | Built |
| QSO logging with ADIF export | Built |
| Band conditions (NOAA solar data) | Built |
| SDR waterfall (requires SoapySDR) | Built |
| Signal identification (Artemis database) | Built |
| ADS-B aircraft tracking (requires dump1090-fa) | Built |
| Themes: Dark / Light / High Contrast / Night | Built |
| Multi-operator profiles | Built |
| Credential storage (OS keyring) | Built |

## Coming Soon

| Feature | Target |
|---------|--------|
| Digital Monitor (P25/DMR/NXDN) | v0.7 |
| Local RF (RadioReference + APRS) | v0.7 |
| Winlink / VARA | v0.8 |
| Help system | v0.8 |
| Dockable UI panels | v0.9 |
| Linux port | v0.9 |
| **Public release** | **v1.0** |

---

## Requirements

**System:** Windows 10/11 or Linux (Ubuntu 22.04+, DragonOS)
**Python:** 3.11 or newer (3.12 recommended — download at python.org)
**RAM:** 4GB minimum, 8GB recommended

**Required:**
- Hamlib — rig CAT control
  github.com/Hamlib/Hamlib/releases

**Optional (enables specific tabs):**
- WSJT-X — FT8/FT4/WSPR — wsjt.sourceforge.io/wsjtx.html
- Fldigi — PSK31/RTTY/CW — sourceforge.net/projects/fldigi
- VARA HF/FM — Winlink — rosmodem.wordpress.com
- Pat — Winlink client — github.com/la5nta/pat/releases
- dump1090-fa — ADS-B — github.com/flightaware/dump1090
- SoapySDR — SDR hardware (see SDR Setup below)
- CHIRP — Radio programming — chirpmyradio.com
- VB-Cable — Virtual audio — vb-audio.com/Cable

---

## Installation

### Step 1 — Add AV exclusion FIRST (Windows)

Antivirus will flag Python package installation as suspicious.
Add your Squelch folder to exceptions before doing anything else.

```
NETGEAR Armor:    Armor app → Settings → Exceptions → Add folder
Windows Defender: Security → Exclusions → Add folder
Bitdefender:      Protection → Exceptions → Add folder
```

### Step 2 — Install Python 3.12

Download from python.org/downloads
Check "Add Python to PATH" during installation.

### Step 3 — Run the installer

```
python installer.py
```

The installer creates a virtual environment, installs
dependencies, checks for external software, and creates
launch scripts. Run it again any time to check your setup.

```
python installer.py --check     # check only, no install
python installer.py --cache     # download packages for offline use
python installer.py --offline   # install from cached packages
```

### Step 4 — Launch

```
run_squelch.bat          # Normal launch (no console window)
run_squelch_debug.bat    # With console for troubleshooting
run_squelch_guest.bat    # Guest operator mode
```

---

## Hardware Setup

### IC-7100

**CP210x driver:** silabs.com/developers/usb-to-uart-bridge-vcp-drivers

**IC-7100 menu settings:**
```
Menu 066 (CI-V Baud Rate):   19200
Menu 067 (CI-V Address):     94h (default)
Menu 071 (CI-V Transceive):  ON
Menu 072 (CI-V USB Baud):    19200
Menu 073 (CI-V USB Echo):    OFF
```

**For FT8/FT4 digital modes:**
```
Menu 040 (DATA OFF MOD): USB
Menu 035 (Connector):    1: USB
Set rig mode to USB-D (not USB)
```

**In Squelch:**
```
Rig tab → Model: ICOM IC-7100
Rig tab → Port: COMx (CP210x UART Bridge)
Rig tab → Baud: 19200 → Connect
```

### SignaLink USB

```
1. Download jumper config for your rig:
   tigertronics.com/sl_wiretable.htm
2. Install jumpers, connect to rig accessory port
3. Connect to PC via USB
4. In WSJT-X: Input/Output → USB Audio CODEC
5. PTT Method: RTS
6. Adjust TX knob for ~25-30W, keep ALC low
```

### Explorer QRZ-1

```
Programming cable: Kenwood K1 type
CHIRP driver: TYT TH-UV88
VOX: ON, level 2-3
CTCSS: use RT Systems RPS-QRZ1 (CHIRP may not work for CTCSS)
```

---

## SDR Setup

Not required if using IC-7100 USB audio — the Rig tab
spectrum works without SoapySDR.

### Windows — all hardware

1. Install PothosSDR bundle (includes SoapySDR + all drivers):
   downloads.myriadrf.org/builds/PothosSDR/
   Run as Administrator, reboot.

2. Install Python binding:
   ```
   pip install soapysdr
   ```

### RTL-SDR on Windows — extra step

RTL-SDR ships with a driver that does not work with SoapySDR.
Replace it with Zadig (zadig.akeo.ie):
```
Options → List All Devices
Select: Bulk-In, Interface (Interface 0)
Driver: WinUSB → Replace Driver
```
After this the dongle no longer works as a TV receiver.

**Recommended hardware:** RTL-SDR Blog V3 (~$30, rtl-sdr.com)

### SDRplay RSP series

```
1. SDRplay API: sdrplay.com/softwarehome → install + reboot
2. SoapySDRPlay: github.com/pothosware/SoapySDRPlay/releases
3. pip install soapysdr
```

### HackRF One

Included in PothosSDR. Supports TX — ensure appropriate
license before transmitting.

### USRP B200/B210

```
UHD installer: ettus.com/all-ettus-software
Select "Add to PATH" during install, reboot.
B210 supports full duplex (simultaneous RX + TX).
```

### Linux / DragonOS

```bash
sudo apt install soapysdr-tools python3-soapysdr

# RTL-SDR
sudo apt install soapyrtlsdr rtl-sdr
sudo cp /lib/udev/rules.d/rtl-sdr.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules

# HackRF
sudo apt install soapyhackrf hackrf

# SDRplay (download .run from sdrplay.com first)
sudo ./SDRplay_RSP_API-Linux-x.xx.run && sudo apt install soapysdrplay3

# USRP
sudo apt install uhd-host python3-uhd soapyuhd && sudo uhd_images_downloader

# LimeSDR
sudo apt install soapylimesuite

# BladeRF
sudo apt install soapybladerf
```

DragonOS has most packages pre-installed. Run installer.py
to verify what is detected.

**Verify:** `SoapySDRUtil --find` should list your device.

---

## ADS-B Aircraft Tracking

Squelch integrates with dump1090-fa for live aircraft
tracking. Your station location appears on the map
automatically.

```
1. Install dump1090-fa:
   Windows: github.com/flightaware/dump1090/releases
   Linux:   sudo apt install dump1090-fa

2. Connect RTL-SDR dongle (1090 MHz works on any whip antenna)

3. In Squelch:
   SDR tab → launch dump1090-fa → click "Open ADS-B Map"
   Your station marker is placed on the map automatically.
```

No FlightAware account required. Feeding FlightAware is optional.

---

## Digital Modes (FT8/FT4/WSPR)

Squelch works alongside WSJT-X — not a replacement.
WSJT-X handles the waterfall and decode engine.
Squelch handles logging, callsign lookup, and operations.

```
1. Install WSJT-X: wsjt.sourceforge.io/wsjtx.html
2. Squelch Modes tab → select FT8 → WSJT-X auto-launches
3. Pick your frequency on the WSJT-X waterfall
4. Decodes appear in both applications
5. Squelch logs QSOs automatically with QRZ lookup
```

**Audio routing (IC-7100 + VB-Cable):**
```
Install VB-Cable: vb-audio.com/Cable

WSJT-X Settings → Audio:
  Input:  CABLE Output (VB-Audio Virtual Cable)
  Output: CABLE Input (VB-Audio Virtual Cable)
```

---

## Offline Installation

```bash
# On internet-connected machine:
python installer.py --cache

# Copy entire Squelch folder to offline machine, then:
python installer.py --offline
```

Cached packages stored in `offline_packages/` (gitignored).

---

## Supported Hardware

**Transceivers (CAT):** IC-705, IC-7100, IC-7300, IC-7610,
IC-9700, FT-817/818, FT-891, FT-991A, FT-DX10, TS-590S,
TS-890S, TS-2000, K3/K3S, K4, KX3, Xiegu G90/X6100

**Audio interfaces:** SignaLink USB, RigBlaster Advantage,
Generic USB audio (VOX), Baofeng UV-5R/UV-82, Explorer QRZ-1

**SDR:** RTL-SDR, HackRF, USRP B200/B210, SDRplay RSP series,
Airspy, LimeSDR, BladeRF, PlutoSDR

---

## License

GNU General Public License v3.0 or later.
Copyright (C) 2026 github.com/dawardy/squelch

See LICENSE, NOTICE (attributions), SECURITY.md,
ROADMAP.md, CHANGELOG.md, CONTRIBUTING.md.
