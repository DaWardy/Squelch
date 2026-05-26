# Squelch — Multi-Perspective Design Review

Every feature and UI decision is evaluated through five personas. A change
ships only when it survives all five. This is a living document; add findings
as they surface.

---

## The Five Reviewers

### 1. Seasoned Ham (40+ years, Extra class, contester/DXer)
Cares about: muscle memory matching real rigs and HRD/N1MM/WSJT-X
conventions, no wasted clicks during a pileup, frequency/mode/split shown
unambiguously, CAT latency, logging that matches ADIF/Cabrillo exactly,
band-edge awareness, nothing that transmits without explicit intent.
Pet peeves: software that "knows better" than the operator, hidden state,
modal dialogs mid-QSO, decoded text you can't copy.

### 2. Software Programmer (maintainer's eye)
Cares about: no crashes, clear error states, threads that don't block the UI,
testable units, no silent failures, consistent naming, recoverable config,
logs that explain what happened. Pet peeves: bare excepts that hide bugs,
inline styling that fights the theme, magic numbers, dead code, UI work on
non-GUI threads.

### 3. RF Instructor (teaches license classes / Elmer)
Cares about: correct terminology, teachable layouts, tooltips that explain
*why*, units always shown (MHz vs kHz, dBm vs S-units), band plan accuracy,
propagation concepts surfaced honestly, safety (RF exposure, PTT, antenna).
Pet peeves: wrong or sloppy terminology, hiding the math, conflating modes,
implying capabilities the hardware doesn't have.

### 4. New Ham (Technician, first HT + first HF rig)
Cares about: not feeling stupid, knowing what to click first, plain-language
labels, sensible defaults, being told when something needs setup before it
works, recoverable mistakes. Pet peeves: jargon with no explanation, blank
screens with no "do this next," features that fail silently, dialogs that
assume knowledge they don't have.

### 5. Student / Ease-of-Use (never touched radio)
Cares about: onboarding, discoverability, visual hierarchy, can I find it
again, does the empty state tell me what to do, is the happy path obvious.
Pet peeves: empty panels, unlabeled icons, no first-run guidance, dead ends.

---

## Standing Rules Derived From the Panel

- **R1 (Ham):** Never transmit without an explicit, deliberate user action.
  No auto-PTT on focus, no "transmit on Enter" without a guard.
- **R2 (Programmer):** Every network/IO call is wrapped; failures set a
  visible state, never a silent hang. Background work never touches widgets
  directly — always marshal back to the GUI thread.
- **R3 (Instructor):** Every frequency shows its unit. Every signal-strength
  shows its unit. Mode and band are never ambiguous.
- **R4 (New Ham):** Every tab that needs setup shows a plain-language empty
  state telling the user exactly what to do first.
- **R5 (Student):** No blank panel. If there's no data yet, say why and what
  to do. Every icon has a text label or tooltip.
- **R6 (All):** Any text the user might want — callsign, frequency, grid,
  decoded text — is selectable and copyable.

---

## Open Findings (audited against current build)

(populated by the audit pass — see below)

### Audited 2026-05-22 (v0.11.3-alpha)

| Rule | Finding | Reviewer flagged | Status |
|------|---------|------------------|--------|
| R5 | SDR tab showed blank when SoapySDR absent — `_build` except handler called `QVBoxLayout(self)` a second time, which fails silently because the widget already had a layout | Student, New Ham | FIXED — except reuses the existing layout and clears partial widgets |
| R4 | FT8 controls (CQ, Halt TX, Tune Rig) and TX-period checkboxes had no explanation of what they do or that they transmit | New Ham, Instructor | FIXED — added tooltips explaining each control and warning where it transmits |
| R1 | Tune/CQ tooltips now explicitly warn "Transmits" so the operator knows before clicking | Seasoned Ham | FIXED |
| R3 | Tooltips state units and the even/odd TX-period convention | Instructor | FIXED |

### Still open (tracked for next passes)
- **Map (R5):** base map is sparse; needs clearer land/water contrast and a
  visible "your station" marker explanation. Continent outline exists (343
  points) and a legend exists, but contrast is low.
- **Local RF (R4/R5):** "Searching…" watchdog added, but RepeaterBook params
  need live verification; needs a configurable start point and a clear
  "no location set" path.
- **SDR full panel (all):** when hardware IS present, the full panel needs the
  device controls a seasoned op expects (gain, sample rate, ppm correction,
  bias-T, demod mode, squelch) — the big build, deferred until it can be done
  properly.

---

## Additional Reviewers (Security)

### 6. Security Engineer (defensive, builds the threat model)
Cares about: input validation on everything from the network (RepeaterBook,
QRZ, PSKReporter, DX cluster, APRS-IS, NOAA), credential storage (OS keyring,
never plaintext, never logged), no secrets in config.json or logs, TLS for all
outbound, no `shell=True`/`eval`/`exec`/`pickle` on untrusted data, safe XML
parsing (XXE/billion-laughs), path-traversal safety on file imports (ADIF,
SIGMF, profiles), least privilege (no admin needed at runtime), supply-chain
(pinned deps, known sources), and a clean audit trail. Pet peeves: credentials
in URLs, broad excepts that swallow security errors, trusting server responses,
auto-executing anything downloaded.

