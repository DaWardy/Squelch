# Squelch — Changelog

All notable changes documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]
Changes not yet in a tagged release.

---

## [0.9.0-alpha] — 2026-05-17

### Added
- Settings editor (Ctrl+,) — full in-app settings
  - Station, Audio, Digital Modes, APIs, Appearance, Advanced tabs
  - Passwords stored in OS keyring via Settings → APIs
  - Live apply: theme and font change without restart
- APRS-IS client — connect/disconnect from Local RF tab
  - Geographic filter around station location
  - Receive-only login (passcode -1, safe for all licenses)
  - Station ring buffer (500), deduplication by call-SSID
  - Beacon via APRS-IS with configurable symbol/path/comment
  - Live station count and Connect/Beacon Now buttons
  - Auto-reconnect setting persisted to config
  - APRS stations wired to map tab (updates every 5 seconds)
- APRS passcode calculator (APRSClient.compute_passcode)
- LoTW upload wired into Log tab Upload button
  - ADIF → TQSL sign → LoTW HTTPS submit with progress dialog
  - Graceful error messages for missing TQSL/credentials
- PSKReporter spot submission
  - FT8/FT4 decodes forwarded from WSJT-X automatically
  - Batched every 5 minutes, XML format, HTTPS POST
  - Deduplication per call/mode before submission
  - Enable/disable via Settings → Advanced
- DX cluster live spots panel in Modes tab
  - Band and mode filter dropdowns
  - Double-click spot to tune rig
  - HamAlert API integration (requires API key in Settings)
- Memory channel export (CHIRP CSV format)
  - Save selected repeater to memory channel
  - Export all search results to CHIRP CSV
  - Full CTCSS/DCS/offset/mode mapping
  - Compatible with CHIRP-supported radios
- Winlink gateway list from Winlink API
  - Real-time fetch with distance calculation
  - Fallback message on network failure
- Inno Setup installer script (setup/squelch.iss)
  - Python version check, ADIF file association
  - Desktop/Start Menu/Startup shortcuts
  - setup/README.md with signing and distribution guide
- CONTRIBUTING.md — full contributor guide
- PSKReporter tests (15 tests)
- Memory channel tests (16 tests)
- APRS tests (17 tests)
- LoTW sync tests (9 tests)

### Fixed
- Window title showed v0.8.0-alpha-alpha
- LogDB._open expected Path but received str
- IP geolocation overwriting user location on startup
- LocationSource enum string vs enum mismatch

---

## [0.8.0-alpha] — 2026-05-17

### Added
- Winlink tab — VARA HF/FM TCP socket control, compose, EmComm templates
  - ICS-213, ICS-214, Radiogram, Winlink Wednesday, Welfare message templates
  - Gateway list (Winlink API integration in v0.8.1)
  - Launch bar: VARA HF, VARA FM, Pat, RMS Express
- Help tab — searchable, 11 articles across 7 categories
  - IC-7100 setup with exact menu numbers
  - FT8 operation guide, SignaLink/QRZ-1 setup
  - Gray line propagation, EmComm/ARES guide
  - Keyboard shortcuts reference, propagation quick reference
  - Live search across all articles
- F1 shortcut opens Help tab
- GPL headers on all 75 files

### Fixed
- Band conditions not displaying — polling loop now retries until data arrives
- IP geolocation overwriting user location on every startup
- LocationSource enum string vs enum value mismatch causing silent failures
- location.apply() now serializes source correctly for JSON

---

## [0.7.1-alpha] — 2026-05-16

### Added
- Map tab with embedded Leaflet (requires PyQtWebEngine)
  - Gray line terminator overlay, updates every 60 seconds
  - QSO great circle paths color-coded by mode
  - Station marker with 4-char and 6-char grid overlays
  - ADS-B aircraft from dump1090-fa
  - Repeater markers from Local RF tab
  - Layer toggles: gray line / QSO paths / repeaters / ADS-B / APRS
- Gray line status bar in Band Conditions tab
- Gray line computation engine (pure Python, no dependencies)
- QSO dataclass: lat/lon fields for map plotting
- location.qso_to_map_points() and grid_to_map_point() helpers
- PyQtWebEngine added to requirements (optional — no Python 3.14 wheel)
- Operator profile switcher in top bar
- Font size menu: Small/Normal/Large/X-Large/XX-Large (persisted)
- Tooltip style: 12px minimum, readable by default
- dump1090 receiver.json writer — station marker on ADS-B map

### Fixed
- Config loading from app folder instead of APPDATA
  (--config default was "config.json" not CONFIG_PATH)
- QComboBox NameError — import missing from top-level block
- QAbstractItemView, QApplication, QDialog missing imports
- Callsign not restoring on startup
- ZIP code: _on_grid_edit reverted to minimal stub — fully rewritten
- ClickableLabel showing ZIP before grid resolved
- IP geolocation setting Las Vegas for all ZIPs
- Installer PyQtWebEngine failure — now excluded cleanly
- Installer package retry logic — individual install on bulk failure

---

## [0.7.0-alpha] — 2026-05-15

### Added
- Digital Monitor tab (P25/DMR/NXDN/YSF/D-STAR)
  - DSD+ subprocess manager (Windows)
  - OP25 HTTP API bridge (Linux)
  - Decode log with protocol filter and encrypted indicator
  - Protocol reference panel for education
- Local RF tab — RepeaterBook integration (free, no API key)
  - Nearest repeaters search by distance and mode
  - Double-click to tune rig
  - Open in CHIRP button
