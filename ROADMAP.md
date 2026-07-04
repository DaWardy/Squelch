# Squelch — Roadmap & Strategic Framework

> Canonical planning document. Read alongside `CLAUDE.md` (engineering
> context) before scoping any new work.
> Last updated: 2026-06-21 · Current build: v0.12.0-alpha · 1933 tests passing

---

## 1. Vision

Squelch is an integrated platform to **search for, identify, correlate,
decode, play back, encode, transmit, and geolocate radio signals** — with a
first-class education layer on top.

Amateur radio is the most visible use case and the public face of the
project, but the capability set is general-purpose RF. The same pipeline
serves:

- **Amateur radio operators** — rig control, digital modes, logging, propagation, EmComm.
- **RF security researchers** — protocol analysis, capture/replay, emitter study (authorized testing only).
- **Spectrum analysts** — occupancy survey, interference hunting, signal classification.
- **Educators & students** — guided RF labs, signal-classification practice, propagation demos.

What makes Squelch distinct: no single existing tool combines direction
finding, multi-protocol decode, propagation modelling, logging, **and** a
teaching layer in one cross-platform GUI. Today that requires stitching
together separate utilities. Squelch unifies them.

> **Public-language policy.** Public-facing surfaces (README, in-app Help,
> the app UI, store/marketing text) describe capabilities in neutral,
> professional terms — amateur radio, RF analysis, RF security *research*,
> spectrum monitoring, transmitter location / interference hunting, and RF
> *education*. Do not use loaded operational labels in public text. The
> broader institutional use cases are intentional but are framed generically.

---

## 2. Capability model — the eight pillars

Every feature maps to one of these verbs, and each pillar feeds a single
**unified Signal record** (see Phase 1). This is the architecture going
forward.

| Pillar | Meaning | Status today |
|--------|---------|--------------|
| **SEARCH** | Wideband scan, energy detection, occupancy survey | 🟡 Scanner exists; no persistent survey/occupancy DB |
| **IDENTIFY** | Classify a signal (DB match + modulation classifier) | 🟡 SigID-wiki DB match (`network/signal_id.py`); no modulation classifier |
| **CORRELATE** | Tie signals together by ID/time/location; fingerprint emitters | ❌ No correlation store |
| **DECODE** | Voice + generic digital + weak-signal | 🟢 Voice (DSD+/OP25), FT8/WSPR done; 🟡 generic OOK/ASK/FSK/PSK bit-slicer core done (`core/bitslicer.py`) |
| **PLAYBACK** | Record & replay IQ, scrub captures | 🟢 `IQRecorder`/`IQPlayer` done |
| **ENCODE** | Build a waveform to transmit | ❌ No modulators/frame builders |
| **TRANSMIT** | Key a TX-capable SDR / rig | 🟡 `transmit_iq()` plumbing only; no encode chain, no authorization layer |
| **GEOLOCATE** | Direction finding, RSSI→GPS, TDOA, emitter mapping | ❌ `digital/rfdf.py` is an empty stub — **keystone gap** |

Cross-cutting: **QUERY** (online "what's near here" + spot networks — 🟡
partial via PSKReporter/RBN/DX/SOTA-POTA) and **EDUCATE** (🟢 RF Lab mode).

---

## 3. Where we are — original requirements audit

The original amateur-radio platform requirements are **complete**:

- ✅ Rig control (26+ CAT models), VFO/split/memory/rotor, calibrated S-meter
- ✅ Digital modes (FT8/FT4/WSPR/JS8, PSK31/RTTY/CW, SSTV), digital voice (P25/DMR/NXDN/YSF/D-STAR)
- ✅ SDR RX waterfall with MHz axis, signal ID, squelch, NR, IF BW, LO offset
- ✅ Logging (ADIF/CSV/Cabrillo), 5-service upload (LoTW/QRZ/ClubLog/eQSL/HRDLog), DXCC/WAS/WAZ tracking
- ✅ Band conditions, propagation side-view, terrain (SRTM), PSKReporter "who hears me", RBN
- ✅ Map (APRS/FT8/PSKReporter/satellites/ADS-B/Winlink), VOACAP path analysis
- ✅ Winlink (VARA HF/FM, Pat, ARDOP soundcard-TNC — `winlink/ardop.py`,
  control port 8515/data 8516, mocked-socket tests), EmComm templates
