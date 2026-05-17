# Squelch — Roadmap

## Version Scheme

```
0.6.x  Alpha     — crashes possible, core features building ✅
0.7.x  Alpha     — app stable, digital tabs filling in ✅
0.8.x  Alpha     — Winlink + Help complete, IC-7100 pending test
0.9.x  Beta      — IC-7100 verified, FT8 end-to-end working
0.9.x  RC        — feature complete, polish and testing
1.0.0  Release   — public release, signed installer
```

---

## Release Targets

### v0.7.0 — Digital Monitor + Local RF ✅ COMPLETE
- P25 / DMR / NXDN / YSF / D-STAR decode (DSD+ / OP25)
- RFDF foxhunt mode with bearing display
- Signal type → decoder routing from SDR tab
- RadioReference Premium API
- RepeaterBook nearest repeater search
- APRS map + beacon + messaging
- SOTA / POTA APIs
- GPS / MGRS / What3Words location input
- Auto-tune rig from RadioReference data
- Radio memory programming (CHIRP integration)
- ADS-B live aircraft on Local RF map
- Embedded map (Leaflet via QtWebEngine)

### v0.8.0 — Winlink + Help system ✅ COMPLETE
- VARA HF + FM TCP socket control
- Auto-launch VARA in background
- ARES EmComm template library (ICS-213, ICS-214, Radiogram)
- Winlink Wednesday net templates
- RMS gateway selection by band/distance
- Pat (open source Winlink client) integration
- ARDOP fallback (Linux/cross-platform)
- Floating searchable help window
- Radio setup guides for all supported rigs
- Keyboard shortcuts reference
- Legal / ethics documentation
- EmComm / ARES operator guide
- Instructor lab guide + exercises
- SoapySDR setup guide (all hardware)

### v0.8.1 — Map System (next)
- Embedded Leaflet map (QWebEngineView)
- QSO log map — great circle paths between stations
- Gray line terminator overlay (day/night boundary)
  - Computed from solar position at current UTC time
  - Updates every 60 seconds
  - Shows propagation sweet spots (near terminator)
- APRS stations on map
- ADS-B aircraft overlay (from dump1090 JSON feed)
- Repeater locations from Local RF tab
- Station location marker with grid square overlay
- Click any point to see what is at that location

### v0.9.0 — UI + Settings + Polish (Release Candidate)
- **Dockable UI panels** (QDockWidget system)
  - Drag any panel to any edge
  - Float panels as separate windows
  - Resize all panels independently
  - Layout saved per tab per profile
  - Reset to default option
- Full in-app settings editor
- LoTW upload via TQSL
- QRZ logbook sync
- ClubLog / eQSL upload
- License class privilege overlay (Tech/General/Extra)
- EchoLink scaffold (no-hardware radio option)
- Spot button (report to DX cluster)
- Operator callsign separate from station callsign
- ITU Region 1/2/3 frequency plan selector
- Time-based band recommendations
- Update checker (GitHub releases)
- Session statistics summary
- ADIF sync with WSJT-X log file
- Inno Setup Windows installer

### v0.9.x — Linux port
- bootstrap.sh
- ALSA loopback (VB-Cable replacement)
- OP25 native Linux
- VARA under Wine + ARDOP fallback
- RTL-SDR native (no Zadig)
- SoapySDR via apt
- .deb packaging
- .desktop application menu entry
- DragonOS detection and customization
- Raspberry Pi OS arm64 support

### v1.0.0 — Public Release
- All planned tabs functional
- Signed installer (SignPath Foundation — free for OSS)
- Submitted to Microsoft SmartScreen
- Full security audit
- Automated Bandit in GitHub Actions
- pip-audit dependency scanning
- Complete documentation
- GitHub Releases with signed artifacts
- Announce on amateur radio forums

---

## Known Bugs

| # | Description | Status | Fixed |
|---|-------------|--------|-------|
| 1 | focusOutEvent crash on edit fields | Fixed | v0.4 |
| 2 | maidenhead.toLoc AttributeError | Fixed | v0.4 |
| 3 | QActionGroup wrong import | Fixed | v0.5 |
| 4 | Optional NameError on Python 3.13 | Fixed | v0.6 |
| 5 | str\|None TypeError on Python 3.13 | Fixed | v0.6 |
| 6 | ZoneInfo("localtime") fails Windows | Fixed | v0.6 |
| 7 | ZIP code not resolving to Maidenhead | Fixed | v0.6 |
| 8 | SDR tab blank without SoapySDR | Fixed | v0.6 |
| 9 | CMD window opening on launch | Fixed | v0.6 |
| 10 | LaunchBar import missing modes_tab | Fixed | v0.6 |
| 11 | PyQt6 undetected by installer | Fixed | v0.6 |

---

## Proposed / Community Requested

- Frequency hopping follow (plugin candidate — high CPU)
- D-STAR panel (IC-7100/IC-705/IC-9700)
- Brandmeister DMR network integration
- Contest logging (Cabrillo export)
- DX cluster telnet connection
- Satellite tracking (N2YO API)
- FreeDV / Codec2 digital voice
- Meteor scatter (MSK144)
- ACARS / AIS / POCSAG via multimon-ng
- EchoLink rig option (no hardware needed)
- What3Words location input
- FT8 native decode (no WSJT-X needed) — v3.0 target

## Deliberately Deferred

| Feature | Reason |
|---------|--------|
| GNU Radio integration | Linux-only, complex, covered by SoapySDR |
| TETRA decode | Mostly encrypted in US |
| IOTA database | Low priority, community contribution welcome |
| SPIKE software integration | Proprietary, no API |
| macOS port | Low demand, no test hardware |
| FreeBSD port | Low demand |

---

## Security Roadmap

See SECURITY.md for full details.

```
v0.6 (done):
  defusedxml for XML parsing
  shell=False all subprocess calls
  Input validation core/validator.py
  OS keyring credential storage
  Bandit scan — 0 high, 0 medium

v0.9:
  Plugin sandboxing
  Signed installer
  Rate limiting on API calls
  Config file permissions check

v1.0:
  Full security audit
  pip-audit in CI
  Bandit in GitHub Actions
```

---

*Last updated: 2026-05-14*
