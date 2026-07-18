# Squelch — Roadmap & Strategic Framework

> Canonical planning document. Read alongside `CLAUDE.md` (engineering
> context) before scoping any new work.
> Last updated: 2026-07-18 · Current build: v0.12.0-alpha · 2894 tests passing
>
> **State of play in one line:** the *engine* is largely built and tested
> (~20 headless analysis cores); the *cockpit* is not. The critical path is now
> the **Integration Layer (§4.5)** — surfacing those cores in the GUI — not more
> cores. See the Engine-vs-Cockpit status in §2/§3.

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

Status is now tracked on **two axes** because they have diverged sharply:
- **Engine** = the tested, headless core logic (`core/…`, `digital/…`).
- **Cockpit** = the user-facing GUI that drives that core in the running app.

| Pillar | Meaning | Engine | Cockpit |
|--------|---------|--------|---------|
| **SEARCH** | Wideband scan, energy detection, occupancy survey | 🟢 `occupancy` + `live_analysis.SurveyEngine` (rolling baseline) | 🔴 no survey view; `offer_frame` not called from the SDR stream |
| **IDENTIFY** | Classify a signal (allocation + modulation + DB match) | 🟢 `signal_classify` + `modulation_classify` + `sigid_db` + `freq_database` | 🔴 not wired to the live IQ/spectrum; no ID panel beyond the legacy sigid bookmark list |
| **CORRELATE** | Tie signals by ID/time/location; fingerprint emitters | 🟢 `emitter_correlate` + `signal_model.record()` merge | 🔴 no emitter view/overlay |
| **DECODE** | Voice + weak-signal + generic digital | 🟢 Voice (DSD+/OP25), FT8/WSPR (with UI); 🟢 generic `bitslicer`+`framing`+`linecoding`+`rds`+`ctcss` cores | 🟡 voice/FT8 have UI; 🔴 generic protocol workbench does not exist |
| **PLAYBACK** | Record & replay IQ, scrub captures | 🟢 `IQRecorder`/`IQPlayer` + `sigmf_io` codec | 🟢 record/scheduled-record in SDR tab; 🟡 no SigMF import/scrub UI |
| **ENCODE** | Build a waveform to transmit | 🟢 `encoder` (frame build + modulate → IQ) | 🔴 no build/replay UI |
| **TRANSMIT** | Key a TX-capable SDR / rig | 🟢 `transmit_iq()` + `authorize_tx` chokepoint (default-deny) | 🟢 TX Authorization settings tab; 🔴 no encode→TX pipeline surface; unvalidated on real TX hardware |
| **GEOLOCATE** | Direction finding, RSSI→GPS, TDOA, emitter mapping | 🟢 `digital/rfdf.py` (real, 195 L) + `df_track` + `emitter_correlate` | 🔴 no foxhunt panel, no RSSI heatmap / bearing / emitter map overlay |

Cross-cutting: **QUERY** (online "what's near here" + spot networks — 🟡
partial via PSKReporter/RBN/DX/SOTA-POTA) and **EDUCATE** (🟢 RF Lab mode).

**Read this table as:** the engine columns are almost all 🟢; the cockpit
columns are almost all 🔴. That gap *is* the roadmap now (§4.5).

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
Airspy, LimeSDR, BladeRF, Pluto via SoapySDR — RTL-SDR is the validated path;
SDRplay/RSP still needs the vendor SDK + `soapysdr-module-sdrplay`).

**Where the broadened vision actually stands (updated 2026-07-18):** the
*logic* for every pillar now exists and is tested — geolocation
(`rfdf`/`df_track`/`emitter_correlate`), generic decode + encode
(`bitslicer`/`framing`/`linecoding`/`encoder`), correlation
(`emitter_correlate`), survey/baseline (`occupancy`/`live_analysis`/
`rf_baseline`/`soi_snoi`), offline signal-ID (`sigid_db`/`freq_database`), and
the authorization-gated TX chokepoint (`authorize_tx` inside `transmit_iq`). So
the earlier "~50% delivered / greenfield" framing is obsolete. **The remaining
half is almost entirely integration and hardware:** none of the ~20 new cores
is imported by any `ui/` file yet (verified 2026-07-18 — zero GUI wiring), and
the TX chain is unvalidated on real transmit hardware. The work left is to
*surface* a finished engine, not to build more of it (see §4.5).