- ✅ Education mode (RF Lab), guided first-run, full Help system
- ✅ Security baseline (no shell/eval/pickle, keyring creds, netlog, CSV sanitize, pentest suite)
- ✅ TX safety (AppState FSM, `operating_callsign()`, Demo/Guest modes)

SDR **receive** support is broad (RTL-SDR, HackRF, USRP B200/B210, SDRplay,
Airspy, LimeSDR, BladeRF, Pluto via SoapySDR). **The broadened vision is
~50% delivered**: the receive/decode/playback/propagation half is mature;
geolocation, generic decode/encode, correlation, and the TX chain are
greenfield.

---

## 4. Phased roadmap (dependency-ordered)

Phases are ordered so each one unlocks the next. Version bands are targets,
not commitments.

### Phase 1 — Foundation: Unified Signal model + Survey  ·  v0.13–0.14  ·  **P0**
The prerequisite for correlate / geolocate / query. Without it those
features have nowhere to write.
- ✅ **DONE** `core/signal_model.py` — `Signal` record + thread-safe SQLite
  `SignalStore`: freq, bandwidth, first/last seen, RSSI/SNR, lat/lon/alt,
  IQ-capture reference, modulation, classification, decoded payload,
  emitter-ID, source, confidence, tags. `record()` merges repeat observations
  of the same emitter (the correlation seed); `add()`/`search()`/`recent()`/
  `distinct_emitters()`/`delete()`. Parameterized throughout. 31 tests.
- ✅ **DONE** Migrate finding sources to **emit Signal records**
  (`SIG-MIGRATE`): APRS / FT8 / WSPR / DX-cluster / SDR signal-ID bookmarks,
  via `core/signal_ingest.py` (pure converters + thread-safe `ingest()`;
  one-line bridges in the handlers). Direction-finding feeds in Phase 3.
- 🟡 **Spectrum occupancy survey** (`SIG-SURVEY`): detection core DONE
  (`core/occupancy.py`: robust noise floor, `detect_segments` →
  OccupancySegment, `occupancy_fraction`; feeds the store via
  `signal_from_occupancy`; 18 tests). Remaining: the live wideband sweep loop
  (tune SDR across a range, accumulate frames) — needs SDR streaming + GUI.
- ✅ **DONE (pending launch-test)** **Signal Browser** tab (`SIG-BROWSER`):
  presenter (`core/signal_browser.py`) + Qt tab (`ui/tabs/signal_browser_tab.py`,
  read-only table, search + source filter, CSV export, double-click→SDR tune,
  save/restore), registered as the 📶 Signals tab (shown in RF Lab mode).
  Source/contract tests pass headlessly; Qt round-trip tests run on a PyQt6
  machine — **launch-test before relying on it**.

### Phase 2 — Identify  ·  v0.14–0.15  ·  **P1**
- Write SigID-wiki matches onto Signal records (classification + confidence).
- 🟡 **Allocation classifier DONE** (`core/signal_classify.py`): matches
  freq → known fixed channels (NOAA/aviation/marine/ISS…), amateur band
  segments, and CB/FRS/GMRS/MURS/ISM service bands → label + suggested mode +
  confidence; `apply_classification()` enriches generic Signals. 18 tests.
- ⬜ **Modulation classifier** — heuristic from IQ/spectrum features
  (energy/bandwidth/symbol-rate → AM/FM/SSB/OOK/FSK/PSK/OFDM); needs real
  feature extraction (SDR). Optional ML model later.

