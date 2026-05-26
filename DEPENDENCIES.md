# Squelch — Software Dependencies

Every package Squelch uses, where it comes from, who maintains it,
and why it is included. Users should be able to make informed decisions
about what runs on their system.

---

## Core Runtime

### Python
- **Version required:** 3.9+ (3.9 recommended for SoapySDR compatibility)
- **Source:** python.org
- **Maintainer:** Python Software Foundation (PSF), US non-profit
- **License:** PSF License (permissive, BSD-like)
- **Est. users:** 8+ million developers worldwide
- **Why:** Application runtime. All Squelch code runs on Python.
- **Country of origin:** USA
- **Audit:** Full source at github.com/python/cpython, reviewed by thousands

### PyQt6
- **Source:** pypi.org/project/PyQt6
- **Pinned:** `PyQt6==6.6.1`, `PyQt6-Qt6==6.6.1`, `PyQt6-sip>=13.6.0,<14`
  — the three components must be a matched set, or Windows raises
  "DLL load failed ... specified procedure could not be found".
- **Maintainer:** Riverbank Computing, UK
- **License:** GPL v3 / Commercial
- **Est. users:** Millions (Qt is used in KDE, VirtualBox, many others)
- **Why:** All UI windows, widgets, dialogs, and event loop.
- **Country of origin:** UK (Qt framework: Norway/Finland, now owned by Qt Group Finland)
- **Audit:** Qt source open at code.qt.io; PyQt bindings at riverbankcomputing.com

---

## Signal Processing / SDR

### numpy
- **Source:** pypi.org/project/numpy OR conda-forge
- **Maintainer:** NumPy community, NumFOCUS (US non-profit)
- **License:** BSD 3-Clause
- **Est. users:** 250+ million downloads/month on PyPI
- **Why:** All IQ sample math — FFT, filtering, conversion, demodulation.
- **Country of origin:** USA (global contributor base)
- **Audit:** github.com/numpy/numpy — one of the most audited Python packages

### SoapySDR
- **Source:** github.com/pothosware/SoapySDR OR conda-forge
- **Maintainer:** Pothosware (Josh Blum), community
- **License:** Boost Software License 1.0 (permissive)
- **Est. users:** Standard SDR abstraction layer — used by GNU Radio,
  SDR#, CubicSDR, and most open-source SDR software
- **Why:** Hardware abstraction — same code works with RTL-SDR,
  HackRF, USRP, SDRplay, Airspy, LimeSDR.
- **Country of origin:** USA
- **Audit:** github.com/pothosware/SoapySDR — ~500 stars, active community
- **Install options:**
  - PothosSDR bundle (Windows): downloads.myriadrf.org — Python 3.9 only
  - conda-forge: `conda install -c conda-forge soapysdr` — Python 3.10+
  - Linux: `apt install python3-soapysdr`

### pyqtgraph
- **Source:** pypi.org/project/pyqtgraph
- **Maintainer:** pyqtgraph community, Luke Campagnola (original author)
- **License:** MIT
- **Est. users:** ~5 million downloads/month
- **Why:** SDR waterfall display and spectrum plot — high-performance
  real-time plotting built on numpy.
- **Country of origin:** USA/Canada
- **Audit:** github.com/pyqtgraph/pyqtgraph — 3,800+ stars

### conda-forge (alternative install method)
- **Source:** conda-forge.org
- **Maintainer:** conda-forge community (4,000+ contributors)
- **License:** BSD 3-Clause (conda itself)
- **Est. users:** 25+ million monthly downloads
- **Why recommended:** Provides pre-built SoapySDR wheels for
  Python 3.10, 3.11, 3.12 — no version mismatch with PothosSDR.
- **Country of origin:** USA (Anaconda Inc., Austin TX)
- **Audit:** All conda-forge builds are reproducible and source is
  on GitHub at github.com/conda-forge. Every package has a
  "feedstock" repo showing exactly how it was built.
- **Provenance:** NumFOCUS endorses the ecosystem. Used by NASA,
  CERN, and major research institutions worldwide.
- **Install:** miniforge3 (minimal, community build of conda):
  github.com/conda-forge/miniforge — ~150 MB
- **Usage for Squelch:**
  ```
  conda create -n squelch python=3.12
  conda activate squelch
  conda install -c conda-forge soapysdr soapyrtlsdr pyqtgraph
  pip install PyQt6 requests sounddevice sgp4 defusedxml
  ```

### sgp4
- **Source:** pypi.org/project/sgp4
- **Maintainer:** Brandon Rhodes
- **License:** MIT
- **Est. users:** ~2 million downloads/month
- **Why:** Satellite orbital mechanics — computes satellite positions
  from TLE data (Two-Line Elements from Celestrak).
- **Country of origin:** USA
- **Audit:** github.com/brandon-rhodes/python-sgp4 — pure Python,
  minimal, easy to read

---

## Networking

