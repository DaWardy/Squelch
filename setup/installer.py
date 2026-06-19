# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
#
# This program is free software: you can redistribute it
# and/or modify it under the terms of the GNU General
# Public License as published by the Free Software
# Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General
# Public License along with this program. If not, see
# <https://www.gnu.org/licenses/>.

"""
Squelch -- installer.py
Cross-platform setup and dependency checker.
Run this instead of bootstrap.bat.

Usage:
  python installer.py          -- full setup
  python installer.py --check  -- check only, no install
  python installer.py --offline -- use cached packages only
  python installer.py --cache  -- download packages for offline use
"""

import sys
import os
import subprocess
if not hasattr(subprocess, "CREATE_NO_WINDOW"):
    subprocess.CREATE_NO_WINDOW = 0
import shutil
import argparse
import json
from pathlib import Path
import installer_soapy as _isoapy
import installer_packages as _ipkg

# ── Version check before anything else ───────────────────────────────────
if sys.version_info < (3, 9):
    print("\nERROR: Python 3.9 or newer required.")
    print(f"       You have Python {sys.version}")
    print("")
    print("       This usually means installer.py was run with the")
    print("       wrong Python. Use run_installer.bat instead.")
    print("       Download Python 3.9+: https://www.python.org/downloads/")
    print("")
    input("Press Enter to exit...")
    sys.exit(1)

# ── Helpers ───────────────────────────────────────────────────────────────

