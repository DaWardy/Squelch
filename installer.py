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
if sys.version_info < (3, 11):
    print("\nERROR: Python 3.11 or newer required.")
    print(f"       You have Python {sys.version}")
    print("       Download: https://www.python.org/downloads/")
    print("       Check 'Add Python to PATH' during install.\n")
    input("Press Enter to exit...")
    sys.exit(1)

# ── Helpers ───────────────────────────────────────────────────────────────

RESET  = "\033[0m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"

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
    print(f"""
{YELLOW}{BOLD}╔══════════════════════════════════════════════════════════╗
║  IMPORTANT — READ BEFORE CONTINUING                       ║
║                                                          ║
║  Add this folder to your antivirus exclusions FIRST:    ║
║                                                          ║
║  {str(BASE_DIR)[:50]}  ║
║                                                          ║
║  NETGEAR Armor: Armor app → Settings → Exceptions       ║
║  Windows Defender: Security → Exclusions → Add folder   ║
║  Bitdefender: Protection → Exceptions → Add folder      ║
║                                                          ║
║  This prevents false positives during Python package    ║
║  installation. The folder contains only ham radio       ║
║  software — no threats.                                 ║
╚══════════════════════════════════════════════════════════╝{RESET}
""")
    response = input("  Have you added the folder exclusion? [Y/N]: ").strip().upper()
    if response != 'Y':
        print("\n  Please add the exclusion first, then run installer.py again.")
        print(f"  Folder to exclude: {BASE_DIR}\n")
        sys.exit(0)


# ── Step 1: Python info ───────────────────────────────────────────────────

def check_python():
    hdr("[1/6] Python")
    ver = sys.version_info
    ok(f"Python {ver.major}.{ver.minor}.{ver.micro}")
    if ver >= (3, 14):
        warn("Python 3.14 is pre-release and has known")
        warn("annotation evaluation changes that affect Squelch.")
        warn("Strongly recommended: install Python 3.12 from")
        warn("https://www.python.org/downloads/")
        warn("and re-run installer.py with Python 3.12.")
    elif ver >= (3, 11):
        ok("Python version supported.")


# ── Step 2: Virtual environment ───────────────────────────────────────────

def setup_venv():
    hdr("[2/6] Virtual Environment")
    if VENV_DIR.exists() and VENV_PYTHON.exists():
        ok("Virtual environment exists.")
        return
    info("Creating virtual environment...")
    result = subprocess.run(
        [sys.executable, "-m", "venv", str(VENV_DIR)],
        capture_output=True, text=True)
    if result.returncode != 0:
        err(f"Failed to create venv: {result.stderr}")
        sys.exit(1)
    ok("Virtual environment created.")


# ── Step 3: Packages ──────────────────────────────────────────────────────

