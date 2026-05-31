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

BASE_DIR     = Path(__file__).parent.resolve()
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

def find_best_python() -> str:
    """Return the best Python executable to use for the venv.

    The user reported that running `python installer.py` with their newest
    Python (3.14) created a 3.14 venv even though they had 3.12 installed
    — and 3.14 lacks wheels for PyQtWebEngine, SoapySDR, etc.

    This function actively probes for Python 3.11/3.12/3.13 (in that order
    of preference, since 3.12 is currently the sweet spot for HAM-radio
    package wheels) using:
      • The Windows `py -X.Y` launcher
      • Direct executables (`python3.12`, `python3.11`, etc.)

    Falls back to `sys.executable` only if nothing better is found.
    Returns the absolute path of the chosen interpreter.
    """
    PREFERRED = ("3.12", "3.11", "3.13")
    candidates: list[str] = []

    # Windows `py` launcher: `py -3.12 -c "import sys; print(sys.executable)"`
    if sys.platform == "win32":
        for ver in PREFERRED:
            try:
                r = subprocess.run(
                    ["py", f"-{ver}", "-c",
                     "import sys; print(sys.executable)"],
                    capture_output=True, text=True, timeout=5)
                if r.returncode == 0:
                    path = r.stdout.strip()
                    if path:
                        candidates.append(path)
                        info(f"Found Python {ver} via py launcher: {path}")
            except Exception:
                pass

    # Direct executables — works on macOS, Linux, and Windows with PATH set
    for ver in PREFERRED:
        for name in (f"python{ver}", f"python{ver.replace('.', '')}"):
            try:
                r = subprocess.run(
                    [name, "-c",
                     "import sys; print(sys.executable)"],
                    capture_output=True, text=True, timeout=5)
                if r.returncode == 0:
                    path = r.stdout.strip()
                    if path and path not in candidates:
                        candidates.append(path)
                        info(f"Found {name}: {path}")
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

    if candidates:
        chosen = candidates[0]
        ver_info = sys.version_info
        if (ver_info.major, ver_info.minor) != (3, 12):
            info(f"Using {chosen} instead of "
                 f"current interpreter (Python "
                 f"{ver_info.major}.{ver_info.minor}) — better wheel "
                 "availability for Squelch's dependencies.")
        return chosen

    # No preferred Python found — fall back to current interpreter
    if sys.version_info >= (3, 14):
        warn(f"No Python 3.11/3.12/3.13 found on system. Falling back to "
             f"Python {sys.version_info.major}.{sys.version_info.minor}, "
             "which may lack wheels for some dependencies (PyQtWebEngine, "
             "SoapySDR). Consider installing Python 3.12 from "
             "https://www.python.org/downloads/")
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

def _install_packages_bulk(pip: str, offline: bool) -> bool:
    """First attempt: install all packages at once. Returns True on success."""
    import tempfile, os
    req_lines = [
        l for l in REQ_FILE.read_text().splitlines()
        if not l.strip().startswith("PyQtWebEngine")
        and not (l.strip().startswith("#") and "PyQtWebEngine" in l)]
    _fd, _tmp = tempfile.mkstemp(suffix=".txt")
    os.close(_fd)
    tmp_req = Path(_tmp)
    tmp_req.write_text("\n".join(req_lines))

    cmd = [pip, "install", "-r", str(tmp_req), *_pip_quiet_flag()]
    if offline and OFFLINE_DIR.exists():
        cmd += ["--no-index", "--find-links", str(OFFLINE_DIR)]
        info("Installing from offline cache...")
    elif OFFLINE_DIR.exists():
        cmd += ["--find-links", str(OFFLINE_DIR)]
        info("Installing packages (using cache if available)...")
    else:
        info("Installing packages from internet...")
        info("This may take a few minutes on first run.")

    result = subprocess.run(cmd, capture_output=_pip_capture(), text=True)
    try:
        tmp_req.unlink()
    except Exception:
        pass

    if result.returncode != 0 and offline:
        warn("Offline install incomplete. Trying internet...")
        result = subprocess.run(
            [pip, "install", "-r", str(REQ_FILE), *_pip_quiet_flag()],
            capture_output=_pip_capture(), text=True)

    if result.returncode == 0:
        ok("Packages installed.")
        return True

    warn("Some packages failed — installing individually...")
    if result.stderr:
        for line in result.stderr.splitlines()[:5]:
            if line.strip():
                info(f"  pip: {line.strip()[:80]}")
    return False