# Suppress pip's "new version available" notice and speed up pip
os.environ["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
os.environ["PIP_NO_INPUT"] = "1"

# Set by --verbose flag in main(); when True, pip output is shown live
VERBOSE = False


def _pip_quiet_flag():
    """Return ['--quiet'] normally, [] when verbose so output shows."""
    return [] if VERBOSE else ["--quiet"]


def _pip_capture():
    """Return False when verbose (stream live), True otherwise (hide)."""
    return not VERBOSE

RESET  = "\033[0m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
WHITE  = "\033[97m"

def ok(msg):    print(f"  {GREEN}[OK]{RESET}   {msg}")
def warn(msg):  print(f"  {YELLOW}[WARN]{RESET} {msg}")
def err(msg):   print(f"  {RED}[FAIL]{RESET} {msg}")
def info(msg):  print(f"  {CYAN}[INFO]{RESET} {msg}")
def hdr(msg):   print(f"\n{BOLD}{msg}{RESET}\n  {'─'*50}")
def sep():      print()

# Wire console helpers + path globals into installer_packages
_ipkg._ok   = ok
_ipkg._warn = warn
_ipkg._err  = err
_ipkg._info = info

BASE_DIR     = Path(__file__).parent.parent.resolve()
VENV_DIR     = BASE_DIR / "venv"
OFFLINE_DIR  = BASE_DIR / "offline_packages"
REQ_FILE     = BASE_DIR / "requirements.txt"
CONFIG_FILE  = BASE_DIR / "config.json"
CONFIG_TMPL  = BASE_DIR / "config.example.json"

IS_WINDOWS = sys.platform == "win32"
IS_LINUX   = sys.platform.startswith("linux")

VENV_PYTHON = (VENV_DIR / "Scripts" / "python.exe"
               if IS_WINDOWS
               else VENV_DIR / "bin" / "python3")
VENV_PIP    = (VENV_DIR / "Scripts" / "pip.exe"
               if IS_WINDOWS
               else VENV_DIR / "bin" / "pip")


# ── AV exclusion reminder ─────────────────────────────────────────────────

def print_av_reminder():
    # Simple separator format — never misaligns regardless of path length
    # or terminal width (the old fixed-width box drew ragged right borders).
    bar = "=" * 64
    print(f"""
{YELLOW}{BOLD}{bar}
  IMPORTANT — READ BEFORE CONTINUING
{bar}{RESET}

  Add this folder to your antivirus exclusions FIRST:

    {BASE_DIR}

  How to add an exclusion:
    NETGEAR Armor    : Armor app  -> Settings -> Exceptions
    Windows Defender : Security   -> Virus protection ->
                       Manage settings -> Exclusions -> Add folder
    Bitdefender      : Protection -> Antivirus -> Settings ->
                       Manage exceptions -> Add folder

  This prevents antivirus false positives during Python package
  installation. The folder contains only ham radio software.

{YELLOW}{BOLD}{bar}{RESET}
""")
    response = input("  Have you added the folder exclusion? [Y/N]: ").strip().upper()
    if response != 'Y':
        print("\n  Please add the exclusion first, then run installer.py again.")
        print(f"  Folder to exclude: {BASE_DIR}\n")
        sys.exit(0)


# ── Step 1: Python info ───────────────────────────────────────────────────

_PREFERRED_PY = ("3.12", "3.11", "3.13")


def _probe_py_launcher(preferred: tuple[str, ...]) -> list[str]:
    """Probe Windows `py -X.Y` launcher for each preferred version."""
    candidates: list[str] = []
    if sys.platform != "win32":
        return candidates
    for ver in preferred:
        try:
            r = subprocess.run(
                ["py", f"-{ver}", "-c", "import sys; print(sys.executable)"],
                capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                candidates.append(r.stdout.strip())
                info(f"Found Python {ver} via py launcher: {r.stdout.strip()}")
        except Exception:
            pass
    return candidates


def _try_probe_exe(name: str) -> str | None:
    """Return sys.executable path for `name`, or None if not found/errors."""
    try:
        r = subprocess.run(
            [name, "-c", "import sys; print(sys.executable)"],
            capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _probe_direct_executables(preferred: tuple[str, ...],
                               existing: list[str]) -> list[str]:
    """Probe direct executable names (python3.12, python312, etc.)."""
    candidates: list[str] = list(existing)
    for ver in preferred:
        for name in (f"python{ver}", f"python{ver.replace('.', '')}"):
            path = _try_probe_exe(name)
            if path and path not in candidates:
                candidates.append(path)
                info(f"Found {name}: {path}")
    return candidates


def find_best_python() -> str:
    """Return the best Python executable for the venv.

    Prefers 3.12 > 3.11 > 3.13 (best wheel availability for HAM-radio
    deps: PyQtWebEngine, SoapySDR). Falls back to sys.executable with a
    warning if on 3.14+ where some wheels are missing.
    """
    candidates = _probe_py_launcher(_PREFERRED_PY)
    candidates = _probe_direct_executables(_PREFERRED_PY, candidates)
    if candidates:
        chosen = candidates[0]
        vi = sys.version_info
        if (vi.major, vi.minor) != (3, 12):
            info(f"Using {chosen} (Python {vi.major}.{vi.minor} active — "
                 "better wheel availability via preferred version).")
        return chosen
    if sys.version_info >= (3, 14):
        warn("No Python 3.11/3.12/3.13 found. "
             f"Falling back to Python {sys.version_info.major}."
             f"{sys.version_info.minor} — some wheels may be missing. "
             "Install Python 3.12: https://www.python.org/downloads/")
    return sys.executable


def check_python():
    hdr("[1/6] Python")
    ver = sys.version_info
    py_major = ver.major
    py_minor = ver.minor
    ok(f"Python {py_major}.{py_minor}.{ver.micro}")

    if py_minor >= 14:
        warn(f"Python {py_major}.{py_minor} is very new.")
        warn("PyQt6, SoapySDR, and other packages may not have wheels yet.")
        warn("Recommended: Python 3.11, 3.12, or 3.13 for best compatibility.")
        warn("Installer will probe for an older Python on this system.")
        warn("Download 3.12: https://www.python.org/downloads/release/python-3120/")
        print()
    elif (py_major, py_minor) < (3, 11):
        warn(f"Python {py_major}.{py_minor} is older than 3.11.")
        warn("Some packages may not install. Python 3.11+ recommended.")
    else:
        ok("Python version supported.")


# ── Step 2: Virtual environment ───────────────────────────────────────────


def setup_venv():
    hdr("[2/6] Virtual Environment")
    if VENV_DIR.exists() and VENV_PYTHON.exists():
        ok("Virtual environment exists.")
        return
    # Find the best Python on the system rather than blindly using
    # sys.executable. User reported sys.executable was 3.14 even though
    # 3.12 was installed.
    venv_python = find_best_python()
    info(f"Creating virtual environment with: {venv_python}")
    result = subprocess.run(
        [venv_python, "-m", "venv", str(VENV_DIR)],
        capture_output=True, text=True)
    if result.returncode != 0:
        err(f"Failed to create venv: {result.stderr}")
        sys.exit(1)
    ok("Virtual environment created.")


# ── Step 3: Packages ──────────────────────────────────────────────────────

def _sync_pkg_globals() -> None:
    """Push current path globals into installer_packages before any call."""
    _ipkg.VENV_PYTHON = VENV_PYTHON
    _ipkg.REQ_FILE    = REQ_FILE
    _ipkg.OFFLINE_DIR = OFFLINE_DIR
    _ipkg.VERBOSE     = VERBOSE


def install_packages(offline: bool = False, cache_only: bool = False):
    hdr("[3/6] Python Packages")
    _sync_pkg_globals()

    if sys.version_info >= (3, 14):
        warn("Python 3.14 — PyQtWebEngine has no wheel yet; map tab will be limited.")
        sep()

    if not REQ_FILE.exists():
        warn("requirements.txt not found — skipping.")
        return

    _ipkg._bootstrap_pip()
    pip = _ipkg._pip_cmd()

    if cache_only:
        info(f"Downloading packages to {OFFLINE_DIR}...")
        OFFLINE_DIR.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(
            pip + ["download", "-r", str(REQ_FILE),
                   "-d", str(OFFLINE_DIR), "--quiet"],
            capture_output=True, text=True)
        count = len(list(OFFLINE_DIR.glob("*.whl")))
        (ok if r.returncode == 0 else warn)(f"Cached {count} packages")
        return

    if not _ipkg._install_packages_bulk(pip, offline):
        _ipkg._install_packages_individual(pip)

    _ipkg._verify_pyqt6(pip, VENV_PYTHON)
    for pkg in ("numpy", "pyqtgraph", "sounddevice", "keyring"):
        _ipkg._verify_package(pkg, VENV_PYTHON)

    if not offline and not OFFLINE_DIR.exists():
        info("Caching packages for offline use...")
        OFFLINE_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            pip + ["download", "-r", str(REQ_FILE),
                   "-d", str(OFFLINE_DIR), "--quiet"],
            capture_output=True)
        count = len(list(OFFLINE_DIR.glob("*.whl")))
        if count > 0:
            ok(f"Cached {count} packages in offline_packages/")


# ── Step 4: External tools ────────────────────────────────────────────────

# ── External-tool definitions ─────────────────────────────────────────────
_EXTERNAL_TOOLS = [
    {
        "name":     "rigctld (Hamlib)",
        "cmd":      "rigctld",
        "args":     ["--version"],
        "required": True,
        "dl":       "https://github.com/Hamlib/Hamlib/releases",
        "note":     "Required for IC-7100 and all CAT rig control.",
    },
    {
        "name":     "WSJT-X",
        "paths":    [
            r"C:\Program Files\WSJT-X\bin\wsjtx.exe",
            r"C:\Program Files (x86)\WSJT-X\bin\wsjtx.exe",
            "/usr/bin/wsjtx",
        ],
        "required": False,
        "dl":       "https://wsjt.sourceforge.io/wsjtx.html",
        "note":     "Required for FT8/FT4/WSPR/JS8 modes.",
    },
    {
        "name":     "Fldigi",
        "paths":    [
            r"C:\Program Files\fldigi\fldigi.exe",
            "/usr/bin/fldigi",
        ],
        "required": False,
        "dl":       "https://sourceforge.net/projects/fldigi/",
        "note":     "Required for PSK31/RTTY/CW/SSTV.",
    },
    {
        "name":     "VARA HF",
        "paths":    [
            r"C:\VARA HF\VARAHF.exe",
            r"C:\Program Files\VARA HF\VARAHF.exe",
        ],
        "required": False,
        "dl":       "https://rosmodem.wordpress.com/",
        "note":     "Required for Winlink HF.",
    },
]


def _soapysdr_install_help():
    """Print installation options for SoapySDR."""
    info("")
    info("EASY PATH (no CMake required):")
    info("")
    info("  Option A — RTL-TCP  (RTL-SDR only, simplest):")
    info("    1. github.com/rtlsdrblog/rtl-sdr-blog/releases")
    info("       → download rtlsdr-release.zip, extract")
    info("    2. zadig.akeo.ie → install WinUSB driver for dongle")
    info("    3. Run rtl_tcp.exe → Squelch auto-detects it")
    info("       No pip install needed for this path.")
    info("")
    info("  Option B — PothosSDR bundle (all SDR hardware):")
    info("    1. downloads.myriadrf.org/builds/PothosSDR/")
    info("       → one installer, includes SoapySDR + drivers")
    info("    2. Reboot  3. pip install soapysdr")
    info("    4. RTL-SDR users: also run Zadig (zadig.akeo.ie)")
    info("")
    info("  Option C — conda / radioconda (GNU Radio users):")
    info("    github.com/ryanvolz/radioconda/releases")
    info("    conda install -c conda-forge soapysdr soapysdr-module-rtlsdr")
    info("")
    info("  Linux:  sudo apt install soapysdr-tools soapysdr-module-rtlsdr")
    info("")
    info("  SDRplay RSP users: install SDRplay API FIRST (sdrplay.com),")
    info("    then PothosSDR (order matters — PothosSDR needs the API DLLs)")
    info("")
    info("Not required for IC-7100 USB audio or Rig tab spectrum.")


def _check_soapysdr():
    """Check SoapySDR Python binding and print diagnostic on failure."""
    result = subprocess.run(
        [str(VENV_PYTHON), "-c",
         "import SoapySDR; "
         "devs=SoapySDR.Device.enumerate(); "
         "print(f'SoapySDR {SoapySDR.getAPIVersion()} "
         "— {len(devs)} device(s) found')"],
        capture_output=True, text=True)
    if result.returncode == 0:
        ok(result.stdout.strip())
        sep()
        return
    err_out = (result.stderr or result.stdout or "").lower()
    if "no module named" in err_out:
        warn("SoapySDR Python package not installed.")
        info(f"  {VENV_PYTHON} -m pip install soapysdr")
        info("  Make sure PothosSDR is installed FIRST.")
    elif "dll" in err_out or "libsoapysdr" in err_out:
        warn("SoapySDR package found but DLLs missing.")
        info("  PothosSDR not installed or not in PATH.")
        info("  Install: downloads.myriadrf.org/builds/PothosSDR/")
        info("  After install: reboot, then try again.")
    else:
        warn("SoapySDR not installed — SDR waterfall unavailable.")
        warn(f"  Error: {(result.stderr or result.stdout or '').strip()[:80]}")
    _soapysdr_install_help()
    sep()


def _check_vbcable():
    """Check for VB-Cable virtual audio device."""
    result = subprocess.run(
        [str(VENV_PYTHON), "-c",
         "import sounddevice as sd; "
         "devs=[d['name'] for d in sd.query_devices()]; "
         "vb=[d for d in devs if 'CABLE' in d.upper() "
         "or 'VB-AUDIO' in d.upper()]; "
         "print('VB-Cable: ' + (vb[0] if vb else 'NOT FOUND'))"],
        capture_output=True, text=True)
    if result.returncode == 0:
        out = result.stdout.strip()
        if "NOT FOUND" in out:
            warn("VB-Cable not detected.")
            info("Required for digital modes audio routing.")
            info("Download: https://vb-audio.com/Cable/")
            info("Install as Administrator then reboot.")
        else:
            ok(out)
    sep()


def _check_serial_ports():
    """List serial ports; highlight if a rig is detected."""
    result = subprocess.run(
        [str(VENV_PYTHON), "-c",
         "import serial.tools.list_ports as lp; "
         "ports=list(lp.comports()); "
         "rig=[p for p in ports if any(x in "
         "(p.description or '').upper() "
         "for x in ['CP210','CI-V','IC-7100','UART'])]; "
         "print(f'Rig port: {rig[0].device} — {rig[0].description}' "
         "if rig else "
         "f'{len(ports)} serial port(s) — no rig detected')"],
        capture_output=True, text=True)
    if result.returncode == 0:
        out = result.stdout.strip()
        if "no rig" in out.lower():
            info(out)
        else:
            ok(out)
    sep()


def _check_tool_by_cmd(tool: dict) -> bool:
    """Try to find the tool via PATH lookup. Returns True and prints if found."""
    path = shutil.which(tool.get("cmd", ""))
    if not path:
        return False
    result = subprocess.run(
        [path] + tool.get("args", []),
        capture_output=True, text=True)
    ver = (result.stdout or result.stderr or "").strip().split("\n")[0]
    ok(f"{tool['name']} — {ver[:60]}")
    return True


def _check_tool_by_paths(tool: dict) -> bool:
    """Try known install paths for the tool. Returns True and prints if found."""
    for candidate in tool.get("paths", []):
        if Path(candidate).exists():
            ok(f"{tool['name']} — {candidate}")
            return True
    return False


def _check_tool(tool: dict):
    """Check one external tool entry; print ok/warn/err and a sep."""
    if _check_tool_by_cmd(tool) or _check_tool_by_paths(tool):
        sep()
        return
    (err if tool.get("required") else warn)(
        f"{tool['name']} — {'NOT FOUND' if tool.get('required') else 'not found'}"
        + (f" ({tool['note']})" if not tool.get("required") else ""))
    info(f"Download: {tool['dl']}")
    info("If installed but not detected, set the path in:")
    info("  Squelch → File → Paths & Executables")
    sep()


def check_external_tools():
    hdr("[4/6] External Tools")
    print("  Warnings here do not prevent Squelch from launching.")
    print("  Affected tabs are disabled until tools are installed.")
    sep()
    _auto_fix_soapysdr()
    _check_soapysdr()
    _check_vbcable()
    _check_serial_ports()
    for tool in _EXTERNAL_TOOLS:
        _check_tool(tool)


# ── Step 5: Config ────────────────────────────────────────────────────────

def setup_config():
    hdr("[5/6] Configuration")
    if CONFIG_FILE.exists():
        ok("config.json exists.")
    elif CONFIG_TMPL.exists():
        import shutil
        shutil.copy(CONFIG_TMPL, CONFIG_FILE)
        ok("config.json created from template.")
        info("Launch Squelch to enter callsign and grid square.")
    else:
        # config.example.json missing (user cleared root folder)
        # Regenerate it from built-in defaults
        warn("config.example.json missing — regenerating.")
        try:
            _write_default_config(CONFIG_TMPL)
            import shutil
            shutil.copy(CONFIG_TMPL, CONFIG_FILE)
            ok("config.json created from built-in defaults.")
        except Exception as e:
            warn(f"Could not create config.json: {e}")
            info("Launch Squelch anyway — "
                 "it will prompt for callsign on first run.")


# ── Step 6: Launch scripts ────────────────────────────────────────────────

def _write_windows_launch_scripts() -> None:
    _write("run_squelch.bat",
           "@echo off\n"
           "cd /d \"%~dp0\"\n"
           "call venv\\Scripts\\activate.bat\n"
           "pythonw main.py %*\n")
    ok("run_squelch.bat")
    _write("run_squelch_debug.bat",
           "@echo off\n"
           "title Squelch Debug\n"
           "cd /d \"%~dp0\"\n"
           "call venv\\Scripts\\activate.bat\n"
           "python main.py --debug %*\n"
           "if errorlevel 1 pause\n")
    ok("run_squelch_debug.bat")
    _write("run_squelch_guest.bat",
           "@echo off\n"
           "title Squelch — Guest Operator\n"
           "cd /d \"%~dp0\"\n"
           "call venv\\Scripts\\activate.bat\n"
           "pythonw main.py --guest-op %*\n")
    ok("run_squelch_guest.bat")


def _write_unix_launch_scripts() -> None:
    _write("run_squelch.sh",
           "#!/bin/bash\n"
           "cd \"$(dirname \"$0\")\"\n"
           "source venv/bin/activate\n"
           "python3 main.py \"$@\"\n",
           executable=True)
    try:
        import stat as _stat
        for _sh in ("run_squelch.sh", "run_squelch_guest.sh"):
            _p = BASE_DIR / _sh
            if _p.exists():
                _p.chmod(_p.stat().st_mode | _stat.S_IXUSR
                         | _stat.S_IXGRP | _stat.S_IXOTH)
    except Exception:
        pass
    ok("run_squelch.sh")
    _write("run_squelch_guest.sh",
           "#!/bin/bash\n"
           "cd \"$(dirname \"$0\")\"\n"
           "source venv/bin/activate\n"
           "python3 main.py --guest-op \"$@\"\n",
           executable=True)
    ok("run_squelch_guest.sh")


def create_launch_scripts():
    hdr("[6/6] Launch Scripts")
    if IS_WINDOWS:
        _write_windows_launch_scripts()
    else:
        _write_unix_launch_scripts()


def _write(filename: str, content: str,
           executable: bool = False):
    path = BASE_DIR / filename
    path.write_text(content, encoding='utf-8')
    if executable and not IS_WINDOWS:
        path.chmod(0o755)


# ── Summary ───────────────────────────────────────────────────────────────

def print_summary(errors: int, warnings: int):
    sep()
    print("=" * 54)
    if errors > 0:
        print(f"  {RED}COMPLETED WITH {errors} ERROR(S).{RESET}")
        print("  Fix errors above before launching Squelch.")
    elif warnings > 0:
        print(f"  {YELLOW}COMPLETED WITH {warnings} WARNING(S).{RESET}")
        print("  Squelch will launch. Missing tools disable")
        print("  their tabs until installed.")
    else:
        print(f"  {GREEN}ALL CHECKS PASSED. Squelch is ready.{RESET}")
    print()
    print("  To launch:   run_squelch.bat")
    if not IS_WINDOWS:
        print("  To launch:   ./run_squelch.sh")
    print("  To diagnose: python installer.py --check")
    print("  Docs:        README.md")
    print("=" * 54)
    sep()


# ── Main ──────────────────────────────────────────────────────────────────

def _check_critical_packages() -> "tuple[list[str], bool]":
    """Probe critical packages in the venv. Returns (missing_names, pyqt6_dll_error)."""
    import subprocess as sp
    critical = {
        "PyQt6":     "from PyQt6.QtWidgets import QApplication",
        "numpy":     "import numpy",
        "requests":  "import requests",
        "pyqtgraph": "import pyqtgraph",
    }
    missing, pyqt6_dll_error = [], False
    for pkg, import_stmt in critical.items():
        r = sp.run([str(VENV_PYTHON), "-c", import_stmt],
                   capture_output=True, text=True)
        if r.returncode != 0:
            missing.append(pkg)
            if pkg == "PyQt6" and "DLL load failed" in (r.stderr or ""):
                pyqt6_dll_error = True
    return missing, pyqt6_dll_error


def _print_final_status():
    """Big visible final status banner — cannot be missed."""
    print()
    print()
    print(BOLD + "=" * 60 + RESET)
    print(f"{BOLD}{WHITE}  INSTALLATION COMPLETE{RESET}")
    print(BOLD + "=" * 60 + RESET)
    print()
    if VENV_DIR.exists() and VENV_PYTHON.exists():
        ok(f"Virtual environment: {VENV_DIR}")
    else:
        warn("Virtual environment was not created")
        return

    missing, pyqt6_dll_error = _check_critical_packages()
    if missing:
        warn(f"Missing or broken: {', '.join(missing)}")
        if pyqt6_dll_error:
            info("")
            info("PyQt6 has a DLL mismatch. Fix with matched versions:")
            info("  venv\\Scripts\\pip uninstall -y PyQt6 PyQt6-Qt6 PyQt6-sip")
            info("  venv\\Scripts\\pip install --no-cache-dir \\")
            info("    PyQt6==6.6.1 PyQt6-Qt6==6.6.1 PyQt6-sip==13.6.0")
        else:
            info("Try: venv\\Scripts\\python -m pip install -r requirements.txt")
    else:
        ok("All critical packages installed and importable")

    print()
    print(f"{BOLD}{CYAN}Next steps:{RESET}")
    print(f"  1. Launch Squelch:")
    print(f"     {CYAN}run_squelch.bat{RESET}  (Windows)")
    print(f"     {CYAN}python main.py{RESET}   (any platform)")
    print(f"  2. On first run, you will be prompted for:")
    print(f"     - Your callsign")
    print(f"     - Your grid square (or city/ZIP)")
    print(f"  3. Configure rigs in Settings (Ctrl+,)")
    print()
    print(BOLD + "=" * 60 + RESET)
    print()




# ── SoapySDR auto-fix (extracted to installer_soapy.py) ──────────────────────
_find_soapy_anywhere    = _isoapy._find_soapy_anywhere
_get_venv_site_packages = _isoapy._get_venv_site_packages
_install_soapy_plugins  = _isoapy._install_soapy_plugins
_auto_fix_soapysdr      = _isoapy._auto_fix_soapysdr
_find_conda             = _isoapy._find_conda
_select_sdr_drivers     = _isoapy._select_sdr_drivers


def _run_install_steps(args) -> None:
    """Run the full install sequence (skipped when --check is passed)."""
    setup_venv()
    if args.cache:
        install_packages(cache_only=True)
    else:
        install_packages(offline=args.offline)
    setup_config()
    create_launch_scripts()
    if not args.no_av_prompt:
        _select_sdr_drivers()


def _print_installer_header() -> None:
    print()
    print(f"{BOLD}{'='*54}")
    print(f"  Squelch — Amateur Radio Operations Platform")
    print(f"  Setup and Dependency Installer")
    print(f"  github.com/dawardy/squelch")
    print(f"{'='*54}{RESET}")
    sep()


def _show_user_data_location() -> None:
    try:
        import sys as _sys, os as _os
        if _sys.platform == "win32":
            _udir = Path(_os.environ.get(
                "APPDATA", Path.home() / "AppData" / "Roaming")) / "Squelch"
        else:
            _udir = Path.home() / ".config" / "squelch"
        info(f"User data stored at: {_udir}")
        info("This location persists through Squelch updates.")
    except Exception:
        pass


def _offer_launch() -> None:
    """Ask user whether to launch Squelch now; spawn if yes."""
    try:
        launch = input("  Launch Squelch now? [Y/N]: ").strip().upper()
    except (EOFError, KeyboardInterrupt):
        return
    if launch != 'Y':
        return
    python_exe = str(VENV_PYTHON)
    main_py    = str(BASE_DIR / "main.py")
    try:
        subprocess.Popen(
            [python_exe, main_py],
            cwd=str(BASE_DIR),
            creationflags=(subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0),
            close_fds=True)
        print("  Squelch launched.")
    except Exception as e:
        print(f"  Launch failed: {e}")
        print(f"  Run manually: {python_exe} main.py")


def main():
    parser = argparse.ArgumentParser(
        description="Squelch installer and dependency checker")
    parser.add_argument("--check",      action="store_true",
                        help="Check dependencies only, do not install")
    parser.add_argument("--offline",    action="store_true",
                        help="Install from offline cache only")
    parser.add_argument("--cache",      action="store_true",
                        help="Download packages for offline use")
    parser.add_argument("--no-av-prompt", action="store_true",
                        help="Skip antivirus reminder (for automation)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show full pip output (for debugging install failures)")
    args = parser.parse_args()

    global VERBOSE
    VERBOSE = args.verbose
    _isoapy.VERBOSE = args.verbose  # propagate to soapy module

    _print_installer_header()

    if not args.check and not args.no_av_prompt:
        print_av_reminder()

    check_python()

    if not args.check:
        _run_install_steps(args)

    check_external_tools()
    _print_final_status()
    print_summary(0, 0)
    _show_user_data_location()
    sep()

    if not args.check:
        _offer_launch()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        warn("Installation cancelled by user.")
    except Exception as exc:
        print()
        print(BOLD + "=" * 60 + RESET)
        print(f"{BOLD}{RED}  INSTALLER ERROR{RESET}")
        print(BOLD + "=" * 60 + RESET)
        err(f"{type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()
        print()
        info("Common fixes:")
        info("  1. Use Python 3.13 (3.14+ has wheel issues)")
        info("  2. Run as Administrator (Windows AppData write access)")
        info("  3. Check internet connection (pip needs network)")
        info("  4. Check antivirus isn't blocking pip")
    # Keep window open so user can read output
    try:
        input("\n  Press Enter to close...")
    except (EOFError, KeyboardInterrupt):
        pass


# ═══════════════════════════════════════════════════════════════════════
# SoapySDR auto-detection and installation helpers
# ═══════════════════════════════════════════════════════════════════════
