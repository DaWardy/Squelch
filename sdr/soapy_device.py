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

from __future__ import annotations
"""Squelch -- sdr/soapy_device.py
SoapySDR device abstraction.
Detects hardware capabilities (RX-only vs TX capable).
Spectral span auto-adjusts per hardware limits.
Supports: RTL-SDR, HackRF, B200/B210, RSP series,
          Airspy, LimeSDR, BladeRF, PlutoSDR.
"""

import logging
import threading
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Callable

log = logging.getLogger(__name__)

# Kept alive for the process lifetime: os.add_dll_directory() handles are
# released when garbage-collected, which would un-register the directory.
_DLL_DIR_HANDLES: list = []


def _inject_soapy_from_path(sp, conda_root) -> None:
    """Inject a conda site-packages dir into sys.path and fix up env vars."""
    import sys, os
    from pathlib import Path as _P

    if str(sp) not in sys.path:
        sys.path.insert(0, str(sp))
        log.info(f"SoapySDR: found in conda at {sp}, added to path")

    soapy_roots = [
        sp / "SoapySDR",
        conda_root / "Library" / "lib" / "SoapySDR",
        conda_root / "lib" / "SoapySDR",
        conda_root / "Library" / "bin",
    ]
    if "SOAPY_SDR_ROOT" not in os.environ:
        for root in soapy_roots:
            if root.exists():
                os.environ["SOAPY_SDR_ROOT"] = str(root)
                log.info(f"SoapySDR: SOAPY_SDR_ROOT -> {root}")
                break

    if sys.platform == "win32":
        win_dll_dirs = [
            conda_root / "Library" / "bin",
            conda_root / "Library" / "mingw-w64" / "bin",
            sp,
        ]
        current_path = os.environ.get("PATH", "")
        additions = [str(d) for d in win_dll_dirs
                     if d.exists() and str(d) not in current_path]
        if additions:
            os.environ["PATH"] = (os.pathsep.join(additions)
                                  + os.pathsep + current_path)
            log.info(f"SoapySDR: added to PATH: {os.pathsep.join(additions)}")
        # CRITICAL (Python 3.8+): modifying PATH no longer affects DLL
        # resolution for extension modules — the SoapySDR loader's
        # LoadLibrary() of e.g. rtlsdrSupport.dll can't find its dependent
        # DLLs (rtlsdr.dll, libusb-1.0.dll in Library/bin) unless the
        # directory is registered via os.add_dll_directory(). This is the
        # usual cause of "LoadLibrary() failed: The specified module could
        # not be found" → 0 devices.
        add_dll = getattr(os, "add_dll_directory", None)
        if add_dll is not None:
            for d in win_dll_dirs:
                try:
                    if d.exists():
                        _DLL_DIR_HANDLES.append(add_dll(str(d)))
                        log.info(f"SoapySDR: add_dll_directory({d})")
                except Exception as e:
                    log.debug(f"SoapySDR: add_dll_directory({d}) failed: {e}")


def _try_conda_soapy() -> bool:
    """SoapySDR is often installed in the conda base environment while
    Squelch runs in a separate venv that can't see it. This function
    searches common conda locations and injects the right site-packages
    into sys.path so the import works. Returns True if SoapySDR is found
    after the path injection (or was already importable)."""
    import sys, importlib
    # Already importable — nothing to do
    if importlib.util.find_spec("SoapySDR") is not None:
        return True

    import os
    from pathlib import Path as _P

    # Candidate conda site-packages locations (Windows + Linux/Mac)
    home = _P.home()
    candidates = [
        # Windows — miniforge/miniconda under user home
        home / "miniforge3"  / "Lib"  / "site-packages",
        home / "miniconda3"  / "Lib"  / "site-packages",
        home / "anaconda3"   / "Lib"  / "site-packages",
        home / "miniforge3"  / "lib"  / "python3.11" / "site-packages",
        home / "miniforge3"  / "lib"  / "python3.12" / "site-packages",
        home / "miniforge3"  / "lib"  / "python3.13" / "site-packages",
        home / "miniconda3"  / "lib"  / "python3.11" / "site-packages",
        home / "miniconda3"  / "lib"  / "python3.12" / "site-packages",
        # Windows — drive root
        _P("C:/miniforge3/Lib/site-packages"),
        _P("C:/miniconda3/Lib/site-packages"),
        # Linux/Mac system paths
        _P("/opt/conda/lib/python3.11/site-packages"),
        _P("/opt/conda/lib/python3.12/site-packages"),
        _P("/usr/lib/python3/dist-packages"),
    ]

    # Also probe the CONDA_PREFIX environment variable if set
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        cp = _P(conda_prefix)
        for sub in ["Lib/site-packages",
                    "lib/python3.11/site-packages",
                    "lib/python3.12/site-packages",
                    "lib/python3.13/site-packages"]:
            candidates.insert(0, cp / sub)

    for sp in candidates:
        if sp.exists() and (sp / "SoapySDR.py").exists() or \
                sp.exists() and any(sp.glob("SoapySDR*.so")) or \
                sp.exists() and any(sp.glob("SoapySDR*.pyd")):
            _inject_soapy_from_path(sp, sp.parent.parent)
            return importlib.util.find_spec("SoapySDR") is not None

    return False