---

## 4. Phased roadmap (dependency-ordered)

Phases are ordered so each one unlocks the next. Version bands are targets,
not commitments.

> **⚠ The build order changed.** Phases 1–5 below built their *engine* cores
> ahead of their cockpits. That was the right call while working headlessly, but
> it has produced a large, tested engine with almost no GUI. **Do not start a new
> pillar core before its predecessors have a usable surface.** The Integration
> Layer (§4.5) is the P0 critical path; the per-phase "Cockpit remaining" notes
> below are its work-list.

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
  `signal_from_occupancy`; 18 tests). **Live-analysis pump DONE**
  (`core/live_analysis.py` `SurveyEngine`): `offer_frame(powers_db, center_hz,
  sample_rate)` — geometry matches `sdr_tab._on_samples`'s FFT — runs occupancy
  → drops SNOI / tags SOI → Signal records (optional store ingest) → folds each
  frame into a rolling `Baseline`; `snapshot()` / `compare_to(reference)` for
  the baseline-compare workflow. Never raises. 18 synthetic-frame tests.
  Remaining: the thin GUI wiring (call `offer_frame` from the sample callback +
  a survey/compare view) + a real SDR to drive it — HARDWARE-READY.
- ✅ **RF Baseline & Compare core DONE** (`core/rf_baseline.py`) — the founding
  "hound" feature (snapshot an environment, compare across time/location,
  surface anomalies = potential bugs / trackers / unauthorized transmitters).
  `baseline_from_spectrum()` snapshots noise floor + occupied segments (via
  occupancy); `Baseline.merge()` folds repeated sweeps; `compare_baselines()`
  diffs reference vs current → appeared / vanished / power-shifted signals +
  floor delta, honours SNOI ignore-ranges, labels anomalies via
  signal_classify; `anomalies_to_signals()` bridges to the unified store
  (source='anomaly'). JSON save/load. 19 tests. Remaining: live sweep capture
  + a compare UI.
- ✅ **SOI / SNOI watch-list core DONE** (`core/soi_snoi.py`) — the founding
  "signals of interest recorded; signals not of interest silently ignored"
  concept. A persistent `WatchList` of frequency rules (SOI = watch/prioritise,
  SNOI = ignore; SOI wins on overlap; optional modulation-family narrowing).
  `snoi_ranges()` plugs straight into `compare_baselines(ignore_ranges=…)`;
  `partition()` / `filter_out_snoi()` sort or drop any freq-bearing objects
  (Signal records, occupancy segments). JSON + cfg persistence;
  `with_common_snoi()` seeds broadcast/paging ignores. 20 tests. Remaining: a
  watch-list editor UI.
- ✅ **DONE (pending launch-test)** **Signal Browser** tab (`SIG-BROWSER`):
  presenter (`core/signal_browser.py`) + Qt tab (`ui/tabs/signal_browser_tab.py`,
  read-only table, search + source filter, CSV export, double-click→SDR tune,
  save/restore), registered as the 📶 Signals tab (shown in RF Lab mode).
  Source/contract tests pass headlessly; Qt round-trip tests run on a PyQt6
  machine — **launch-test before relying on it**.

