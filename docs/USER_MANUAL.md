# Squelch User Manual
## Amateur Radio Operations Platform v0.9.0-alpha

---

## Quick Start

### 1. Install Python
Download Python 3.12 from [python.org](https://www.python.org/downloads/)  
✓ Check "Add Python to PATH" during installation

### 2. Install Squelch
```
Extract Squelch_v0.9.0-alpha.zip to any folder
Double-click installer.py
Wait for packages to install (~2 minutes first time)
```

### 3. Launch
```
Double-click run_squelch.bat
```
On first launch, enter your **callsign** and **location** (ZIP code, grid square, or city).

---

## Top Bar

```
[Callsign] [Profile▼] [Grid Square] [UTC Time]  [Rig: ●]
```

- **Callsign** — click to edit; saved to config
- **Profile** — operator profile switcher; click "+" to add
- **Grid Square** — click and type a ZIP code, city, or Maidenhead grid (e.g. `DM79rr`); resolves automatically
- **Clock** — click to toggle UTC/Local time
- **Rig indicator** — green = connected, red = disconnected

---

## Tabs

### 📻 Rig
Controls your transceiver via Hamlib CAT.

**Setup for IC-7100:**
1. Select model: `ICOM IC-7100`
2. Select COM port (the one labeled CP210x in Device Manager)
3. Baud: `19200`
4. Click Connect

See **Help → IC-7100 Setup** for complete menu settings.

### 📡 Modes
FT8, FT4, WSPR, JS8 digital modes via WSJT-X.

1. Select a band (20m, 40m, etc.)
2. Select FT8
3. WSJT-X launches automatically
4. Completed QSOs log automatically

The DX cluster panel at the bottom shows live spots.  
Double-click a spot to tune the rig.

### 📒 Log
QSO log with search, filter, and export.

- **Add QSO** — manual entry with dropdowns
- **Export ADIF** — for standard log exchange
- **Export Cabrillo** — for contest submission
- **Export CSV** — for spreadsheet import
- **Upload LoTW** — sends to ARRL Logbook of the World

### ☀️ Band Conditions
Live solar data from NOAA:
- **SFI** — Solar Flux Index (>120 = good HF)
- **K-index** — Geomagnetic activity (0 = best)
- **Gray line** — shows when you're near the dawn/dusk terminator (best DX propagation)

### 〰 SDR
Software defined radio waterfall and spectrum.  
Requires SoapySDR and a compatible SDR device.  
See **Help → SDR Setup**.

### 🔊 Digital Monitor
P25, DMR, NXDN, YSF, D-STAR decode.  
Windows: requires DSD+. Linux: requires OP25.

### 📋 Local RF
Nearest repeaters via RepeaterBook (free).

- Search by distance and mode
- Double-click to tune rig
- Export to CHIRP CSV for radio programming
- **APRS-IS** panel: connect to receive APRS stations

### 🗺 Map
Embedded map showing:
- Your station location with grid square
- QSO paths (great circle lines)
- Gray line terminator
- ADS-B aircraft (requires dump1090-fa)
- APRS stations

Requires PyQtWebEngine (not available on Python 3.14).

### ✉ Winlink
Email over radio via VARA HF/FM modem.

1. Launch VARA from the launch bar
2. Click Connect HF or Connect FM
3. Compose a message or load a template
4. Check the Gateway tab for nearby RMS gateways

EmComm templates: ICS-213, ICS-214, Radiogram,  
Winlink Wednesday check-in, Welfare message.

### ❓ Help
Searchable help articles. Press **F1** from anywhere.

---

## Settings

**File → Settings** (Ctrl+,) opens the full settings editor:

| Tab | Contents |
|-----|----------|
| Station | Callsign, grid, license class, ITU region |
| Audio | Input/output devices for digital modes |
| Digital Modes | WSJT-X port, CQ timeout, PTT timeout |
| APIs | QRZ, HamQTH, LoTW, ClubLog, RadioReference |
| Appearance | Theme, font size, clock format |
| Advanced | Log level, API timeout, gray line interval |

**File → Paths & Executables** — set paths to WSJT-X, VARA, Pat, DSD+, TQSL, CHIRP.

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| F1 | Help tab |
| Ctrl+, | Settings |
| Ctrl+L | Log tab |
| Ctrl+M | Modes tab |
| Ctrl+R | Rig tab |
| Ctrl+B | Band Conditions |
| Ctrl+D | Digital Monitor |
| Ctrl+W | Winlink |
| Ctrl+N | New manual QSO (in Log tab) |
| Ctrl+E | Export ADIF (in Log tab) |

---

## Data Location

All your data is saved here — never lost when Squelch updates:

**Windows:**
```
C:\Users\YourName\AppData\Roaming\Squelch\
├── config.json          ← all settings
├── logs\squelch.log     ← debug log
├── logs\squelch_log.db  ← QSO database
└── profiles\            ← operator profiles
```

---

## Troubleshooting

**App won't start:**  
Run `run_squelch_debug.bat` — keeps the window open with error output.  
Check `%APPDATA%\Squelch\logs\squelch.log`.

**COM port not detected:**  
Install pyserial: `venv\Scripts\pip install pyserial`  
Or select the port manually in the Rig tab dropdown.

**LoTW upload fails:**  
1. Check TQSL is installed and path set in Paths & Executables
2. Check LoTW credentials in Settings → APIs
3. Ensure your TQSL certificate is installed

**Map tab shows "Setup Required":**  
PyQtWebEngine is not available on Python 3.14.  
Install Python 3.12 for full map support.

**Band Conditions blank:**  
Squelch fetches from NOAA — requires internet.  
Wait 10–30 seconds after opening the tab.

---

## License

Squelch is free and open source software.  
GNU General Public License v3.  
Source: [github.com/dawardy/squelch](https://github.com/dawardy/squelch)

73 de github.com/dawardy/squelch
