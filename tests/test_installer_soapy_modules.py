from __future__ import annotations
# Squelch — RF / SDR signal platform
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for the installer's SoapySDR native-module detection.

Regression: the installer looked for Python `.pyd` plugin wrappers, but on
Windows conda the device plugins are native module DLLs under
Library/lib/SoapySDR/modules*/ — so it falsely reported "No device plugins
found" even when rtlsdr etc. were installed and working.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "setup"))
sys.path.insert(0, str(ROOT))

import installer_soapy as isoapy


def _fake_conda(tmp_path, *module_dlls, ver="0.8"):
    """Build a fake conda env with the given native SoapySDR module DLLs."""
    site = tmp_path / "Lib" / "site-packages"
    site.mkdir(parents=True)
    (site / "SoapySDR.py").write_text("# stub\n", encoding="utf-8")
    mdir = tmp_path / "Library" / "lib" / "SoapySDR" / f"modules{ver}"
    mdir.mkdir(parents=True)
    for name in module_dlls:
        (mdir / name).write_bytes(b"\x00")
    return site


class TestNativeModuleDetection:
    def test_finds_rtlsdr_module(self, tmp_path):
        site = _fake_conda(tmp_path, "rtlsdrSupport.dll", "uhdSupport.dll")
        root = isoapy._conda_root_of(site)
        assert root == tmp_path
        hw = isoapy._native_soapy_modules(root)
        assert "RTL-SDR dongles" in hw
        assert "USRP B200/B210" in hw

    def test_maps_all_known_stems(self, tmp_path):
        site = _fake_conda(
            tmp_path, "rtlsdrSupport.dll", "hackrfSupport.dll",
            "sdrplaySupport.dll", "airspySupport.dll")
        hw = isoapy._native_soapy_modules(isoapy._conda_root_of(site))
        for name in ("RTL-SDR dongles", "HackRF One",
                     "SDRplay RSP family", "Airspy R2/Mini"):
            assert name in hw

    def test_no_modules_returns_empty(self, tmp_path):
        site = _fake_conda(tmp_path)          # modules dir exists but empty
        assert isoapy._native_soapy_modules(isoapy._conda_root_of(site)) == []

    def test_missing_soapy_dir_safe(self, tmp_path):
        assert isoapy._native_soapy_modules(tmp_path) == []

    def test_conda_root_none_when_absent(self, tmp_path):
        # a bare site-packages with no Library/lib/SoapySDR
        site = tmp_path / "Lib" / "site-packages"
        site.mkdir(parents=True)
        assert isoapy._conda_root_of(site) is None


class TestNoFalseNegativeSource:
    def test_installer_checks_native_modules_not_pyd(self):
        src = (ROOT / "setup/installer_soapy.py").read_text(encoding="utf-8")
        # the old misleading .pyd glob must be gone from the plugin reporter
        assert "_native_soapy_modules" in src
        assert 'glob(f"{stem}*.pyd")' not in src
        # accurate messaging: only warn when genuinely none found
        assert "No SoapySDR device modules found" in src
