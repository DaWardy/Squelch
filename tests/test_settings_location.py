from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Licensed under GNU GPL v3 — see LICENSE
"""Settings → Station location-source tests.

Source-level checks run anywhere; the Qt build/round-trip checks skip cleanly
when PyQt6 is unavailable.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
ROOT = Path(__file__).parent.parent
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ── Source-level wiring (no Qt needed) ─────────────────────────────────────

class TestStationLocationSource:

    def _station_src(self) -> str:
        return (ROOT / "ui/dialogs/settings_station_tab.py").read_text(
            encoding="utf-8")

    def _dialog_src(self) -> str:
        return (ROOT / "ui/dialogs/settings_dialog.py").read_text(
            encoding="utf-8")

    def test_location_section_built(self):
        src = self._station_src()
        assert "_build_station_location_section" in src
        assert "_build_station_location_section(f)" in src

    def test_source_selector_options(self):
        src = self._station_src()
        assert '"manual"' in src and '"windows"' in src and '"serial"' in src

    def test_core_widgets_present(self):
        src = self._station_src()
        for attr in ("_gps_source", "_gps_port", "_gps_baud",
                     "_gps_auto_grid", "_gps_getfix_btn", "_gps_status"):
            assert attr in src, attr

    def test_get_fix_handler_present(self):
        assert "def _gps_get_fix(" in self._station_src()

    def test_uses_worker_signals_not_singleshot(self):
        src = self._station_src()
        assert "fix_received.connect" in src
        # The worker delivers via pyqtSignal; the dialog must NOT poke the GUI
        # from a worker thread via QTimer.singleShot.
        assert "singleShot" not in src

    def test_config_keys_loaded_and_saved(self):
        src = self._dialog_src()
        for key in ("location.gps_source", "location.gps_serial_port",
                    "location.gps_serial_baud", "location.gps_auto_grid"):
            assert key in src, key


# ── Qt build / behaviour ───────────────────────────────────────────────────


@pytest.fixture(scope="module")
def app():
    pytest.importorskip("PyQt6", reason="PyQt6 not installed")
    from PyQt6.QtWidgets import QApplication
    a = QApplication.instance() or QApplication([])
    yield a


def _dialog(app):
    # Use an ISOLATED, throwaway config file — never the user's real
    # %APPDATA%/Squelch/config.json. `_on_gps_settings_fix` below calls
    # cfg.save(), so a real Config() here would overwrite the user's saved
    # station location (the GPS-fix test uses Munich coordinates!). Isolate it.
    import tempfile
    from pathlib import Path
    from core.config import Config
    from ui.dialogs.settings_dialog import SettingsDialog
    tmp = Path(tempfile.mkdtemp(prefix="squelch_test_cfg_")) / "config.json"
    return SettingsDialog(Config(tmp))


class TestSettingsDialogLocationQt:

    def test_dialog_builds_with_location_widgets(self, app):
        dlg = _dialog(app)
        assert dlg._gps_source.count() == 3
        assert hasattr(dlg, "_gps_port")
        assert hasattr(dlg, "_gps_getfix_btn")
        dlg.close()

    def test_manual_source_disables_serial_widgets(self, app):
        dlg = _dialog(app)
        idx = dlg._gps_source.findData("manual")
        dlg._gps_source.setCurrentIndex(idx)
        assert dlg._gps_port.isEnabled() is False
        assert dlg._gps_getfix_btn.isEnabled() is False
        dlg.close()

    def test_serial_source_enables_serial_widgets(self, app):
        dlg = _dialog(app)
        idx = dlg._gps_source.findData("serial")
        dlg._gps_source.setCurrentIndex(idx)
        assert dlg._gps_port.isEnabled() is True
        assert dlg._gps_baud.isEnabled() is True
        dlg.close()

    def test_fix_slot_updates_grid_and_config(self, app):
        from core.gps import GPSFix
        dlg = _dialog(app)
        dlg._on_gps_settings_fix(GPSFix(lat=48.1173, lon=11.5167))
        assert dlg._grid.text().startswith("JN58")
        assert abs(dlg.cfg.get("location.lat") - 48.1173) < 1e-3
        dlg.close()

    def test_save_then_load_roundtrip(self, app):
        dlg = _dialog(app)
        idx = dlg._gps_source.findData("serial")
        dlg._gps_source.setCurrentIndex(idx)
        dlg._gps_auto_grid.setChecked(False)
        dlg._save_station(dlg.cfg)
        assert dlg.cfg.get("location.gps_source") == "serial"
        assert dlg.cfg.get("location.gps_auto_grid") is False
        dlg._load_station_location(dlg.cfg)
        assert dlg._gps_source.currentData() == "serial"
        assert dlg._gps_auto_grid.isChecked() is False
        dlg.close()