def _install_packages_individual(pip: str):
    """Fallback: install each package individually, skipping non-critical."""
    import sys as _sys
    py_ver = (_sys.version_info.major, _sys.version_info.minor)
    PY314_SKIP = {"PyQtWebEngine"}
    NON_CRITICAL = {
        "PyQtWebEngine", "scipy", "pyqtgraph", "sounddevice",
        "soundfile", "soapysdr", "PyQtWebEngine>=6.4.0"}

    packages = [
        p.strip() for p in REQ_FILE.read_text().splitlines()
        if p.strip() and not p.strip().startswith(("#", "//"))
        and not p.strip().startswith("PyQtWebEngine")]

    failed, skipped = [], []
    for pkg in packages:
        if "; sys_platform" in pkg:
            import platform as _plat
            marker = pkg.split(";")[1].strip()
            if "win32" in marker and _plat.system() != "Windows":
                continue
            pkg = pkg.split(";")[0].strip()
        name = pkg.split(">=")[0].split("==")[0].split("[")[0].strip()
        if py_ver >= (3, 14) and name in PY314_SKIP:
            warn(f"  {name} — skipped (no Python 3.14 wheel)")
            skipped.append(name)
            continue
        r = subprocess.run(
            [pip, "install", pkg, "--quiet", "--no-cache-dir"],
            capture_output=True, text=True)
        (ok if r.returncode == 0 else warn)(
            f"  {name}" if r.returncode == 0 else f"  {name} — FAILED")
        if r.returncode != 0:
            failed.append(name)

    if skipped:
        info(f"Skipped (Python 3.14+): {', '.join(skipped)}")
    if failed:
        real = [p for p in failed if p not in NON_CRITICAL]
        optional = [p for p in failed if p in NON_CRITICAL]
        if real:
            warn(f"Failed (critical): {', '.join(real)}")
        if optional:
            info(f"Not installed (optional, app still works): {', '.join(optional)}")


def _verify_pyqt6(pip: str):
    """Verify PyQt6 works; attempt matched-version reinstall if not."""
    check = subprocess.run(
        [str(VENV_PYTHON), "-c", "from PyQt6.QtCore import QT_VERSION_STR"],
        capture_output=True, text=True)
    if check.returncode == 0:
        ok("PyQt6 detected")
        return
    warn("PyQt6 not working — attempting matched-version reinstall...")
    subprocess.run(
        [pip, "uninstall", "-y", "PyQt6", "PyQt6-Qt6", "PyQt6-sip"],
        capture_output=True)
    subprocess.run(
        [pip, "install", "--no-cache-dir",
         "PyQt6==6.6.1", "PyQt6-Qt6==6.6.1", "PyQt6-sip==13.6.0"],
        capture_output=_pip_capture())
    check2 = subprocess.run(
        [str(VENV_PYTHON), "-c",
         "from PyQt6.QtCore import QT_VERSION_STR; print('Qt/' + QT_VERSION_STR)"],
        capture_output=True, text=True)
    if check2.returncode == 0:
        ok(f"PyQt6 fixed — {check2.stdout.strip()}")
        return
    # Last resort: install pyqt6-qt6 separately
    info("Trying separate pyqt6-qt6 install...")
    subprocess.run([pip, "install", "pyqt6-qt6", "--no-cache-dir", "--quiet"],
                   capture_output=True)
    check3 = subprocess.run(
        [str(VENV_PYTHON), "-c", "from PyQt6.QtCore import QT_VERSION_STR"],
        capture_output=True, text=True)
    if check3.returncode == 0:
        ok("PyQt6 fixed")
    else:
        err("PyQt6 install failed — Squelch cannot run without it")
        info("Manual fix:")
        info("  venv\\Scripts\\pip uninstall -y PyQt6 PyQt6-Qt6 PyQt6-sip")
        info("  venv\\Scripts\\pip install --no-cache-dir PyQt6==6.6.1 PyQt6-Qt6==6.6.1 PyQt6-sip==13.6.0")


