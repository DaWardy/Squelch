"""Tests for core/authorization.py — TX authorization gate (AUTH-LAYER)."""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))


def _profile(**kw):
    from core.authorization import AuthorizationProfile
    return AuthorizationProfile(**kw)


# 14.074 MHz = 20m (amateur); 146.52 = 2m; 462.5625 = FRS/GMRS
_F_20M = 14_074_000
_F_2M  = 146_520_000
_F_FRS = 462_562_500


# ── default-deny ─────────────────────────────────────────────────────────────


class TestDefaultDeny:
    def test_unacknowledged_denied(self):
        from core.authorization import can_transmit
        d = can_transmit(_F_20M, _profile(acknowledged=False,
                                          allowed_bands={"20m"}))
        assert not d.allowed
        assert "acknowledg" in d.reason.lower()

    def test_acknowledged_but_no_bands_denied(self):
        from core.authorization import can_transmit
        d = can_transmit(_F_20M, _profile(acknowledged=True))
        assert not d.allowed
        assert "not in the authorized" in d.reason

    def test_bool_protocol(self):
        from core.authorization import can_transmit
        d = can_transmit(_F_20M, _profile(acknowledged=True,
                                          allowed_bands={"20m"}))
        assert bool(d) is True


# ── per-band allow-list ──────────────────────────────────────────────────────


class TestBandAllowList:
    def test_allowed_band(self):
        from core.authorization import can_transmit
        d = can_transmit(_F_20M, _profile(acknowledged=True,
                                          allowed_bands={"20m"}))
        assert d.allowed
        assert d.band == "20m"

    def test_other_band_denied(self):
        from core.authorization import can_transmit
        # 2m not in the list (only 20m authorized)
        d = can_transmit(_F_2M, _profile(acknowledged=True,
                                         allowed_bands={"20m"}))
        assert not d.allowed
        assert d.band == "2m"

    def test_service_band_authorizable(self):
        from core.authorization import can_transmit
        d = can_transmit(_F_FRS, _profile(acknowledged=True,
                                          allowed_bands={"FRS / GMRS"}))
        assert d.allowed

    def test_unknown_frequency_denied(self):
        from core.authorization import can_transmit
        d = can_transmit(2_500_000, _profile(acknowledged=True,
                                             allowed_bands={"20m"}))
        assert not d.allowed
        assert "not within a known" in d.reason

    def test_invalid_freq_denied(self):
        from core.authorization import can_transmit
        d = can_transmit(0, _profile(acknowledged=True, allowed_bands={"20m"}))
        assert not d.allowed


# ── unrestricted override ────────────────────────────────────────────────────


class TestUnrestricted:
    def test_override_allows_any_band(self):
        from core.authorization import can_transmit
        p = _profile(acknowledged=True, unrestricted=True)  # no bands listed
        assert can_transmit(_F_2M, p).allowed
        assert can_transmit(_F_20M, p).allowed

    def test_override_still_requires_ack(self):
        from core.authorization import can_transmit
        p = _profile(acknowledged=False, unrestricted=True)
        assert not can_transmit(_F_20M, p).allowed

    def test_override_reason_mentions_responsibility(self):
        from core.authorization import can_transmit
        p = _profile(acknowledged=True, unrestricted=True)
        assert "responsibility" in can_transmit(_F_20M, p).reason.lower()


# ── mutators + persistence ───────────────────────────────────────────────────


class TestProfileMutators:
    def test_allow_deny_band(self):
        p = _profile(acknowledged=True)
        p.allow_band("40m")
        assert "40m" in p.allowed_bands
        p.deny_band("40m")
        assert "40m" not in p.allowed_bands

    def test_allow_empty_noop(self):
        p = _profile()
        p.allow_band("")
        assert p.allowed_bands == set()


class TestPersistence:
    def _cfg(self):
        store = {}
        cfg = MagicMock()
        cfg.get.side_effect = lambda k, d=None: store.get(k, d)
        cfg.set.side_effect = lambda k, v: store.__setitem__(k, v)
        return cfg, store

    def test_save_then_load_roundtrip(self):
        from core.authorization import AuthorizationProfile
        cfg, _ = self._cfg()
        p = AuthorizationProfile(acknowledged=True,
                                 allowed_bands={"20m", "40m"},
                                 unrestricted=False)
        p.save(cfg)
        p2 = AuthorizationProfile.from_cfg(cfg)
        assert p2.acknowledged is True
        assert p2.allowed_bands == {"20m", "40m"}
        assert p2.unrestricted is False

    def test_from_cfg_defaults_deny(self):
        from core.authorization import AuthorizationProfile
        cfg, _ = self._cfg()
        p = AuthorizationProfile.from_cfg(cfg)
        assert p.acknowledged is False
        assert p.allowed_bands == set()
        assert p.unrestricted is False


# ── resolve_band helper ──────────────────────────────────────────────────────


class TestResolveBand:
    def test_amateur(self):
        from core.authorization import resolve_band
        assert resolve_band(_F_20M).name == "20m"

    def test_service(self):
        from core.authorization import resolve_band
        assert resolve_band(_F_FRS).category == "FRS/GMRS"

    def test_none(self):
        from core.authorization import resolve_band
        assert resolve_band(2_500_000) is None