### Phase 3 — Correlate + Geolocate  ·  v0.15–0.17  ·  **P0 (flagship)**
The keystone and biggest differentiator. Implement `digital/rfdf.py` for real.
- 🟡 **Single-receiver gradient DF** (foxhunt) — math core DONE
  (`digital/rfdf.py`: `bearing_from_rssi_sweep`, `triangulate` least-squares
  bearing intersection, `estimate_location_rssi` centroid; DF fixes feed the
  Signal store via `signal_from_df_estimate`; 22+ tests). Remaining: a foxhunt
  UI panel + live RSSI/heading/GPS capture (SDR + rotor/compass/GPS, GUI).
  - 🟡 **Live position source DONE (DF-RSSI-GPS prerequisite)**:
    `core/gps.py` — pure NMEA (`$GPGGA`/`$GPRMC`) parsing → `GPSFix`,
    Windows Location API one-shot (WinRT, graceful when absent), and a
    threaded NMEA-over-serial `SerialGPSReader` delivering fixes via
    `pyqtSignal`. Feeds `LocationManager.apply_gps_fix()` / `start_gps_serial()`;
    Settings → Station has a source selector (Manual / Windows / GPS serial),
    port+baud, "Get fix", and auto-update-grid. This is the live lat/lon feed
    the foxhunt RSSI→GPS track logging below will consume.
- **Coherent / pseudo-doppler DF** where hardware supports (KrakenSDR-class
  multi-channel).
- 🟡 **RSSI→GPS track logging + heatmap** — drive/walk a signal, map strength.
  Capture/logging core DONE (`core/df_track.py`): `DFTrack` accumulator +
  `DFSample`; four capture triggers (MANUAL/CONTINUOUS/TIMED/DISTANCE) via the
  pure `should_log()`; delegates to `digital/rfdf.py` for the location fix &
  gradient bearing; `to_signal()` bridges into the store; `heatmap_points()`
  (normalized weights), bbox/strongest/path-length/duration stats; JSON
  save/load. 41 tests. Remaining: foxhunt UI panel wiring the live GPS+RSSI
  feed in and drawing the track/heatmap overlay (GUI).
- **TDOA / multilateration** from multi-node captures (needs Phase 6 sensor mode).
- 🟡 **Emitter fingerprint correlation** — group Signal records by frequency +
  digital ID (radio ID, talkgroup, protocol identifiers) → estimated location;
  persistent emitter map overlay. Correlation core DONE
  (`core/emitter_correlate.py`): `fingerprint()` (non-empty emitter-id names the
  physical emitter across every frequency; anonymous obs group by
  source+classification+freq-bucket), `correlate_emitters()` /
  `correlate_from_store()` → `Emitter` records (freq range, distinct
  sources/classifications/modulations, obs count, first/last seen, estimated
  location via `rfdf.estimate_location_rssi` or plain centroid). 18 tests.
  Remaining: the persistent emitter map overlay (GUI).
- Map integration: bearings, heatmaps, estimated emitter locations.

### Phase 4 — Decode + Encode (generic protocol)  ·  v0.17–0.19  ·  **P1**
Reach URH-class parity for arbitrary digital protocols.
- 🟡 **Generic demod/bit-slicer from IQ: OOK/ASK/FSK/PSK — core DONE**
  (`core/bitslicer.py`): `slice_bits()` → soft signal per family (OOK envelope
  level-threshold, FSK inst-freq sign, coherent-BPSK derotate) → shortest-run
  samples-per-symbol estimator → symbol-centre sampling → bits, with an
  eye-opening confidence and `bits_to_bytes`/`bits_to_hex`. Auto-selects the
  family via the modulation classifier. Pure numpy, never raises; 23
  synthetic-signal tests (exact OOK recovery, FSK/PSK up-to-inversion, sps
  estimation, packing). Remaining: a UI to drive it + tie into DEC-FRAMING.
- Protocol framing inspector — preamble / sync / payload / CRC (Inspectrum-style).
- **Encode** — frame builder + modulator → IQ (feeds Phase 5 TX).
- Replay: captured IQ → TX (authorization-gated).
- Targets: ISM-band telemetry, IoT/sensor protocols, and general protocol research.