def install_packages(offline: bool = False, cache_only: bool = False):
    hdr("[3/6] Python Packages")

    import sys as _sys
    if _sys.version_info >= (3, 14):
        warn("Python 3.14 — PyQtWebEngine has no wheel yet; map tab will be limited.")
        sep()

    if not REQ_FILE.exists():
        warn("requirements.txt not found — skipping.")
        return

    pip = str(VENV_PIP)
    subprocess.run([pip, "install", "--upgrade", "pip", "--quiet"],
                   capture_output=True)

    if cache_only:
        info(f"Downloading packages to {OFFLINE_DIR}...")
        OFFLINE_DIR.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(
            [pip, "download", "-r", str(REQ_FILE),
             "-d", str(OFFLINE_DIR), "--quiet"],
            capture_output=True, text=True)
        count = len(list(OFFLINE_DIR.glob("*.whl")))
        (ok if r.returncode == 0 else warn)(f"Cached {count} packages")
        return

    if not _install_packages_bulk(pip, offline):
        _install_packages_individual(pip)

    _verify_pyqt6(pip)
    for pkg in ("numpy", "pyqtgraph", "sounddevice", "keyring"):
        _verify_package(pkg)

    if not offline and not OFFLINE_DIR.exists():
        info("Caching packages for offline use...")
        OFFLINE_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [pip, "download", "-r", str(REQ_FILE),
             "-d", str(OFFLINE_DIR), "--quiet"],
            capture_output=True)
        count = len(list(OFFLINE_DIR.glob("*.whl")))
        if count > 0:
            ok(f"Cached {count} packages in offline_packages/")


def _verify_package(name: str):
    # Special case for PyQt6 - check differently
    if name == "PyQt6":
        result = subprocess.run(
            [str(VENV_PYTHON), "-c",
             "from PyQt6.QtCore import QT_VERSION_STR; "
             "print('PyQt6 Qt/' + QT_VERSION_STR)"],
            capture_output=True, text=True)
    else:
        safe_name = name.lower().replace("-", "_")
        result = subprocess.run(
            [str(VENV_PYTHON), "-c",
             f"import {safe_name}; "
             f"v = getattr({safe_name}, '__version__', "
             f"getattr({safe_name}, 'version', 'ok')); "
             f"print(v)"],
            capture_output=True, text=True)
    if result.returncode == 0:
        ver = result.stdout.strip()
        ok(f"{name} {ver}")
    else:
        warn(f"{name} — not detected")
        info(f"Try: pip install {name} --no-cache-dir")


# ── Step 4: External tools ────────────────────────────────────────────────

