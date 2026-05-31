# Squelch — Agent Context (CLAUDE.md)
> Drop this file in project root. Any AI agent (Claude Code, Copilot, etc.)
> should read it before touching anything.

## What this is
Amateur radio operations platform. Python 3.9+ / PyQt6 / GPL v3.
GitHub: github.com/dawardy/squelch
Operator: NR6U, Manassas VA, grid FM18GS.
Hardware: IC-7100, RTL-SDR + RSP2Pro + B200/B210, Hamlib 4.7.1, Windows.

## Current version: 0.11.32-alpha
~135 files, 445 tests passing (0 skipped). QA gate exits 0.

---

## Architecture
```
main.py                    entry point; setup_logging(force=True),
                           _apply_theme_fixes(), _fix_combo_sizing()
core/
  config.py                XDG config (~/.config/squelch / %APPDATA%\Squelch)
  safety.py                AppState FSM; _exception_hook with Copy-error button
  guest_op.py              operating_callsign(cfg) — single source for TX call
  themes.py                Theme dataclass; build_stylesheet(theme, font_size)
  units.py                 format_distance/altitude, metric↔imperial
  rig.py                   rigctld wrapper; diagnose_serial_permission()
  profiles.py              ProfileManager (create/rename/delete/switch_to)
  sanitize.py              csv_safe(), redact_url()
  netlog.py                outbound connection log (Help → Network Activity)
  credentials.py           OS keyring wrapper
  location.py              LocationManager, _grid_to_latlon(), geocode_place()
ui/
  main_window.py           MainWindow; _FloatingTab (re-docks on close);
                           profile dropdown; demo/guest banners;
                           _open_log_folder(); _apply_theme_fixes()
  tabs/                    rig, modes, log, band_conditions (side-view),
                           sdr, digital, localrf (CHIRP CSV import), map,
                           map_fallback, winlink, help, flowgraph, stub
  widgets/
    propagation_sideview.py  2D cross-section: terrain + ionosphere + paths
    freq_display.py
    spectrum_widget.py
  dialogs/
    settings_dialog.py     7 tabs; _tab_apis() returns scroll (not w!)
    paths_dialog.py
modes/
  ft8.py                   FT8Engine; _set_state(state, detail) always 2 args
  fldigi_bridge.py
network/
  repeaterbook.py          token auth; falls back to RadioID.net for digital;
                           raises RepeaterBookError for analog no-token
  chirp_import.py          CHIRP CSV → Repeater list (no token needed)
  propagation.py           NOAA live SFI/SSN/K-index
  grayline.py
  pskreporter.py
sdr/
  soapy_device.py          SoapySDR wrapper; conda/venv bridge;
                           _try_conda_soapy() injects conda site-packages
  rtltcp_device.py         RTL-TCP client (used when SoapySDR sees 0 devices
                           but rtl_tcp is running on 127.0.0.1:1234)
digital/
  dsdplus.py               DSD+ launcher (no synthetic args; CREATE_NEW_CONSOLE)
winlink/
  templates.py             [CALLSIGN] tokens — no hardcoded callsigns
core/terrain.py            elevation_profile(); gc_profile(); download_tiles();
                           online=OpenTopoData, offline=Amazon SRTM S3 tiles
installer.py               find_best_python() probes for 3.12/3.11/3.13
                           before falling back to sys.executable (avoids
                           3.14 venv on user systems with mixed Python)
qa_check.py                MANDATORY pre-package gate (see QA/QC section)
```

---

## QA/QC gate — NEVER skip, NEVER package without it

```bash
python qa_check.py     # must exit 0
```

Runs in order:
1. `compile()` every .py — catches syntax + `__future__` ordering
2. `pyflakes` undefined-name scan — catches NameError class of bug
3. Connected-method reference check (`tests/test_method_references.py`) —
   catches `.connect(self._foo)` where `_foo` doesn't exist (the most
   common runtime crash class in this codebase)
4. Signal/callback smoke test (`tests/test_signal_smoke.py`) — fires
   state callbacks with both 1- and 2-arg forms; catches arity mismatches
   that only crash at emit time (not at tab-build time)
5. Full pytest suite with `QT_QPA_PLATFORM=offscreen` — 445 tests, 0 skips.
   Tab smoke test asserts NO tab builds as an error-stub (objectName ==
   "tab_load_error"). If any tab throws during build, the test fails.

**Common crash patterns this codebase has seen (all gated now):**
- `self._foo` in `.connect()` but `_foo` not defined → method-reference check
- Slot takes 2 args, signal emits 3 → signal smoke test
- QScrollArea created, inner widget returned instead of scroll → widget deleted
- QTimer.singleShot(0,...) from worker thread → silently never fires; use pyqtSignal
- `basicConfig()` no-op if handlers exist → always use `force=True`