### Phase 2 — Identify  ·  v0.14–0.15  ·  **P1**
- Write SigID-wiki matches onto Signal records (classification + confidence).
- ✅ **Offline signal-ID lookup DONE** (`core/sigid_db.py`): a data-source-
  agnostic engine that ranks candidate identities from a signal's (frequency,
  bandwidth, modulation) fingerprint. Ships an **original, factual** built-in
  table (public allocations / well-known traits) — no third-party catalogue is
  bundled. `import_entries()` / `from_json()` load a user-supplied SigIDWiki /
  Artemis export (attribution preserved), keeping Squelch clear of those
  catalogues' NonCommercial / ShareAlike terms. Ties `signal_classify` +
  `modulation_classify` together. 22 tests.
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
- 🟡 **Protocol framing inspector — preamble / sync / payload / CRC — core DONE**
  (`core/framing.py`): `inspect_frame(bits, sync_word, crc_bits)` → `FrameReport`
  (preamble/sync/payload/CRC fields + notes). Alternating-run preamble finder,
  sync-word search (bits/bytes/hex), and a generic bit-wise CRC engine with a
  registry (CRC-8, CRC-16/CCITT-FALSE, XMODEM, ARC, CRC-32) validated against
  the published "123456789" check vectors; `identify_crc()` reports which
  polynomial validates the payload. Pure Python, never raises; 28 tests.
  Remaining: a UI panel to visualise detected frames.
- ✅ **Line-coding decode/encode DONE** (`core/linecoding.py`): sits between the
  bit-slicer and the framing inspector — Manchester (IEEE 802.3 + G.E. Thomas,
  auto chip-phase, invalid-pair count), NRZI, and differential, each with a
  matching encoder so encode∘decode is the identity. Pure Python; 22 tests
  (round-trips + a Manchester→framing chain check).
- 🟡 **Encode — frame builder + modulator → IQ — core DONE**
  (`core/encoder.py`): the inverse of the decode chain. `build_frame()`
  assembles preamble + sync + payload + CRC; `modulate()` renders OOK/FSK/
  coherent-BPSK to complex-baseband IQ; `encode_iq()` is the one-shot →
  `EncodeResult`. Validated by encode→`slice_bits`→`inspect_frame` round-trips
  (OOK/FSK recover exactly with CRC ok; PSK up to its 180° ambiguity). 18
  tests. `result.iq` feeds `SoapyManager.transmit_iq()` — the AUTH-LAYER
  chokepoint — so the TX path is authorization-gated end to end. Remaining:
  a build/replay UI.