### 7. Pentester / Red Teamer (offensive, tries to break it)
Attacks: malicious server responses (oversized/malformed JSON/XML, injected
HTML, huge payloads → DoS), crafted ADIF/SIGMF/profile files (path traversal,
zip-slip, formula injection if exported to CSV/XLSX), CAT/rigctld socket
abuse (localhost service hijack, command injection via frequency fields),
APRS/Winlink message injection, config tampering, plugin loading (arbitrary
code via plugins/), clipboard/IPC, and the rigctld/rtl_tcp/VARA TCP ports for
SSRF or local pivot. Also: what does this expose on a work network — open
listeners, outbound beacons, telemetry. Pet peeves: "it's just ham radio,"
unbounded reads, trusting file extensions, plugins with no sandbox.

### Standing Security Rules

- **S1:** All outbound network calls use HTTPS and a request timeout, and cap
  the response size before parsing (no unbounded `.json()`/`.read()`).
- **S2:** All XML parsing uses `defusedxml` (never bare `ElementTree`).
- **S3:** File imports (ADIF/SIGMF/profile/plugin) validate the resolved path
  stays inside the intended directory (no `..` traversal, no absolute escape,
  no zip-slip), and cap file size.
- **S4:** Credentials live only in the OS keyring; never written to
  config.json, never logged, never placed in a URL query string.
- **S5:** No `shell=True`, `eval`, `exec(str)`, or `pickle.load` on any data
  that could originate from a file, network, or plugin.
- **S6:** Values that flow into CSV/XLSX export are sanitized against formula
  injection (leading `= + - @` get prefixed).
- **S7:** Local TCP clients (rigctld, rtl_tcp, VARA) connect to a configurable
  host that defaults to 127.0.0.1, validate it's a loopback/whitelisted host,
  and never bind a listener without the user explicitly enabling it.
- **S8:** Plugins are opt-in, listed before load, and the user is told a
  plugin runs arbitrary Python — no silent autoload of dropped files.
- **S9 (work use):** Squelch makes no outbound connection the user didn't
  initiate (no telemetry/analytics), and every periodic beacon (APRS, PSK,
  Winlink) is off by default and clearly labeled when on.

---

## Additional Reviewer (Platform)

### 8. Linux / Debian Systems Programmer
Builds and runs Squelch on Debian-based distros (Debian, Ubuntu, Raspberry Pi
OS, Mint) where many hams actually operate — especially on Raspberry Pi for
portable/field and digital-mode stations. **Ensures the app plays nice with a
Debian-based OS.** Cares about:
- No Windows-only assumptions: paths (`/` vs `\`, no `C:\`), no hardcoded
  drive letters, no `.exe` assumptions, case-sensitive filesystems.
- System integration done the Debian way: XDG base directories
  (`~/.config/squelch`, `~/.local/share/squelch`), a `.desktop` launcher, an
  icon in the hicolor theme, no writing into the install dir.
- Dependencies available via `apt` or pip wheels on `aarch64`/`armhf`
  (Raspberry Pi), and SoapySDR/rtl-sdr/Hamlib installed through the distro's
  packages (`apt install soapysdr-tools rtl-sdr libhamlib-utils`).
- Serial/USB device permissions: the user must be in the `dialout` group to
  reach `/dev/ttyUSB*`/`/dev/ttyACM*`; the app should detect and explain this,
  not fail cryptically.
- Audio via PipeWire/PulseAudio/ALSA; device names differ from Windows.
- No assumption of a single display server (X11 vs Wayland); Qt handles most,
  but file dialogs and tray icons can differ.
- Pet peeves: backslash paths, `os.startfile`, `winreg`, shelling out to
  `cmd`/`powershell`, hardcoded `Program Files`, assuming admin/UAC, CRLF-only
  files, anything that bricks on a case-sensitive FS.

### Standing Platform Rules
- **P1:** All filesystem paths use `pathlib.Path`; never hardcode separators,
  drive letters, or `Program Files`. Config/data go in XDG dirs on Linux.
- **P2:** No Windows-only API (`winreg`, `os.startfile`, `ctypes.windll`)
  without an `if platform == "win32"` guard and a Linux/macOS branch.
- **P3:** External-tool discovery checks Linux locations (`/usr/bin`,
  `/usr/local/bin`, `$PATH`) and Linux binary names (no `.exe` suffix), and
  honors the user's configured path.
- **P4:** Serial access detects missing `dialout` group membership and tells
  the user how to fix it (`sudo usermod -aG dialout $USER`, re-login).
- **P5:** Document the Debian/Ubuntu/Raspberry Pi install path
  (apt packages + pip) alongside Windows; CI runs the test suite on Linux.

### Linux audit 2026-05-24 (v0.11.9-alpha)

| Rule | Finding | Status |
|------|---------|--------|
| P3 | install_check.py detected external tools by Windows paths only; on Linux nothing was found even when installed | FIXED — added `shutil.which()` fallback with Linux binary names (wsjtx, fldigi, rigctld, js8call, dsd) |
| P4 | No detection of missing `dialout` group — serial connect failed cryptically on Debian/Ubuntu | FIXED — `diagnose_serial_permission()` explains the `usermod -aG dialout` fix on connect failure |
| P5 | No Debian/Pi install docs; `.sh` launchers weren't executable | FIXED — added docs/INSTALL_LINUX.md, setup/squelch.desktop, and chmod +x on generated `.sh` scripts |
| P1 | Config/data dirs | Already XDG-compliant (`~/.config/squelch`) — verified |
| P1/P2 | Candidate path lists in launcher/fldigi/location already include Linux paths; no unguarded `winreg`/`os.startfile` | Verified clean |
