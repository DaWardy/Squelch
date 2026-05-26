# Squelch — Changelog

All notable changes documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]
Changes not yet in a tagged release.

---

## [0.11.16-alpha] — 2026-05-26

### QA/QC gate strengthened (root cause of recurring crashes)

Added tests/test_method_references.py — a new static analysis gate that
parses every UI file's AST and verifies every `.connect(self._x)` has a
matching method definition. Runs without Qt. This exact check would have
caught every crash in this release before it shipped.

### Fixed (crashes that reached the user — all caught by new gate)

- **Rig tab crash: 'RigTab' object has no attribute '_toggle_split'** —
  a duplicate .connect() call to the old name survived from before the
  rename to _on_split_toggle. Removed the stale wiring.

- **SDR tab crash: not enough values to unpack (expected 4, got 3)** —
  three setup-path step tuples had 3 elements where the loop expected 4.
  Added the missing None fourth element to each.

- **Winlink tab crash: 'WinlinkTab' object has no attribute '_connect_hf'** —
  six methods were connected to UI buttons but never implemented:
  _connect_hf, _connect_fm, _clear_compose, _send_message,
  _refresh_gateways, _populate_gateways. All added with real behaviour.

- **DXClusterClient has no attribute 'start'** — DXClusterClient had
  fetch_async() but no start()/stop() polling loop. HamAlertClient had
  one; added the same pattern to DXClusterClient so both have a
  consistent interface.

### Added
- Help tab: KiwiSDR info (remote web SDRs + VAC-to-Digital-tab workflow)
  at the user's request. Low priority, informational only.

---

## [0.11.15-alpha] — 2026-05-26

### Consumer pipeline

**C-03 Hank (P1) — VFO A/B + Split + TX VFO display**
- New "VFO A / B" panel on the Rig tab showing both VFO frequencies
  side by side with live MHz readout.
- A↔B swap button (calls Hamlib G command).
- Split toggle: OFF = simplex TX on A; ON = RX on A, TX on B. The TX
  VFO indicator (▶) moves to show exactly which VFO will key the rig —
  amber on B to make split state unmistakable (C-08, no unexpected TX).
- VFO B frequency is fetched in a background thread on swap/refresh so
  the UI never blocks.
- core/rig.py: added get_vfo_b_freq() and set_vfo_b_freq() (brief VFO
  switch, read, switch back — transparent to the operator).

**Rig tab duplicate sections (user feedback)**
- The Status group was showing Port and Rig Model labels that were also
  visible in the Connection group directly below it. Removed the
  duplicates from Status; it now shows only runtime state (● Connected /
  Disconnected / TX) and the S-meter — the things that change while
  operating. Configuration (model, port, baud) remains in Connection.

**C-05 Tyler (P2) — Map land masses**
- The continent outlines were drawn as data but the rendering loop was
  missing — the method defined the polygon coordinates and returned
  without drawing them. Added the QPainter drawPolygon loop that
  converts lat/lon to pixel coordinates. Continents now appear as dark
  green fills with outline on the fallback map alongside the grayline
  and station marker.

---

## [0.11.14-alpha] — 2026-05-26

### Security / Source vetting
- Audited every URL and binary source the installer recommends. All verified
  as US/EU open-source projects (Hamlib, WSJT-X, Fldigi, MyriadRF/SoapySDR,
  Ettus, Airspy, Zadig, VB-Audio, VARA/EA4HWT, Python.org). Full vetting
  comment block added to installer.py for transparency.
- DSD+ flagged throughout (installer, install_check, help) as closed-source
  with an anonymous developer that cannot be independently audited. The
  open-source alternative (github.com/szechyjs/dsd) is noted.
- Fixed wrong RTL-SDR download URL: was github.com/airspy/airspyone_host
  (outdated); corrected to github.com/rtlsdrblog/rtl-sdr-blog (official
  RTL-SDR Blog drivers, MIT licensed).

### Fixed
- Right-click "Copy section text" on any label now gathers all visible label
  text in the surrounding panel and copies it as one block — solving the
  "can only highlight title OR body, not both" troubleshooting friction. The
  standard Qt cross-widget drag-select limitation remains, but this gives
  a practical one-click workaround for pasting full error/status blocks.
- Windows taskbar icon: added SetCurrentProcessExplicitAppUserModelID call
  before the first window is shown (guarded win32-only, P2). Also now loads
  the multi-resolution .ico on Windows and falls back to .png on Linux/macOS.

---