### Phase 5 — Transmit chain + Authorization  ·  v0.19–0.21  ·  **P0 for any TX**
The Authorization layer is a **hard prerequisite** before any encode→TX
feature ships.
- 🟡 **DONE (decision core + chokepoint)** `core/authorization.py` —
  **Authorization Profiles**: per-band TX allow/deny, default-deny, legal-use
  acknowledgment gate, buried unrestricted override; `can_transmit()` returns
  an AuthDecision; 18 tests. **Chokepoint wired (2026-07-04):**
  `authorize_tx(freq_hz)` (fail-closed; Demo-mode absolute block; every keying
  logged via `core/netlog` → Help→Network Activity) enforced INSIDE
  `SoapyManager.transmit_iq()` — raises PermissionError before any hardware
  call, so no caller can bypass it. 15 chokepoint tests incl. a gate-coverage
  source guard. **Settings UI DONE (2026-07-04):**
  `ui/dialogs/settings_tx_auth_tab.py` — a "TX Authorization" settings tab:
  legal-acknowledgment checkbox gating a per-band opt-in grid (all amateur +
  service bands, disabled until acknowledged), plus the buried unrestricted
  override behind a red danger disclaimer. Reads/writes only the `tx.auth.*`
  keys the decision core consumes; 12 tests incl. an end-to-end check that a
  UI-saved profile authorizes via `can_transmit`. **AUTH-LAYER complete.**
- Wire encode → `transmit_iq()` strictly through the authorization gate,
  integrated with the AppState FSM. (Gate half done — transmit_iq is the hard
  auth chokepoint; the encode→modulator pipeline lands with Phase 4 ENC-BUILD.)
- **Buried "Unrestricted TX" override** — behind layered disclaimers, for
  emergency use or when the operator holds authorization for the band(s).
  Off by default, requires explicit acknowledgment, every use logged. Legal
  onus is on the end user (made explicit in the disclaimer).
- Validate end-to-end TX on USRP B200/B210 (real hardware).

### Phase 6 — Query nearby + Multi-node  ·  v0.21+  ·  **P2**
- Live "what's active near this GPS/grid" aggregator over PSKReporter, RBN,
  APRS, spot nets, and the local occupancy DB.
- Remote/networked sensor mode (also the TDOA enabler and a
  classroom/lab deployment story).
- Optional crowd/shared sensor map (much later).

### Cross-cutting (every phase)
- **SDR breadth & TX validation** — keep device profiles current; verify on
  real hardware as it becomes available.
- **Filters / bandwidth UX** — consistent, discoverable controls across SDR,
  decode, and DF.
- **Education labs** — each new pillar ships with at least one RF Lab exercise.
- **Compliance & safety** — see §6.

---

## 5. Priorities

| Priority | Definition | Items |
|----------|------------|-------|
| **P0** | Foundational or flagship; unblocks the vision | Phase 1 (Signal model + survey), Phase 3 (DF/geolocation), Authorization layer (Phase 5 gate) |
| **P1** | High value, depends on P0 | Phase 2 (classifier), Phase 4 (generic decode/encode) |
| **P2** | Valuable, later | Phase 6 (online query, multi-node), crowd sensor map |
| **Ongoing** | Continuous | SDR breadth, filters UX, education labs, code health |

Sequencing rule: **do not start a phase whose data dependency isn't built.**
Phase 1 first, always.

---

## 6. Compliance & authorization posture

Squelch is dual-use and (in part) TX-capable and decode-broad. The posture:

1. **Authorization Profiles are first-class** (Phase 5). TX is **default-deny**
   per band; the operator opts bands in. Every keying is logged.
2. **Emergency / unrestricted override exists but is buried** behind layered
   disclaimers — for emergencies or operators who hold authorization for the
   band(s). Off by default; explicit acknowledgment; fully logged. **Legal
   responsibility rests with the end user**, stated plainly at the gate.
3. **Receive/analysis features are not gated**, but the app surfaces a clear
   legal-use notice and keeps the existing outbound-network log
   (`core/netlog`, Help → Network Activity).
4. The existing safety stack stays: AppState FSM, `operating_callsign()`,
   Demo/Guest modes, no shell/eval/pickle, keyring credentials, pentest suite.

### Security hardening (continuous workstream)

Squelch ingests **untrusted input over the air and from the network** (APRS
packets, DX-cluster/RBN spots, SDR captures, API responses) and launches
external tools — so input-handling and process safety are ongoing concerns,
not a one-time audit.

