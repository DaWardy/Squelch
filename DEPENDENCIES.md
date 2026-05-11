# Squelch — Dependency Version Matrix

Consult this file before updating any external dependency.
All links verified to official sources only.

**Squelch version:** 1.0.0
**Last updated:** Chunk 1
**Test platform:** Windows 11 64-bit, Python 3.13.x

---

## Update Safety Reference

| Component | Safe to update? | Risk if broken |
|-----------|----------------|----------------|
| Python packages | ✅ Generally safe | Easy to roll back |
| Hamlib 4.x | ✅ Within 4.x | Rig control stops |
| WSJT-X | ⚠️ Check notes | FT8/WSPR stops |
| JS8Call 2.x | ✅ Generally | JS8 tab stops |
| Fldigi 4.x | ✅ Generally | PSK31/RTTY/CW stops |
| VARA HF/FM | ⚠️ Check notes | Winlink stops |
| OP25 | ❌ Pin to commit | P25 decode stops |
| DSD+ | ⚠️ Test first | DMR/NXDN stops |
| dump1090-fa | ✅ Generally | ADS-B stops |
| UHD 4.x | ✅ Generally | B210 not detected |
| SoapySDR | ⚠️ Match plugins | All SDR stops |
| SDRplay API 3.x | ✅ Generally | RSP not detected |

---

## Python Packages

Installed via `pip install -r requirements.txt`
Safe to update within stated version ranges.
If something breaks after update: `pip install packagename==LAST_KNOWN_GOOD`

| Package | Minimum | Tested | Purpose |
|---------|---------|--------|---------|
| PyQt6 | 6.6.0 | 6.7.x | GUI |
| numpy | 1.26.0 | 2.x | FFT / arrays |
| scipy | 1.11.0 | 1.13.x | Signal processing |
| sounddevice | 0.4.6 | 0.4.6 | Audio I/O |
| soundfile | 0.12.1 | 0.12.1 | Audio files |
| pyserial | 3.5 | 3.5 | Serial ports |
| requests | 2.31.0 | 2.31.x | HTTP APIs |
| aiohttp | 3.9.0 | 3.9.x | Async HTTP |
| websockets | 12.0 | 12.x | WebSocket |
| folium | 0.15.0 | 0.15.x | Maps |
| geopy | 2.4.0 | 2.4.x | Geocoding |
| maidenhead | 1.0.0 | 1.0.x | Grid squares |
| mgrs | 1.4.4 | 1.4.x | MGRS coordinates |
| adif-io | 0.0.5 | 0.0.5 | ADIF logs |
| xmltodict | 0.13.0 | 0.13.x | XML parsing |
| python-dateutil | 2.8.2 | 2.9.x | Dates |
| pyhamtools | 0.6.8 | 0.6.8 | DXCC / propagation |
| appdirs | 1.4.4 | 1.4.4 | App paths |
| psutil | 5.9.0 | 6.x | Process management |
| Markdown | 3.5.0 | 3.6.x | Help text |
| Pillow | 10.0.0 | 10.x | Images |
| pyqtgraph | 0.13.3 | 0.13.x | Waterfall display |
| pywin32 | 306 | 306 | Windows API |

---

## External Programs

Must be installed manually. Squelch controls via subprocess / TCP socket.

### Hamlib
- **Tested:** 4.5.x
- **Download:** https://github.com/Hamlib/Hamlib/releases
- **Install to:** C:\hamlib\ — add C:\hamlib\bin to system PATH
- **IC-7100 model:** 370
- **Update risk:** Low within 4.x. Do not use 3.x.
- **Breaking changes:** Rare in 4.x series

### WSJT-X
- **Tested:** 2.6.1
- **Download:** https://wsjt.sourceforge.io/wsjtx.html
- **Update risk:** Medium — UDP message format changed 2.5 → 2.6
- **Notes:** Stay on 2.6.x until Squelch is verified with 2.7+
- **Do not:** Configure audio manually — Squelch manages it

### JS8Call
- **Tested:** 2.2.0
- **Download:** https://js8call.com/
- **Update risk:** Low — TCP API stable across 2.x
- **Port:** 2442

### Fldigi
- **Tested:** 4.1.26
- **Download:** https://sourceforge.net/projects/fldigi/
- **Update risk:** Low — XML-RPC API stable for years
- **Port:** 7362

### VARA HF
- **Tested:** 4.8.x
- **Download:** https://rosmodem.wordpress.com/
- **Update risk:** Medium — EA5HVK occasionally changes TCP protocol
- **Port:** 8300 (default)
- **Notes:** Read release notes before any update. Free version speed-limited.

### VARA FM
- **Tested:** 5.0.x
- **Download:** https://rosmodem.wordpress.com/
- **Update risk:** Medium — same as VARA HF
- **Port:** 8400 (default)

### DSD+
- **Tested:** 1.101
- **Download:** https://www.dsdplus.com/
- **Update risk:** Medium — closed source, no changelog published
- **Notes:** Test DMR decode after any update

### OP25 (P25 Decode)
- **No version numbers** — git repository only
- **Repository:** https://github.com/osmocom/op25
- **Tested commit:** Pin to a specific commit for classroom use
- **Update risk:** HIGH — interface changes without warning
- **Recommendation:** `git clone` then `git checkout <commit_hash>` — never pull
- **Windows:** Requires specific GNU Radio Windows build — see help/digital_protocols.md
- **Port:** 8080 (built-in HTTP server)

### dump1090-fa (ADS-B)
- **Tested:** 8.x
- **Download:** https://github.com/flightaware/dump1090
- **Maintained by:** FlightAware (US company)
- **Update risk:** Low — JSON output format stable

### SDRplay API
- **Current version:** 3.15
- **Download:** https://www.sdrplay.com/api/
- **Update risk:** Low within 3.x
- **Notes:** Install BEFORE SoapySDRPlay3. Installs as Windows service.

### SoapySDRPlay3
- **Download:** https://github.com/pothosware/SoapySDRPlay3
- **Requires:** SDRplay API 3.x installed first
- **Update risk:** Match to SoapySDR core version

### UHD (USRP B210/B200)
- **Tested:** 4.6.x
- **Download:** https://files.ettus.com/manual/page_install.html
- **Maintained by:** Ettus Research / NI (US company)
- **Notes:** USB 3.0 required. Firmware auto-downloads on first use.

### SoapySDR Core
- **Tested:** 0.8.x
- **Download:** https://github.com/pothosware/SoapySDR
- **Notes:** Version must match all hardware plugins (SoapyRTLSDR, SoapyUHD, etc.)
  Mismatched versions cause silent detection failures.

### SoapyRTLSDR
- **Download:** https://github.com/pothosware/SoapyRTLSDR

### SoapyUHD
- Included with UHD Windows package

### Artemis Signal Database
- **Download:** https://github.com/AresValley/Artemis
- **Maintained by:** Società Italiana Radioascolto (Italian amateur radio society)
- **Notes:** Bundle locally for offline use. Update periodically from official source.

---

## CP210x Driver

- **Required version:** CP210x Universal Windows Driver v11.5.0
- **Download:** https://www.silabs.com/documents/public/software/CP210x_Universal_Windows_Driver.zip
- **Maintained by:** Silicon Labs (US company)
- **Do not use:** CP210x VCP Windows v6.7 / v6.7.6 (Windows XP/7 era drivers)

---

*Update this file whenever a new version is tested and confirmed working.*
