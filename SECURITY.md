# Squelch — Security Policy

## Overview

Squelch is an open source amateur radio operations platform.
This document describes the security model, known limitations,
and how to report vulnerabilities.

---

## Supported Versions

| Version       | Security Updates |
|---------------|-----------------|
| 0.11.x (alpha) | Yes             |
| < 0.11        | No              |

---

## Threat Model

Squelch is a desktop application used by licensed amateur
radio operators. The relevant threats and mitigations:

### What Squelch protects against

**Credential exposure**
- Passwords and API keys are stored in the OS keyring
  (Windows Credential Manager, macOS Keychain, libsecret)
- Nothing sensitive is written to config.json
- Credentials are never logged, never displayed after entry
- Optional master password per profile for shared machines

**Input injection**
- All user input passes through `core/validator.py`
- Callsigns, frequencies, grid squares validated before use
- Subprocess calls use `shell=False` throughout
  (prevents shell injection via crafted inputs)
- File paths validated before read/write operations

**Network data**
- All API responses validated for type and size
  before processing
- Response size limits prevent memory exhaustion
- XML responses parsed via `defusedxml`
  (prevents XML entity expansion attacks)
- Request timeouts on all network calls (5-15 seconds)
- HTTPS used for all external API calls

**Serial port access**
- Only connects to ports the user explicitly selects
- Port names validated against allowlist before use
- PTT watchdog releases transmit on any crash

### What Squelch does NOT protect against

**Local machine compromise**
- An attacker with admin access to the machine can
  read credentials from Windows Credential Manager
- Squelch cannot defend against keyloggers
- Physical access to an unlocked machine bypasses
  all protections

**Malicious plugins**
- Plugins run with full access to Squelch internals
  and the local filesystem
- Only install plugins from trusted sources
- Future: plugin sandboxing via subprocess

**Network eavesdropping**
- API keys transmitted over HTTPS are protected
- Winlink/VARA traffic is transmitted in the clear
  over radio — this is by design and expected in
  amateur radio operation
- No guarantee of privacy for over-the-air traffic

**VPN/proxy interference**
- IP geolocation for auto-location uses your public IP
- VPN users will get incorrect auto-location estimates

---

## Known Security Considerations

### Credential storage

Squelch stores the following in the OS keyring:

| Credential          | Risk if leaked          |
|--------------------|------------------------|
| QRZ password        | Account access          |
| HamQTH password     | Account access          |
| RadioReference key  | API quota burn          |
| HamAlert key        | API quota burn          |
| LoTW password       | False QSL submissions   |
| ClubLog key         | Log manipulation        |

Recommendation: use unique passwords for each service
and enable 2FA where available.

### External software execution

Squelch launches external programs (WSJT-X, Fldigi,
VARA, etc.) via `subprocess.Popen` with `shell=False`.
Paths are configured by the user via Settings →
Paths & Executables and validated to exist before
execution.

Squelch does not execute any code downloaded from
the internet at runtime.

### Network connections made by Squelch

| Endpoint                     | Purpose                    | Auth      |
|-----------------------------|---------------------------|-----------|
| xmlfr.qrz.com               | Callsign lookup            | Username/password |
| api.hamqth.com              | Callsign lookup (fallback) | Username/password |
| radioreference.com          | Local RF data              | API key   |
| api.hamalert.org            | DX alerts                  | API key   |
| pskreporter.info            | Propagation spots          | None      |
| www.wsprnet.org             | WSPR spots                 | None      |
| services.swpc.noaa.gov      | Solar data                 | None      |
| ipapi.co                    | IP geolocation (first run) | None      |
| raw.githubusercontent.com   | Artemis signal DB download | None      |
| localhost:8080              | dump1090-fa (local only)   | None      |
| localhost:4532              | rigctld Hamlib (local only)| None      |

No data is sold or shared. Squelch products are ad-free.
See NOTICE for all integrated project attributions.

---

## Security Scan Results