Baseline (in place): parameterized SQL throughout, `subprocess` list-form with
`shell=False` (no shell), no `eval`/`exec`/`pickle`, OS-keyring credentials,
`core/sanitize` (CSV-injection + URL redaction), `core/validator` +
`api_callsign`/`api_string` for network fields, response-size caps on some
fetches, `tests/test_security_pentest.py`.

Audited & fixed (2026-06-21):
- **XSS in the embedded map** — Leaflet popups concatenated RF/network strings
  (APRS callsign/comment, DX-cluster fields) into HTML. Now HTML-escaped at the
  render chokepoint in `network/map_data.py` (`_esc_deep` over RF/user data;
  pre-serialized JSON and numbers untouched). 13 tests in `test_map_xss.py`.
- **XXE hardening** — `network/pskreporter.py` now uses `defusedxml` (with
  stdlib fallback), matching `network/qrz_lookup.py`.

Open hardening backlog (`SEC-*`, see CLAUDE.md):
- **Plugin trust model** — `core/plugins.py` executes code from `plugins/`
  (RCE by design). Document the trust boundary in UI; future: subprocess
  sandbox and/or signature/allow-list before load.
- **Process-launch review** — confirm external-tool paths are validated /
  absolute (mitigate local PATH-hijack of WSJT-X/DSD+/rigctld launches).
- **Network input limits** — apply response-size caps and stricter schema
  validation uniformly across all fetchers.
- **CI security gates** — Bandit + `pip-audit` in GitHub Actions (v1.0 target).
- **TX safety is the highest-severity surface** — handled by the Phase 5
  Authorization layer; no TX path ships before it.

A dedicated security sprint runs as needed and at v1.0 (full audit). Any sprint
that adds an input parser, a network fetcher, an external-process launch, or a
TX path includes a security check in its Definition of Done.

---

## 7. SDR hardware support

| Device | RX | TX | Notes |
|--------|----|----|-------|
| USRP B200 / B210 | ✅ | 🎯 target | Primary TX target; B210 full-duplex |
| HackRF One | ✅ | 🟡 | Half-duplex; TX behind authorization |
| RTL-SDR | ✅ | — | RX only; RTL-TCP fallback when SoapySDR absent |
| SDRplay RSP series | ✅ | — | RX only |
| Airspy / LimeSDR / BladeRF / Pluto | ✅ | varies | Via SoapySDR |

RX should "just work" across all SoapySDR devices. TX is validated
device-by-device, starting with B200/B210.

---

## 8. Engineering framework

### Definition of Done (every sprint)
- `python qa_check.py` exits 0 (no exceptions).
- New behavior has tests (pure-logic preferred; Qt tests skip-clean without PyQt6).
- `CLAUDE.md` handoff block + this roadmap's status reconciled.
- No function > ~60 lines added to a file scored < 7.0 (extract instead).
- No new hardcoded dark hex; use theme tokens.

### Housekeeping cadence — **every 5th sprint**
A dedicated housekeeping sprint that does:
- CodeScene (or radon MI) scan; update the scores table in `CLAUDE.md`.
- Dark-hex sweep on any files touched since the last housekeeping pass.
- Dead-code / stale-stub review (e.g. retire or implement leftover stubs).
- Test-count + backlog + roadmap reconciliation.
- Dependency check (conda-forge win-64 compatibility).
- **`.gitignore` review** — add any new runtime/cache/user-data paths a sprint
  introduced (recordings, voice clips, bookmarks, caches); confirm
  `git ls-files` shows no artifacts (pyc, logs, db, venv, build) tracked.

Rationale: weekly feature sprints erode complexity scores gradually; a fixed
1-in-5 cadence catches drift before any file drops below 7.0, without the
overhead of housekeeping every sprint.

### Architecture rules (unchanged, see CLAUDE.md for detail)
- Mixins for large UI classes; write-verify-delete extraction order.
- `pyqtSignal` across threads, never `QTimer.singleShot` from workers.
- New panels implement `save_state`/`restore_state`.
- New cross-tab data flows through the **unified Signal model** (Phase 1+),
  not bespoke per-tab stores.

---

## 9. UX, UI & installation — first-class standard

UX and UI are **not** a polish-at-the-end concern; they are a continuous,
P0-quality bar that every feature is held to. A capable tool that is
confusing or ugly fails its users — especially educators, students, and
first-time operators.