## Packaging
```bash
# After QA passes:
python3 bump_version.py patch|minor|major
# Write /tmp/entry.md then:
python3 -c "
from pathlib import Path
entry = Path('/tmp/entry.md').read_text()
c = Path('CHANGELOG.md').read_text()
idx = c.find('---\n\n')
c = c[:idx+5] + entry + c[idx+5:]
Path('CHANGELOG.md').write_text(c)
"
cd /home/claude && zip -r outputs/Squelch_vX.Y.Z-alpha.zip squelch/ \
  --exclude "squelch/__pycache__/*" ... (see full exclude list in project brief)
```

---

## Design rules — DO NOT violate

| Rule | Rationale |
|------|-----------|
| `operating_callsign(cfg)` in `core/guest_op.py` is the ONLY source of the TX callsign | All modes must call this; never read cfg.callsign directly for TX |
| Demo Mode blocks TX, Guest Mode enables TX with a different callsign | Demo ≠ Guest; they are separate features |
| No `shell=True` / `eval` / `exec` / `pickle` anywhere | Security (S5) |
| CSV export via `csv_safe()` | Blocks formula injection (S6) |
| All network calls recorded in `core/netlog.py` | Operator visibility (C-12) |
| Credentials in OS keyring via `core/credentials.py` | Security (S4) |
| All paths use `pathlib.Path` | Cross-platform (P1) |
| Windows-only APIs guarded with `sys.platform == "win32"` | Cross-platform (P2) |
| Logs go to `%APPDATA%\Squelch\logs\squelch.log` (Windows) | Not the app folder |
| `setup_logging(force=True)` — force is critical | basicConfig is a no-op without it |
| Settings `_tab_apis()` must `return scroll` not `return w` | QScrollArea GC bug |

---

## Themes

Three themes: **Dark** (default), **Light**, **High Contrast**, **Night**.

Theme is applied globally via `app.setStyleSheet(get_stylesheet(theme, fs))`
plus a post-load `_apply_theme_fixes(window, theme_name)` that walks all
widgets and substitutes hardcoded dark hex values in inline stylesheets.

**The inline-stylesheet problem:** ~320 widgets have hardcoded dark colors
in `setStyleSheet()` calls. The substitution pass is a necessary band-aid
until a proper semantic-color refactor is done. When adding new widgets,
DO NOT hardcode `#141414` etc. — use theme variables or leave unset.

pyqtgraph (spectrum/waterfall) has its own background API; set via
`pg.setConfigOption("background", ...)` in `_apply_theme_fixes`.

---

## Key external dependencies and their status

| Dependency | Status |
|-----------|--------|
| RepeaterBook API | Requires approved free token since March 2026. Token in Settings → APIs. Without token: RadioID.net for digital, error for analog. |
| hearham.com | Returns HTTP 403. Removed. Do not add back. |
| SoapySDR | Often in conda base env, not venv. `_try_conda_soapy()` bridges. |
| rtl_tcp | If running on 127.0.0.1:1234, offered as synthetic device when SoapySDR finds 0 hardware. |
| DSD+ | Windows freeware; launch with NO synthetic args, CREATE_NEW_CONSOLE. |
| Celestrak TLEs | Returns 403 occasionally — handled gracefully. |
| Nominatim geocoder | Used for path-to resolution in Band Conditions. Called from worker thread; result returned via pyqtSignal (NOT QTimer.singleShot from thread). |
| GTOPO30/SRTM terrain | IMPLEMENTED (v0.11.34). core/terrain.py. Two backends: online (OpenTopoData SRTM30m API, no key) and offline (Amazon open terrain S3 tiles, NASA SRTM3 HGT, ~0.4MB/tile gzipped). Opt-in via Band Conditions → Path side-view → Terrain dropdown. Download button in the same row. |

---

## Consumer pipeline (8 personas)
| ID | Name | Profile | Key needs |
|----|------|---------|-----------|
| C-02 | Dorothy-66 | New older user | First-run wizard |
| C-03 | Hank-72 | Seasoned op | VFO A/B, split, no surprise TX |
| C-04 | Marcus-34 | Digital/POTA | Local RF, repeaters, FT8 |
| C-05 | Tyler-15 | Young new ham | Livelier map, visual feedback |
| C-06 | Elena-50 | Instructor | Demo mode, auto-CQ blocked |
| C-07 | All | Font size setting | |
| C-11 | Tyler | ON-AIR indicator | |
| C-12 | Priya-38 | Pentester | Network activity log, no eval/exec |
| C-15 | Sam-19 | Student | Guest operator mode, TX enabled |

---

## Open backlog (priority order)

| ID | Feature | Blocked by |
|----|---------|-----------|
| C-01 | SDR waterfall (THE BIG ONE) | Dedicated session; needs SoapySDR working |
| TERRAIN | ~~Real terrain in side-view~~ | DONE v0.11.34 |
| THEME | Full semantic-color refactor | Dedicated sprint; ~320 inline stylesheets |
| C-10 | Export waterfall data | C-01 |
| C-13 | SigMF capture export | C-01 |
| EIRP | Path-loss model with EIRP | Terrain first |
| WORKSPACE | ~~Custom tab layout~~ | DONE v0.11.38-39 |
| TX-TEXT | Digital TX from text box | New feature |
| MAP | Station pins from more sources | PSKReporter next after FT8 done |