def check_external_tools():
    hdr("[4/6] External Tools")
    print("  Warnings here do not prevent Squelch from launching.")
    print("  Affected tabs are disabled until tools are installed.")
    sep()

    tools = [
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

    # SoapySDR — try to auto-link from conda/PothosSDR if pip fails
    _auto_fix_soapysdr()

    # SoapySDR — check via Python import
    result = subprocess.run(
        [str(VENV_PYTHON), "-c",
         "import SoapySDR; "
         "devs=SoapySDR.Device.enumerate(); "
         "print(f'SoapySDR {SoapySDR.getAPIVersion()} "
         "— {len(devs)} device(s) found')"],
        capture_output=True, text=True)
    if result.returncode == 0:
        ok(result.stdout.strip())
    else:
        # More helpful: distinguish "not installed" from
        # "installed but SoapySDR DLLs not in PATH"
        err_out = (result.stderr or result.stdout or "").lower()
        if "no module named" in err_out:
            warn("SoapySDR Python package not installed.")
            info("")
            info("  To install (run in the Squelch folder):")
            info(f"    {VENV_PYTHON} -m pip install soapysdr")
            info("  Or use the venv pip directly:")
            info(f"    {VENV_PYTHON.parent / 'pip'} install soapysdr")
            info("")
            info("  Make sure PothosSDR is installed FIRST.")
        elif "dll" in err_out or "libsoapysdr" in err_out:
            warn("SoapySDR package found but DLLs missing.")
            info("  PothosSDR not installed or not in PATH.")
            info("  Install: downloads.myriadrf.org/builds/PothosSDR/")
            info("  After install: reboot, then try again.")
        else:
            warn("SoapySDR not installed — SDR waterfall unavailable.")
            warn(f"  Error: {(result.stderr or result.stdout or '').strip()[:80]}")
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
        info("    2. Reboot")
        info("    3. pip install soapysdr")
        info("    4. RTL-SDR users: also run Zadig (zadig.akeo.ie)")
        info("")
        info("  Option C — conda / radioconda (GNU Radio users):")
        info("    github.com/ryanvolz/radioconda/releases")
        info("    conda install -c conda-forge soapysdr soapysdr-module-rtlsdr")
        info("")
        info("  Linux:  sudo apt install soapysdr-tools soapysdr-module-rtlsdr")
        info("")
        info("  SDRplay RSP users:")
        info("    Install SDRplay API FIRST: sdrplay.com/softwarehome")
        info("    Then PothosSDR bundle (includes SoapySDRplay)")
        info("    Order matters — PothosSDR must see the API to install driver")
        info("")
        info("Not required for IC-7100 USB audio or Rig tab spectrum.")
    sep()

    # VB-Cable
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

    # Serial ports
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

    for tool in tools:
        found = False
        # Check PATH first
        if "cmd" in tool:
            path = shutil.which(tool["cmd"])
            if path:
                result = subprocess.run(
                    [path] + tool.get("args", []),
                    capture_output=True, text=True)
                ver = (result.stdout or result.stderr
                       or "").strip().split("\n")[0]
                ok(f"{tool['name']} — {ver[:60]}")
                found = True

        # Check common paths
        if not found:
            for candidate in tool.get("paths", []):
                if Path(candidate).exists():
                    ok(f"{tool['name']} — {candidate}")
                    found = True
                    break

        if not found:
            if tool.get("required"):
                err(f"{tool['name']} — NOT FOUND")
            else:
                warn(f"{tool['name']} — not found ({tool['note']})")
            info(f"Download: {tool['dl']}")
            info(f"If installed but not detected, set the path in:")
            info(f"  Squelch → File → Paths & Executables")
        sep()


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

def create_launch_scripts():
    hdr("[6/6] Launch Scripts")

    if IS_WINDOWS:
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

    else:
        # Linux / macOS
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

def _print_final_status():
    """Big visible final status banner — cannot be missed."""
    import sys
    print()
    print()
    print(BOLD + "=" * 60 + RESET)
    print(f"{BOLD}{WHITE}  INSTALLATION COMPLETE{RESET}")
    print(BOLD + "=" * 60 + RESET)
    print()
    # Verify the venv has what it needs
    if VENV_DIR.exists() and VENV_PYTHON.exists():
        ok(f"Virtual environment: {VENV_DIR}")
    else:
        warn("Virtual environment was not created")
        return

    # Quick package check — use the REAL import statement for each
    # (Python imports are case-sensitive: it's PyQt6, not pyqt6)
    import subprocess as sp
    critical = {
        "PyQt6":     "from PyQt6.QtWidgets import QApplication",
        "numpy":     "import numpy",
        "requests":  "import requests",
        "pyqtgraph": "import pyqtgraph",
    }
    missing = []
    pyqt6_dll_error = False
    for pkg, import_stmt in critical.items():
        r = sp.run([str(VENV_PYTHON), "-c", import_stmt],
                   capture_output=True, text=True)
        if r.returncode != 0:
            missing.append(pkg)
            if pkg == "PyQt6" and "DLL load failed" in (r.stderr or ""):
                pyqt6_dll_error = True
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



def _find_soapy_anywhere() -> str:
    """Search conda, miniforge, PothosSDR for SoapySDR Python package.
    Returns path to the SoapySDR directory or SoapySDR.py parent, or ''."""
    import os
    home = Path.home()

    candidates = [
        home / "miniforge3" / "Lib" / "site-packages",
        home / "miniconda3" / "Lib" / "site-packages",
        home / "anaconda3"  / "Lib" / "site-packages",
        home / "mambaforge" / "Lib" / "site-packages",
        Path(os.environ.get("LOCALAPPDATA", "")) / "miniforge3" / "Lib" / "site-packages",
        Path(os.environ.get("LOCALAPPDATA", "")) / "miniconda3"  / "Lib" / "site-packages",
        Path(r"C:/miniforge3/Lib/site-packages"),
        Path(r"C:/miniconda3/Lib/site-packages"),
        Path(r"C:/anaconda3/Lib/site-packages"),
        Path(r"C:/Program Files/PothosSDR/lib/python3.9/site-packages"),
    ]
    # Also check conda envs/ subdirectories
    for base in [home / "miniforge3", home / "miniconda3",
                 Path(r"C:/miniforge3"), Path(r"C:/miniconda3")]:
        envs = base / "envs"
        if envs.exists():
            for env in envs.iterdir():
                candidates.append(env / "Lib" / "site-packages")

    for sp in candidates:
        if not sp or not sp.exists():
            continue
        if (sp / "SoapySDR.py").exists():
            return str(sp)
        if (sp / "SoapySDR" / "__init__.py").exists():
            return str(sp / "SoapySDR")
    return ""


def _get_venv_site_packages() -> Path:
    """Return the venv's site-packages directory reliably."""
    import subprocess
    r = subprocess.run(
        [str(VENV_PYTHON), "-c",
         "import sysconfig; print(sysconfig.get_path('purelib'))"],
        capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        p = Path(r.stdout.strip())
        if p.exists():
            return p
    # Fallback: construct manually
    return VENV_DIR / "Lib" / "site-packages"


def _install_soapy_plugins(site_pkgs: Path):
    """Copy SoapySDR device plugins from conda into venv site-packages."""
    import shutil
    PLUGIN_STEMS = {
        "SoapyRTLSDR":   "RTL-SDR dongles",
        "SoapyHackRF":   "HackRF One",
        "SoapySDRPlay":  "SDRplay RSP family",
        "SoapyUHD":      "USRP B200/B210",
        "SoapyAirspy":   "Airspy R2/Mini",
        "SoapyLMS7":     "LimeSDR",
        "SoapyBladeRF":  "BladeRF",
    }
    soapy_src = _find_soapy_anywhere()
    if not soapy_src:
        return
    src_dir = Path(soapy_src)
    if src_dir.name == "SoapySDR":
        src_dir = src_dir.parent
    found = False
    for stem, hw in PLUGIN_STEMS.items():
        for pyd in src_dir.glob(f"{stem}*.pyd"):
            try:
                shutil.copy2(pyd, site_pkgs / pyd.name)
                ok(f"  Plugin: {pyd.name}  ({hw})")
                found = True
            except Exception as e:
                info(f"  Could not copy {pyd.name}: {e}")
    if not found:
        info("No device plugins found in conda.")
        info("Install: conda install -c conda-forge "
             "soapysdr-module-rtlsdr soapysdr-module-hackrf")
        info("Then re-run: python installer.py")


def _recreate_venv(python_exe: Path):
    """Delete and recreate venv with the given Python, reinstall packages,
    then copy SoapySDR and device plugins."""
    import shutil, subprocess as sp
    info(f"Recreating venv with {python_exe} ...")

    if VENV_DIR.exists():
        try:
            shutil.rmtree(VENV_DIR)
            ok("Old venv removed.")
        except Exception as e:
            warn(f"Could not remove old venv: {e}")
            return

    result = sp.run(
        [str(python_exe), "-m", "venv", str(VENV_DIR)],
        capture_output=True, text=True)
    if result.returncode != 0:
        warn(f"venv creation failed: {result.stderr[:200]}")
        return
    ok(f"New venv created.")

    pkgs = ["PyQt6", "requests", "pyqtgraph", "numpy",
            "sounddevice", "sgp4", "defusedxml"]
    sp.run([str(VENV_PYTHON), "-m", "pip", "install",
            "--quiet", "--upgrade", "pip"],
           capture_output=True)
    r = sp.run([str(VENV_PYTHON), "-m", "pip", "install",
                "--quiet"] + pkgs, capture_output=True, text=True)
    if r.returncode == 0:
        ok(f"Packages installed: {', '.join(pkgs)}")
    else:
        warn(f"Some packages failed: {r.stderr[:100]}")

    # Copy SoapySDR core + plugins
    soapy_src = _find_soapy_anywhere()
    if not soapy_src:
        warn("SoapySDR not found — run fix_soapysdr.bat after install.")
        return

    import shutil
    site = _get_venv_site_packages()
    src_dir = Path(soapy_src)
    if src_dir.name == "SoapySDR":
        src_dir = src_dir.parent

    spy = src_dir / "SoapySDR.py"
    if spy.exists():
        shutil.copy2(spy, site / "SoapySDR.py")
        ok("Copied SoapySDR.py")

    soapy_folder = src_dir / "SoapySDR"
    if soapy_folder.exists():
        dst = site / "SoapySDR"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(soapy_folder, dst)
        ok("Copied SoapySDR/")

    for pyd in src_dir.glob("_SoapySDR*.pyd"):
        shutil.copy2(pyd, site / pyd.name)
        ok(f"Copied {pyd.name}")

    _install_soapy_plugins(site)


def _auto_fix_soapysdr():
    """Full SoapySDR auto-fix pipeline integrated into installer."""
    import re as _re, subprocess as sp, shutil

    # Step 1: already works?
    r = sp.run([str(VENV_PYTHON), "-c",
                "import SoapySDR; d=SoapySDR.Device.enumerate();"
                "print(f'SoapySDR {SoapySDR.getAPIVersion()} "
                "-- {len(d)} device(s)')"],
               capture_output=True, text=True)
    if r.returncode == 0:
        ok(r.stdout.strip())
        _install_soapy_plugins(_get_venv_site_packages())
        return

    # Step 2: find SoapySDR in conda/PothosSDR
    soapy_src = _find_soapy_anywhere()
    if not soapy_src:
        warn("SoapySDR not installed.")
        info("  conda install -c conda-forge soapysdr")
        info("  Then re-run: python installer.py")
        return

    src_dir = Path(soapy_src)
    if src_dir.name == "SoapySDR":
        src_dir = src_dir.parent

    # Step 3: check Python version vs .pyd version
    rv = sp.run([str(VENV_PYTHON), "--version"],
                capture_output=True, text=True)
    m = _re.search(r"Python (\d+)\.(\d+)", rv.stdout + rv.stderr)
    venv_maj, venv_min = (int(m.group(1)), int(m.group(2))) if m else (0, 0)

    pyd_files = list(src_dir.glob("_SoapySDR*.pyd"))
    pyd_maj, pyd_min = 0, 0
    if pyd_files:
        m2 = _re.search(r"cp(\d)(\d+)", pyd_files[0].name)
        if m2:
            pyd_maj, pyd_min = int(m2.group(1)), int(m2.group(2))

    if pyd_maj and (venv_maj != pyd_maj or venv_min != pyd_min):
        warn(f"Python version mismatch!")
        warn(f"  Venv:    Python {venv_maj}.{venv_min}")
        warn(f"  SoapySDR .pyd: cp{pyd_maj}{pyd_min} "
             f"= Python {pyd_maj}.{pyd_min}")
        info("")
        # Find matching conda Python
        for root in [Path.home() / "miniforge3", Path.home() / "miniconda3",
                     Path(r"C:/miniforge3"), Path(r"C:/miniconda3")]:
            py = root / "python.exe"
            if not py.exists():
                py = root / "bin" / "python3"
            if py.exists():
                rv2 = sp.run([str(py), "--version"],
                             capture_output=True, text=True)
                m3 = _re.search(r"Python (\d+)\.(\d+)",
                                rv2.stdout + rv2.stderr)
                if m3 and (int(m3.group(1)), int(m3.group(2))) == (pyd_maj, pyd_min):
                    ok(f"Found matching Python {pyd_maj}.{pyd_min}: {py}")
                    _recreate_venv(py)
                    return
        info(f"Install Python {pyd_maj}.{pyd_min} from python.org")
        info("Or: conda install -c conda-forge soapysdr  "
             "(to get a version matching your venv Python)")
        return

    # Step 4: copy into venv
    site = _get_venv_site_packages()
    info(f"Copying SoapySDR from {src_dir} to {site} ...")

    spy = src_dir / "SoapySDR.py"
    if spy.exists():
        shutil.copy2(spy, site / "SoapySDR.py")
        ok("  Copied SoapySDR.py")

    sf = src_dir / "SoapySDR"
    if sf.exists():
        dst = site / "SoapySDR"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(sf, dst)
        ok("  Copied SoapySDR/")

    for pyd in src_dir.glob("_SoapySDR*.pyd"):
        shutil.copy2(pyd, site / pyd.name)
        ok(f"  Copied {pyd.name}")

    # Step 5: verify and install plugins
    r2 = sp.run([str(VENV_PYTHON), "-c",
                 "import SoapySDR; d=SoapySDR.Device.enumerate();"
                 "print(f'SoapySDR {SoapySDR.getAPIVersion()} "
                 "-- {len(d)} device(s)')"],
                capture_output=True, text=True)
    if r2.returncode == 0:
        ok(f"SoapySDR working: {r2.stdout.strip()}")
        _install_soapy_plugins(site)
    else:
        err_msg = (r2.stderr or r2.stdout or "").strip()[:120]
        warn(f"SoapySDR still failing: {err_msg}")


def _select_sdr_drivers():
    """Interactive SDR driver selection step during install."""
    import shutil, subprocess as sp
    conda_exe = None
    for name in ["conda", "mamba", "micromamba"]:
        f = shutil.which(name)
        if f:
            conda_exe = f
            break
    if not conda_exe:
        for p in [
            Path.home() / "miniforge3" / "Scripts" / "conda.exe",
            Path.home() / "miniconda3"  / "Scripts" / "conda.exe",
            Path(r"C:/miniforge3/Scripts/conda.exe"),
            Path(r"C:/miniconda3/Scripts/conda.exe"),
        ]:
            if p.exists():
                conda_exe = str(p)
                break

    if not conda_exe:
        info("conda not found — skipping driver selection.")
        info("Install drivers later: conda install -c conda-forge soapyrtlsdr ...")
        return

    sep()
    hdr("[5b/6] SDR Hardware Drivers")
    DRIVERS = [
        ("1", "RTL-SDR  (any RTL2832U dongle)",
         "soapysdr-module-rtlsdr",
         "RTL-SDR Blog V3/V4, Nooelec, generic. Also needs Zadig WinUSB."),
        ("2", "HackRF One",
         "soapysdr-module-hackrf",
         "1 MHz - 6 GHz transceiver by Great Scott Gadgets."),
        ("3", "SDRplay RSP2Pro / RSP1A / RSPdx / RSPduo",
         "soapysdr-module-sdrplay",
         "Requires SDRplay API installed first: sdrplay.com/softwarehome"),
        ("4", "USRP B200 mini / B210  (Ettus Research)",
         "soapysdr-module-uhd",
         "Professional full-duplex, 70 MHz - 6 GHz. (may be Linux-only on conda)"),
        ("5", "Airspy R2 / Airspy Mini",
         "soapysdr-module-airspy",
         "High performance, 24 MHz - 1.8 GHz. (may be Linux-only on conda)"),
        ("6", "LimeSDR / LimeSDR Mini",
         "soapysdr-module-lms7",
         "Open source transceiver, 100 kHz - 3.8 GHz."),
        ("7", "ALL of the above",
         "soapysdr-module-rtlsdr soapysdr-module-hackrf "
         "soapysdr-module-sdrplay soapysdr-module-uhd "
         "soapysdr-module-airspy soapysdr-module-lms7",
         "Install all drivers (each tried separately; skips any unavailable)."),
        ("0", "Skip — install later via Settings > SDR Hardware",
         None, ""),
    ]
    print()
    print("  What SDR hardware do you have?")
    print("  You can select multiple: type  1 3  for RTL-SDR and RSP2Pro")
    print()
    for num, name, pkg, note in DRIVERS:
        print(f"    [{num}]  {name}")
        if note:
            print(f"         {note}")
        print()
    try:
        choice = input("  Your choice(s): ").strip()
    except (EOFError, KeyboardInterrupt):
        info("Skipped.")
        return
    if not choice or choice.strip() == "0":
        info("Skipped. Install drivers later via Settings > SDR Hardware.")
        return

    selected_pkgs = []
    for token in choice.split():
        for num, name, pkg, note in DRIVERS:
            if token == num and pkg:
                for p in pkg.split():
                    if p not in selected_pkgs:
                        selected_pkgs.append(p)

    if not selected_pkgs:
        info("No valid selection — skipped.")
        return

    info(f"Installing {len(selected_pkgs)} driver(s), one at a time "
         "(so one unavailable package doesn't block the rest)...")
    succeeded, failed = [], []
    for pkg in selected_pkgs:
        print(f"  → {pkg}")
        r = sp.run([conda_exe, "install", "-c", "conda-forge", "-y", pkg],
                   capture_output=not VERBOSE)
        if r.returncode == 0:
            succeeded.append(pkg)
        else:
            failed.append(pkg)

    if succeeded:
        ok(f"Installed: {', '.join(succeeded)}")
        site = _get_venv_site_packages()
        _install_soapy_plugins(site)
    if failed:
        warn(f"Not available on this platform/channel: {', '.join(failed)}")
        info("  These drivers may be Linux-only on conda-forge, or need a")
        info("  vendor SDK first (e.g. SDRplay API, Ettus UHD). RTL-SDR and")
        info("  HackRF are the most reliable on Windows via conda.")
    if not succeeded:
        warn("No drivers installed. RTL-SDR is the simplest to start with:")
        info("  conda install -c conda-forge soapysdr-module-rtlsdr")


def main():
    parser = argparse.ArgumentParser(
        description="Squelch installer and dependency checker")
    parser.add_argument(
        "--check", action="store_true",
        help="Check dependencies only, do not install")
    parser.add_argument(
        "--offline", action="store_true",
        help="Install from offline cache only")
    parser.add_argument(
        "--cache", action="store_true",
        help="Download packages for offline use")
    parser.add_argument(
        "--no-av-prompt", action="store_true",
        help="Skip antivirus reminder (for automation)")
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Show full pip output (for debugging install failures)")
    args = parser.parse_args()

    # Make verbosity available to install_packages via module global
    global VERBOSE
    VERBOSE = args.verbose

    print()
    print(f"{BOLD}{'='*54}")
    print(f"  Squelch — Amateur Radio Operations Platform")
    print(f"  Setup and Dependency Installer")
    print(f"  github.com/dawardy/squelch")
    print(f"{'='*54}{RESET}")
    sep()

    if not args.check and not args.no_av_prompt:
        print_av_reminder()

    check_python()

    if not args.check:
        setup_venv()
        if args.cache:
            install_packages(cache_only=True)
        else:
            install_packages(offline=args.offline)
        setup_config()
        create_launch_scripts()
        # Interactive SDR driver selection (skip if --no-av-prompt = automation mode)
        if not args.no_av_prompt:
            _select_sdr_drivers()

    check_external_tools()
    # Final banner — always visible regardless of what happened above
    _print_final_status()
    print_summary(0, 0)

    # Show where user data is stored
    try:
        import sys as _sys
        import os as _os
        if _sys.platform == "win32":
            _udir = Path(_os.environ.get(
                "APPDATA",
                Path.home() / "AppData" / "Roaming")) / "Squelch"
        else:
            _udir = Path.home() / ".config" / "squelch"
        info(f"User data stored at: {_udir}")
        info("This location persists through Squelch updates.")
    except Exception:
        pass
    sep()

    if not args.check:
        launch = input(
            "  Launch Squelch now? [Y/N]: ").strip().upper()
        if launch == 'Y':
            python_exe = str(VENV_PYTHON)
            main_py    = str(BASE_DIR / "main.py")
            try:
                subprocess.Popen(
                    [python_exe, main_py],
                    cwd=str(BASE_DIR),
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW
                        if IS_WINDOWS else 0),
                    close_fds=True)
                print("  Squelch launched.")
                # Don't show "Press Enter to close" — window can close now.
                return
            except Exception as e:
                print(f"  Launch failed: {e}")
                print(f"  Run manually: {python_exe} main.py")


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