Squelch is scanned with [Bandit](https://bandit.readthedocs.io/)
before each release.

**v0.6.0-alpha results:**
```
High:   0
Medium: 0
Low:    95 (subprocess informational + credential key names)
```

**Low findings breakdown:**
- `B105` — Credential key name constants (e.g. `"qrz_password"`)
  flagged as "hardcoded password". These are keyring lookup
  keys, not actual credentials. False positive.
- `B404/B603` — `subprocess` import and `shell=False` usage.
  `shell=False` is intentionally the *safer* option.
  Bandit flags it informationally. Not a vulnerability.
- `B110` — `try/except/pass` in cleanup paths where
  failure is expected and non-fatal (e.g., deleting a
  keyring entry that may not exist).

---

## Reporting Vulnerabilities

**Please do not file public GitHub issues for
security vulnerabilities.**

Report privately via:
- GitHub private vulnerability reporting:
  github.com/dawardy/squelch/security/advisories/new
- Or email (see GitHub profile for contact)

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix if known

Response target: 72 hours for acknowledgement,
14 days for fix or mitigation.

---

## Security Hardening Roadmap

```
v0.7 (current alpha):
  ✅ defusedxml for XML parsing
  ✅ shell=False on all subprocess calls
  ✅ Input validation via core/validator.py
  ✅ OS keyring for credential storage
  ✅ Response size limits on all API calls
  ✅ Bandit scan — 0 high, 0 medium

v0.9 (release candidate):
  [ ] Plugin sandboxing via subprocess isolation
  [ ] Signed installer (SignPath Foundation)
  [ ] HTTPS certificate verification hardening
  [ ] Rate limiting on outbound API calls
  [ ] Config file permissions check on startup

v1.0:
  [ ] Full security audit
  [ ] Dependency vulnerability scanning (Safety/pip-audit)
  [ ] Automated Bandit in GitHub Actions CI
```

---

*Last updated: 2026-05-14*
*Squelch 0.11.3-alpha*


---

## Security Model (current — 0.11.3-alpha)

Squelch is reviewed against nine standing security rules, defined in
`docs/DESIGN_REVIEW.md` and audited each release. Summary:

- **S1 — Network:** every outbound call uses HTTPS with a timeout and caps
  the response size before parsing (no unbounded reads). Sources: NOAA SWPC,
  RepeaterBook, QRZ/HamQTH, PSKReporter, DX cluster / HamAlert, APRS-IS,
  Celestrak, ARRL LoTW, ClubLog.
- **S2 — XML:** all parsing uses `defusedxml` (XXE / billion-laughs safe).
- **S3 — File imports:** ADIF / SIGMF / profile / plugin loads validate the
  resolved path and cap size (no traversal, no zip-slip).
- **S4 — Credentials:** stored only in the OS keyring; never written to
  `config.json`, never logged, never shown. ARRL LoTW requires login and
  password in the request URL (their API has no token option) — that URL is
  passed through `core.sanitize.redact_url()` before any logging.
- **S5 — No dangerous eval:** zero `shell=True`, `eval`, `exec(str)`, or
  `pickle.load` on file / network / plugin data.
- **S6 — Spreadsheet export:** CSV/XLSX cells are run through
  `core.sanitize.csv_safe()` to neutralize formula injection (a leading
  `= + - @` is prefixed so Excel/LibreOffice treats it as text).
- **S7 — Local services:** rigctld / rtl_tcp / VARA clients default to
  `127.0.0.1`; no listener is opened unless the user explicitly enables it.
- **S8 — Plugins:** opt-in only, listed before load, with a clear notice that
  a plugin runs arbitrary Python. No silent autoload of dropped files.
- **S9 — Work-network friendly:** no telemetry or analytics; Squelch makes no
  outbound connection the user did not initiate. Every periodic beacon (APRS,
  PSKReporter, Winlink) is off by default and labeled when enabled.

### Network transparency (C-12)
- `core/netlog.py` records every outbound connection to `logs/network.log`
  and an in-app viewer (Help -> Network Activity), tagged AUTO (app-initiated:
  band conditions, satellites, optional IP geolocation) vs USER (you clicked).
  Credentials are redacted. This lets an operator on a sensitive or client
  network audit exactly what Squelch contacted and confirm there are no
  unsolicited beacons (rule S9).

### Recent hardening
- Added `core/sanitize.py` (pure-Python, unit-tested) for `csv_safe` and
  `redact_url`; covered by `tests/test_csv_injection.py`.
- Replaced `os.system("color")` with a `ctypes` console call (no shell spawn).
- Pinned PyQt6 component versions to a matched set to avoid DLL-mismatch.