- OP25 added to launcher paths
- SDR → Digital IQ routing

### Fixed
- run_squelch.bat: pythonw → start venv\Scripts\python.exe
- install_check.py: pause at end so window stays readable
- CQ guard: blocks CQ if WSJT-X not connected
- CQ timeout: returns to IDLE after 2 cycles without response
- Log manual entry: mode/band dropdowns with RST auto-fill
- Rig dropdown: all models showing, grouped by manufacturer
- Spectrum/waterfall: separate splitter for independent resize
- Location restores on startup from saved config
- Band conditions: placeholder shown while fetching
- SDR tab: layout collapse fixed
- Version: 0.7.0-alpha throughout

---

## [0.7.0-alpha] — 2026-05-14

### Added
- Digital Monitor tab (P25/DMR/NXDN/YSF/D-STAR)
  - DSD+ subprocess manager (Windows)
  - OP25 bridge via HTTP API (Linux)
  - Real-time decode event log with protocol filter
  - Encrypted call detection and indicator
  - Protocol reference panel (educational)
  - Session statistics
  - Audio routing from SDR tab
  - Auto-connect to OP25 if already running
- Local RF tab
  - RepeaterBook.com integration (free, no API key)
  - Nearest repeaters by distance with band/mode/tone
  - Mode filter (FM/DMR/P25/YSF/D-STAR/NXDN)
  - Double-click repeater to tune rig
  - Save to memory (v0.7.1)
  - Open in CHIRP button
  - RadioReference Premium stub
  - APRS stub (v0.7.1)
- OP25 added to launcher and paths dialog
- SDR → Digital IQ routing wired

### Fixed
- run_squelch.bat: pythonw → start python (no silent failures)
- install_check.py closes before readable — pause added
- CQ transmitted without WSJT-X connected — guard added
- CQ timeout — returns to IDLE after 2 cycles if no response
- Log manual entry: mode and band now dropdowns with RST auto-fill
- Rig dropdown: all 26 models showing, grouped by manufacturer
- Spectrum/waterfall: separate splitter for independent resize
- Location --- in status bar: restored from config on startup
- ZIP code not resolving: closure variable bug fixed
- Band conditions tab blank: placeholder shown while fetching
- SDR tab blank: layout collapse fixed
- Version: 0.7.0-alpha throughout

---

## [0.6.0-alpha] — 2026-05-14

### Added
- SDR tab with waterfall, spectrum, IQ recorder/player, scanner
- LaunchBar widget — software launch buttons on every tab
- Signal identification via Artemis database (right-click signal)
- core/launcher.py — auto-detects all external software on startup
- Paths & Executables dialog — browse/test/launch/download for all tools
- Band Conditions tab — NOAA solar data, K/A/SFI, band-by-band conditions
- User profile system — separate config/log per operator
- Credential storage via OS keyring (never in config.json)
- Theme system — Dark / Light / High Contrast / Night
- Plugin scaffold — community addons via plugins/ folder
- Tab show/hide, drag to reorder, lock layout
- UTC/Local time toggle (fixed for Windows)
- Auto-location on first launch via IP geolocation
- dump1090 receiver.json writer — station marker on ADS-B map
- ADS-B map button in SDR tab (links to localhost:8080)
- ADS-B location estimation from aircraft positions
- Explorer QRZ-1, SignaLink USB, RigBlaster, Generic USB Audio presets
- Pat and RMS Express in Winlink paths
- CHIRP and RT Systems in programming paths

### Fixed
- NameError: Optional not defined on Python 3.13 (from __future__ annotations)
- TypeError: str | NoneType on Python 3.13 (forward refs in dataclasses)
- QActionGroup wrong import (QtWidgets → QtGui)
- setHighDpiScaleFactorRoundingPolicy order
- focusOutEvent double-commit crash (callsign/grid editor)
- ZIP code not resolving to Maidenhead grid
- Location label persisting "Searching…" or raw ZIP string
- UTC clock toggle not working on Windows (ZoneInfo Linux-only)
- SDR tab showing blank instead of setup guide
- CMD window opening on launch (subprocess not os.startfile)
- LaunchBar import missing in modes_tab
- pyserial unguarded import crashing on missing dependency
- dx_cluster.py Validator class reference (converted to functions)

### Known Issues
- IC-7100 CAT control not yet field-tested (hardware required)
- Digital Monitor tab — stub (Chunk 7)
- Local RF tab — stub (Chunk 8)
- Winlink tab — stub (Chunk 9)
- Help system — stub (Chunk 10)
- UI dockable panels — planned Chunk 11

---

## [0.5.0-alpha] — 2026-05-07
- Band Conditions tab
- User profiles
- Credential storage (keyring)
- Paths configurator
- Squelch rename from APEX

## [0.4.0-alpha] — 2026-05-06
- APEX rename from SIGLAB
- GPL v3 license
- Theme system scaffold
- Plugin system scaffold
- Window persistence

## [0.3.0-alpha] — 2026-05-05
- Log tab, QSO logging, ADIF export
- Safety system (PTT watchdog, TX timeout)
- DX spot feeds
- QRZ callsign lookup

## [0.2.0-alpha] — 2026-05-04
- Modes tab (FT8/FT4/WSPR auto-sequence)
- WSJT-X UDP bridge

## [0.1.0-alpha] — 2026-05-03
- Initial scaffold
- IC-7100 rig control
- Band plan