def _register_soapy_dll_dirs() -> None:
    """Put conda's Library/bin on the DLL search path (Windows, Python 3.8+).

    SoapySDR.py — even when imported straight from the venv — loads its binary
    support modules (rtlsdrSupport.dll, uhdSupport.dll, …) from the conda
    install, and those depend on DLLs in <conda>/Library/bin (rtlsdr.dll,
    uhd.dll, libusb-1.0.dll). Since Python 3.8 only os.add_dll_directory()
    (NOT %PATH%) makes those dependencies resolvable; without it the module
    LoadLibrary() fails with "The specified module could not be found" and
    0 devices are enumerated.
    """
    import os
    import sys
    from pathlib import Path as _P
    if sys.platform != "win32":
        return
    add_dll = getattr(os, "add_dll_directory", None)
    if add_dll is None:
        return
    home = _P.home()
    roots = []
    cp = os.environ.get("CONDA_PREFIX")
    if cp:
        roots.append(_P(cp))
    roots += [
        home / "miniforge3", home / "miniconda3", home / "anaconda3",
        _P("C:/miniforge3"), _P("C:/miniconda3"),
        _P(getattr(sys, "base_prefix", sys.prefix)),   # conda-based venv base
    ]
    bin_dirs = []
    seen = set()
    for root in roots:
        for sub in ("Library/bin", "Library/mingw-w64/bin"):
            d = root / sub
            key = str(d).lower()
            if key in seen:
                continue
            seen.add(key)
            try:
                if d.exists():
                    _DLL_DIR_HANDLES.append(add_dll(str(d)))
                    bin_dirs.append(d)
                    log.info(f"SoapySDR: add_dll_directory({d})")
            except Exception as e:
                log.debug(f"SoapySDR: add_dll_directory({d}) failed: {e}")

    # add_dll_directory alone is NOT enough: SoapySDR's C++ module loader uses
    # LOAD_WITH_ALTERED_SEARCH_PATH, which bypasses the registered user dirs, so
    # rtlsdrSupport.dll/uhdSupport.dll still fail to find rtlsdr.dll/uhd.dll.
    # Fix: pre-load the dependency DLLs here so they're already resident in the
    # process when SoapySDR loads its support modules (in-memory modules win).
    import ctypes
    dep_dlls = [
        "SoapySDR.dll", "libusb-1.0.dll",      # core + shared USB
        "rtlsdr.dll", "hackrf.dll", "airspy.dll", "airspyhf.dll",
        "uhd.dll", "LimeSuite.dll", "bladeRF.dll", "libiio.dll",
    ]
    for d in bin_dirs:
        for name in dep_dlls:
            p = d / name
            try:
                if p.exists():
                    _DLL_DIR_HANDLES.append(ctypes.WinDLL(str(p)))
                    log.debug(f"SoapySDR: pre-loaded {name}")
            except Exception as e:
                log.debug(f"SoapySDR: pre-load {name} failed: {e}")


_register_soapy_dll_dirs()

try:
    import SoapySDR
    from SoapySDR import SOAPY_SDR_RX, SOAPY_SDR_TX, SOAPY_SDR_CF32
    HAS_SOAPY = True
