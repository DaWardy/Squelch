# Squelch — Changelog

All notable changes documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]
Changes not yet in a tagged release.

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
