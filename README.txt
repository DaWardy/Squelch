Squelch -- Amateur Radio Operations Platform
github.com/dawardy/squelch
======================================================

Squelch — Amateur Radio Operations Platform
------------------------------------------------------

[](https://github.com/dawardy/squelch)
[](https://www.python.org/downloads/)
[](LICENSE)

A unified amateur radio education tool combining rig control, FT8/FT4/WSPR,
PSKReporter, propagation prediction, SDR waterfall, ADS-B, P25/DMR digital
monitoring, Winlink/VARA, APRS, and RadioReference in one application.

Built for classroom and lab use. Students operate under the instructor's license.
Designed around the ICOM IC-7100 and RTL-SDR as the accessible student baseline,
with full support for USRP B210/B200 mini, SDRplay RSP series, HackRF, and more.

> All download links in this document have been verified to official or
> well-established open source sources only. Do not substitute mirror links.

---

Table of Contents
------------------------------------------------------

1. What Squelch Does
2. Hardware
3. Quick Start
4. Step-by-Step Installation
5. SDR Driver Installation
6. External Program Setup
7. First Launch
8. Configuration
9. Launching Squelch
10. Lab Mode
11. Guest and Student Operators
12. Updating
13. Troubleshooting
14. Legal and Ethics
15. Credits

---

What Squelch Does
------------------------------------------------------

| Tab | What it does |
|-----|-------------|
| Rig Control | IC-7100 CAT via Hamlib — frequency, mode, PTT, preamp, ATT, filter, S-meter |
| Modes | FT8/FT4/WSPR/JS8/PSK31/RTTY/CW/SSTV with full auto-sequence |
| PSKReporter | Live world map of who hears you and who you hear |
| Propagation | NOAA solar data, VOACAP predictions, greyline, band recommendations |
| SDR | Waterfall, scanner, IQ recorder, ADS-B, drone Remote ID, NOAA APT satellite |
| Digital Monitor | P25, DMR, NXDN, YSF, D-STAR decode + RFDF foxhunt mode |
| Radio Reference | Local RF environment browser, auto-tune, GPS-aware |
| Winlink | Email over radio via VARA HF/FM, ARES templates |
| APRS | Position beaconing, messaging, live station map |
| Help | Built-in docs, legal notes, instructor guide |

---

Hardware
------------------------------------------------------

Transceivers
------------------------------------------------------
| Radio | Connection | Notes |
|-------|-----------|-------|
| ICOM IC-7100 | USB (CP210x) | Primary supported rig, GPS + APRS built in |
| Any Hamlib rig | Serial / USB | See hamlib.sourceforge.net for full list |
| Baofeng UV-5R/82 | Audio interface | Digital modes via sound card |

SDR Hardware (all via SoapySDR)
------------------------------------------------------
| Device | Notes |
|--------|-------|
| RTL-SDR (RTL2832U) | $25-35, recommended for students |
| RTL-SDR Blog V3/V4 | Enhanced version, bias tee, better performance |
| USRP B200 / B210 / B200 mini | Professional grade, USB 3.0 required |
| SDRplay RSP1A / RSP2 / RSPduo / RSPdx / RSP2pro | UK company, good value |
| HackRF One | TX capable (with appropriate license) |
| LimeSDR / LimeSDR Mini | Open hardware |
| Airspy R2 / Mini / HF+ | High dynamic range |
| BladeRF (x40/x115/2.0) | TX capable |
| PlutoSDR (ADALM-PLUTO) | Good for experimentation |

Audio
------------------------------------------------------
- VB-Cable required for VARA and Fldigi audio routing
- IC-7100 USB audio used for TX/RX (appears as USB Audio CODEC in Windows)

PC Requirements
------------------------------------------------------
- Windows 10 64-bit or Windows 11
- Python 3.11+
- 8 GB RAM (16 GB recommended with B210 + multiple decoders)
- USB 3.0 for USRP B210 (mandatory)
- Internet for PSKReporter, NOAA, WSPRnet, RadioReference

---

Quick Start
------------------------------------------------------

``
1. Install Python 3.11+     https://www.python.org/downloads/
2. Install Hamlib            https://github.com/Hamlib/Hamlib/releases
3. Install VB-Cable          https://vb-audio.com/Cable/
4. Install CP210x driver     (IC-7100 USB — see Step 3 below)
5. Run bootstrap.bat
6. Double-click run_apex.bat
`

---

Step-by-Step Installation
------------------------------------------------------

Step 1 — Python 3.11+
------------------------------------------------------

Download from https://www.python.org/downloads/

> CRITICAL: During installation, check "Add Python to PATH"
> before clicking Install Now. Without this, nothing will work.

Verify in Command Prompt:
`
python --version
`
Expected: Python 3.11.x or higher.

---

Step 2 — Hamlib (rigctld)
------------------------------------------------------

Hamlib provides rigctld which Squelch uses to talk to the IC-7100.

1. Download from https://github.com/Hamlib/Hamlib/releases
   - Choose the latest hamlib-w64-x.x.x.zip (64-bit Windows)
2. Extract to C:\hamlib
3. Add C:\hamlib\bin to your system PATH:
   - Press Win+S → "Edit the system environment variables"
   - Click Environment Variables
   - Under System variables, select Path → Edit
   - Click New and add C:\hamlib\bin
   - Click OK on all dialogs
4. REBOOT — Windows does not reload PATH in existing windows

Verify after reboot:
`
rigctld --version
`
Expected: rigctld Hamlib 4.x.x

> If rigctld is not recognized after reboot, verify the bin folder
> path is correct and that you edited System variables, not User variables.

---

Step 3 — IC-7100 USB Driver
------------------------------------------------------

The IC-7100 uses a Silicon Labs CP210x USB-to-Serial chip.

Download the CP210x Universal Windows Driver v11.5.0:
https://www.silabs.com/documents/public/software/CP210x_Universal_Windows_Driver.zip

> Use this specific version. The older CP210x VCP Windows drivers
> (v6.7 / v6.7.6) are for Windows XP/7 and cause issues on Windows 10/11.
> Do not use the WinCE or Linux drivers.

1. Extract the zip
2. Right-click silabser.inf → Install
3. Connect IC-7100 via USB
4. Verify in Device Manager: should show Silicon Labs CP210x USB to UART Bridge (COMx)
5. Note the COM port number

---

Step 4 — VB-Cable
------------------------------------------------------

Required for routing audio between Squelch and VARA/Fldigi without a physical cable.

1. Download from https://vb-audio.com/Cable/
2. Right-click the installer → Run as Administrator
3. Reboot when prompted
4. Verify in Windows Sound settings: CABLE Input and CABLE Output should appear

> The free version is sufficient. Do not pay for VB-Audio unless you
> specifically need multiple virtual cables.

---

Step 5 — Run bootstrap.bat
------------------------------------------------------

In the Squelch folder:
`
bootstrap.bat
`

Or double-click it in Explorer.

Bootstrap will:
- Check Python version
- Create venv\ virtual environment
- Install all Python packages (with progress)
- Check for Hamlib, VB-Cable, IC-7100
- Create config.json from the template
- Create run_apex.bat and run_apex_lab.bat

> Missing hardware only generates warnings — Squelch will still launch.
> Tabs requiring missing hardware are grayed out until installed.

> If you see Cache entry deserialization failed warnings during pip install,
> these are harmless. They indicate a corrupted pip cache that is automatically
> bypassed with --no-cache-dir.

---

SDR Driver Installation
------------------------------------------------------

Skip this section if you are only using the IC-7100.

RTL-SDR (any RTL2832U dongle)
------------------------------------------------------

1. Plug in your RTL-SDR
2. Download Zadig from https://zadig.akeo.ie/
   - Zadig is by Pete Batard, a well-known open source developer
3. In Zadig: Options → List All Devices
4. Select Bulk-In, Interface (Interface 0)
5. Select WinUSB as the driver
6. Click Replace Driver
7. Download SoapyRTLSDR from https://github.com/pothosware/SoapyRTLSDR
   - Use the pre-built release for your platform

USRP B210 / B200 mini
------------------------------------------------------

Requires USB 3.0 — will not work reliably on USB 2.0.

1. Download UHD from https://files.ettus.com/manual/page_install.html
2. Run the UHD Windows installer
3. Run uhd_find_devices to verify detection
4. USRP firmware images download automatically on first use (requires internet)
5. SoapyUHD is typically included with the UHD Windows package

SDRplay RSP series (RSP1A, RSP2, RSPduo, RSPdx, RSP2pro)
------------------------------------------------------

1. Download SDRplay API v3 from https://www.sdrplay.com/api/
   - Current version: 3.15
   - Installs as a Windows service — verify it is running after install
2. Download SoapySDRPlay3 from https://github.com/pothosware/SoapySDRPlay3
3. Install SDRplay API BEFORE SoapySDRPlay3

> SDRplay is a UK company. All downloads are from official SDRplay servers
> or the Pothosware GitHub organization.

HackRF One
------------------------------------------------------

1. Download Zadig (see RTL-SDR above)
2. Install WinUSB driver for HackRF
3. Download SoapyHackRF from https://github.com/pothosware/SoapyHackRF

Other devices (LimeSDR, Airspy, BladeRF)
------------------------------------------------------

All are supported via SoapySDR plugins available at:
https://github.com/pothosware

Install the SoapySDR plugin matching your device.

---

External Program Setup
------------------------------------------------------

These programs run alongside Squelch. Squelch controls them automatically
via TCP/socket interfaces. You do not need to configure them manually.

> Do not auto-update these programs without checking DEPENDENCIES.md first.
> Some updates change interfaces that Squelch depends on.

WSJT-X — FT8 / FT4 / WSPR
------------------------------------------------------

https://wsjt.sourceforge.io/wsjtx.html

- Download the Windows installer (not the source archive)
- Install with default settings
- Do not configure audio in WSJT-X — Squelch manages this
- Tested: WSJT-X 2.6.x

JS8Call — JS8 Keyboard Messaging
------------------------------------------------------

https://js8call.com/

- Install with default settings
- Squelch connects via TCP on port 2442
- Tested: JS8Call 2.2.x

Fldigi — PSK31 / RTTY / CW / SSTV
------------------------------------------------------

https://sourceforge.net/projects/fldigi/

- Install with default settings
- Squelch connects via XML-RPC on port 7362
- Tested: Fldigi 4.1.x

VARA HF — Winlink HF
------------------------------------------------------

https://rosmodem.wordpress.com/

- Download VARA HF from the WordPress page
- Install to C:\VARA HF\ (default)
- Free version works but is speed-limited
- Paid license ($69 USD) removes speed limit — recommended for EmComm
- Tested: VARA HF 4.8.x

VARA FM — Winlink VHF/UHF
------------------------------------------------------

https://rosmodem.wordpress.com/

- Download VARA FM from the same page
- Install to C:\VARA FM\ (default)
- Tested: VARA FM 5.0.x

DSD+ — DMR / NXDN / YSF Decode
------------------------------------------------------

https://www.dsdplus.com/

- Download and extract to C:\dsdplus\
- Enter the path in Squelch Settings → Paths
- Tested: DSD+ 1.101

dump1090-fa — ADS-B Aircraft Tracking
------------------------------------------------------

https://github.com/flightaware/dump1090

- FlightAware maintains this open source fork
- Pre-built Windows binaries available in the releases page
- Tested: dump1090-fa 8.x

---

First Launch
------------------------------------------------------

After bootstrap:
`
run_apex.bat
`
or:
`
python main.py
`

On first launch, Squelch prompts for your callsign and grid square.

Find your grid square:
- https://www.levinecentral.com/ham/grid_square.php
- Or enter a ZIP code, city/state, or MGRS coordinate in Settings → Location

---

Configuration
------------------------------------------------------

Settings are stored in config.json. Key settings:

| Setting | Key in config.json | Default |
|---------|-------------------|---------|
| Callsign | callsign | blank |
| Grid square | grid_square | blank |
| Rig COM port | rig.port | AUTO |
| Rig baud rate | rig.baud | 19200 |
| RadioReference key | apis.radioreference_key | blank |
| RadioReference user | apis.radioreference_user | blank |
| QRZ username | apis.qrz_user | blank |

API Keys
------------------------------------------------------

| Service | Where to get | Required for |
|---------|-------------|-------------|
| RadioReference Premium | https://radioreference.com/api | Radio Reference tab |
| QRZ XML | https://xmldata.qrz.com | Callsign lookup |

Leave blank if you do not have them. Tabs show a setup prompt with a link.

> Never commit config.json to git — it contains your callsign and API keys.
> config.json is in .gitignore. Share config.example.json instead.

---

Launching Squelch
------------------------------------------------------

| Method | What it does |
|--------|-------------|
| run_apex.bat | Normal launch |
| run_apex_lab.bat | Launch in lab/classroom mode |
| python main.py | Normal launch from command line |
| python main.py --lab-mode | Lab mode from command line |
| python main.py --debug | Verbose logging to logs/squelch.log |

---

Lab Mode
------------------------------------------------------

Lab mode restricts the UI for classroom use:
- Settings are locked (students cannot change callsign, API keys, COM port)
- Session logging enabled to logs/sessions/
- All transmissions logged with timestamp

Enable lab mode:
- Double-click run_apex_lab.bat
- Or: python main.py --lab-mode
- Or: Menu → Lab → Toggle Lab Mode

Configure lab defaults in config.json under classroom:
`json
"classroom": {
    "lab_mode": false,
    "instructor_callsign": "W4XYZ",
    "session_logging": true,
    "lock_settings": true
}
`

---

Guest and Student Operators
------------------------------------------------------

Under FCC Part 97.105, a licensed amateur (the control operator) may
allow unlicensed persons to operate a station under their supervision.

What this means for the classroom:

- The instructor holding the license is the control operator
- Students may transmit under the control operator's callsign
- The control operator must be present or immediately available
- All transmissions must be identified with the control operator's callsign
- The control operator is legally responsible for all transmissions

In Squelch, students should identify as follows:

When making voice contact: "This is [CALLSIGN], operating under the
supervision of control operator [CALLSIGN]."

For digital modes (FT8, Winlink), Squelch logs the instructor's callsign
on all transmissions automatically when lab mode is enabled.

For Winlink specifically: Each student should note in their message
header or body that they are a student/guest operator under the control
operator's supervision.

> This is a simplified overview. For the full regulatory text, see
> FCC Part 97.105 at https://www.ecfr.gov/current/title-47/part-97

---

Updating
------------------------------------------------------

Squelch itself
------------------------------------------------------
`
git pull
bootstrap.bat
`

Or download a new release ZIP and extract over the existing folder.
Your config.json is not overwritten.

Python packages (generally safe)
------------------------------------------------------
`
pip install -r requirements.txt --upgrade --no-cache-dir
`

External programs — check DEPENDENCIES.md first
------------------------------------------------------

Some external programs (VARA, WSJT-X) occasionally change their TCP
interface between versions. Check DEPENDENCIES.md before updating any
external program. If something breaks after an update, roll back the
program and file an issue on GitHub.

---

Troubleshooting
------------------------------------------------------

"rigctld not recognized" after installing Hamlib
------------------------------------------------------
Hamlib was installed but PATH was not updated yet. Reboot your PC.
If still not recognized after reboot, verify C:\hamlib\bin is in your
system PATH (not user PATH) via Environment Variables.

bootstrap.bat exits immediately / pip errors
------------------------------------------------------
Run from Command Prompt rather than double-clicking so you can read the output:
`
cd C:\path\to\apex
bootstrap.bat
`
If you see Python not found, reinstall Python and check "Add to PATH".

IC-7100 not connecting
------------------------------------------------------
1. Verify USB cable is connected and IC-7100 is on
2. Check Device Manager for CP210x under Ports (COM & LPT)
3. Install CP210x Universal Windows Driver v11.5.0 if not present
4. Try selecting the COM port manually instead of AUTO
5. Verify IC-7100 CI-V baud rate: Menu → Connectors → CI-V → 19200

No audio from IC-7100
------------------------------------------------------
1. Check Windows Sound settings — IC-7100 USB Audio should appear
2. Set as default recording device for rig audio
3. VB-Cable must be installed for VARA/Fldigi routing

SDR not detected
------------------------------------------------------
- RTL-SDR: Re-run Zadig, ensure WinUSB driver is installed
- B210: Run uhd_find_devices`. If empty, reinstall UHD
- RSPduo: Verify SDRplay API service is running (Windows Services)
- Try unplugging and replugging

WSJT-X decode list is empty
------------------------------------------------------
1. Verify IC-7100 mode is USB or PKTUSB
2. Tune to a known FT8 frequency (e.g. 14.074 MHz)
3. Check IC-7100 audio input level in Windows Sound
4. Verify you are within the FT8 window (even/odd minute timing)

---

Legal and Ethics
------------------------------------------------------

Amateur radio transmissions
------------------------------------------------------
- The control operator (licensed amateur) is legally responsible
- Students operate under the control operator's license (Part 97.105)
- No encrypted transmissions on amateur frequencies (Part 97.113)
- Station identification every 10 minutes and at end of contact
- Third-party traffic rules apply (Part 97.115)

Monitoring P25, DMR, NXDN
------------------------------------------------------
- Receiving unencrypted transmissions is generally lawful under federal law
- The Electronic Communications Privacy Act (ECPA) restricts use and
  disclosure of intercepted communications
- Several states have stricter laws — verify your state statutes
- Squelch is for educational monitoring only — receive and observe
- Do not record, retransmit, or act on intercepted communications
- Encrypted traffic must not be decrypted

SDR hardware export
------------------------------------------------------
- The USRP B210 is subject to US Export Administration Regulations (EAR)
- Squelch does not enable transmission via SDR hardware
- SDR hardware is for receive-only operation within Squelch

ADS-B and Remote ID
------------------------------------------------------
- ADS-B reception is legal and unrestricted
- FAA Remote ID monitoring is legal — it is a public broadcast
- Do not use received data to interfere with aircraft or drone operations

---

Credits
------------------------------------------------------

Project: github.com/dawardy/squelch

Open source components:
- Hamlib — LGPL 2.1
- SoapySDR — Boost License
- PyQt6 — GPL v3
- WSJT-X — GPL v3 (K1JT et al.)
- Fldigi — GPL v3 (W1HKJ)
- OP25 — GPL v3 (Osmocom)
- dump1090-fa — GPL v2 (FlightAware)
- NumPy / SciPy — BSD
- folium — MIT
- geopy — MIT
- maidenhead — MIT
- mgrs — MIT

Proprietary components (separate install):
- VARA / VARA HF — EA5HVK, freeware/paid
- DSD+ — freeware

License: MIT — see LICENSE file
