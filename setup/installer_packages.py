"""
Squelch -- installer_packages.py
pip package installation helpers, extracted from installer.py.
All functions here relate to installing/verifying Python packages.
"""

import subprocess
import sys
from pathlib import Path

# These are set by the main installer before calling any function here.
VENV_PYTHON: Path = None
REQ_FILE: Path = None
OFFLINE_DIR: Path = None
VERBOSE: bool = False


def _pip_quiet_flag() -> list:
    return [] if VERBOSE else ["--quiet"]


def _pip_capture() -> bool:
    return not VERBOSE


def _pip_cmd() -> list:
    return [str(VENV_PYTHON), "-m", "pip"]


def _bootstrap_pip() -> None:
    """Ensure pip is available in the venv, bootstrapping via ensurepip if needed."""
    probe = subprocess.run(
        [str(VENV_PYTHON), "-m", "pip", "--version"],
        capture_output=True, text=True)
    if probe.returncode == 0:
        return
    _info("pip not found in venv — bootstrapping via ensurepip...")
    r = subprocess.run(
        [str(VENV_PYTHON), "-m", "ensurepip", "--upgrade"],
        capture_output=True, text=True)
    if r.returncode != 0:
        _warn(f"ensurepip failed: {r.stderr.strip()[:120]}")
    subprocess.run(
        [str(VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip", "--quiet"],
        capture_output=True)


def _bulk_req_without_webengine() -> Path:
    """Write a temp requirements file with PyQtWebEngine lines stripped."""
    import tempfile, os
    req_lines = [
        l for l in REQ_FILE.read_text().splitlines()
        if not l.strip().startswith("PyQtWebEngine")
        and not (l.strip().startswith("#") and "PyQtWebEngine" in l)]
    _fd, _tmp = tempfile.mkstemp(suffix=".txt")
    os.close(_fd)
    tmp = Path(_tmp)
    tmp.write_text("\n".join(req_lines))
    return tmp


def _build_bulk_pip_cmd(pip: list, req_file: Path, offline: bool) -> list:
    """Build the pip install command, wiring in offline/cache flags."""
    cmd = pip + ["install", "-r", str(req_file), *_pip_quiet_flag()]
    if offline and OFFLINE_DIR.exists():
        cmd += ["--no-index", "--find-links", str(OFFLINE_DIR)]
        _info("Installing from offline cache...")
    elif OFFLINE_DIR.exists():
        cmd += ["--find-links", str(OFFLINE_DIR)]
        _info("Installing packages (using cache if available)...")
    else:
        _info("Installing packages from internet...")
        _info("This may take a few minutes on first run.")
    return cmd


def _log_pip_stderr(stderr: str) -> None:
    for line in stderr.splitlines()[:5]:
        if line.strip():
            _info(f"  pip: {line.strip()[:80]}")


def _install_packages_bulk(pip: list, offline: bool) -> bool:
    """First attempt: install all packages at once. Returns True on success."""
    tmp_req = _bulk_req_without_webengine()
    try:
        cmd = _build_bulk_pip_cmd(pip, tmp_req, offline)
        result = subprocess.run(cmd, capture_output=_pip_capture(), text=True)
    finally:
        try:
            tmp_req.unlink()
        except Exception:
            pass

    if result.returncode != 0 and offline:
        _warn("Offline install incomplete. Trying internet...")
        result = subprocess.run(
            pip + ["install", "-r", str(REQ_FILE), *_pip_quiet_flag()],
            capture_output=_pip_capture(), text=True)

    if result.returncode == 0:
        _ok("Packages installed.")
        return True

    _warn("Some packages failed — installing individually...")
    if result.stderr:
        _log_pip_stderr(result.stderr)
    return False


def _apply_platform_marker(pkg: str) -> "str | None":
    """Strip or skip a package line that has a '; sys_platform' marker."""
    if "; sys_platform" not in pkg:
        return pkg
    import platform as _plat
    marker = pkg.split(";")[1].strip()
    if "win32" in marker and _plat.system() != "Windows":
        return None
    return pkg.split(";")[0].strip()


def _report_individual_results(
        failed: list, skipped: list, non_critical: set) -> None:
    if skipped:
        _info(f"Skipped (Python 3.14+): {', '.join(skipped)}")
    if not failed:
        return
    real     = [p for p in failed if p not in non_critical]
    optional = [p for p in failed if p in non_critical]
    if real:
        _warn(f"Failed (critical): {', '.join(real)}")
    if optional:
        _info(f"Not installed (optional, app still works): {', '.join(optional)}")


def _install_packages_individual(pip: list) -> None:
    """Fallback: install each package individually, skipping non-critical."""
    py_ver = (sys.version_info.major, sys.version_info.minor)
    PY314_SKIP   = {"PyQtWebEngine"}
    NON_CRITICAL = {
        "PyQtWebEngine", "scipy", "pyqtgraph", "sounddevice",
        "soundfile", "soapysdr", "PyQtWebEngine>=6.4.0"}

    packages = [
        p.strip() for p in REQ_FILE.read_text().splitlines()
        if p.strip() and not p.strip().startswith(("#", "//"))
        and not p.strip().startswith("PyQtWebEngine")]

    failed, skipped = [], []
    for raw_pkg in packages:
        pkg = _apply_platform_marker(raw_pkg)
        if pkg is None:
            continue
        name = pkg.split(">=")[0].split("==")[0].split("[")[0].strip()
        if py_ver >= (3, 14) and name in PY314_SKIP:
            _warn(f"  {name} — skipped (no Python 3.14 wheel)")
            skipped.append(name)
            continue
        r = subprocess.run(
            pip + ["install", pkg, "--quiet", "--no-cache-dir"],
            capture_output=True, text=True)
        (_ok if r.returncode == 0 else _warn)(
            f"  {name}" if r.returncode == 0 else f"  {name} — FAILED")
        if r.returncode != 0:
            failed.append(name)

    _report_individual_results(failed, skipped, NON_CRITICAL)


def _verify_pyqt6(pip: list, venv_python: Path) -> None:
    """Verify PyQt6 works; attempt matched-version reinstall if not."""
    check = subprocess.run(
        [str(venv_python), "-c", "from PyQt6.QtCore import QT_VERSION_STR"],
        capture_output=True, text=True)
    if check.returncode == 0:
        _ok("PyQt6 detected")
        return
    _warn("PyQt6 not working — attempting matched-version reinstall...")
    subprocess.run(
        pip + ["uninstall", "-y", "PyQt6", "PyQt6-Qt6", "PyQt6-sip"],
        capture_output=True)
    subprocess.run(
        pip + ["install", "--no-cache-dir",
               "PyQt6==6.6.1", "PyQt6-Qt6==6.6.1", "PyQt6-sip==13.6.0"],
        capture_output=_pip_capture())
    check2 = subprocess.run(
        [str(venv_python), "-c",
         "from PyQt6.QtCore import QT_VERSION_STR; print('Qt/' + QT_VERSION_STR)"],
        capture_output=True, text=True)
    if check2.returncode == 0:
        _ok(f"PyQt6 fixed — {check2.stdout.strip()}")
        return
    _info("Trying separate pyqt6-qt6 install...")
    subprocess.run(pip + ["install", "pyqt6-qt6", "--no-cache-dir", "--quiet"],
                   capture_output=True)
    check3 = subprocess.run(
        [str(venv_python), "-c", "from PyQt6.QtCore import QT_VERSION_STR"],
        capture_output=True, text=True)
    if check3.returncode == 0:
        _ok("PyQt6 fixed")
    else:
        _err("PyQt6 install failed — Squelch cannot run without it")
        _info("Manual fix:")
        _info("  venv\\Scripts\\pip uninstall -y PyQt6 PyQt6-Qt6 PyQt6-sip")
        _info("  venv\\Scripts\\pip install --no-cache-dir PyQt6==6.6.1 "
              "PyQt6-Qt6==6.6.1 PyQt6-sip==13.6.0")


def _verify_package(name: str, venv_python: Path) -> None:
    if name == "PyQt6":
        result = subprocess.run(
            [str(venv_python), "-c",
             "from PyQt6.QtCore import QT_VERSION_STR; "
             "print('PyQt6 Qt/' + QT_VERSION_STR)"],
            capture_output=True, text=True)
    else:
        safe_name = name.lower().replace("-", "_")
        result = subprocess.run(
            [str(venv_python), "-c",
             f"import {safe_name}; "
             f"v = getattr({safe_name}, '__version__', "
             f"getattr({safe_name}, 'version', 'ok')); "
             f"print(v)"],
            capture_output=True, text=True)
    if result.returncode == 0:
        _ok(f"{name} {result.stdout.strip()}")
    else:
        _warn(f"{name} — not detected")
        _info(f"Try: pip install {name} --no-cache-dir")


# ── Console helpers (injected by installer.py after import) ──────────────────
# These are set by installer.py so this module can call ok/warn/err/info
# without duplicating ANSI colour logic.
_ok:   callable = print
_warn: callable = print
_err:  callable = print
_info: callable = print