except ImportError:
    # Not in venv — try conda environment before giving up
    if _try_conda_soapy():
        try:
            import SoapySDR
            from SoapySDR import SOAPY_SDR_RX, SOAPY_SDR_TX, SOAPY_SDR_CF32
            HAS_SOAPY = True
            log.info("SoapySDR loaded from conda environment")
        except ImportError:
            HAS_SOAPY = False
    else:
        HAS_SOAPY = False
    if not HAS_SOAPY:
        log.info("SoapySDR not found — SDR tab will show setup guide")


# Hardware capability profiles
# Drives UI — TX controls only shown for TX-capable devices
DEVICE_PROFILES = {
    "rtlsdr": {
        "name": "RTL-SDR", "tx": False,
        "max_sr": 3_200_000, "max_span": 3_000_000,
        "freq_min": 24_000_000, "freq_max": 1_750_000_000,
        "gain_range": (0, 49.6),
        "recommended_sr": 2_048_000,
        "ppm_correction": True,
        "direct_sampling": True,
        "stable_rates": [
            250_000, 1_024_000, 1_536_000,
            2_048_000, 2_400_000, 3_200_000],
        "install_note": (
            "Easiest: rtl_tcp.exe (no SoapySDR needed)\n"
            "Full: PothosSDR bundle + Zadig"),
    },
    "hackrf": {
        "name": "HackRF One", "tx": True,
        "max_sr": 20_000_000, "max_span": 18_000_000,
        "freq_min": 1_000_000, "freq_max": 6_000_000_000,
        "gain_range": (0, 116),
        "recommended_sr": 10_000_000,
        "amp_available": True,
        "bias_tee": True,
        "half_duplex": True,
        "lna_gain_range": (0, 40),
        "vga_gain_range": (0, 62),
        "vga_tx_range": (0, 47),
        "stable_rates": [
            2_000_000, 4_000_000, 8_000_000,
            10_000_000, 16_000_000, 20_000_000],
        "install_note": (
            "PothosSDR bundle includes SoapyHackRF.\n"
            "No Zadig needed for HackRF."),
    },
    "uhd": {
        "name": "USRP B200/B210", "tx": True,
        "max_sr": 61_440_000, "max_span": 56_000_000,
        "freq_min": 70_000_000, "freq_max": 6_000_000_000,
        "gain_range": (0, 76),
        "recommended_sr": 10_000_000,
        "full_duplex": True,
        "clock_sources": [
            "internal", "external", "gpsdo", "mimo"],
        "subdev_b200mini": "A:A",
        "subdev_b210": "A:A A:B",
        "stable_rates": [
            1_000_000, 2_000_000, 4_000_000,
            8_000_000, 16_000_000, 25_000_000,
            56_000_000],
        "install_note": (
            "Install UHD first:\n"
            "  PothosSDR bundle (includes UHD), OR\n"
            "  files.ettus.com/binaries/uhd/\n"
            "Then: pip install soapysdr\n"
            "Verify: uhd_find_devices"),
    },
    # SDRplay RSP lineup (all use driver="sdrplay")
    "sdrplay": {
        "name": "SDRplay RSP",
        "tx": False,
        "max_sr": 10_000_000,
        "max_span": 8_000_000,
        "freq_min": 1_000,          # 1 kHz (better than RTL-SDR)
        "freq_max": 2_000_000_000,  # 2 GHz
        "gain_range": (0, 102),     # gain reduction 0-102 dB
        "recommended_sr": 6_000_000,
        "stable_rates": [
            200_000, 500_000, 1_000_000,
            2_000_000, 4_000_000, 6_000_000,
            7_000_000, 8_000_000, 10_000_000],
        "if_bandwidths_hz": [
            200_000, 300_000, 600_000,
            1_536_000, 5_000_000, 6_000_000,
            7_000_000, 8_000_000],
        # Per-model capability flags (detected at runtime)
        "models": {
            "RSP1":   {"antennas": ["Antenna A"],
                       "notch": False, "dab_notch": False,
                       "bias_tee": False, "hiz": False},
            "RSP1A":  {"antennas": ["Antenna A"],
                       "notch": True,  "dab_notch": True,
                       "bias_tee": False, "hiz": False},
            "RSP1B":  {"antennas": ["Antenna A"],
                       "notch": True,  "dab_notch": True,
                       "bias_tee": False, "hiz": False},
            "RSP2":   {"antennas": [
                            "Antenna A", "Antenna B", "Hi-Z"],
                       "notch": True,  "dab_notch": False,
                       "bias_tee": True,  "hiz": True},
            "RSP2Pro":{"antennas": [
                            "Antenna A", "Antenna B", "Hi-Z"],
                       "notch": True,  "dab_notch": False,
                       "bias_tee": True,  "hiz": True},
            "RSPdx":  {"antennas": [
                            "Antenna A", "Antenna B", "Antenna C"],
                       "notch": True,  "dab_notch": True,
                       "bias_tee": True,  "hiz": False,
                       "max_sr": 10_000_000},
            "RSPduo": {"antennas": [
                            "Tuner 1 50ohm", "Tuner 2 50ohm",
                            "Tuner 1 Hi-Z"],
                       "notch": True,  "dab_notch": True,
                       "bias_tee": True,  "hiz": True,
                       "dual_tuner": True},
        },
        "install_note": (
            "1. Install SDRplay API (REQUIRED first):\n"
            "   sdrplay.com/softwarehome\n"
            "   (Free, no account needed, ~30 MB)\n"
            "2. Install PothosSDR bundle (includes SoapySDRplay):\n"
            "   downloads.myriadrf.org/builds/PothosSDR/\n"
            "3. pip install soapysdr\n"
            "4. Verify: python installer.py"),
    },
    "airspy": {
        "name": "Airspy", "tx": False,
        "max_sr": 10_000_000, "max_span": 9_000_000,
        "freq_min": 24_000_000, "freq_max": 1_750_000_000,
        "gain_range": (0, 21),
        "recommended_sr": 10_000_000,
        "stable_rates": [2_500_000, 10_000_000],
        "install_note": "PothosSDR bundle includes SoapyAirspy.",
    },
    "lime": {
        "name": "LimeSDR", "tx": True,
        "max_sr": 61_440_000, "max_span": 56_000_000,
        "freq_min": 100_000, "freq_max": 3_800_000_000,
        "gain_range": (0, 73),
        "recommended_sr": 10_000_000,
        "stable_rates": [
            1_000_000, 2_000_000, 5_000_000,
            10_000_000, 30_720_000, 61_440_000],
        "install_note": "PothosSDR bundle includes LimeSuite driver.",
    },
}