def install_packages(offline: bool = False, cache_only: bool = False):
    hdr("[3/6] Python Packages")

    import sys as _sys
    if _sys.version_info >= (3, 14):
        warn("Python 3.14 detected — pre-release version!")
        warn("PyQtWebEngine lacks a Python 3.14 wheel.")
        warn("The map tab will show a setup guide instead.")
        warn("All other features will work normally.")
        warn("For map support: install Python 3.12")
        warn("from https://www.python.org/downloads/")
        warn("For full functionality: install Python 3.12")
        warn("from https://www.python.org/downloads/")
        sep()

    if not REQ_FILE.exists():
        warn("requirements.txt not found — skipping.")
        return

    pip = str(VENV_PIP)

    # Upgrade pip quietly first
    subprocess.run(
        [pip, "install", "--upgrade", "pip", "--quiet"],
        capture_output=True)

    if cache_only:
        # Just download to cache, don't install
        info(f"Downloading packages to {OFFLINE_DIR}...")
        OFFLINE_DIR.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [pip, "download", "-r", str(REQ_FILE),
             "-d", str(OFFLINE_DIR), "--quiet"],
            capture_output=True, text=True)
        if result.returncode == 0:
            count = len(list(OFFLINE_DIR.glob("*.whl"))) + \
                    len(list(OFFLINE_DIR.glob("*.tar.gz")))
            ok(f"Cached {count} packages in offline_packages/")
        else:
            warn(f"Some packages failed to cache: {result.stderr[:200]}")
        return

    # Build pip command
    # Build a filtered requirements file without PyQtWebEngine
    import tempfile, os
    req_lines = [
        l for l in REQ_FILE.read_text().splitlines()
        if not l.strip().startswith("PyQtWebEngine")
        and not (l.strip().startswith("#") and
                 "PyQtWebEngine" in l)]
    tmp_req = Path(tempfile.mktemp(suffix=".txt"))
    tmp_req.write_text("\n".join(req_lines))
    cmd = [pip, "install", "-r", str(tmp_req), "--quiet"]

    if offline and OFFLINE_DIR.exists():
        cmd += ["--no-index",
                "--find-links", str(OFFLINE_DIR)]
        info("Installing from offline cache...")
    elif OFFLINE_DIR.exists():
        # Try offline first, fall back to internet
        cmd += ["--find-links", str(OFFLINE_DIR)]
        info("Installing packages (using cache if available)...")
    else:
        info("Installing packages from internet...")
        info("This may take a few minutes on first run.")

    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        tmp_req.unlink()
    except Exception:
        pass

    if result.returncode != 0 and offline:
        warn("Offline install incomplete. Trying internet...")
        cmd_online = [pip, "install", "-r", str(REQ_FILE),
                      "--quiet"]
        result = subprocess.run(
            cmd_online, capture_output=True, text=True)

    if result.returncode == 0:
        ok("Packages installed.")
    else:
        warn("Some packages failed — installing individually...")
        # Show the actual error
        if result.stderr:
            for line in result.stderr.splitlines()[:5]:
                if line.strip():
                    info(f"  pip: {line.strip()[:80]}")

        # Install each package individually with verbose output
        import sys as _sys
        py_ver = (_sys.version_info.major,
                  _sys.version_info.minor)

        # Packages known to lack Python 3.14 wheels
        # Note: numpy/scipy/pyqtgraph DO work on 3.14 now
        PY314_SKIP = {
            "PyQtWebEngine",  # no 3.14 wheel yet
        }

        packages = [
            p.strip() for p in
            REQ_FILE.read_text().splitlines()
            if p.strip() and
               not p.strip().startswith("#") and
               not p.strip().startswith("//") and
               not p.strip().startswith("PyQtWebEngine")]

        failed = []
        skipped = []
        for pkg in packages:
            # Handle platform markers
            if "; sys_platform" in pkg:
                import platform as _plat
                marker = pkg.split(";")[1].strip()
                if "win32" in marker and                    _plat.system() != "Windows":
                    continue
                pkg = pkg.split(";")[0].strip()

            name = pkg.split(">=")[0].split("==")[0]                      .split("[")[0].strip()

            # Skip known Python 3.14 incompatible packages
            if py_ver >= (3, 14) and                name in PY314_SKIP:
                warn(f"  {name} — skipped "
                     f"(no Python 3.14 wheel yet)")
                skipped.append(name)
                continue

            r = subprocess.run(
                [pip, "install", pkg,
                 "--quiet", "--no-cache-dir"],
                capture_output=True, text=True)
            if r.returncode == 0:
                ok(f"  {name}")
            else:
                warn(f"  {name} — FAILED")
                failed.append(name)

        if skipped:
            info(f"Skipped on Python 3.14: "
                 f"{', '.join(skipped)}")
            info("Install Python 3.12 for full "
                 "feature support.")

        if failed:
            non_critical = {
                "PyQtWebEngine", "scipy", "pyqtgraph",
                "sounddevice", "soundfile", "soapysdr",
                "PyQtWebEngine>=6.4.0"}
            real_failures = [
                p for p in failed
                if p not in non_critical]
            if real_failures:
                warn(f"Failed (critical): "
                     f"{', '.join(real_failures)}")
            optional_failures = [
                p for p in failed
                if p in non_critical]
            if optional_failures:
                info(f"Not installed (optional): "
                     f"{', '.join(optional_failures)}")
                info("App will run without these.")

    # Verify key packages - force reinstall PyQt6 if missing
    pyqt_result = subprocess.run(
        [str(VENV_PYTHON), "-c",
         "from PyQt6.QtCore import QT_VERSION_STR"],
        capture_output=True, text=True)
    if pyqt_result.returncode != 0:
        warn("PyQt6 not working — attempting reinstall...")
        subprocess.run(
            [pip, "install", "PyQt6", "--force-reinstall",
             "--no-cache-dir", "--quiet"],
            capture_output=True)
        # Verify again
        pyqt_result2 = subprocess.run(
            [str(VENV_PYTHON), "-c",
             "from PyQt6.QtCore import QT_VERSION_STR;"
             "print('PyQt6 Qt/' + QT_VERSION_STR)"],
            capture_output=True, text=True)
        if pyqt_result2.returncode == 0:
            ok(f"PyQt6 {pyqt_result2.stdout.strip()}")
        else:
            err("PyQt6 install failed — Squelch cannot run")
            err("Try manually: pip install PyQt6 --no-cache-dir")
    else:
        subprocess.run(
            [str(VENV_PYTHON), "-c",
             "from PyQt6.QtCore import QT_VERSION_STR;"
             "print('  [OK]   PyQt6 Qt/' + QT_VERSION_STR)"],
            capture_output=True, text=True)
        ok("PyQt6 detected")

    _verify_package("numpy")
    _verify_package("pyqtgraph")
    _verify_package("sounddevice")
    _verify_package("keyring")

    # Cache for future offline use if not already cached
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
        warn("SoapySDR not installed — SDR tab unavailable.")
        info("Not required if using IC-7100 USB audio for spectrum.")
        info("Install guide: github.com/dawardy/squelch/wiki/sdr-setup")
        info("Quick reference:")
        info("  RTL-SDR:  zadig.akeo.ie (driver) then pip install soapysdr")
        info("  SDRplay:  sdrplay.com/softwarehome")
        info("  HackRF:   github.com/pothosware/SoapyHackRF")
        info("  USRP:     ettus.com/all-ettus-software")
        info("  Windows:  Install PothosSDR bundle first:")
        info("  downloads.myriadrf.org/builds/PothosSDR/")
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
        warn("config.example.json not found.")


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
    args = parser.parse_args()

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

    check_external_tools()
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
            # Launch directly via Python — no cmd window
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
            except Exception as e:
                print(f"  Launch failed: {e}")
                print(f"  Run manually: {python_exe} main.py")


if __name__ == "__main__":
    main()