### Guiding principles
- **Clean, functional, consistent.** Theme tokens everywhere (no hardcoded
  hex), consistent spacing/typography, discoverable controls, sensible
  defaults, no dead-end states.
- **Don't silo by habit.** Put information where the task lives, not where the
  org chart says. If two things are used together, show them together; if a
  tab only exists to hold one widget, fold it. Challenge every tab boundary —
  consolidate when siloing adds clicks without adding clarity.
- **Progressive disclosure.** Beginners see a clean surface; power features
  (filters, raw IQ, authorization override) are reachable but not in the way.
- **Forgiving.** Clear errors with next steps, undo where possible, nothing
  destructive without confirmation.

### Custom tabs & layout (largely built — polish + extend)
The user must be able to **build any number of custom tabs, fill them with any
applet/panel they want, rearrange them, then lock/unlock as desired.** Most of
this exists today and must be kept first-class:
- `ui/tabs/custom_tab.py` `CustomLayoutTab` — add panels as cards
  (`＋ Add panel`), reorder/remove in `🔓 Rearrange` unlock mode.
- `main_window` — `_add_custom_tab` / `_rename_custom_tab` /
  `_remove_custom_tab` / `_assign_panel_to_custom_tab`; movable tab bar
  (`setMovable(not locked)`); `🔒 Lock / 🔓 Unlock tab order`; Tab Presets +
  `ui.saved_tab_layouts`; custom-tab state persisted across sessions.

Forward work (backlog `UX-*`):
- **Any applet, including plugins.** Let custom tabs host plugin-provided
  panels (`plugins/` `register()` widgets), not only built-in panels — turns
  custom tabs into a true dashboard builder.
- **Drag-and-drop card reorder** (today uses ◀ ▶ buttons) and drag-between-tabs.
- **Per-tab layout polish** — grid/free placement, resizable cards, save named
  dashboards.
- **Lock affordance clarity** — make the lock state obvious; tooltip already
  notes it controls tab order, not in-tab section order.

### Installation experience
The first five minutes decide adoption. The installer must be **pleasant, not a
hazing ritual.**
- One obvious entry point; plain-language progress; clear success/failure with
  remediation (the `installer.py --check` self-diagnostic is the model).
- Detect what's present (Python, SoapySDR, rig drivers, optional apps) and tell
  the user exactly what's missing and how to get it — no silent failures.
- Offline install path (`--cache` / `--offline`) stays first-class.
- AV-exclusion guidance up front (already in README) so Defender/Armor don't
  derail a new user.
- Backlog `UX-INSTALL`: friendlier installer output / optional GUI installer,
  guided first-run that flows straight into a working layout per user class.

> Definition of Done (§8) includes the UX bar: no hardcoded dark hex, theme
> tokens used, controls discoverable, no new siloed single-widget tabs.

---

## 10. Deferred / out of scope (for now)

| Item | Reason |
|------|--------|
| Decrypting protected/encrypted traffic | Out of scope; tool decodes openly-receivable signals only |
| macOS / FreeBSD ports | Low demand, no test hardware |
| Cloud-hosted multi-user service | Desktop-first; revisit after Phase 6 |
| Frequency-hopping follow | High CPU; plugin candidate |
| Full ML classifier | After heuristic classifier proves the UX (Phase 2) |

---

## 11. Appendix — legacy version targets (historical)

The original v0.7–v1.0 targets (digital monitor, Winlink, help system,
map system, settings, Linux port) are **complete or in-tree** as of
v0.12.0-alpha. The version arc going forward is organized by the phases in
§4 rather than the old per-tab milestones. v1.0.0 remains: signed installer,
full security audit, CI hardening (Bandit + pip-audit), complete docs,
public release.

---

## 12. Operator / instructor / analyst vision backlog (2026-07-01 pass)

Running to-do list captured from an operator vision pass. Broadened audience:
amateur operators (new → expert), RF educators and engineering students,
spectrum / RF-signal analysts, authorized RF-security testers, and the general
public exploring their local RX environment. **Public-language policy (§1)
holds** — neutral, professional framing everywhere public; capabilities are
dual-use and the user decides the application. Items cross-reference the phases
in §4.

