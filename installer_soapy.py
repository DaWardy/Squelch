from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
installer_soapy.py
SoapySDR auto-fix pipeline and SDR driver selection helpers.
Extracted from installer.py to reduce file complexity.

Public API:
  _auto_fix_soapysdr()   — detect, copy, and verify SoapySDR in the venv
  _select_sdr_drivers()  — interactive conda driver selection step
  _find_conda()          — locate conda/mamba executable
  _get_venv_site_packages() — return venv site-packages Path
  _install_soapy_plugins()  — copy device plugins into venv
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# ── Shared constants (mirrors installer.py — same directory) ─────────────────

VERBOSE: bool = False          # set by installer.main() after arg parse

_BASE_DIR    = Path(__file__).parent.resolve()
_VENV_DIR    = _BASE_DIR / "venv"
_IS_WINDOWS  = sys.platform == "win32"
_VENV_PYTHON = (_VENV_DIR / "Scripts" / "python.exe"
                if _IS_WINDOWS
                else _VENV_DIR / "bin" / "python3")

# ── Print helpers ────────────────────────────────────────────────────────────

_RESET  = "\033[0m"
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_RED    = "\033[91m"
_BOLD   = "\033[1m"
_CYAN   = "\033[96m"

def ok(msg):    print(f"  {_GREEN}[OK]{_RESET}   {msg}")
def warn(msg):  print(f"  {_YELLOW}[WARN]{_RESET} {msg}")
def err(msg):   print(f"  {_RED}[FAIL]{_RESET} {msg}")
def info(msg):  print(f"  {_CYAN}[INFO]{_RESET} {msg}")
def hdr(msg):   print(f"\n{_BOLD}{msg}{_RESET}\n  {'─'*50}")
def sep():      print()

# ── SoapySDR auto-fix pipeline ───────────────────────────────────────────────