## [0.11.13-alpha] — 2026-05-25

### Added
- **UI-wide metric/imperial units toggle** (Settings -> Appearance -> Units).
  New core/units.py centralizes formatting; distances and altitudes across the
  app honor the pref. Local RF distances, the radius spinbox suffix, and the
  search status now switch between km and miles; the radius is converted back
  to km internally so filtering stays correct. Tests in tests/test_units.py.
- **Manage Operator Profiles dialog** — the profile dropdown next to the
  callsign now has "Manage profiles…" (rename/delete) in addition to
  "+ New profile…". Switching a profile updates the displayed callsign and,
  because operating_callsign() reads the active config, the correct callsign
  is used on transmit (logged on switch for transparency).

### Fixed
- **Dropdowns clipped their text.** Every QComboBox now sizes to its content
  (AdjustToContents) and its popup is widened to the longest item, so labels
  like "SDRplay RSP2Pro / RSP1A…" are no longer cut off.

---

## [0.11.12-alpha] — 2026-05-25

### Fixed
- **Help search returned nothing** for partial terms like "ic". It used
  exact word-membership, so "ic" never matched "IC-7100". Now uses substring
  matching with a title-hit bonus — "ic", "7100", "ft8" all find their articles.
- **conda SDR driver install failed** with PackagesNotFoundError. Root cause:
  wrong package names (soapyrtlsdr, soapyuhd, soapyairspy). The real
  conda-forge names are soapysdr-module-rtlsdr, soapysdr-module-hackrf,
  soapysdr-module-sdrplay, soapysdr-module-uhd, soapysdr-module-airspy,
  soapysdr-module-lms7. Corrected all. Drivers now install one at a time, so
  an unavailable package (UHD/Airspy can be Linux-only on conda-forge) no
  longer fails the whole batch — the others still succeed and the installer
  reports which worked.

### Changed (consumer: "FT8 means all applicable modes")
- Added core.guest_op.operating_callsign(cfg) as the single source of truth
  for the identifying callsign across ALL modes (FT8/FT4/JS8/PSK/RTTY/CW/SSB/
  Winlink). Guest operator's call when active, else station call. FT8 now
  delegates to it; the CQ log line uses it.

### Docs
- Help -> SDR Setup documents the conda / miniforge path (easier than
  PothosSDR) with correct soapysdr-module-* names.

---

## [0.11.11-alpha] — 2026-05-24

### QA/QC — the big one (ops: broken builds were reaching the customer)
- **Added a mandatory pre-package quality gate: `qa_check.py`.** It runs
  syntax compile, pyflakes undefined-name detection, the full test suite, and
  a headless tab smoke test. No release zip is built unless it exits 0. This
  directly addresses the missing QA/QC: every crash below would have been
  caught before packaging.
- **tests/test_no_undefined_names.py** — pyflakes gate (runs everywhere, no Qt
  needed) catching the recurring NameError class.
- **tests/test_tab_smoke.py** — builds MainWindow + every tab under offscreen
  Qt; names the exact failing tab. Runs on the dev box and in CI.
- CI now runs pyflakes; requirements-dev.txt added.

### Fixed (crashes that reached the user)
- **modes tab:** `NameError: _hold_tx_cb` — missing `self.` (tooltip edit).
- **SDR tab:** `NameError: _sep` — helper used but not defined in the module.
- **winlink tab:** `NameError: _vsep` — same, added the helper.
- **Latent crashes pyflakes then caught:** winlink used QTreeWidget/
  QTreeWidgetItem/QColor without importing them; localrf and core/location
  used `Path` with no import (and one `__future__` import was out of order);
  log_tab's `csv_safe` import had been swallowed into the module docstring;
  band_conditions used gray_line helpers without importing; rig_tab called
  `_on_connect_standard(self)` instead of `self._on_connect_standard()`.
  All fixed; pyflakes now reports zero undefined names.

### Fixed (usability from feedback)
- **Installer asked to close twice** — removed the redundant `pause` from the
  .bat files; installer.py holds the window once.
- **About box** no longer claims IC-7100 only; now lists multi-rig CAT
  (Icom/Yaesu/Kenwood via Hamlib) and all supported modes.

---

## [0.11.10-alpha] — 2026-05-24

