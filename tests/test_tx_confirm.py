# Squelch — RF / SDR signal platform
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for ui/tx_confirm.py — the license-class TX confirmation gate.

Only needs_tx_confirmation() (pure, no Qt) is unit-tested here; confirm_tx()'s
QMessageBox branch is a thin wrapper exercised via source-scan + the rig_tab
wiring checks below.
"""

import ast
from pathlib import Path

from ui.tx_confirm import needs_tx_confirmation

ROOT = Path(__file__).parent.parent


class _FakeCfg:
    """Minimal stand-in for core.config.Config."""
    def __init__(self, values=None):
        self._v = dict(values or {})
        self.saved = False

    def get(self, key, default=None):
        return self._v.get(key, default)

    def set(self, key, value):
        self._v[key] = value

    def save(self):
        self.saved = True


class TestNeedsTxConfirmation:
    def test_in_privilege_returns_none(self):
        # General has full 20m privileges.
        cfg = _FakeCfg({"station.license": "General"})
        assert needs_tx_confirmation(cfg, 14_074_000) is None

    def test_technician_out_of_privilege_needs_confirmation(self):
        cfg = _FakeCfg({"station.license": "Technician"})
        d = needs_tx_confirmation(cfg, 14_074_000)   # 20m, Tech has no privileges
        assert d is not None
        assert d.needs_ack is True

    def test_out_of_amateur_band_needs_confirmation(self):
        cfg = _FakeCfg({"station.license": "Extra"})
        d = needs_tx_confirmation(cfg, 462_562_500)   # GMRS — not amateur
        assert d is not None

    def test_already_acknowledged_returns_none(self):
        # Same out-of-privilege case as above, but the one-time ack is set.
        cfg = _FakeCfg({"station.license": "Technician", "tx.out_of_band_ack": True})
        assert needs_tx_confirmation(cfg, 14_074_000) is None

    def test_other_emergency_always_needs_confirmation_until_acked(self):
        cfg = _FakeCfg({"station.license": "Other / Emergency"})
        d = needs_tx_confirmation(cfg, 146_520_000)   # valid amateur freq
        assert d is not None
        cfg.set("tx.out_of_band_ack", True)
        assert needs_tx_confirmation(cfg, 146_520_000) is None

    def test_no_cfg_defaults_safely(self):
        # None cfg must not raise — default to the most conservative class.
        d = needs_tx_confirmation(None, 14_074_000)
        assert d is not None   # Technician default has no 20m privileges

    def test_missing_license_key_defaults_to_technician(self):
        cfg = _FakeCfg({})   # no station.license set at all
        d = needs_tx_confirmation(cfg, 14_074_000)
        assert d is not None
        assert d.license_class == "Technician"


class TestConfirmTxSource:
    """Source-scan: confirm_tx must persist acknowledgment on accept, not on decline."""

    def _src(self) -> str:
        return (ROOT / "ui" / "tx_confirm.py").read_text(encoding="utf-8")

    def test_confirm_tx_defined(self):
        assert "def confirm_tx(" in self._src()

    def test_ack_only_persisted_on_yes(self):
        src = self._src()
        idx = src.find("def confirm_tx(")
        body = src[idx:]
        yes_idx = body.find("StandardButton.Yes:")
        set_idx = body.find("cfg.set(_CFG_ACK, True)")
        assert yes_idx != -1 and set_idx != -1 and set_idx > yes_idx


class TestRigTabWiring:
    """Source-scan: the PTT chokepoint must gate through confirm_tx before TX."""

    def _src(self) -> str:
        return (ROOT / "ui" / "tabs" / "rig_tab.py").read_text(encoding="utf-8")

    def test_on_ptt_parses_cleanly(self):
        ast.parse(self._src())

    def test_on_ptt_calls_confirm_tx(self):
        src = self._src()
        idx = src.find("def _on_ptt(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "confirm_tx" in body

    def test_confirm_tx_checked_before_set_ptt_on_tx(self):
        src = self._src()
        idx = src.find("def _on_ptt(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        # confirm_tx() must gate the True/keying path, not run after set_ptt.
        confirm_idx = body.find("confirm_tx(")
        set_ptt_idx = body.find("self.rig.set_ptt(tx)")
        assert confirm_idx != -1 and set_ptt_idx != -1
        assert confirm_idx < set_ptt_idx


class TestAllTxPathsGated:
    """Every user-initiated TX path must route through confirm_tx() before it
    transmits. A future refactor that drops one of these gates should fail here.
    """

    def _method_body(self, rel: str, method: str) -> str:
        src = (ROOT / rel).read_text(encoding="utf-8")
        idx = src.find(f"def {method}(")
        assert idx != -1, f"{method} not found in {rel}"
        end = src.find("\n    def ", idx + 10)
        return src[idx: end if end != -1 else len(src)]

    def test_manual_ptt_gated(self):
        body = self._method_body("ui/tabs/rig_tab.py", "_on_ptt")
        assert "confirm_tx" in body

    def test_cw_keyer_and_macros_gated(self):
        # _cw_macro_click routes through _send_cw, so gating _send_cw covers both.
        body = self._method_body("ui/tabs/rig_cw_mixin.py", "_send_cw")
        assert "confirm_tx" in body

    def test_voice_keyer_gated(self):
        body = self._method_body("ui/tabs/rig_voice_mixin.py", "_voice_play")
        assert "confirm_tx" in body

    def test_digital_send_and_macros_gated(self):
        # _on_macro_btn routes through _send_tx_text, so one gate covers both.
        body = self._method_body("ui/tabs/digital_tab.py", "_send_tx_text")
        assert "confirm_tx" in body

    def test_sdr_tx_iq_gated(self):
        body = self._method_body("ui/tabs/sdr_signal_id.py", "_tx_iq_file")
        assert "confirm_tx" in body

    def test_cw_macro_routes_through_send_cw(self):
        # Guards the "one gate covers macros too" assumption for CW.
        body = self._method_body("ui/tabs/rig_cw_mixin.py", "_cw_macro_click")
        assert "_send_cw()" in body

    def test_digital_macro_routes_through_send_tx_text(self):
        body = self._method_body("ui/tabs/digital_tab.py", "_on_macro_btn")
        assert "_send_tx_text()" in body


class TestSettingsStationLicenseCombo:
    def _src(self) -> str:
        return (ROOT / "ui" / "dialogs" / "settings_station_tab.py").read_text(
            encoding="utf-8")

    def test_five_choices_present(self):
        src = self._src()
        for label in ("Technician", "General", "Extra",
                      "Other / Non-US", "Other / Emergency"):
            assert label in src

    def test_no_stale_lowercase_token_mapping(self):
        # The old lic_map/lic_labels lowercase-token scheme (which never
        # matched BandPlanDialog's capitalized keys) must not come back.
        save_src = (ROOT / "ui" / "dialogs" / "settings_dialog.py").read_text(
            encoding="utf-8")
        assert "lic_labels" not in save_src
        assert "lic_map" not in save_src