---

## Known issues in current build (0.11.39)

- **Theme differentiation:** High Contrast and Dark look too similar. High
  Contrast needs stronger white text, higher-contrast borders.
- **Light theme:** Mode buttons still dark in light mode on some builds —
  the inline `QTabBar::tab{background:#141414}` is caught by substitution
  but the user should test after `_apply_theme_fixes` runs at startup.
- **RTL-TCP device:** Shows in dropdown, Connect wires to RTLTCPDevice,
  but full waterfall pipeline through SoapySDR manager is not yet confirmed
  end-to-end with real hardware.
- **Side-view terrain:** DONE — real SRTM data online/offline (v0.11.34).
- **installer "press Enter twice":** FIXED (v0.11.36).

---

## Instructions for AI agents working on this project

### Before ANY code change
1. Run `python qa_check.py` to get a clean baseline.
2. Check `tests/test_method_references.py` runs clean.
3. Check `tests/test_signal_smoke.py` runs clean.

### Recurring bug patterns — check for these before submitting
- Does any new `.connect(self._x)` call actually have `_x` defined?
- Does any new signal/callback have matching arg count at all call sites?
- Does any new dialog/widget build a QScrollArea and return the inner widget instead of the scroll?
- Does any new thread use QTimer.singleShot? If yes, use pyqtSignal instead.
- Does any new tab build method catch exceptions silently before the user-visible error is set?

### Callsigns and privacy
- NR6U is the operator's real callsign — never hardcode it in templates, defaults, or sample data.
- AI4EW is a third-party callsign that appeared in old test data — do not use.
- Template placeholders: `[CALLSIGN]`, `[MYCALL]`, `{my_callsign}`.

### Packaging
- ALWAYS run `qa_check.py` before packaging. Never package if it fails.
- Version bump via `bump_version.py patch|minor|major`, NEVER by hand.
- Changelog: write to `/tmp/entry.md` then prepend (avoids Python heredoc escaping).

### What NOT to do
- Do not use `shell=True`, `eval()`, `exec()`, `pickle`.
- Do not hardcode dark hex colors (`#141414`, `#0a0a0a` etc.) in new widget stylesheets.
- Do not add `force=False` to `logging.basicConfig` calls.
- Do not call `hearham.com` for anything — it 403s. It is gone.
- Do not add more dependencies to `requirements.txt` without checking conda-forge availability for win-64.
- Do not store real credentials, callsigns, or location data in code.

---

## Workspace system — planned architecture

### Why now is the right time
All tabs are already in individual files after the mixin refactor. Converting
a tab to a panel is a 2-line change. Doing this before the refactor would have
meant converting 2666-line monoliths.

### Target architecture

```
SquelchPanel(QWidget)        # base class — all tabs inherit from this
  panel_id: str              # e.g. "sdr", "modes", "rig"
  panel_title: str
  save_state() → dict        # geometry + widget state
  restore_state(dict)

PanelShell(QMainWindow)      # sits alongside MainWindow during transition
  registry: dict[id, Panel]  # auto-discovers all SquelchPanel subclasses
  QDockWidget per panel       # each panel is a dockable floating unit
  save_workspace() → JSON
  restore_workspace(JSON)

Workspace presets (JSON files in {data_dir}/workspaces/)
  "HF Ops"      Rig + Modes + Band Conditions
  "Digital"     SDR waterfall + Digital decoder + Map
  "Winlink"     Winlink + Band Conditions + Local RF
  "Custom"      user-saved
```

### Migration path (non-breaking)
1. Add SquelchPanel base class — tabs inherit from it, zero behaviour change
2. Build PanelShell alongside MainWindow (not replacing it)
3. "Switch to workspace mode" toggle in View menu — falls back to tab view
4. Convert tabs to panels one by one behind the toggle
5. When all panels stable in workspace mode, make it default

### Sprint arc
- Sprint A: SquelchPanel base class + panel registry + PanelShell skeleton
- Sprint B: Workspace save/restore (JSON), preset loader, View menu toggle
- Sprint C: Drag-and-drop panel arrangement, snap zones, per-panel toolbars

### Key user capability unlocked
- Rig + SDR waterfall + FT8 decodes on one screen (asked for repeatedly)
- Pop map out next to Band Conditions during DX
- "Contesting layout" vs "digital monitoring layout" as named saves
- Panels resize freely — docked, not tabbed
- Every panel independently floatable and re-dockable

### Do not start until
- settings_dialog.py refactor done (5.13 score, blocks clean panel state save)
- rig_tab.py Large Method issue addressed (6.33 score)
Both reduce risk of the workspace system inheriting tangled state.

---
*Last updated: v0.11.34-alpha — 2026-05-29*
