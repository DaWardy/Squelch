from __future__ import annotations
# Squelch — RF / SDR signal platform
# Licensed under GNU GPL v3 — see LICENSE
"""Settings → TX Authorization tab tests (ROADMAP Phase 5, AUTH-LAYER UI).

Source-level checks run anywhere; the Qt build / round-trip checks skip
cleanly when PyQt6 is unavailable.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
ROOT = Path(__file__).parent.parent
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ── Source-level wiring (no Qt needed) ─────────────────────────────────────

class TestTxAuthSourceWiring:

    def _tab_src(self) -> str:
        return (ROOT / "ui/dialogs/settings_tx_auth_tab.py").read_text(
            encoding="utf-8")

    def _dialog_src(self) -> str:
        return (ROOT / "ui/dialogs/settings_dialog.py").read_text(
            encoding="utf-8")

    def test_tab_registered_in_dialog(self):
        src = self._dialog_src()
        assert "_SettingsTxAuthTab" in src
        assert "self._tab_tx_auth()" in src

    def test_load_and_save_wired(self):
        src = self._dialog_src()
        assert "self._load_tx_auth(cfg)" in src
        assert "self._save_tx_auth(cfg)" in src

    def test_uses_the_authorization_config_keys(self):
        """Must read/write exactly the keys AuthorizationProfile consumes."""
        src = self._tab_src()
        for key in ("tx.auth.acknowledged", "tx.auth.allowed_bands",
                    "tx.auth.unrestricted"):
            assert key in src, key

    def test_keys_match_authorization_module(self):
        from core import authorization as A
        assert A._CFG_ACK == "tx.auth.acknowledged"
        assert A._CFG_BANDS == "tx.auth.allowed_bands"
        assert A._CFG_UNRESTRICT == "tx.auth.unrestricted"

    def test_default_deny_widgets_present(self):
        src = self._tab_src()
        for attr in ("_tx_ack", "_tx_band_checks", "_tx_unrestricted"):
            assert attr in src, attr

    def test_no_hardcoded_dark_hex(self):
        # Warning accents (amber/red) are allowed; dark backgrounds are not.
        src = self._tab_src().lower()
        for bad in ("#141414", "#0a0a0a", "#111", "#1a1a1a", "#333"):
            assert bad not in src, bad


# ── Qt build / round-trip ──────────────────────────────────────────────────


@pytest.fixture(scope="module")
def app():
    pytest.importorskip("PyQt6", reason="PyQt6 not installed")
    from PyQt6.QtWidgets import QApplication
    a = QApplication.instance() or QApplication([])
    yield a


def _dialog(app):
    from core.config import Config
    from ui.dialogs.settings_dialog import SettingsDialog
    return SettingsDialog(Config())


class TestTxAuthTabQt:

    def test_tab_builds_with_widgets(self, app):
        dlg = _dialog(app)
        assert hasattr(dlg, "_tx_ack")
        assert hasattr(dlg, "_tx_unrestricted")
        assert len(dlg._tx_band_checks) > 10        # amateur + service bands
        dlg.close()

    def test_band_names_match_band_plan(self, app):
        from core.band_plan import BANDS, SERVICE_BANDS
        dlg = _dialog(app)
        expected = {b.name for b in list(BANDS) + list(SERVICE_BANDS)}
        assert set(dlg._tx_band_checks) == expected
        dlg.close()

    def test_ack_off_disables_bands(self, app):
        dlg = _dialog(app)
        dlg._tx_ack.setChecked(False)
        assert all(not c.isEnabled() for c in dlg._tx_band_checks.values())
        dlg._tx_ack.setChecked(True)
        assert all(c.isEnabled() for c in dlg._tx_band_checks.values())
        dlg.close()

    def test_select_and_clear_all(self, app):
        dlg = _dialog(app)
        dlg._tx_ack.setChecked(True)
        dlg._set_all_tx_bands(True)
        assert all(c.isChecked() for c in dlg._tx_band_checks.values())
        dlg._set_all_tx_bands(False)
        assert not any(c.isChecked() for c in dlg._tx_band_checks.values())
        dlg.close()

    def test_save_load_round_trip(self, app):
        from core.config import Config
        cfg = Config()
        dlg = _dialog(app)
        dlg._tx_ack.setChecked(True)
        dlg._tx_band_checks["20m"].setChecked(True)
        dlg._tx_band_checks["2m"].setChecked(True)
        dlg._tx_unrestricted.setChecked(False)
        dlg._save_tx_auth(cfg)
        assert cfg.get("tx.auth.acknowledged") is True
        assert set(cfg.get("tx.auth.allowed_bands")) == {"20m", "2m"}
        assert cfg.get("tx.auth.unrestricted") is False
        # a fresh dialog loads the saved state back
        dlg2 = _dialog(app)
        dlg2._load_tx_auth(cfg)
        assert dlg2._tx_ack.isChecked()
        assert dlg2._tx_band_checks["20m"].isChecked()
        assert dlg2._tx_band_checks["2m"].isChecked()
        assert not dlg2._tx_band_checks["40m"].isChecked()
        dlg.close(); dlg2.close()

    def test_saved_profile_authorizes_via_can_transmit(self, app):
        """End-to-end: what the UI saves is what the decision core reads."""
        from core.config import Config
        from core.authorization import AuthorizationProfile, can_transmit
        cfg = Config()
        dlg = _dialog(app)
        dlg._tx_ack.setChecked(True)
        dlg._tx_band_checks["20m"].setChecked(True)
        dlg._save_tx_auth(cfg)
        prof = AuthorizationProfile.from_cfg(cfg)
        assert can_transmit(14_074_000, prof).allowed        # 20m in list
        assert not can_transmit(146_520_000, prof).allowed   # 2m not
        dlg.close()
