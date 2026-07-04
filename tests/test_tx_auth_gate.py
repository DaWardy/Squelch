"""Tests for the TX authorization chokepoint (AUTH-LAYER wiring / TX-CHAIN):
core.authorization.authorize_tx() + the gate inside SoapyManager.transmit_iq().
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

_F_20M = 14_074_000        # 20m amateur
_F_2M  = 146_520_000       # 2m amateur
_F_OOB = 99_999_999_999    # not in any known band


class _FakeCfg:
    """Duck-typed cfg exposing .get(key, default) over a dict."""
    def __init__(self, data=None):
        self._d = dict(data or {})

    def get(self, key, default=None):
        return self._d.get(key, default)


class _FakeSafety:
    def __init__(self, demo=False):
        self._demo = demo

    def is_demo_mode(self):
        return self._demo


def _cfg(ack=True, bands=("20m",), unrestricted=False):
    return _FakeCfg({
        "tx.auth.acknowledged": ack,
        "tx.auth.allowed_bands": list(bands),
        "tx.auth.unrestricted": unrestricted,
    })


# ── authorize_tx composition ─────────────────────────────────────────────────


class TestAuthorizeTx:
    def test_allows_authorized_band(self):
        from core.authorization import authorize_tx
        d = authorize_tx(_F_20M, cfg=_cfg(), safety=_FakeSafety())
        assert d.allowed
        assert d.band == "20m"

    def test_denies_unauthorized_band(self):
        from core.authorization import authorize_tx
        d = authorize_tx(_F_2M, cfg=_cfg(bands=("20m",)),
                         safety=_FakeSafety())
        assert not d.allowed
        assert "2m" in d.reason

    def test_denies_without_ack(self):
        from core.authorization import authorize_tx
        d = authorize_tx(_F_20M, cfg=_cfg(ack=False), safety=_FakeSafety())
        assert not d.allowed
        assert "acknowledg" in d.reason.lower()

    def test_demo_mode_is_absolute_block(self):
        from core.authorization import authorize_tx
        # fully authorized profile — demo mode must still deny
        d = authorize_tx(_F_20M, cfg=_cfg(unrestricted=True),
                         safety=_FakeSafety(demo=True))
        assert not d.allowed
        assert "demo" in d.reason.lower()

    def test_unrestricted_override(self):
        from core.authorization import authorize_tx
        d = authorize_tx(_F_OOB, cfg=_cfg(bands=(), unrestricted=True),
                         safety=_FakeSafety())
        assert d.allowed
        assert "responsibility" in d.reason.lower()

    def test_unknown_band_denied(self):
        from core.authorization import authorize_tx
        d = authorize_tx(_F_OOB, cfg=_cfg(), safety=_FakeSafety())
        assert not d.allowed

    def test_fails_closed_on_broken_cfg(self):
        from core.authorization import authorize_tx
        broken = MagicMock()
        broken.get.side_effect = RuntimeError("boom")
        d = authorize_tx(_F_20M, cfg=broken, safety=_FakeSafety())
        assert not d.allowed          # AuthorizationProfile.from_cfg → default-deny

    def test_fails_closed_on_broken_safety(self):
        from core.authorization import authorize_tx
        broken = MagicMock()
        broken.is_demo_mode.side_effect = RuntimeError("boom")
        d = authorize_tx(_F_20M, cfg=_cfg(), safety=broken)
        assert not d.allowed
        assert "failed" in d.reason.lower()

    def test_keying_logged_to_netlog(self):
        from core.authorization import authorize_tx
        from core.netlog import recent_events
        authorize_tx(_F_20M, cfg=_cfg(), safety=_FakeSafety())
        authorize_tx(_F_2M, cfg=_cfg(bands=("20m",)), safety=_FakeSafety())
        evs = recent_events(limit=10)
        tx_evs = [e for e in evs if e["host"].startswith("TX ")]
        assert any("AUTHORIZED" in e["purpose"] for e in tx_evs)
        assert any("DENIED" in e["purpose"] for e in tx_evs)
        # user-visible frequency in MHz
        assert any("14.0740 MHz" in e["host"] for e in tx_evs)


# ── safety accessor ──────────────────────────────────────────────────────────


class TestDemoAccessor:
    def test_is_demo_mode_roundtrip(self):
        from core.safety import SafetyManager
        s = SafetyManager()
        assert s.is_demo_mode() is False
        s.set_demo_mode(True)
        assert s.is_demo_mode() is True
        s.set_demo_mode(False)
        assert s.is_demo_mode() is False


# ── transmit_iq chokepoint ───────────────────────────────────────────────────


class TestTransmitIqGate:
    def _manager(self, freq):
        from sdr.soapy_device import SoapyManager
        m = SoapyManager()
        m._center_hz = freq
        return m

    def test_denied_raises_permission_error(self, monkeypatch):
        import core.config as config_mod
        import core.safety as safety_mod
        monkeypatch.setattr(config_mod, "get_config",
                            lambda: _cfg(ack=False))
        monkeypatch.setattr(safety_mod, "get_safety",
                            lambda: _FakeSafety())
        m = self._manager(_F_20M)
        # give it a "TX-capable device" so ONLY the auth gate can stop it
        m.current_device = MagicMock(can_tx=True)
        m._device = MagicMock()
        m._tx_stream = MagicMock()
        try:
            m.transmit_iq([0j])
            assert False, "expected PermissionError"
        except PermissionError as e:
            assert "not authorized" in str(e).lower()
        # the gate fired BEFORE any hardware call
        m._device.writeStream.assert_not_called()

    def test_authorized_passes_gate(self, monkeypatch):
        import core.config as config_mod
        import core.safety as safety_mod
        monkeypatch.setattr(config_mod, "get_config", lambda: _cfg())
        monkeypatch.setattr(safety_mod, "get_safety",
                            lambda: _FakeSafety())
        m = self._manager(_F_20M)
        m.current_device = MagicMock(can_tx=True)
        m._device = MagicMock()
        m._tx_stream = MagicMock()
        m.transmit_iq([0j])                        # no PermissionError
        m._device.writeStream.assert_called_once()

    def test_demo_mode_blocks_transmit_iq(self, monkeypatch):
        import core.config as config_mod
        import core.safety as safety_mod
        monkeypatch.setattr(config_mod, "get_config",
                            lambda: _cfg(unrestricted=True))
        monkeypatch.setattr(safety_mod, "get_safety",
                            lambda: _FakeSafety(demo=True))
        m = self._manager(_F_20M)
        m.current_device = MagicMock(can_tx=True)
        m._device = MagicMock()
        try:
            m.transmit_iq([0j])
            assert False, "expected PermissionError"
        except PermissionError:
            pass
        m._device.writeStream.assert_not_called()

    def test_gate_precedes_capability_check(self, monkeypatch):
        """Even an RX-only device must hit the auth gate first — denial
        reason must be authorization, not capability."""
        import core.config as config_mod
        import core.safety as safety_mod
        monkeypatch.setattr(config_mod, "get_config",
                            lambda: _cfg(ack=False))
        monkeypatch.setattr(safety_mod, "get_safety",
                            lambda: _FakeSafety())
        m = self._manager(_F_20M)                  # no device at all
        try:
            m.transmit_iq([0j])
            assert False, "expected PermissionError"
        except PermissionError:
            pass


# ── gate-coverage source check ───────────────────────────────────────────────


class TestGateCoverage:
    def test_transmit_iq_contains_auth_gate(self):
        """Guard: a refactor must not silently drop the authorize_tx call
        from the transmit_iq chokepoint (mirrors the tx_license gate tests)."""
        src = (Path(__file__).parent.parent / "sdr" /
               "soapy_device.py").read_text(encoding="utf-8")
        import re
        m = re.search(r"def transmit_iq\(.*?(?=\n    def |\nclass )",
                      src, re.DOTALL)
        assert m, "transmit_iq not found"
        body = m.group(0)
        assert "authorize_tx" in body
        assert "PermissionError" in body
