# Squelch Roadmap

## Known Bugs

| # | Description | Status | Fixed in |
|---|-------------|--------|----------|
| 1 | focusOutEvent TypeError on callsign/grid edit | ✅ Fixed | v1.4 |
| 2 | maidenhead.toLoc AttributeError | ✅ Fixed | v1.4 |
| 3 | setHighDpiScaleFactorRoundingPolicy order | ✅ Fixed | v1.4 |
| 4 | QFont::setPointSize <= 0 | ✅ Fixed | v1.4 |
| 5 | Placeholder text saved as callsign | ✅ Fixed | v1.4 |
| 6 | Dropdown boxes truncating text | ✅ Fixed | v1.4 |
| 7 | Power spin arrows overlapping number | ✅ Fixed | v1.4 |
| 8 | Mode buttons instead of dropdown | ✅ Fixed | v1.4 |

## Upcoming Features by Version

### v1.4 (Current)
- Squelch rename from SIGLAB
- GPL v3 license
- Theme system (Dark/Light/High Contrast/Night)
- Tab show/hide in View menu
- UTC + Local time toggle
- Plugin system scaffold
- Window size/position persistence
- Safety system (PTT watchdog, TX timeout)
- Input validation (no crashes on bad input)
- CTY.DAT DXCC lookup
- PSKReporter/RBN/DX Watch/HamAlert spot feeds
- QRZ/HamQTH callsign lookup
- Log tab with awards tracking

### v1.5 (Chunk 4)
- Band Conditions tab (PSKReporter map + propagation)
- NOAA solar data + VOACAP predictions
- Greyline overlay
- WSPRnet band condition display

### v1.6 (Chunk 5)
- Full SDR waterfall tab
- Dynamic RX/TX capability detection
- Networked SDR (WebSDR/KiwiSDR)
- ADS-B live aircraft tracking
- FAA Remote ID drone monitor
- NOAA APT weather satellite
- IQ recorder/player (SigMF)
- Scanner (sweep/channel/band/RR-fed)
- Artemis/SigID signal identification
- SDR→Digital routing pipeline

### v1.7 (Chunk 6)
- Digital Monitor tab (P25/DMR/NXDN/YSF/D-STAR)
- RFDF foxhunt mode
- Signal type identification → decoder routing

### v1.8 (Chunk 7)
- Local RF tab (RadioReference + RepeaterBook)
- APRS integration
- SOTA/POTA API
- GPS/MGRS/What3Words location
- Auto-tune from RR data

### v1.9 (Chunk 8)
- Winlink/VARA tab
- ARES EmComm templates
- Winlink Wednesday net templates
- ARDOP fallback for Linux

### v2.0 (Chunk 9)
- Help window (floating, searchable)
- Instructor guide
- Legal/ethics documentation
- Radio setup guides for all supported rigs
- SECURITY.md

### v2.1 (Chunk 10)
- Full in-app settings editor
- LoTW upload via TQSL
- QRZ logbook sync
- ClubLog/eQSL support
- Lab mode polish
- Session logging and export

### v2.2 (Chunk 11)
- Linux port (bootstrap.sh)
- ALSA loopback (VB-Cable replacement)
- OP25 native on Linux
- VARA under Wine
- .deb packaging for Debian/Ubuntu/DragonOS

## Proposed / Community Requested

- EchoLink rig option (software radio, no hardware needed)
- Frequency hopping follow (plugin candidate)
- D-STAR panel (IC-7100/IC-705/IC-9700)
- Brandmeister DMR network integration
- Contest logging (Cabrillo export)
- DX cluster telnet connection
- Satellite tracking (N2YO API)
- FreeDV/Codec2 digital voice
- Meteor scatter (MSK144)
- ACARS/AIS/POCSAG via multimon-ng

## Deliberately Deferred

| Feature | Reason |
|---------|--------|
| GNU Radio integration | Linux-only, complex, covered by SoapySDR |
| SPIKE software | Proprietary, no API |
| 3dB Labs Scepter | Too expensive for student use case |
| TETRA decode | Mostly encrypted in US deployments |
| IOTA database | Low priority, community contribution welcome |
