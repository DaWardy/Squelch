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
# Enable ANSI color on Windows
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleMode(
            ctypes.windll.kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass  # ANSI not available, colors will be ignored

os.environ["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

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
        ok(f"SoapySDR {SoapySDR.getAPIVersion()} -- installed")
        devs = SoapySDR.Device.enumerate()
        if devs:
            for i, d in enumerate(devs):
                label = d.get("label", d.get("driver", f"Device {i}"))
                ok(f"  SDR device: {label}")
        else:
            info("SoapySDR installed but no devices detected.")
            info("This is normal if no SDR is plugged in,")
            info("OR if device plugins are missing.")
            info("")
            info("Device plugins needed (install via conda):")
            info("  RSP2Pro / RSP1A:  conda install -c conda-forge soapysdrplay3")
            info("  RTL-SDR:          conda install -c conda-forge soapyrtlsdr")
            info("  HackRF:           conda install -c conda-forge soapyhackrf")
            info("  USRP B200/B210:   conda install -c conda-forge soapyuhd")
            info("  Airspy:           conda install -c conda-forge soapyairspy")
            info("")
            info("Then copy new .pyd files from conda to venv and re-run.")
        return True
    except ImportError:
        warn("SoapySDR not installed -- SDR tab unavailable")
        info("")
        info("Install core library:")
        info("  conda install -c conda-forge soapysdr")
        info("Then copy to venv with fix_soapysdr.bat")
        return True
    except Exception as e:
        warn(f"SoapySDR error: {e}")
        return True


def _saved_paths() -> dict:
    """Read tool paths the user configured in Squelch Settings.
    These live in config.json under keys like 'paths.wsjtx'."""
    import json, os
    try:
        appdata = os.environ.get("APPDATA", str(Path.home()))
        cfg_path = Path(appdata) / "Squelch" / "config.json"
        if not cfg_path.exists():
            cfg_path = Path("config.json")
        if cfg_path.exists():
            data = json.loads(cfg_path.read_text())
            # Flatten nested {"paths": {"wsjtx": "..."}} or flat "paths.wsjtx"
            result = {}
            paths = data.get("paths", {})
            if isinstance(paths, dict):
                for k, v in paths.items():
                    result[k] = v
            for k, v in data.items():
                if k.startswith("paths."):
                    result[k.split(".", 1)[1]] = v
            return result
    except Exception:
        pass
    return {}


def check_external():
    head("External Programs")
    pf = Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
    pf86 = Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)"))

    checks = [
        ("WSJT-X", [
            pf/"WSJT-X/bin/wsjtx.exe",
            pf86/"WSJT-X/bin/wsjtx.exe",
            Path(r"C:\WSJT\wsjtx\bin\wsjtx.exe"),
            Path(r"C:\WSJT\WSJTX\bin\wsjtx.exe"),
            Path(r"C:\wsjtx\bin\wsjtx.exe"),
            Path(r"D:\WSJT\wsjtx\bin\wsjtx.exe"),
        ], "FT8/FT4/WSPR digital modes",
           "https://wsjt.sourceforge.io/wsjtx.html", True),

        ("JS8Call", [
            pf/"JS8Call/js8call.exe",
            pf/"JS8Call/bin/js8call.exe",
            pf86/"JS8Call/js8call.exe",
            Path(r"C:\Program Files\JS8Call\js8call.exe"),
            Path(r"C:\JS8Call\js8call.exe"),
        ], "JS8 keyboard messaging",
           "https://js8call.com/", False),

        ("Fldigi", [
            pf/"Fldigi/fldigi.exe",
            pf/"Fldigi-4.2.11/fldigi.exe",
            pf/"Fldigi-4.2.10/fldigi.exe",
            pf/"Fldigi-4.2.05/fldigi.exe",
            pf/"Fldigi-4.1.20/fldigi.exe",
            pf86/"Fldigi/fldigi.exe",
            pf86/"Fldigi-4.2.11/fldigi.exe",
        ], "PSK31/RTTY/CW/SSTV digital modes",
           "https://sourceforge.net/projects/fldigi/", False),

        ("VARA HF", [
            Path(r"C:\VARA\VARA.exe"),
            Path(r"C:\VARA\VARAHF.exe"),
            Path(r"C:\VARA HF\VARA.exe"),
            Path(r"C:\VARA HF\VARAHF.exe"),
            pf/"VARA/VARA.exe",
            pf/"VARA HF/VARAHF.exe",
        ], "Winlink HF modem (required for HF Winlink)",
           "https://rosmodem.com/vara-hf/", False),

        ("VARA FM", [
            Path(r"C:\VARA FM\VARAFM.exe"),
            Path(r"C:\VARA FM\VARA FM.exe"),
            Path(r"C:\VARAFM\VARAFM.exe"),
            pf/"VARA FM/VARAFM.exe",
        ], "Winlink VHF/UHF modem (required for VHF Winlink)",
           "https://rosmodem.com/vara-fm/", False),

        ("DSD+ (closed source)", [
            Path(r"C:\DSDPlusFull\DSDPlus.exe"),
            Path(r"C:\DSDPlus\DSDPlus.exe"),
            Path(r"C:\dsdplus\DSDPlus.exe"),
            pf/"DSDPlus/DSDPlus.exe",
        ], "P25/DMR/NXDN/YSF digital voice decode",
           "https://www.dsdplus.com/", False),

        ("Hamlib (rigctld)", [
            Path(r"C:\hamlib\bin\rigctld.exe"),
            Path(r"C:\Hamlib\bin\rigctld.exe"),
            pf/"Hamlib/bin/rigctld.exe",
            pf86/"Hamlib/bin/rigctld.exe",
        ], "CAT control for 300+ rigs (IC-7100, FT-991A, etc.)",
           "https://hamlib.org/", False),

        ("CHIRP", [
            pf/"CHIRP/chirp.exe",
            pf/"CHIRP/chirpw.exe",
            pf86/"CHIRP/chirp.exe",
        ], "Radio programming — Baofeng, IC-7100, FT-991A and 200+ radios",
           "https://chirpmyradio.com/", False),

        ("Winlink Express", [
            Path(r"C:\RMS Express\RMS Express.exe"),
            pf/"RMS Express/RMS Express.exe",
            pf86/"RMS Express/RMS Express.exe",
        ], "Winlink email client (optional — Squelch has built-in Winlink)",
           "https://downloads.winlink.org/User%20Programs/", False),
    ]

    results = {}
    saved = _saved_paths()
    # Map display names to config keys so we honor user-configured paths
    name_to_key = {
        "WSJT-X": "wsjtx", "JS8Call": "js8call", "Fldigi": "fldigi",
        "VARA HF": "vara_hf", "VARA FM": "vara_fm", "DSD+": "dsdplus",
        "Hamlib (rigctld)": "rigctld", "RMS Express": "rms_express",
    }

    # Linux/Debian binary names for PATH lookup (P3 — no .exe suffix)
    which_names = {
        "WSJT-X": "wsjtx", "JS8Call": "js8call", "Fldigi": "fldigi",
        "Hamlib (rigctld)": "rigctld", "DSD+": "dsd",
    }

    for name, paths, desc, url, required in checks:
        # First honor the path the user set in Settings, if it exists
        key = name_to_key.get(name)
        configured = saved.get(key, "") if key else ""
        found = bool(configured and Path(configured).exists())
        # Fall back to scanning the standard install locations
        if not found:
            found = any(p.exists() for p in paths)
        # On Linux/macOS, tools are usually on PATH (e.g. /usr/bin) — check
        # there too with the platform binary name (P3, Linux reviewer).
        if not found:
            import shutil as _sh
            wn = which_names.get(name)
            if wn and _sh.which(wn):
                found = True
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
    try:
        return _check_config_inner()
    except Exception as e:
        fail(f"Config check error (non-fatal): {e}")
        return False


def _check_config_inner():
    import os, json

    # Squelch stores config in APPDATA, not the app folder
    appdata = Path(os.environ.get("APPDATA", Path.home()))
    appdata_cfg = appdata / "Squelch" / "config.json"
    local_cfg   = Path("config.json")
    example_cfg = Path("config.example.json")

    # Find whichever config exists
    cfg_path = None
    if appdata_cfg.exists():
        cfg_path = appdata_cfg
        ok(f"config.json: {appdata_cfg}")
    elif local_cfg.exists():
        cfg_path = local_cfg
        ok(f"config.json: {local_cfg}")
    else:
        # Neither exists - create from template
        if example_cfg.exists():
            import shutil
            appdata_cfg.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(example_cfg, appdata_cfg)
            ok("config.json created from template in AppData")
            cfg_path = appdata_cfg
        else:
            warn("config.json not found -- will be created on first launch")
            info("This is normal on first install.")
            info("Launch Squelch to complete setup.")
            return True   # Not a failure - first run is fine

    try:
        with open(cfg_path) as f:
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
        print(f"  {CYAN}         run_squelch.bat{RESET}")
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

    # Warn about Python 3.14+ — many packages don't have wheels yet
    py_major, py_minor = sys.version_info[:2]
    if py_major == 3 and py_minor >= 14:
        print()
        print(f"  {YELLOW}{BOLD}WARNING: Python {py_major}.{py_minor} is very new.{RESET}")
        print(f"  {YELLOW}Many packages (PyQt6, SoapySDR) may not have wheels yet.{RESET}")
        print(f"  {YELLOW}Recommended: Python 3.11, 3.12, or 3.13 for best compatibility.{RESET}")
        print(f"  {YELLOW}Download: https://www.python.org/downloads/{RESET}")
        print()

    if args.fix:
        print("\nReinstalling Python packages...")
        subprocess.run([sys.executable, "-m", "pip", "install",
                        "-r", "requirements.txt",
                        "--no-cache-dir", "--upgrade"])

    results = {}
    # Each check is isolated — one failing crash can't prevent others
    # or the final summary from running
    for name, fn in [
        ("Python",          check_python),
        ("Python packages", lambda: check_python_packages(args.verbose)),
        ("Hamlib",          check_hamlib),
        ("Audio",           check_audio),
        ("Serial ports",    check_serial),
        ("SDR Hardware",    lambda: (check_sdr() or True)),
        ("External tools",  lambda: check_external().get("WSJT-X", False)),
        ("Config",          check_config),
    ]:
        try:
            results[name] = fn()
        except Exception as e:
            fail(f"{name} check crashed: {e}")
            results[name] = False

    print_summary(results)

    # Offer to launch the installer if packages are missing
    if not results.get("Python packages", True):
        print()
        print(f"  {YELLOW}{BOLD}Python packages are missing.{RESET}")
        print(f"  {CYAN}Run the installer to fix automatically:{RESET}")
        print(f"  {CYAN}    python installer.py{RESET}")
        print()
        try:
            ans = input("  Launch installer now? (Y/n): ").strip().lower()
            if ans in ("", "y", "yes"):
                import subprocess as _sp
                _sp.run([sys.executable, "installer.py"])
        except (EOFError, KeyboardInterrupt):
            pass


if __name__ == "__main__":
    main()
    # Keep window open when double-clicked
    import os
    if os.environ.get("PROMPT") or os.name == "nt":
        input("\nPress Enter to close...")