### Changed (important conceptual fix)
- **Separated Guest Operator mode from Demo mode.** Earlier versions wrongly
  made "Guest Operator mode" disable all transmit — that is *demo/lecture*
  behavior, not what a guest operator needs. They are now two distinct things:
  - **Demo Mode** (View -> Demo Mode): disables ALL transmit for lectures and
    demos with zero risk of keying the rig. This is Elena's C-06. Shows an
    amber "DEMO MODE — transmit is disabled" banner.
  - **Guest Operator** (View -> Guest Operator...): for a **student or
    visiting operator** actually getting on the air (supervised). Transmit
    stays ENABLED. They enter their own callsign, which is then used for
    identification, and the station callsign is kept for correct IDs/logs.
    Shows a blue "GUEST OPERATOR: <call> operating <station>" banner.

### Added (C-15 — students/visitors)
- **core/guest_op.py**: guest-operator support with a NATO-phonetic speller
  and a **read-aloud voice contact script generator**. The Guest Operator
  dialog shows a friendly, step-by-step script (calling CQ, answering,
  exchanging, and ending with correct identification) with the guest's
  callsign spelled phonetically — exactly what a nervous student needs for a
  first voice QSO.
- **FT8 now identifies with the guest operator's callsign** when a guest is
  active (`_operating_call()`), falling back to the station call otherwise.
- Tests: tests/test_guest_op.py (4) including an explicit check that Guest
  Operator mode does NOT block transmit (only Demo mode does).

### Migration
- The TX-block now lives under config key `demo.mode` (was
  `classroom.lab_mode`). `safety.set_guest_mode()` remains as a deprecated
  alias for `set_demo_mode()`.

---

## [0.11.9-alpha] — 2026-05-24

### Fixed (crash)
- **`AttributeError: ClickableLabel object has no attribute
  _apply_saved_guest_mode`** on startup. The Guest-mode startup call was
  accidentally inserted into ClickableLabel.__init__ instead of
  MainWindow.__init__ (an edit landed in the wrong class). Moved it to the
  correct place at the end of MainWindow.__init__.

### Added (Linux / Debian support — new platform reviewer)
- Added a **Linux / Debian Systems Programmer** to the review panel
  (docs/DESIGN_REVIEW.md) with platform rules P1-P5, and audited the
  codebase against them. This ensures Squelch plays nice on Debian-based
  systems (Debian, Ubuntu, Mint, Raspberry Pi OS).
- **External-tool detection now works on Linux.** install_check.py only
  scanned Windows paths; it now also uses `shutil.which()` with Linux
  binary names (wsjtx, fldigi, rigctld, js8call, dsd), so tools installed
  via apt in /usr/bin are found. (P3)
- **Serial permission diagnostics.** On a Linux serial-connect failure,
  Squelch now detects whether you're missing from the `dialout` group and
  tells you the fix (`sudo usermod -aG dialout $USER`, then re-login)
  instead of a cryptic error. (P4)
- **docs/INSTALL_LINUX.md** — full Debian/Ubuntu/Raspberry Pi install guide
  (apt packages, dialout, RTL-SDR DVB-T blacklist, XDG dirs, Pi notes).
- **setup/squelch.desktop** launcher for Linux application menus, and the
  installer now makes generated `.sh` launch scripts executable. (P5)

### Verified
- Config/data already use XDG dirs (~/.config/squelch); candidate path lists
  in launcher/fldigi/location already include Linux paths; no unguarded
  Windows-only APIs. (P1/P2)

### Pipeline (C-09, C-02)
- C-09 (Marcus): app now restores the last-used tab on launch (window
  geometry was already restored).
- C-02 (Dorothy): first-run wizard now includes a radio-selection step
  (from the real preset list) in addition to callsign and location.

---

## [0.11.8-alpha] — 2026-05-23

### Fixed / Changed (consumer C-04, Marcus — Local RF)
- **RepeaterBook integration was calling a proximity endpoint that does not
  exist.** Verified against RepeaterBook's current API docs: there is no
  public lat/lon/radius endpoint; the supported method is to query by
  `country` + `state_id` (FIPS) and filter distance locally. Rewrote
  `nearest_repeaters` to do exactly that — reverse-geocodes the location to
  a US state, queries the correct endpoint, and filters/sorts by a local
  haversine distance.
- **RepeaterBook now requires an approved API token (policy change, March
  2026).** Added a RepeaterBook API-token field under Settings -> Credentials
  (stored in the OS keyring, rule S4). When no token is set, Local RF no
  longer fails silently — it shows a clear message with the application link
  (repeaterbook.com/api/token_request.php) instead of an empty table.