- Replay: captured IQ → TX (authorization-gated).
- ✅ **IQ ↔ SigMF codec DONE** (`core/sigmf_io.py`): pure `read_iq()` /
  `write_iq()` complementing the streaming recorder (`sdr/iq_recorder.py`).
  `read_iq()` parses `core:datatype` and normalises any common sample format
  (RTL-SDR cu8, HackRF ci8, ci16, cf32/cf64, LE/BE) to complex64 so foreign
  captures feed the decode / classify / survey cores; `write_iq()` persists an
  array (e.g. the encoder's output) as a `.sigmf-meta`+`.sigmf-data` pair for
  replay. Annotations supported. 16 tests incl. encode→write→read→slice→frame.
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

---

## 4.5 Integration Layer — surface the engine  ·  **P0 critical path**

This is where the next several sprints should go. ~20 tested cores exist with
**zero** GUI wiring (verified 2026-07-18). Each item below turns finished engine
logic into a usable feature. Ordered by value × unblocking. Every item needs a
**launch-test session** (running app + RTL-SDR) — offscreen Qt cannot verify
pyqtgraph render or feel, and blind UME builds have twice corrupted real user
data (see CLAUDE.md conftest guards). Build them build → user-screenshots → fix.

| # | Integration item | Cores surfaced | Priority | Notes |
|---|------------------|----------------|----------|-------|
| **I-1** | **Survey / Baseline "hound" panel** (flagship). 🟡 **Data path DONE** (2026-07-18, `add48ae`): `ui/tabs/sdr_survey.py` `_SDRSurveyMixin` — a Survey toggle in the SDR toolbar drives `SurveyEngine.offer_frame` (throttled, off the plot timer so the RX thread stays pristine) → detections stream to the Signal Log + fold into a rolling baseline; `survey_snapshot` / `survey_compare` / `survey_reset` exposed; 15 tests. **Cockpit remaining:** the *view* — live occupancy/detections list, baseline **snapshot / save / load**, **compare → anomaly table** (appeared / vanished / power-shifted), SNOI-filtered — needs a launch-test session (offscreen Qt can't verify render). | `live_analysis`, `occupancy`, `rf_baseline`, `soi_snoi`, `signal_model` | **P0** | The founding counter-surveillance workflow; first vertical slice that makes the whole stack demonstrable. Signal Log tab already receives records. |
| **I-2** | **SOI / SNOI watch-list editor** — add/edit frequency rules (watch vs ignore, modulation narrowing); feeds I-1's compare + partitions the Signal Log. | `soi_snoi` | P0 | Small; unblocks I-1's noise suppression being user-controllable. |
| **I-3** | **Foxhunt / DF panel + map overlays** — live GPS (`core/gps.py`) + SDR RSSI → `DFTrack`; bearing readout, RSSI→GPS **heatmap overlay**, estimated-emitter markers, **emitter map overlay** from `correlate_from_store`. | `df_track`, `rfdf`, `emitter_correlate`, `gps` | **P0** | Phase-3 flagship; the biggest differentiator (KrakenSDR-class single-RX DF). |
| **I-4** | **Decode / Encode workbench** — one panel that chains `modulation_classify → bitslicer → linecoding → framing` on a live/loaded IQ selection (preamble/sync/payload/CRC visualised), and the inverse `encoder` build → (auth-gated) replay/TX. | `bitslicer`, `framing`, `linecoding`, `encoder`, `modulation_classify`, `sigmf_io` | P1 | URH-class surface; the "flag a freq → record → decode by talkgroup/time/freq" north-star the user restated. |
| **I-5** | **Live signal-ID on the spectrum** — wire `modulation_classify`+`sigid_db`+`freq_database` to the live IQ/spectrum so clicking/annotating a signal shows candidate identity + who's scheduled on that channel; replaces the legacy static bookmark list. | `sigid_db`, `freq_database`, `signal_classify`, `modulation_classify` | P1 | Needs the live feature-extraction path (the stream). |
| **I-6** | **SigMF import / scrub** — load a foreign `.sigmf`/`.wav`/`cu8` capture, scrub it, and run it through I-4/I-5 offline (no hardware needed to demo the whole decode/ID stack). | `sigmf_io` | P1 | Also the easiest way to launch-test I-4/I-5 without live RF. |
| **I-7** | **Frequency-database overlay + RDS/CTCSS readouts** — import EiBi/Aoki/HFCC, label the spectrum by station; live RDS (FM) and CTCSS (FM audio) readouts where the demod path already exists. | `freq_database`, `rds`, `ctcss` | P2 | RDS/CTCSS still need the last-mile live bitstream/audio tap. |

**Sequencing:** I-1 → I-2 first (they make the flagship real and are the origin
"hound" spec). I-3 next (Phase-3 flagship). I-4/I-5/I-6 form the decode/ID
workbench cluster — I-6 is the cheapest launch-test harness for the other two.
I-7 is polish.

**Definition of done for an integration item:** the core is imported and driven
from a `ui/` surface; save/restore where stateful; theme tokens (no dark hex);
launch-verified by the user against real hardware or a real capture; a Qt smoke
test that skips clean headlessly.

---

### SDR-app parity — user-requested (from an SDR Console session, 2026-07-05)
Feature targets inspired by SDR Console v3.3, with an honest feasibility read
so we sequence them realistically (not all are quick, and several need hardware):
- ✅ **Frequency database core DONE** (`core/freq_database.py`): schedule-aware
  "who's on this channel?" lookup. `FreqDatabase` of `FreqEntry` rows;
  `import_eibi()` parses the EiBi shortwave CSV, `import_csv()` maps arbitrary
  catalogues (Aoki/HFCC/FMLIST/custom); `lookup(freq, utc)` returns nearby
  active stations (UTC on/off windows incl. midnight wrap). No catalogue data
  bundled — user-downloaded, `source` attribution preserved (sigid_db posture).
  23 tests. Remaining: a UI (import button + spectrum station labels).
- ✅ **FHSS detection — detector DONE** (`core/fhss_detect.py`): over the survey
  output `[(t, freq), …]`, channelises → counts channel transitions → measures
  peak *simultaneity* (a hopper is on ~one channel at a time; N static signals
  are all present at once) → returns a `HopSet` (channels, hop rate, dwell,
  span) with a `to_signal()` bridge (source='fhss'). Cleanly separates a hopper
  from several static carriers. 15 tests. Full hop-*following* (retune to stay
  on it) still needs hardware + control path (P2).
- **DSSS detection / despread** → **research-tier.** Detecting below-noise
  spread-spectrum energy is feasible; despreading needs the PN code. Later. P2.
- **Trunk voice following** (P25 / DMR trunked control-channel → voice, like
  SDR Console's "Trunk Voice Following") → extends the existing DSD+/OP25
  digital-voice bridges; needs control-channel decode + fast retune + hardware.
  Substantial, multi-sprint. P2.
- **Richer map styles** — SDR Console-style world-map options for the Map tab.
  Small/cosmetic. P2.

Fuller inventory from the SDR Console v3.3 screenshots (captured so nothing is
lost — not all wanted, listed as inspiration; ✓ = Squelch already has some form):
- **Frequency Database overlay** — load Aoki / EiBi / HFCC / FMLIST / ILGRadio /
  MWLIST / custom CSV; annotate the spectrum with station IDs by frequency
  (columns: Freq/Station/Call-ID/Lang/TX Country/On/Off/Days/Target/Notes/Source).
  Ties into `sigid_db`. P1.
- **Band & time favourites bar** — one-click jump to amateur bands (2200m→70cm/
  23cm) + broadcast bands (LW/MW/tropical/SW 120m→16m) + time stations
  (WWV/RWM). Quick-dial exists for rig ✓; add an SDR band-jump bar. P2.
- **Multiple simultaneous receivers** (Multi-Band / Matrix) — several demods on
  one device at once. Bigger DSP/UI lift. P2.
- ✅ **RDS decode — protocol core DONE** (`core/rds.py`): the RDS/RBDS data on
  FM broadcast. `make_block`/`check_block` (CRC-10 g(x)=x^10+x^8+x^7+x^5+x^4+
  x^3+1 + A/B/C/C'/D offset words), `bits_to_groups` synchroniser,
  `decode_group`, and `RDSDecoder` accumulating PS name / RadioText / PI / PTY
  (RBDS table). Round-trip tested (encode groups → sync → decode). 15 tests.
  Remaining (live): recover the RDS bitstream from FM IQ (FM-demod → 57 kHz
  bandpass → biphase DBPSK @1187.5 bps → differential) and feed
  `bits_to_groups`.
- **Built-in digital decoder** — Squelch bridges DSD+/OP25 ✓; SDR Console has an
  integrated one. Keep bridging.
- **Display modes** — spectrum persistence/histogram, 3D waterfall, audio
  waterfall, continuum mode, signal history, smoothing/windowing options,
  peaks (max/shaded). Squelch has waterfall + peak-hold ✓; persistence/3D/
  audio-waterfall are new. P2/P3 polish.
- **QO-100 / transverter TX** with a TX meter panel (PWR/SWR/DRV/IPA/VDD/ALC) —
  relevant once the TX chain + LO-offset are live (LO offset exists ✓). P2.
- **Scheduler + data/video record + datafile (IQ) editor** — Squelch has
  scheduled + IQ record/playback ✓ and the new SigMF codec; a recorded-IQ
  editor/annotator would extend it. P3.
- Already-covered overlaps: DX cluster ✓, scanner ✓, band plan ✓, screenshot ✓,
  IQ record/playback ✓.

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
| **P0 — now** | The critical path; unblocks everything user-visible | **Integration Layer §4.5** (surface the finished cores — Survey/Baseline I-1, SOI/SNOI editor I-2, Foxhunt/DF I-3) |
| **P0 — gate** | Hard prerequisite already met | Authorization layer (Phase 5 gate — DONE; keeps blocking any TX feature) |
| **P1** | High value, follows the P0 integration | Decode/Encode workbench (I-4), live signal-ID (I-5), SigMF scrub (I-6) |
| **P2** | Valuable, later | Freq-DB/RDS/CTCSS surfacing (I-7), Phase 6 (online query, multi-node), SDR-parity extras, crowd sensor map |
| **Ongoing** | Continuous | SDR breadth + real-TX validation, filters UX, education labs, code health, security hardening |

Sequencing rule (revised 2026-07-18): the engine got ahead of the cockpit, so
the rule is now **surface before you build.** Do not start a new pillar *core*
until the previous pillar has a usable GUI surface. The one exception is a pure
core with no live dependency that is genuinely blocking a launch-test — but
those are exhausted (§3). When in doubt, wire something up.

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
   - ✅ **First-run legal acknowledgment DONE** (`DISCLAIMER.md` +
     `core/legal.py` + `ui/legal_ack.py`): a version-stamped, plain-language
     terms-of-use / disclaimer shown once at first launch (RX/TX legality is
     the user's responsibility, no authorization granted, third-party-data
     licences are the user's responsibility, GPL no-warranty). Declining quits
     the app; acceptance persists and re-prompts only if the disclaimer version
     is bumped. Third-party signal catalogues are never bundled (`core/sigid_db`
     ships original factual data only) — see NOTICE.
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

## 13. Best-in-class gaps (new scope — 2026-07-18 pass)

To be *the* tool for RF exploration + counter-surveillance (not just a bag of
capable cores), these are missing and worth adding. They are curated, not
speculative — each closes a real workflow gap the current backlog doesn't cover.

### 13.1 Capture sessions / project files — **P1, high leverage**
The hound workflow is inherently multi-artifact and comparative: baseline +
Signal records + IQ captures + watch-list + notes, captured at a place/time, and
**compared against another place/time**. Today these live in separate stores
with no way to snapshot "the survey I did at location A" as one thing.
- 🟡 **Baseline library DONE** (2026-07-18, `ee29b1c`): `core/survey_session.py`
  `SurveyStore` — a folder of saved `Baseline` JSON files with save / list /
  load / delete + `compare(ref_id, live)` / `compare_ids(a, b)` (path-traversal
  guarded, never-raises); wired to `SDRTab` as `survey_save_baseline` /
  `survey_saved_baselines` / `survey_compare_saved`. This is the persistence the
  I-1 compare view drives; 22 tests. **This delivers the "compare location A
  (saved) vs here (live)" core** of the hound workflow.
- [ ] Extend to a full **`.squelch` session/project file** bundling not just the
  baseline but the run's Signal records, referenced IQ captures (SigMF paths),
  the active watch-list, GPS track, and free-text notes — one savable/loadable
  unit.
- [ ] **Compare two whole sessions** (baseline diff + emitter diff + notes).
- [ ] Reuses existing cores (`survey_session`/`rf_baseline` JSON, `signal_model`,
  `df_track` save/load, `soi_snoi` persistence) — a container + a compare view.

### 13.2 Sweep / anomaly report export — **P1**
A survey that finds something should produce an artifact a user can keep or hand
off.
- 🟡 **HTML / text report DONE** (2026-07-18, `17db00d`): `core/survey_report.py`
  turns a `BaselineDiff` into a self-contained HTML or plain-text/markdown report
  (header: title / when / location / reference→current / floor delta / anomaly
  count; sections: appeared / power-changed / vanished with freq / BW / peak / Δ /
  label / category). All RF-derived strings HTML-escaped at the render chokepoint
  (map-XSS lesson). `diff_rows()` also feeds CSV/table consumers. Wired to
  `SDRTab.survey_export_report(path, diff, fmt, location)`; 12 tests.
- [ ] PDF output + an occupancy/waterfall thumbnail (needs the render surface).
- [ ] Ties to 13.1 (report a whole session) and the Signal Log CSV export.

### 13.3 Live alerting — **P1**
The counter-surveillance and monitoring use cases want to be *told* when
something changes, not to stare at a waterfall.
- 🟡 **Alert policy DONE** (2026-07-18, `2a10853`): `core/survey_alert.py`
  `AlertMonitor` — SOI-active (watch-list), novel-emitter (off by default), and
  anomaly-vs-baseline triggers, each toggleable; per-(kind, freq-bucket) cooldown
  debounce + optional min-peak gate; `from_cfg` (`survey.alert.*`); pure, never
  raises. Wired into the survey pump (`_survey_tick` runs detections through it,
  logs + rings fires into `survey_recent_alerts()`). 19 tests.
- [ ] **Notification surface** — a visual banner + optional sound on the SDR/
  survey view reading `survey_recent_alerts()` (needs the view / launch-test).

### 13.4 Waterfall-shape fingerprinting for signal ID — **P2, real gap**
`sigid_db` matches on (frequency, bandwidth, modulation) only. SigIDWiki/Artemis
identification — and the origin spec — key heavily on the **visual waterfall
shape** (sweep, ticks, hash marks, hop pattern). This is the single biggest
accuracy gap in IDENTIFY.
- [ ] Extract shape features (bandwidth profile, symbol/tick cadence, hop
  structure via `fhss_detect`, on/off duty) into the `sigid_db` fingerprint so
  matches use shape, not just freq/bw/mod. Optional: a small template/thumbnail
  match. Keeps the "original factual data only, no bundled catalogue" posture.

### 13.5 Retention / scale hygiene for long surveys — **P2**
A multi-hour survey streams a large number of Signal records into SQLite via the
pump. Left unbounded, the store and Signal Log degrade.
- [ ] Configurable **retention / dedup / decimation** policy on `SignalStore`
  (age-out, merge near-duplicates harder, cap rows) so a long hound run stays
  responsive. `record()` already merges repeats — extend with a retention pass.

> These join the §12 operator-vision backlog and the §4.5 Integration Layer.
> Priority order across all three: finish §4.5 I-1…I-3 first (surface what
> exists), then 13.1–13.3 (make the hound workflow complete and shareable),
> then the P2 depth items.

---

## 14. SDR-Console parity (new scope — 2026-07-18 pass)

Benchmarked against **SDR Console V3** (SDR-Radio.com, Simon Brown G4ELI) — the
most feature-complete Windows SDR receiver app — to find what a best-in-class
receiver has that Squelch lacks. SDR Console headline features: up to **24
parallel receivers** (matrix view), **Signal History** (band-power sampled every
50 ms, 3-speed scroll-back display, CSV export), multi-format **recording +
playback** (IQ RAW, WAV/MP3/MP4) with a **scheduler** and reverse/fast-forward,
full DSP chain (NB/NR/AGC/notch, per-mode filter sets), **markers/annotations**,
memories/favourites, satellite tracking, external-radio (CAT) control, and a
**Console Server** for remote operation.
Sources: [sdr-radio.com/console](https://www.sdr-radio.com/console) ·
[rtl-sdr.com — Signal History & Receiver Panes](https://www.rtl-sdr.com/sdr-console-v3-latest-update-signal-history-receiver-panes/).

**Gap analysis** (✅ have · 🟡 partial · ❌ gap). Squelch already matches most of
the single-receiver surface: wideband spectrum+waterfall (MHz axis, palettes,
click-tune, span), demod modes + auto-demod + IF-BW + draggable passband, NB/NR/
AGC/squelch, LO offset, scanner, IQ record + scheduled record, signal-ID panel,
S-meter, memories, satellite Doppler, demod profiles.

| # | SDR-Console feature | Squelch today | Action | Build w/o SDR? | Pri |
|---|---------------------|---------------|--------|:---:|:---:|
| 14.1 | **Universal IQ playback** (play any capture) | ✅ **DONE** (2026-07-18, `196357a`) — `IQPlayer` datatype-aware via `sigmf_io.bytes_per_sample`/`decode_iq_bytes` (cu8/ci8/ci16/cf32/cf64, LE/BE); raw `.iq/.bin` format picker; fixed `Recording.from_meta_file` duration bug (was cf32-only). The whole app now runs on **downloaded SigMF/RTL-SDR captures — no dongle**. 12 tests | **YES** | **P0** |
| 14.2 | Reverse / fast-forward playback | 🟡 FF via speed≤4×; no reverse | add reverse + scrub in the playback transport | YES (core) | P1 |
| 14.3 | **Signal History** (band-power over time, scroll-back) | 🟡 **data layer DONE** (2026-07-18, `1aec06d`) — `core/signal_history.py` `SignalHistory`: wideband + per-channel peak/mean band-power per frame, rolling caps (count+age), window/series read-back, CSV export (csv_safe). Wired into the survey pump; channels auto-seeded from watch-list SOI; `SDRTab.survey_history_*`. 13 tests. **Remaining: the scroll-back plot/display** (launch session) | data layer YES | **P1** |
| 14.4 | **Multiple receivers** (N parallel demodulators, matrix) | ❌ single VFO | a multi-demodulator engine (N channels tap one IQ buffer; each own freq/mode/BW/squelch/record). Engine headless-testable w/ synthetic IQ; matrix UI needs launch | engine YES | **P1** |
| 14.5 | Auto-notch + manual notch filters | 🟡 have NR/NB; no notch | notch DSP cores (auto-notch = adaptive; manual = fixed bins), testable w/ synthetic audio | YES | P2 |
| 14.6 | Markers / annotations (peak, delta, channel power, OBW) | 🟡 `core/measure.py` exists, not wired | wire markers onto the spectrum (peak/delta, channel-power, occupied-BW readouts) | core YES, UI launch | P2 |
| 14.7 | Audio (demod) recording → WAV/FLAC | ❌ (IQ only) | record demod audio to WAV; small logic + toolbar button | mostly YES | P2 |
| 14.8 | Per-mode filter sets / bandwidth presets | 🟡 demod profiles exist | extend profiles into full per-mode filter sets | YES | P3 |
| 14.9 | **Console Server** — remote receiver over network | ❌ | maps to `NODE-SENSOR` (Phase 6): stream IQ/spectrum from a headless node to a client. Large, network | partial | P2 |
| 14.10 | MIDI / hardware controller tuning | ❌ | optional: map a MIDI controller to VFO/gain | YES | P3 |
| 14.11 | **Simulated signal source** (no-hardware demo) | ✅ **DONE** (2026-07-18, `5606697`) — `sdr/sim_source.py` `SimSource`: synthetic wideband IQ (noise floor + offset signals, one pulsing on/off) on the SoapyManager `on_samples` interface; offered as a "Simulated signal (no hardware)" virtual device (Connect → live waterfall + survey/history/alerts react). 12 tests | **YES** | **P1** |

**Sequencing:** 14.1 first (it's the enabler — turns "no SDR" into a non-issue and
lets the flagship survey/hound view be exercised on real captures). Then 14.3
(signal history) and 14.4 (multi-VFO engine) as the two biggest capability adds,
both with headless-buildable cores. 14.5–14.7 are self-contained depth items.
14.9 (server) is the Phase-6 `NODE-SENSOR` story.

> **No-hardware development note:** with 14.1 (universal playback) and 14.11
> (simulated source) done, Squelch is fully usable, demonstrable, and
> launch-testable with **zero hardware** — either play a downloaded SigMF /
> RTL-SDR capture, or pick the built-in "Simulated signal" device for a live
> synthetic spectrum. Every core (survey, signal-ID, decode, classify,
> DF-from-file) can be exercised without a dongle. This is the key that unlocks
> the whole platform for a no-SDR user AND makes the flagship survey view
> demoable end-to-end.

---

*Supersedes the v0.7–v1.0 milestone roadmap. Update the status line and
phase markers each sprint; do a full reconciliation every 5th (housekeeping)
sprint.*
