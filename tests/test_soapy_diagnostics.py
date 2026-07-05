from __future__ import annotations
# Squelch — RF / SDR signal platform
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for the SDR 0-device diagnostics hint (sdr/soapy_device.py)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from sdr.soapy_device import soapy_driver_hint, SoapyManager


class TestDriverHint:
    def test_devices_present_no_hint(self):
        assert soapy_driver_hint(["rtlsdrSupport.dll"], 2) == ""

    def test_no_modules_suggests_install(self):
        hint = soapy_driver_hint([], 0)
        assert "soapysdr-module-rtlsdr" in hint
        assert "Rescan" in hint

    def test_rtl_module_present_but_no_device(self):
        # module installed but nothing enumerated → check cable/driver/other app
        hint = soapy_driver_hint(
            [r"C:\miniforge3\Library\lib\SoapySDR\modules0.8\rtlsdrSupport.dll"], 0)
        assert "RTL-SDR" in hint
        assert "no device was detected" in hint
        assert "soapysdr-module-rtlsdr" not in hint   # don't tell them to install it

    def test_recognises_multiple_drivers(self):
        hint = soapy_driver_hint(["uhdSupport.dll", "hackrfSupport.dll"], 0)
        assert "USRP (UHD)" in hint and "HackRF" in hint

    def test_none_module_list_safe(self):
        assert "install" in soapy_driver_hint(None, 0).lower()


class TestDiagnostics:
    def test_diagnostics_shape(self):
        d = SoapyManager.diagnostics()
        assert set(d) == {"has_soapy", "modules", "n_devices", "hint"}
        assert isinstance(d["modules"], list)
        assert isinstance(d["hint"], str)

    def test_no_soapy_hint_mentions_conda(self):
        import sdr.soapy_device as sd
        if sd.HAS_SOAPY:
            pytest.skip("SoapySDR present in this env")
        d = SoapyManager.diagnostics()
        assert d["has_soapy"] is False
        assert "conda" in d["hint"].lower()


class TestUiWiring:
    def test_populate_devices_surfaces_hint(self):
        src = (Path(__file__).parent.parent
               / "ui/tabs/sdr_device_connect.py").read_text(encoding="utf-8")
        assert "SoapyManager.diagnostics()" in src
        assert "setToolTip(hint)" in src