def _find_soapy_anywhere() -> str:
    """Search conda, miniforge, PothosSDR for SoapySDR Python package.
    Returns path to the SoapySDR directory or SoapySDR.py parent, or ''."""
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
    r = subprocess.run(
        [str(_VENV_PYTHON), "-c",
         "import sysconfig; print(sysconfig.get_path('purelib'))"],
        capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        p = Path(r.stdout.strip())
        if p.exists():
            return p
    # Fallback: construct manually
    return _VENV_DIR / "Lib" / "site-packages"


def _install_soapy_plugins(site_pkgs: Path):
    """Copy SoapySDR device plugins from conda into venv site-packages."""
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


def _copy_soapy_to_venv(soapy_src: str, site: Path) -> None:
    """Copy SoapySDR core module + device plugins into the venv site-packages."""
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


def _recreate_venv(python_exe: Path):
    """Delete and recreate venv with the given Python, reinstall packages,
    then copy SoapySDR and device plugins."""
    import subprocess as sp
    info(f"Recreating venv with {python_exe} ...")

    if _VENV_DIR.exists():
        try:
            shutil.rmtree(_VENV_DIR)
            ok("Old venv removed.")
        except Exception as e:
            warn(f"Could not remove old venv: {e}")
            return

    result = sp.run(
        [str(python_exe), "-m", "venv", str(_VENV_DIR)],
        capture_output=True, text=True)
    if result.returncode != 0:
        warn(f"venv creation failed: {result.stderr[:200]}")
        return
    ok("New venv created.")

    pkgs = ["PyQt6", "requests", "pyqtgraph", "numpy",
            "sounddevice", "sgp4", "defusedxml"]
    sp.run([str(_VENV_PYTHON), "-m", "pip", "install",
            "--quiet", "--upgrade", "pip"],
           capture_output=True)
    r = sp.run([str(_VENV_PYTHON), "-m", "pip", "install",
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
    _copy_soapy_to_venv(soapy_src, _get_venv_site_packages())


_SOAPY_PROBE = (
    "import SoapySDR; d=SoapySDR.Device.enumerate();"
    "print(f'SoapySDR {SoapySDR.getAPIVersion()} -- {len(d)} device(s)')"
)


def _soapy_already_works() -> bool:
    """Return True (and install plugins) if SoapySDR already imports in venv."""
    r = subprocess.run([str(_VENV_PYTHON), "-c", _SOAPY_PROBE],
                       capture_output=True, text=True)
    if r.returncode == 0:
        ok(r.stdout.strip())
        _install_soapy_plugins(_get_venv_site_packages())
        return True
    return False


def _find_matching_conda_python(
        pyd_maj: int, pyd_min: int) -> Path | None:
    """Search conda roots for a Python whose version matches the .pyd ABI tag."""
    import re as _re
    for root in [Path.home() / "miniforge3", Path.home() / "miniconda3",
                 Path(r"C:/miniforge3"), Path(r"C:/miniconda3")]:
        py = root / "python.exe"
        if not py.exists():
            py = root / "bin" / "python3"
        if not py.exists():
            continue
        rv = subprocess.run([str(py), "--version"],
                            capture_output=True, text=True)
        m = _re.search(r"Python (\d+)\.(\d+)", rv.stdout + rv.stderr)
        if m and (int(m.group(1)), int(m.group(2))) == (pyd_maj, pyd_min):
            return py
    return None


def _soapy_version_compatible(src_dir: Path) -> bool:
    """Check venv Python vs SoapySDR .pyd ABI tag.
    Returns True if compatible (proceed to copy).
    Returns False and prints guidance if mismatched (caller should abort).
    """
    import re as _re
    rv = subprocess.run([str(_VENV_PYTHON), "--version"],
                        capture_output=True, text=True)
    m = _re.search(r"Python (\d+)\.(\d+)", rv.stdout + rv.stderr)
    venv_maj, venv_min = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    pyd_files = list(src_dir.glob("_SoapySDR*.pyd"))
    pyd_maj, pyd_min = 0, 0
    if pyd_files:
        m2 = _re.search(r"cp(\d)(\d+)", pyd_files[0].name)
        if m2:
            pyd_maj, pyd_min = int(m2.group(1)), int(m2.group(2))
    if not pyd_maj or (venv_maj == pyd_maj and venv_min == pyd_min):
        return True  # compatible or unknown — proceed
    warn(f"Python version mismatch: venv={venv_maj}.{venv_min}  "
         f"SoapySDR .pyd=cp{pyd_maj}{pyd_min}")
    py = _find_matching_conda_python(pyd_maj, pyd_min)
    if py:
        ok(f"Found matching Python {pyd_maj}.{pyd_min}: {py}")
        _recreate_venv(py)
        return False
    info(f"Install Python {pyd_maj}.{pyd_min} from python.org, or:")
    info("  conda install -c conda-forge soapysdr  (matches your venv Python)")
    return False


def _soapy_copy_to_venv(src_dir: Path, site: Path):
    """Copy SoapySDR Python binding files from src_dir into the venv."""
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


def _soapy_verify_install(site: Path):
    """Verify SoapySDR works after copy; install plugins if ok."""
    r = subprocess.run([str(_VENV_PYTHON), "-c", _SOAPY_PROBE],
                       capture_output=True, text=True)
    if r.returncode == 0:
        ok(f"SoapySDR working: {r.stdout.strip()}")
        _install_soapy_plugins(site)
    else:
        warn(f"SoapySDR still failing: "
             f"{(r.stderr or r.stdout or '').strip()[:120]}")


def _auto_fix_soapysdr():
    """Full SoapySDR auto-fix pipeline: check → find → verify ABI → copy → verify."""
    if _soapy_already_works():
        return
    soapy_src = _find_soapy_anywhere()
    if not soapy_src:
        warn("SoapySDR not installed.")
        info("  conda install -c conda-forge soapysdr")
        info("  Then re-run: python installer.py")
        return
    src_dir = Path(soapy_src)
    if src_dir.name == "SoapySDR":
        src_dir = src_dir.parent
    if not _soapy_version_compatible(src_dir):
        return
    site = _get_venv_site_packages()
    _soapy_copy_to_venv(src_dir, site)
    _soapy_verify_install(site)


# ── SDR driver selection ─────────────────────────────────────────────────────

_SDR_DRIVERS = [
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
    ("0", "Skip — install later via Settings > SDR Hardware", None, ""),
]


def _find_conda() -> str | None:
    """Return path to conda/mamba/micromamba, or None if not found."""
    for name in ["conda", "mamba", "micromamba"]:
        f = shutil.which(name)
        if f:
            return f
    for p in [
        Path.home() / "miniforge3" / "Scripts" / "conda.exe",
        Path.home() / "miniconda3"  / "Scripts" / "conda.exe",
        Path(r"C:/miniforge3/Scripts/conda.exe"),
        Path(r"C:/miniconda3/Scripts/conda.exe"),
    ]:
        if p.exists():
            return str(p)
    return None


def _sdr_tokens_to_pkgs(tokens: list[str]) -> list[str]:
    """Resolve user token list (e.g. ['1','3']) to deduplicated conda pkg names."""
    pkgs: list[str] = []
    for token in tokens:
        for num, _name, pkg, _note in _SDR_DRIVERS:
            if token == num and pkg:
                for p in pkg.split():
                    if p not in pkgs:
                        pkgs.append(p)
    return pkgs


def _prompt_sdr_selection() -> list[str]:
    """Display SDR driver menu; return list of conda package names to install."""
    print()
    print("  What SDR hardware do you have?")
    print("  You can select multiple: type  1 3  for RTL-SDR and RSP2Pro")
    print()
    for num, name, _pkg, note in _SDR_DRIVERS:
        print(f"    [{num}]  {name}")
        if note:
            print(f"         {note}")
        print()
    try:
        choice = input("  Your choice(s): ").strip()
    except (EOFError, KeyboardInterrupt):
        info("Skipped.")
        return []
    if not choice or choice.strip() == "0":
        info("Skipped. Install drivers later via Settings > SDR Hardware.")
        return []
    pkgs = _sdr_tokens_to_pkgs(choice.split())
    if not pkgs:
        info("No valid selection — skipped.")
    return pkgs


def _install_sdr_packages(conda_exe: str, pkgs: list[str]):
    """Install each SDR conda package individually; report results."""
    info(f"Installing {len(pkgs)} driver(s), one at a time "
         "(so one unavailable package doesn't block the rest)...")
    succeeded, failed = [], []
    for pkg in pkgs:
        print(f"  → {pkg}")
        r = subprocess.run(
            [conda_exe, "install", "-c", "conda-forge", "-y", pkg],
            capture_output=not VERBOSE)
        (succeeded if r.returncode == 0 else failed).append(pkg)
    if succeeded:
        ok(f"Installed: {', '.join(succeeded)}")
        _install_soapy_plugins(_get_venv_site_packages())
    if failed:
        warn(f"Not available on this platform/channel: {', '.join(failed)}")
        info("  RTL-SDR and HackRF are the most reliable on Windows via conda.")
        info("  Others may need a vendor SDK first (SDRplay API, Ettus UHD).")
    if not succeeded:
        warn("No drivers installed. RTL-SDR is the simplest to start with:")
        info("  conda install -c conda-forge soapysdr-module-rtlsdr")


def _select_sdr_drivers():
    """Interactive SDR driver selection step during install."""
    conda_exe = _find_conda()
    if not conda_exe:
        info("conda not found — skipping driver selection.")
        info("Install drivers later: conda install -c conda-forge soapyrtlsdr ...")
        return
    sep()
    hdr("[5b/6] SDR Hardware Drivers")
    pkgs = _prompt_sdr_selection()
    if pkgs:
        _install_sdr_packages(conda_exe, pkgs)