### requests
- **Source:** pypi.org/project/requests
- **Maintainer:** Python Software Foundation (donated by Kenneth Reitz)
- **License:** Apache 2.0
- **Est. users:** 300+ million downloads/month — most downloaded Python package
- **Why:** HTTP requests to NOAA solar data, Winlink API, RepeaterBook,
  Nominatim geocoding, Celestrak TLE data.
- **Country of origin:** USA
- **Audit:** github.com/psf/requests — extensively audited, PSF stewardship

### defusedxml
- **Source:** pypi.org/project/defusedxml
- **Maintainer:** Christian Heimes (CPython core developer)
- **License:** PSF License
- **Est. users:** ~50 million downloads/month
- **Why:** Safe XML parsing — prevents XML External Entity (XXE) attacks
  when parsing QRZ.com callsign data and FLRig XML-RPC responses.
  **Security-critical: do not replace with stdlib xml.etree.**
- **Country of origin:** Germany
- **Audit:** github.com/tiran/defusedxml — authored by CPython core dev,
  well-reviewed security library

---

## Audio

### sounddevice
- **Source:** pypi.org/project/sounddevice
- **Maintainer:** Matthias Geier
- **License:** MIT
- **Est. users:** ~5 million downloads/month
- **Why:** Audio input/output — rig USB audio as IQ source,
  audio playback for digital mode monitoring.
- **Country of origin:** Germany
- **Audit:** github.com/spatialaudio/python-sounddevice

---

## Security / Utilities

### PyYAML (optional)
- **Source:** pypi.org/project/PyYAML
- **Maintainer:** Kirill Simonov, community
- **License:** MIT
- **Est. users:** 200+ million downloads/month
- **Why:** Imports GNU Radio .grc flowgraph files (optional feature).
- **Country of origin:** Russia (original author), now community-maintained
- **Audit:** github.com/yaml/pyyaml — well-audited, widely used
- **Note:** Only used for reading .grc files, never for untrusted input.
  If you prefer to exclude it, .grc import will show a warning.

---

## Hardware Drivers (not Python packages)

### Hamlib / rigctld
- **Source:** hamlib.org
- **Maintainer:** Hamlib development team (international ham radio community)
- **License:** LGPL v2.1
- **Est. users:** Standard CAT control library — used by WSJT-X, fldigi,
  JS8Call, N1MM+, and virtually all open-source ham radio software
- **Why:** CAT control for IC-7100, FT-991A, TS-2000, and 300+ other rigs.
- **Country of origin:** International open source community
- **Audit:** github.com/Hamlib/Hamlib — 1,200+ stars, 20+ year history

### PothosSDR bundle (Windows)
- **Source:** downloads.myriadrf.org/builds/PothosSDR/
- **Maintainer:** Josh Blum (Pothosware), MyriadRF (Lime Microsystems)
- **License:** Various open source (Boost, GPL, LGPL per component)
- **Why:** Windows installer that bundles SoapySDR + hardware drivers
  for RTL-SDR, HackRF, LimeSDR, USRP, SDRplay in one package.
- **Country of origin:** USA (Pothosware), UK (MyriadRF/Lime Microsystems)
- **Note:** Bundles Python 3.9 — Squelch venv must match this version.
  Alternative: conda-forge provides Python 3.10+ compatible packages.

### SDRplay API
- **Source:** sdrplay.com/softwarehome/
- **Maintainer:** SDRplay Ltd
- **License:** Proprietary (free, no-cost)
- **Why:** Required hardware API for all SDRplay RSP devices
  (RSP2Pro, RSP1A, RSPdx, RSPduo). Must be installed before PothosSDR.
- **Country of origin:** UK
- **Note:** Closed-source hardware driver. Source not auditable.
  Standard practice for hardware vendors (same as NVIDIA, Intel, etc.)

### VARA HF / VARA FM
- **Source:** rosmodem.com
- **Maintainer:** EA5HVK (Jose Alberto Nieto Ros)
- **License:** Freeware (shareware for full speed)
- **Why:** Winlink over HF and VHF/UHF. VARA is the modem software;
  Squelch connects to it via TCP.
- **Country of origin:** Spain
- **Note:** Closed-source. Widely used in ham radio emergency
  communications (ARES, RACES, EMCOMM). Source not auditable.

---

## What Squelch does NOT use

To address common concerns:

- **No telemetry or analytics** — Squelch does not phone home,
  report usage, or collect any data about you or your operating habits.
- **No ads** — No advertising SDKs or tracking.
- **No cloud dependencies** — All core functions work offline.
  Internet is used only when you explicitly request data
  (band conditions, repeater lookup, QRZ lookup, etc.)
- **No auto-update** — Squelch never downloads or executes
  code from the internet. Updates are manual.
- **No cloud storage** — All your logs, settings, and recordings
  stay on your machine.

---

## Verifying what is installed

After installation, you can audit exactly what packages are in your venv:

```
venv\Scripts\pip list
venv\Scripts\pip show <package>   # shows version, source, license
```

For a full dependency tree including transitive dependencies:
```
venv\Scripts\pip install pipdeptree
venv\Scripts\pipdeptree
```

---

*Last updated: 2026-05 — Squelch 0.11.3-alpha*