### 12.1 Composable operating dashboard (custom tabs) — flagship
- [ ] **Interactive control widgets** in the à-la-carte catalog, not just
  read-only summaries: **SDR tune (→ rig auto-tune)**, rig VFO/mode, digital-
  voice decode, propagation-to-target. Each = one catalog entry + a factory
  bound to that tab's shared singleton backend.
- [ ] **Cross-widget workflow:** tune the SDR to a spot → auto-tune the rig to
  it → check propagation to that area → work it — all in one custom tab.
- [x] MDI windows: move / resize / **snap-to-grid** / **lock in place** (done
  e4cb564 + snap tuning; launch-verify feel). [ ] persist per-window geometry.
- [ ] **Hide / show widgets within the default tabs** + **Restore defaults per
  tab** + unhide (Microsoft-toolbar-style checklist). Default tabs are a
  starting layout, not fixed.
- [ ] Let **community plugin** widgets register into the catalog.

### 12.2 Packaging, install & platforms (v1.0 gate)
- [ ] One-click installer; **workflow install profiles** (e.g. amateur /
  education / analysis / developer) that pull only what's needed.
- [x] Fix **SoapySDR module load failures** (rtlsdr/uhd `*.dll` LoadLibrary
  errors → 0 devices). DONE 7e9deef — os.add_dll_directory(conda/Library/bin)
  + ctypes pre-load of dependency DLLs (LOAD_WITH_ALTERED_SEARCH_PATH bypass).
  [ ] still: auto-install required native packages at install time.
- [ ] **AV-friendly distributable** — signed `.exe` (and submit to AV vendors
  for allow-listing) so Defender/AV don't flag it; keep the offline install path.
- [ ] **Linux support** — Debian-based first; **Raspberry Pi** target.
- [ ] Optional online asset downloads at install/first-run (see 12.3).

### 12.3 Signal identification (Phase 2 IDENTIFY)
- [ ] Bundled/downloadable **Signal-ID database** (sigidwiki-style, Artemis-like):
  frequency + bandwidth + waterfall-shape → candidate matches; flag/annotate
  unknown signals of interest. Wire into the SDR signal-ID panel + Signal model.

### 12.4 IQ record / playback / retransmit (PLAYBACK + Phase 5)
- [ ] **Specify + document IQ recording location and formats** (WAV / SigMF
  sidecar metadata; a known recordings dir, `.gitignore`d).
- [ ] **Replay stored IQ** back through the pipeline (scrub, loop).
- [ ] **Classroom retransmit** — replay recorded IQ → TX (authorization-gated)
  for demos on TX-capable hardware.

### 12.5 Map & propagation overhaul (map currently "feels useless")
- [ ] Real map renderer — install `PyQt6-WebEngine` for the Leaflet map;
  otherwise substantially improve the Qt fallback.
- [ ] **Satellite tracking** layer — select/track sats + ISS, pass predictions.
- [ ] **RX↔TX great-circle path** with **MUF / LUF / optimal band** for a chosen
  target area; click-a-location → propagation to it.
- [ ] Surface **NVIS** (short-range) in path analysis + on the map, not just the
  side-view overlay.

### 12.6 Direction finding (Phase 3 refinement)
- [ ] DF a target from **RSSI + RX-antenna GPS location + time**.
- [ ] Reading triggers: **on-demand / continuous / timed / distance-interval**.
- [ ] RSSI→GPS track log + heatmap; bearing + estimated emitter location on map.

### 12.7 Transmit safety & authorization (Phase 5 refinement)
- [ ] First TX **outside the amateur bands** → explicit warning + acknowledgment
  before it's allowed.
- [ ] **License-class TX filter** — dropdown (Technician / General / Extra / …)
  gating permitted frequencies, plus an **"Other / Emergency"** override (buried,
  disclaimer-gated, every keying logged). Legal onus on the operator, stated at
  the gate. Use cases are left to the user — not enumerated in-app.

---

*Supersedes the v0.7–v1.0 milestone roadmap. Update the status line and
phase markers each sprint; do a full reconciliation every 5th (housekeeping)
sprint.*