- **Configurable search start point (Marcus's actual ask).** Local RF now has
  a "From" field — enter a grid square, ZIP, or city to search from a
  location other than your station. Blank uses your configured location.
- The search request and the geocode lookups are recorded in the Network
  Activity log (C-12) as USER-initiated.

### Notes
- This requirement is *partially* delivered: the code is correct and the UX
  guides the operator, but actually fetching repeaters depends on the user
  obtaining their own RepeaterBook token (free for non-commercial use).
  Documented in docs/PRODUCT_FEEDBACK.md under External Dependencies.

---

## [0.11.7-alpha] — 2026-05-23

### Added (security / consumer C-12, Priya)
- **Network Activity log.** New `core/netlog.py` records every outbound
  connection — timestamp, host, purpose, and whether it was AUTO
  (app-initiated) or USER (you clicked) — to `logs/network.log` and an
  in-app viewer under **Help -> Network Activity**. Credentials are redacted.
  This directly serves Priya's work-use requirement: on a client network she
  can prove exactly what Squelch contacted and that there are no unsolicited
  beacons (rule S9).
- The three automatic network calls are now explicitly recorded as AUTO:
  IP geolocation (grid auto-fill), NOAA solar/band conditions, and Celestrak
  satellite TLEs. Everything else is USER-initiated and tagged as such.
- Tests: `tests/test_netlog.py` (4) covering recording, AUTO/USER
  classification, credential redaction, and never-raises behavior.

### Docs
- SECURITY.md documents the network-transparency model.
- PRODUCT_FEEDBACK.md: C-12 shipped; C-13 (SigMF capture export) remains open.

---

## [0.11.6-alpha] — 2026-05-23

### Fixed (safety — important)
- **FT8 auto-transmit was not covered by the safety gate.** FT8 is an
  auto-transmit mode: once auto-sequence or auto-CQ is armed, the engine
  keys the rig on its own — it does not go through the manual CQ button that
  v0.11.5 gated. The real funnel is `FT8Engine._queue_tx`, which handles
  every transmission (manual CQ, signal report, RRR, 73, auto-CQ). The safety
  check now lives there, so Guest Operator mode and unsafe states block ALL
  FT8 TX including the automatic steps. (Raised by consumers Tyler + Elena;
  enforced by Security/Pentester.)

### Added
- **ON-AIR indicator on the FT8 panel (C-11, Tyler).** A large, color-coded
  banner shows "RECEIVING" (green) or "ON THE AIR — TRANSMITTING" (red),
  driven by the engine's real sequence state — so the operator can always
  tell at a glance whether the rig is keyed. Important precisely because FT8
  transmits automatically.

### Pipeline (docs/PRODUCT_FEEDBACK.md)
- Added **Priya**, a Pentester / Security Engineer who is also a *consumer*:
  she uses Squelch for paid RF/security work, so her requirements (no beacons
  on a client network, reproducible SigMF captures, audit trail) feed the
  backlog. The Security Engineer and Pentester are documented as dual-role —
  on the DevSecOps team enforcing S1–S9 AND on the consumer side. Security
  review is represented on both sides of the pipeline, never optional.
- Updated **Tyler's** profile: digital modes (FT8/FT4/JS8) are his main
  activity, and he specifically wants to know when he's transmitting.
- Filed C-11..C-14; shipped C-11 and C-14 this release.

---

## [0.11.5-alpha] — 2026-05-23

### Added
- **docs/PRODUCT_FEEDBACK.md** — a consumer feedback pipeline. Six customer
  personas (Hank, Marcus, Elena, Sam, Dorothy, Tyler) file requirements and
  comments that flow to the DevSecOps team (Programmer, Security Engineer,
  Pentester) who triage, build, and sign off. Includes a prioritized
  requirements backlog (C-01..C-10) and a shipped log.
- **Guest Operator mode now actually blocks transmit** (consumer reqs C-06
  from Elena, C-08 from Hank). Toggling it in the View menu takes effect
  immediately (no restart), shows a persistent "transmit disabled" banner,
  and is restored from config at startup.

### Security / Safety
- All transmit paths (`_send_cq`, Fldigi `transmit`) are now gated through
  `core.safety.get_safety().can_transmit()`, which returns False in Guest
  mode or any unsafe app state. Even though both were already behind explicit
  button clicks (rule R1), this adds defense-in-depth (rule S9 — no
  unexpected RF). Covered by a new test in tests/test_safety.py.

---

## [0.11.4-alpha] — 2026-05-22

### Fixed (crash)
- **Modes tab failed to load: `NameError: _even_cb is not defined`.**
  My previous tooltip edit referenced the TX-period checkboxes without the
  `self.` prefix and left duplicate tooltip blocks. Fixed all checkbox
  references and removed the redundant duplicates.

### Fixed (UI / installer)
- **Installer AV-exclusion box had ragged, misaligned borders.** The
  fixed-width box-drawing characters did not line up because content width
  (especially the install path) varies. Replaced with a clean separator
  format that never misaligns on any terminal or path length.
- **Blank application icon.** Added `assets/squelch.png` and
  `assets/squelch.ico` (a green signal-source-with-radio-waves mark) and
  wired them into the QApplication, the main window, and the Inno Setup
  installer.

### Security
- **Added `core/sanitize.py`** (pure-Python, unit-tested) implementing
  `csv_safe()` (CSV/Excel formula-injection prevention, rule S6) and
  `redact_url()` (strips LoTW credentials before logging, rule S4).
  log_tab and lotw_sync now import from it. Covered by
  `tests/test_csv_injection.py` (4 tests).
- Added Security Engineer and Pentester/Red-Teamer reviewers to
  `docs/DESIGN_REVIEW.md` with nine standing rules (S1–S9) covering
  network limits, XML safety, path-traversal, credential handling, no
  dangerous eval, formula injection, loopback-only local services, plugin
  opt-in, and work-network friendliness (no telemetry).

### Docs
- **SECURITY.md** updated: supported version table (0.11.x), current
  security model documenting S1–S9, and recent hardening notes.
- **DEPENDENCIES.md** updated: footer version, and the PyQt6 matched-set
  pin requirement (6.6.1) with the DLL-mismatch explanation.

---

## [0.11.3-alpha] — 2026-05-22

### Added
- **docs/DESIGN_REVIEW.md** — a five-persona review framework (seasoned
  ham, software programmer, RF instructor, new ham, ease-of-use student)
  with standing rules (no TX without intent, units always shown, no blank
  panels, everything copyable, etc.). Features are now audited against all
  five lenses before shipping.

### Fixed
- **SDR tab showed a blank screen** when SoapySDR was not installed. The
  build error handler called `QVBoxLayout(self)` a second time, which fails
  silently when the widget already has a layout — leaving nothing visible.
  Now the handler reuses the existing layout and clears partial widgets, so
  the setup guide always appears. (Flagged by: Student, New Ham)
- **FT8 controls had no guidance.** Added tooltips to CQ, Halt TX, Tune Rig,
  and the TX-period / auto-sequence / auto-CQ / hold-frequency / DX-only
  checkboxes. Tooltips explain what each does, the even/odd TX convention,
  and warn explicitly where a control transmits. (Flagged by: New Ham,
  Instructor, Seasoned Ham)

---

## [0.11.2-alpha] — 2026-05-22

### Fixed
- **Light theme (and Night/High-Contrast) looked broken.** Root cause:
  171 inline `color:#gray` declarations hardcoded for dark backgrounds
  overrode the theme — gray/invisible text on light backgrounds.
  Stripped all neutral grays (#888, #555, #ccc, etc.) so muted text now
  follows the active theme. Semantic colors (green=active, red=TX/error,
  orange=warning) are kept.
- **Band Conditions had a large empty area at the top.** The splitter now
  gets stretch=1 to fill below the header, and both columns are top-aligned
  so the panels sit at the top instead of floating mid-screen.

### Added
- **"System" theme option** — detects the OS light/dark preference
  (Qt 6.5+ colorScheme, with a palette-luminance fallback) and applies
  Light or Dark to match. Available in Settings → Appearance and the
  View → Theme menu.

---

## [0.11.1-alpha] — 2026-05-22

### Fixed (crashes)
- **Settings crash `No module named sip`.** Bare `import sip` is wrong
  for PyQt6 — must be `from PyQt6 import sip`. Fixed in main_window.py
  and settings_dialog.py with a fallback.
- **Winlink tab fails to load: `no attribute _check_vara_status`.**
  Method was called from __init__ but missing again. Re-added with a
  DO NOT REMOVE marker.

### Fixed (usability)
- **Cannot copy text from any view.** Added app-wide text selection:
  every QLabel is now selectable, and every table supports Ctrl+C to
  copy the selected cells (tab-separated). Applied after window load.
- **Font size setting did nothing.** Root cause: 260 inline
  `font-size:Npx` declarations in widget stylesheets overrode the
  global font. Stripped them all so widgets inherit the font size set
  in Settings → Appearance.
- **Installer reported tools "not installed" despite configured paths.**
  install_check.py now reads the paths you set in Settings (config.json
  `paths.*` keys) before falling back to scanning standard locations.
- **"Toggle Spectrum / Waterfall" showed on tabs with no waterfall.**
  Now only enabled/visible on Rig and SDR tabs that actually have one.
- **Local RF "Searching…" could hang forever.** Added a 20-second
  watchdog that resets the button and shows a timeout message if
  RepeaterBook does not respond.

### Known issues (still being worked)
- Local RF: RepeaterBook proximity params need live-API verification.
- Themes: Light / Night / High-Contrast need polish; no System default yet.
- Map: sparse, needs work.
- SDR tab: blank, needs full device controls.
- Band Conditions: data is live (SFI/SSN from NOAA) but layout has an
  empty top area and no "last updated" indicator.

---

## [0.11.0-alpha] — 2026-05-22

### Added
- **`--verbose` / `-v` flag on installer.py.** Off by default (clean,
  quiet output). When enabled, pip output streams live to the console
  instead of being captured — essential for diagnosing install failures
  like the PyQt6 DLL mismatch. Applies to the main package install,
  the online fallback, and the PyQt6 matched-version reinstall.
- **`install_verbose.bat`** — double-click equivalent of
  `installer.py --verbose` for users who do not use the command line.
- **`install.bat` now passes arguments through**, so `install.bat -v`
  works too.

### Notes
- This is a minor bump (new feature) rather than patch, per SemVer.
- All output-reading code guarded against `None` (pip output goes
  straight to console in verbose mode, so `result.stderr` is `None`).

---

## [0.10.9-alpha] — 2026-05-22

### Changed
- **Suppressed pip's "new release available" notice.** Set
  `PIP_DISABLE_PIP_VERSION_CHECK=1` in the environment at the top of
  installer.py and install_check.py, and in install.bat. The installer
  already upgrades pip before installing packages, so the notice was
  pure noise. Also set `PIP_NO_INPUT=1` so pip never blocks waiting
  for input during automated install.

---

## [0.10.8-alpha] — 2026-05-22

### Fixed
- **PyQt6 `DLL load failed ... specified procedure could not be found`.**
  Root cause: pip installed mismatched versions of the three PyQt6
  components (PyQt6 bindings, PyQt6-Qt6 libraries, PyQt6-sip). The
  bindings expected a Qt function not present in the installed Qt DLL.
  - `requirements.txt` now pins `PyQt6==6.6.1` and `PyQt6-Qt6==6.6.1`
    as a matched set (was `>=6.6.0`, which let them drift apart).
  - When PyQt6 import fails, the installer now uninstalls all three
    components and reinstalls them pinned to the matched 6.6.1 set,
    rather than just force-reinstalling PyQt6 alone.
  - Fallback advice gives the exact copy-paste commands.

---

## [0.10.7-alpha] — 2026-05-22

### Fixed
- **installer.py: `NameError: WHITE is not defined`** in
  `_print_final_status()`. The function used the `WHITE` ANSI color
  constant, which install_check.py defines but installer.py did not.
  Added `WHITE` to installer.py color block.
- **main.py: `APP_VERSION` used but never imported.** `setApplicationVersion(APP_VERSION)`
  would crash on launch. Added `from core.constants import APP_VERSION`.
- Audited every .py file for uppercase constants used without import —
  these two were the only cases. Now clean.

### Changed
- **bootstrap.bat** now redirects to **install.bat** to remove confusion
  about which batch file to run. Both call `installer.py`. Use either —
  install.bat is the canonical one (picks best Python version, keeps
  window open).

---

## [0.10.6-alpha] — 2026-05-21

### Fixed
- **installer.py: `_try_link_pothossdr_soapy` not defined.** This
  function was renamed to `_auto_fix_soapysdr` in an earlier session
  but the call site in `check_external_tools()` was never updated.
  Replaced with the correct function name.
- **PyQt6 failure handling** improved: installer now shows the actual
  pip stderr output (the real error message) rather than generic advice.
  Adds a second attempt installing `pyqt6-qt6` separately, which fixes
  the common Windows case where PyQt6 installs but Qt DLLs are missing.
  Corrected the VC++ advice — error 0x80070666 means already installed,
  which is correct; the real fixes are pinning `PyQt6==6.6.1` or using
  Python 3.11.3.

---

## [0.10.5-alpha] — 2026-05-21

### Fixed
- **installer.py crashed with `NameError: _select_sdr_drivers is not defined`.**
  Root cause: the SoapySDR helper functions (`_find_soapy_anywhere`,
  `_get_venv_site_packages`, `_install_soapy_plugins`, `_recreate_venv`,
  `_auto_fix_soapysdr`, `_select_sdr_drivers`) were all defined *after* the
  `if __name__ == "__main__": main()` block. Python executes that block
  before reading the definitions below it, so `main()` could not find them.
  All six functions moved above `main()`.
- **PyQt6 install failure** now gives Windows-specific advice: install
  Visual C++ Redistributable (the most common root cause), try a pinned
  version (`PyQt6==6.6.1`), and link to the Python 3.11.3 installer.
  Installer continues past the failure instead of crashing, so the rest
  of setup (config, scripts, SDR drivers) still completes.

---

## [0.10.4-alpha] — 2026-05-21

### Fixed
- **installer.py crashed immediately on Python 3.11** with
  `NameError: name 'py_minor' is not defined`. The 3.14+ warning block
  I added used `py_minor` and `py_major` as if they were local variables,
  but they were never assigned. The previous `check_python()` block used
  `ver = sys.version_info` instead. Merged both blocks — `py_major` and
  `py_minor` are now defined before any check that uses them.
- Bonus: installer now also warns if Python < 3.11 (not just 3.14+).

---

## [0.10.3-alpha] — 2026-05-21

### Fixed
- **winlink_tab.py**: duplicate `_vara_fm` assignment and two undefined
  method calls (`_current_tmpl_fn`, `_on_vara_state`). Added stubs.
- **winlink_tab.py**: `_set_status` was called in `_check_vara_status`
  but not defined. Added.
- **modes_tab.py**: `_set_freq` called when DX spot is clicked but not
  defined. Added — tunes rig when connected.
- **sdr_tab.py**: `_decoder_cb` referenced but not defined. Added.
- **log_db.py**: `export_adif` did not accept `qso_ids` parameter even
  though log_tab called it that way. Added the parameter and filtering.
- **propagation.py**: `_fetch_kp` network call not wrapped in try/except.
- **Stale 0.9.0-alpha version string** in 5 files (repeaterbook.py,
  sota_pota.py, pskreporter.py, aprs_client.py, log_tab.py). All now use
  `APP_VERSION` constant.

### Added
- **Log tab column widths** are now saved to QSettings and restored on
  next launch.

---

## [0.10.2-alpha] — 2026-05-21

### Fixed
- **Settings stale-dialog guard kept regressing** — restored with
  "DO NOT REMOVE" sentinel comment block so it's harder to lose
  in subsequent edits.
- **`_fetch_kp` in propagation.py** could leak a network exception
  to the caller. Wrapped in try/except.
- **ADIF export to read-only path** raised uncaught `PermissionError`.
  Now caught, logged, and re-raised cleanly.

### Changed
- **Removed 34 unused imports** across 55 files (zero behavior change,
  cleaner traceback for any real errors).
- Added docstrings to public APIs in `aprs_client.py`, `vara.py`, and
  `beacon.py`.

---

## [0.10.1-alpha] — 2026-05-21

### Fixed
- **install_check.py crashed silently at "Squelch Configuration" header.**
  `check_config()` could raise `PermissionError` writing to AppData,
  killing the script before `print_summary()` ran. Now each check is
  isolated in try/except, summary always prints.
- **Final status was easy to miss.** Summary is now a 60-char banner
  with explicit `[PASS]`/`[FAIL]` per check, big enough to spot in any
  terminal. Both `install_check.py` and `installer.py` use the pattern.
- **Users confused between `install_check.py` (diagnostic) and
  `installer.py` (installs).** When checker finds missing packages, it
  now prompts "Launch installer now? (Y/n)" and runs it.

### Added
- **`install.bat`** — double-click to install. Picks the best Python
  version available (prefers 3.13 over 3.14 due to wheel availability),
  runs `installer.py` (not the checker), keeps the window open.
- **Python 3.14+ warning** in both installer and checker — many
  packages (PyQt6, SoapySDR) don't have cp314 wheels yet. Recommends
  Python 3.13.
- **Installer error handler** — if `main()` raises, prints a clear
  diagnostic with common fixes (Python version, admin rights, AV, network).

### Changed
- `run_squelch.bat` now checks for venv before launching and shows a
  clear error pointing to `install.bat` if missing.

---

## [0.10.0-alpha] — 2026-05-21

### Added
- **Dockable tabs** — double-click any tab label to pop it into a floating
  window. Drag back to re-dock. `AllowTabbedDocks | AllowNestedDocks` enabled
  on the main window for side-by-side panel arrangements.
- **Settings → SDR Hardware tab** — install and check SoapySDR device plugins
  (RTL-SDR, HackRF, RSP2Pro, USRP, Airspy, LimeSDR) directly from the UI.
  Runs `conda install` in a background thread and copies `.pyd` files into the
  venv automatically. Shows installed/missing status on tab open.
- **Installer — interactive SDR driver selection** — `python installer.py`
  now asks which SDR hardware you have and runs `conda install` for the
  correct plugins. Skippable with `--no-av-prompt` for automation.
- **Installer — full SoapySDR auto-fix pipeline** — detects Python version
  vs `.pyd` version mismatch, finds conda/miniforge automatically, copies
  SoapySDR + all device plugins into venv, recreates venv with correct
  Python version if needed.
- **Log tab — multi-select operations** — hold Ctrl/Shift to select multiple
  QSOs. Right-click shows "Upload N QSOs to LoTW", "Export N QSOs as ADIF",
  "Delete N QSOs" with single confirmation. `ExtendedSelection` mode.
- **Map — APRS station overlay** — APRS stations shown as orange diamonds
  with callsign labels. Updated every 5 seconds from APRS-IS connection.
- **Map — DX cluster spot overlay** — DX spots shown as pink dots on the map.
- **Map — satellite footprint circles** — each satellite shows its ground
  coverage ring (green for visible passes, blue for below-horizon).

### Fixed
- **Grid search stuck on "Searching…"** — `pyqtSignal` declarations
  (`_location_found`, `_location_failed`) were class-level but `.connect()`
  calls were missing from `__init__`. Background thread now safely crosses
  to the GUI thread via Qt signals. Fixed definitively.
- **Settings crash "wrapped C/C++ object deleted"** — stale dialog from
  a previous open was not destroyed before creating a new instance. Now
  calls `deleteLater()` on any existing dialog before opening a new one.
- **Delete QSO crash `'NoneType' has no attribute 'execute'`** — `LogDB._open()`
  returned `None` (no return statement). Now returns `self._conn` and
  reuses the connection instead of reopening on every call.
- **Winlink crash `'WinlinkTab' has no attribute '_check_vara_status'`** —
  method was called in `__init__` but never defined. Added.
- **Font size ignored** — `themes.py` only set `font-size` on `QMainWindow`.
  All child widget rules (`QPushButton`, `QLabel`, `QLineEdit`, `QComboBox`,
  etc.) override inherited font. Rewrote `build_stylesheet` with explicit
  `font-size: {fs}px` in all 30+ widget rules including `QDockWidget`.
- **VARA / Fldigi not detected** — search paths didn't include `C:\VARA\`,
  `C:\VARA FM\`, `C:\Program Files\Fldigi-4.2.11\`. All added to
  both `core/launcher.py` and `install_check.py`.
- **"apex" references** — old project name remaining in 9 files. All replaced
  with "Squelch". `run_apex.bat` reference replaced with `run_squelch.bat`.
- **fix_soapysdr.bat corrupting SoapySDR.py** — `echo` lines containing `→`
  were treated as CMD redirect operators, writing echo text into the destination
  file. All `→` removed from `echo` lines.
- **Map APRS/DX rendering** — `_draw_aprs` and `_draw_dx_spots` methods were
  referenced in `paintEvent` but missing from `map_fallback.py`. Added.
- **Log row right-click menu** — `customContextMenuRequested` signal was never
  connected to the table widget. Connected during table construction.

### Security
- `os.system("color")` replaced with `ctypes.windll.kernel32.SetConsoleMode()`
  — no shell spawned.
- 13 files had duplicate GPL copyright headers — removed.
- `pytest` moved from `requirements.txt` to `requirements-dev.txt`.
- All subprocess calls audited: 37 total, all `shell=False`.
- No hardcoded credentials, no SSL verification disabled, no eval().

### Changed
- Version number is now single-sourced from `core/constants.APP_VERSION`.
  `main.py`, `pskreporter.py`, and `squelch.iss` all import or reference it.
- RepeaterBook User-Agent updated from `0.7.0-alpha` to `0.9.0-alpha`.
- `requirements-dev.txt` created for test-only dependencies.

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
