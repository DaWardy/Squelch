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
Squelch -- install_check.py
Checks all dependencies and reports status clearly.
Run any time something stops working or after any update.

Usage:
    python install_check.py
    python install_check.py --verbose
    python install_check.py --fix
"""

import sys
import os
import subprocess
import shutil
import argparse
from pathlib import Path

# ── Console colors (Windows-safe) ────────────────────────────────────────
if sys.platform == "win32":
    os.system("color")

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
WHITE  = "\033[97m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):    print(f"  {GREEN}[OK]  {RESET} {msg}")
def warn(msg):  print(f"  {YELLOW}[WARN]{RESET} {msg}")
def fail(msg):  print(f"  {RED}[FAIL]{RESET} {msg}")
def info(msg):  print(f"  {CYAN}  -->  {RESET}{msg}")
def head(msg):  print(f"\n{BOLD}{WHITE}{msg}{RESET}\n{'─'*54}")


# ── Checks ────────────────────────────────────────────────────────────────

def check_python():
    head("Python Runtime")
    v = sys.version_info
    vs = f"{v.major}.{v.minor}.{v.micro}"
    if v.major == 3 and v.minor >= 11:
        ok(f"Python {vs}")
        return True
    elif v.major == 3 and v.minor >= 9:
        warn(f"Python {vs} -- 3.11+ recommended for full compatibility")
        return True
    else:
        fail(f"Python {vs} -- 3.11+ required")
        info("https://www.python.org/downloads/")
        return False


def check_python_packages(verbose=False):
    head("Python Packages")
    pkgs = [
        ("PyQt6",        "PyQt6",          "GUI framework",           True),
        ("numpy",        "numpy",          "Signal processing",       True),
        ("scipy",        "scipy",          "DSP / FFT",               True),
        ("sounddevice",  "sounddevice",    "Audio I/O",               True),
        ("soundfile",    "soundfile",      "Audio files",             True),
        ("serial",       "pyserial",       "Serial / COM ports",      True),
        ("requests",     "requests",       "HTTP API calls",          True),
        ("aiohttp",      "aiohttp",        "Async HTTP",              True),
        ("websockets",   "websockets",     "WebSocket",               False),
        ("folium",       "folium",         "Map rendering",           True),
        ("geopy",        "geopy",          "Geocoding",               True),
        ("maidenhead",   "maidenhead",     "Grid squares",            True),
        ("mgrs",         "mgrs",           "MGRS coordinates",        False),
        ("adif_io",      "adif-io",        "ADIF log files",          True),
        ("xmltodict",    "xmltodict",      "XML parsing",             True),
        ("dateutil",     "python-dateutil","Date handling",           True),
        ("pyhamtools",   "pyhamtools",     "Ham radio utilities",     False),
        ("appdirs",      "appdirs",        "App directories",         True),
        ("psutil",       "psutil",         "Process management",      True),
        ("markdown",     "Markdown",       "Help rendering",          False),
        ("PIL",          "Pillow",         "Images",                  False),
        ("pyqtgraph",    "pyqtgraph",      "Waterfall display",       True),
    ]
    missing_required = []
    missing_optional = []
    for imp, pkg, desc, required in pkgs:
        try:
            mod = __import__(imp)
            ver = getattr(mod, "__version__", "")
            if verbose:
                ok(f"{pkg:<22} {ver:<12} {desc}")
            else:
                ok(f"{pkg}")
        except ImportError:
            if required:
                fail(f"{pkg} -- MISSING ({desc})")
                missing_required.append(pkg)
            else:
                warn(f"{pkg} -- missing, optional ({desc})")
                missing_optional.append(pkg)

    # SoapySDR separate
    try:
        import SoapySDR
        ok(f"SoapySDR               {SoapySDR.getAPIVersion()}")
    except ImportError:
        warn("SoapySDR -- not installed (SDR Waterfall unavailable)")
        info("https://github.com/pothosware/SoapySDR")
        info("See README for platform-specific install instructions")

    if missing_required:
        print()
        fail(f"{len(missing_required)} required package(s) missing")
        info("Run:  pip install -r requirements.txt --no-cache-dir")
        return False
    return True


def check_hamlib():
    head("Hamlib  (Rig Control)")
    # Check PATH first
    path = shutil.which("rigctld")
    if path:
        try:
            r = subprocess.run(["rigctld", "--version"],
                               capture_output=True, text=True, timeout=5)
            ver = (r.stdout + r.stderr).strip().split("\n")[0]
            ok(f"rigctld found: {ver}")
            return True
        except Exception:
            ok("rigctld found in PATH")
            return True
    # Check common install locations
    candidates = [
        Path("C:/hamlib/bin/rigctld.exe"),
        Path("C:/Program Files/Hamlib/bin/rigctld.exe"),
        Path("C:/Program Files (x86)/Hamlib/bin/rigctld.exe"),
    ]
    for c in candidates:
        if c.exists():
            warn(f"Hamlib found at {c.parent} but NOT in PATH")
            info("Add that folder to your system PATH variable")
            info("Then REBOOT for the change to take effect")
            return False
    fail("Hamlib (rigctld) not found")
    info("Download: https://github.com/Hamlib/Hamlib/releases")
    info("Extract and add the bin\\ folder to your system PATH")
    info("Reboot after adding to PATH")
    return False


def check_audio():
    head("Audio Devices")
    try:
        import sounddevice as sd
        devs = sd.query_devices()
        names = [d["name"] for d in devs]

        vb = [n for n in names if "CABLE" in n.upper() or "VB-AUDIO" in n.upper()]
        if vb:
            ok(f"VB-Cable: {vb[0]}")
        else:
            warn("VB-Cable not detected")
            info("https://vb-audio.com/Cable/")
            info("Install as Administrator then reboot")

        ic = [n for n in names if any(x in n.upper() for x in
              ["USB AUDIO", "USB CODEC", "IC-7100", "USB2.0 MIC"])]
        if ic:
            ok(f"IC-7100 audio: {ic[0]}")
        else:
            info("IC-7100 USB audio not detected (OK if not connected)")

        ok(f"Total audio devices: {len(devs)}")
        return True
    except Exception as e:
        fail(f"Could not query audio: {e}")
        return False


def check_serial():
    head("Serial Ports  (IC-7100 CI-V)")
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            info("No serial ports found -- IC-7100 not connected (OK if no rig)")
            return True
        ic = [p for p in ports if any(x in (p.description or "").upper()
              for x in ["CP210", "CI-V", "IC-7100", "USB SERIAL", "UART"])]
        if ic:
            for p in ic:
                ok(f"Likely IC-7100: {p.device}  {p.description}")
        else:
            for p in ports:
                info(f"Port: {p.device}  {p.description or 'no description'}")
            warn("No port identified as IC-7100 -- select manually in app if needed")
        return True
    except Exception as e:
        fail(f"Serial port check failed: {e}")
        return False


def check_sdr():
    head("SDR Hardware  (SoapySDR)")
    try:
        import SoapySDR
        devs = SoapySDR.Device.enumerate()
        if devs:
            for i, d in enumerate(devs):
                label = d.get("label", d.get("driver", f"Device {i}"))
                ok(f"SDR {i}: {label}")
        else:
            info("No SDR hardware detected -- connect device and re-run")
            info("Supported: RTL-SDR, USRP B200/B210, RSP2duo, HackRF,")
            info("           LimeSDR, Airspy, BladeRF, PlutoSDR")
        return True
    except ImportError:
        warn("SoapySDR not installed -- SDR tab unavailable")
        info("https://github.com/pothosware/SoapySDR")
        return True
    except Exception as e:
        warn(f"SoapySDR error: {e}")
        return True


def check_external():
    head("External Programs")
    pf = Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
    pf86 = Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)"))

    checks = [
        ("WSJT-X",    [pf/"WSJT-X/bin/wsjtx.exe",
                        pf86/"WSJT-X/bin/wsjtx.exe"],
                       "FT8/FT4/WSPR/JT modes",
                       "https://wsjt.sourceforge.io/wsjtx.html",
                       True),
        ("JS8Call",   [pf/"JS8Call/js8call.exe",
                        pf86/"JS8Call/js8call.exe"],
                       "JS8 keyboard messaging",
                       "https://js8call.com/",
                       False),
        ("Fldigi",    [pf/"fldigi/fldigi.exe",
                        pf86/"fldigi/fldigi.exe"],
                       "PSK31/RTTY/CW/SSTV",
                       "https://sourceforge.net/projects/fldigi/",
                       False),
        ("VARA HF",   [Path("C:/VARA HF/VARAHF.exe"),
                        Path("C:/VARA/VARAHF.exe")],
                       "Winlink HF",
                       "https://rosmodem.wordpress.com/",
                       False),
        ("VARA FM",   [Path("C:/VARA FM/VARAFM.exe"),
                        Path("C:/VARA FM/VARAFM.exe")],
                       "Winlink VHF/UHF",
                       "https://rosmodem.wordpress.com/",
                       False),
        ("DSD+",      [Path("C:/dsdplus/DSDPlus.exe"),
                        Path("C:/DSDPlus/DSDPlus.exe")],
                       "DMR/NXDN/YSF decode",
                       "https://www.dsdplus.com/",
                       False),
    ]

    results = {}
    for name, paths, desc, url, required in checks:
        found = any(p.exists() for p in paths)
        if found:
            ok(f"{name:<16} found  ({desc})")
        elif required:
            fail(f"{name:<16} NOT FOUND  ({desc})")
            info(f"{url}")
        else:
            warn(f"{name:<16} not found, optional  ({desc})")
            info(f"{url}")
        results[name] = found

    return results


def check_config():
    head("Squelch Configuration")
    if not Path("config.json").exists():
        if Path("config.example.json").exists():
            warn("config.json not found -- will be created from template on launch")
            info("Run python main.py to complete first-run setup")
        else:
            fail("config.json and config.example.json both missing")
        return False
    try:
        import json
        with open("config.json") as f:
            cfg = json.load(f)
        cs = cfg.get("callsign", "")
        gr = cfg.get("grid_square", "")
        ok(f"Callsign:    {cs if cs else '(not set -- enter on first launch)'}")
        ok(f"Grid square: {gr if gr else '(not set -- enter on first launch)'}")
        rr = cfg.get("apis", {}).get("radioreference_key", "")
        if rr:
            ok("RadioReference API key: configured")
        else:
            info("RadioReference API key not set (optional)")
            info("https://radioreference.com/api")
        return True
    except Exception as e:
        fail(f"config.json parse error: {e}")
        return False


def print_summary(results: dict):
    head("Summary")
    passed = sum(1 for v in results.values() if v)
    total  = len(results)
    failed = total - passed
    print()
    if failed == 0:
        print(f"  {GREEN}{BOLD}All {total} checks passed.{RESET}")
        print(f"  {CYAN}Launch:  python main.py{RESET}")
        print(f"  {CYAN}         run_apex.bat{RESET}")
    else:
        print(f"  {YELLOW}{BOLD}{passed}/{total} checks passed -- {failed} issue(s) found.{RESET}")
        failing = [k for k, v in results.items() if not v]
        print(f"  Issues:  {', '.join(failing)}")
        print()
        print("  Review items marked [FAIL] or [WARN] above.")
        print("  Missing optional tools only disable their specific tab.")
        print("  Squelch will still launch if Python packages are installed.")
    print()


def main():
    parser = argparse.ArgumentParser(description="Squelch dependency checker")
    parser.add_argument("--verbose", action="store_true",
                        help="Show version for every Python package")
    parser.add_argument("--fix", action="store_true",
                        help="Reinstall Python packages from requirements.txt")
    args = parser.parse_args()

    print(f"\n{BOLD}{WHITE}Squelch -- Dependency Checker{RESET}")
    print("=" * 54)
    print(f"Platform: {sys.platform}   Python: {sys.version.split()[0]}")

    if args.fix:
        print("\nReinstalling Python packages...")
        subprocess.run([sys.executable, "-m", "pip", "install",
                        "-r", "requirements.txt",
                        "--no-cache-dir", "--upgrade"])

    results = {}
    results["Python"]          = check_python()
    results["Python packages"] = check_python_packages(args.verbose)
    results["Hamlib"]          = check_hamlib()
    results["Audio"]           = check_audio()
    results["Serial ports"]    = check_serial()
    check_sdr()   # informational only, not in pass/fail
    ext = check_external()
    results["WSJT-X"] = ext.get("WSJT-X", False)
    results["Config"] = check_config()

    print_summary(results)


if __name__ == "__main__":
    main()