@dataclass
class SDRDevice:
    """Detected SDR device with capabilities."""
    driver:     str
    label:      str
    serial:     str      = ""
    can_tx:     bool     = False
    max_sr:     int      = 3_200_000
    max_span:   int      = 3_000_000
    freq_min:   int      = 1_000_000
    freq_max:   int      = 1_750_000_000
    gain_range: tuple    = (0, 50)
    extra:      dict     = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        profile = DEVICE_PROFILES.get(
            self.driver.lower(), {})
        name = profile.get("name", self.driver.upper())
        if self.serial:
            return f"{name} ({self.serial[:8]})"
        return name

    @property
    def recommended_span(self) -> int:
        """Default span based on hardware."""
        spans = {
            "rtlsdr":  2_400_000,
            "sdrplay": 6_000_000,
            "airspy":  6_000_000,
            "hackrf":  10_000_000,
            "uhd":     20_000_000,
            "lime":    20_000_000,
        }
        return spans.get(self.driver.lower(), 2_000_000)


class SoapyManager:
    """
    Manages SoapySDR device lifecycle.
    Enumerates hardware, opens streams, delivers samples.
    TX controls shown only when hardware supports it.
    """

    def __init__(self):
        self._device     = None
        self._rx_stream  = None
        self._tx_stream  = None
        self._running    = False
        self._lock       = threading.Lock()
        self._rx_thread: threading.Thread | None = None

        self._center_hz  = 100_000_000
        self._sample_rate = 2_400_000
        self._gain       = 30.0
        self._ppm        = 0

        self._on_samples: Callable | None = None
        self._on_error:   Callable | None = None

        self.current_device: SDRDevice | None = None

    # ── Device enumeration ────────────────────────────────────────────────

    @staticmethod
    def enumerate() -> list[SDRDevice]:
        """Return list of all connected SDR devices."""
        if not HAS_SOAPY:
            return []
        try:
            results = SoapySDR.Device.enumerate()
            devices = []
            for r in results:
                driver = str(r.get("driver", "unknown"))
                label  = str(r.get("label",
                             r.get("product", driver)))
                serial = str(r.get("serial", ""))
                profile = DEVICE_PROFILES.get(
                    driver.lower(), {})
                dev = SDRDevice(
                    driver   = driver,
                    label    = label,
                    serial   = serial,
                    can_tx   = profile.get("tx", False),
                    max_sr   = profile.get("max_sr",
                                          3_200_000),
                    max_span = profile.get("max_span",
                                          3_000_000),
                )
                devices.append(dev)
                log.info(
                    f"SDR found: {dev.display_name} "
                    f"TX={dev.can_tx}")
            return devices
        except Exception as e:
            log.warning(f"SDR enumerate: {e}")
            return []

    # ── Open / Close ──────────────────────────────────────────────────────

    def open(self, device: SDRDevice) -> bool:
        """Open an SDR device for streaming."""
        if not HAS_SOAPY:
            return False
        try:
            # Build device args — omit serial if empty, since an empty
            # serial string can cause SoapySDR to fail matching (notably
            # for single UHD B200/B210 units that report no serial).
            dev_args = {"driver": device.driver}
            if device.serial:
                dev_args["serial"] = device.serial
            self._device = SoapySDR.Device(dev_args)
            self.current_device = device

            # Configure RX
            self._device.setSampleRate(
                SOAPY_SDR_RX, 0, self._sample_rate)
            self._device.setFrequency(
                SOAPY_SDR_RX, 0, self._center_hz)
            # Disable hardware AGC so the gain slider actually controls gain.
            # RTL-SDR in particular defaults to AGC, which makes the manual
            # gain setting appear to do nothing. Not all drivers support
            # this, so guard it.
            try:
                self._device.setGainMode(SOAPY_SDR_RX, 0, False)
            except Exception:
                pass
            self._device.setGain(
                SOAPY_SDR_RX, 0, self._gain)
            if self._ppm != 0:
                try:
                    self._device.setFrequencyCorrection(
                        SOAPY_SDR_RX, 0, self._ppm)
                except Exception:
                    pass

            # Setup RX stream
            self._rx_stream = self._device.setupStream(
                SOAPY_SDR_RX, SOAPY_SDR_CF32)
            self._device.activateStream(self._rx_stream)

            log.info(
                f"SDR opened: {device.display_name} "
                f"{self._center_hz/1e6:.3f}MHz "
                f"{self._sample_rate/1e6:.2f}MSPS")
            return True
        except Exception as e:
            log.error(f"SDR open failed: {e}")
            self._device = None
            return False

    def close(self):
        self._running = False
        if self._rx_stream and self._device:
            try:
                self._device.deactivateStream(
                    self._rx_stream)
                self._device.closeStream(self._rx_stream)
            except Exception:
                pass
        if self._device:
            try:
                self._device = None
            except Exception:
                pass
        self._rx_stream = None
        self.current_device = None

    # ── Tuning ────────────────────────────────────────────────────────────

    def set_frequency(self, hz: int):
        self._center_hz = hz
        if self._device:
            try:
                self._device.setFrequency(
                    SOAPY_SDR_RX, 0, float(hz))
            except Exception as e:
                log.debug(f"Set freq: {e}")

    def set_sample_rate(self, sps: int):
        if self.current_device:
            sps = min(sps, self.current_device.max_sr)
        self._sample_rate = sps
        if self._device:
            try:
                self._device.setSampleRate(
                    SOAPY_SDR_RX, 0, float(sps))
            except Exception as e:
                log.debug(f"Set SR: {e}")

    def set_gain(self, db: float):
        self._gain = db
        if self._device:
            try:
                self._device.setGain(
                    SOAPY_SDR_RX, 0, db)
            except Exception as e:
                log.debug(f"Set gain: {e}")

    def set_ppm(self, ppm: int):
        self._ppm = ppm
        if self._device:
            try:
                self._device.setFrequencyCorrection(
                    SOAPY_SDR_RX, 0, float(ppm))
            except Exception:
                pass

    def set_agc(self, enabled: bool) -> None:
        """Enable/disable the device's hardware automatic gain control.

        AGC is disabled by default (so the manual gain slider works); enabling
        it lets the device ride gain automatically. When AGC is on the manual
        gain setting is ignored by most drivers. Not all drivers support AGC —
        guarded. For weak-signal / digital work, keep AGC OFF (manual gain).
        """
        self._agc = bool(enabled)
        if self._device:
            try:
                self._device.setGainMode(SOAPY_SDR_RX, 0, bool(enabled))
            except Exception as e:
                log.debug(f"Set AGC: {e}")

    # ── Streaming ─────────────────────────────────────────────────────────

    def start_rx(self):
        if not self._device:
            return
        self._running  = True
        self._rx_thread = threading.Thread(
            target=self._rx_loop,
            daemon=True, name="SDRRx")
        self._rx_thread.start()

    def stop_rx(self):
        self._running = False

    def _rx_loop(self):
        """Continuous RX sample delivery loop."""
        import time
        buf_size = 16384
        buf = np.zeros(buf_size, dtype=np.complex64)
        consecutive_errors = 0
        while self._running and self._device:
            try:
                sr = self._device.readStream(
                    self._rx_stream,
                    [buf], buf_size,
                    timeoutUs=100_000)
                if sr.ret > 0 and self._on_samples:
                    consecutive_errors = 0
                    samples = buf[:sr.ret].copy()
                    try:
                        self._on_samples(
                            samples,
                            self._sample_rate,
                            self._center_hz)
                    except Exception as e:
                        log.debug(f"Sample cb: {e}")
                elif sr.ret < 0:
                    # Negative return = SoapySDR error code (e.g. timeout,
                    # overflow). Brief backoff so we don't spin the CPU or
                    # flood the log if the stream stalls.
                    consecutive_errors += 1
                    if consecutive_errors > 50:
                        log.warning(
                            "SDR RX stream stalled (50 consecutive "
                            "errors) — stopping receive loop")
                        break
                    time.sleep(0.01)
            except Exception as e:
                if self._running:
                    log.debug(f"RX loop: {e}")
                    time.sleep(0.05)   # backoff on exception

    # ── TX (for capable hardware) ─────────────────────────────────────────

    def tx_capable(self) -> bool:
        return (self.current_device is not None and
                self.current_device.can_tx)

    def transmit_iq(self, iq_data: np.ndarray):
        """TX IQ samples — only for TX-capable hardware.

        Hard authorization chokepoint (AUTH-LAYER / TX-CHAIN): every keying
        passes through core.authorization.authorize_tx() — default-deny,
        Demo-mode absolute block, per-band opt-in, every attempt logged.
        Raises PermissionError when denied so no caller can key unauthorized.
        """
        from core.authorization import authorize_tx
        decision = authorize_tx(self._center_hz)
        if not decision.allowed:
            raise PermissionError(
                f"TX not authorized: {decision.reason}")
        if not self.tx_capable():
            raise RuntimeError(
                "Connected SDR is RX-only")
        if not self._device:
            raise RuntimeError("No SDR device open")
        try:
            if not self._tx_stream:
                self._tx_stream = \
                    self._device.setupStream(
                        SOAPY_SDR_TX, SOAPY_SDR_CF32)
                self._device.activateStream(
                    self._tx_stream)
            self._device.writeStream(
                self._tx_stream,
                [iq_data], len(iq_data))
        except Exception as e:
            log.error(f"TX failed: {e}")
            raise

    # ── Callbacks ─────────────────────────────────────────────────────────

    def on_samples(self, cb: Callable):
        self._on_samples = cb

    def on_error(self, cb: Callable):
        self._on_error = cb


# Module singleton
_manager: SoapyManager | None = None

def get_sdr_manager() -> SoapyManager:
    global _manager
    if _manager is None:
        _manager = SoapyManager()
    return _manager
