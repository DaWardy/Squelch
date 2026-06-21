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
| **DECODE** | Voice + generic digital + weak-signal | 🟢 Voice (DSD+/OP25), FT8/WSPR done; ❌ generic OOK/ASK/FSK/PSK |
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
- ✅ Winlink (VARA/Pat/ARDOP), EmComm templates
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
- `core/signal_model.py` — `Signal` record + SQLite store: freq, bandwidth,
  first/last seen, RSSI/SNR, lat/lon/alt, IQ-capture reference, modulation,
  classification, decoded payload, emitter-ID, source, confidence, tags.
- Migrate existing finding sources (FT8 decode, APRS, SDR bookmark, RBN,
  future DF) to **emit Signal records** instead of living in tab silos.
- **Spectrum occupancy survey** — long-dwell wideband sweep → energy
  detection → Signal records with time-stamped occupancy.
- **Signal Browser** tab — searchable/filterable table across everything
  captured; export; jump-to-map / jump-to-SDR.

### Phase 2 — Identify  ·  v0.14–0.15  ·  **P1**
- Write SigID-wiki matches onto Signal records (classification + confidence).
- **Modulation classifier** — heuristic first (energy/bandwidth/symbol-rate
  features → AM/FM/SSB/OOK/ASK/FSK/PSK/OFDM), optional ML model later.
  High education value; analyst time-saver.

### Phase 3 — Correlate + Geolocate  ·  v0.15–0.17  ·  **P0 (flagship)**
The keystone and biggest differentiator. Implement `digital/rfdf.py` for real.
- **Single-receiver gradient DF** (foxhunt) — RSSI vs. heading from
  rotor/compass/GPS track; bearing estimate on map.
- **Coherent / pseudo-doppler DF** where hardware supports (KrakenSDR-class
  multi-channel).
- **RSSI→GPS track logging + heatmap** — drive/walk a signal, map strength.
- **TDOA / multilateration** from multi-node captures (needs Phase 6 sensor mode).
- **Emitter fingerprint correlation** — group Signal records by frequency +
  digital ID (radio ID, talkgroup, protocol identifiers) → estimated location;
  persistent emitter map overlay.
- Map integration: bearings, heatmaps, estimated emitter locations.

### Phase 4 — Decode + Encode (generic protocol)  ·  v0.17–0.19  ·  **P1**
Reach URH-class parity for arbitrary digital protocols.
- Generic demod/bit-slicer from IQ: OOK/ASK/FSK/PSK.
- Protocol framing inspector — preamble / sync / payload / CRC (Inspectrum-style).
- **Encode** — frame builder + modulator → IQ (feeds Phase 5 TX).
- Replay: captured IQ → TX (authorization-gated).
- Targets: ISM-band telemetry, IoT/sensor protocols, and general protocol research.

### Phase 5 — Transmit chain + Authorization  ·  v0.19–0.21  ·  **P0 for any TX**
The Authorization layer is a **hard prerequisite** before any encode→TX
feature ships.
- `core/authorization.py` — **Authorization Profiles**: per-band TX
  allow/deny lists, default-safe (deny unless allowed), legal-use
  acknowledgment, all keyings logged via `core/netlog`.
- Wire encode → `transmit_iq()` strictly through the authorization gate,
  integrated with the AppState FSM.
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

## 9. Deferred / out of scope (for now)

| Item | Reason |
|------|--------|
| Decrypting protected/encrypted traffic | Out of scope; tool decodes openly-receivable signals only |
| macOS / FreeBSD ports | Low demand, no test hardware |
| Cloud-hosted multi-user service | Desktop-first; revisit after Phase 6 |
| Frequency-hopping follow | High CPU; plugin candidate |
| Full ML classifier | After heuristic classifier proves the UX (Phase 2) |

---

## 10. Appendix — legacy version targets (historical)

The original v0.7–v1.0 targets (digital monitor, Winlink, help system,
map system, settings, Linux port) are **complete or in-tree** as of
v0.12.0-alpha. The version arc going forward is organized by the phases in
§4 rather than the old per-tab milestones. v1.0.0 remains: signed installer,
full security audit, CI hardening (Bandit + pip-audit), complete docs,
public release.

---

*Supersedes the v0.7–v1.0 milestone roadmap. Update the status line and
phase markers each sprint; do a full reconciliation every 5th (housekeeping)
sprint.*
