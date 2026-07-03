# Squelch — RF / SDR signal platform
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/tx_license.py — license-class TX-privilege decisions."""

from core.band_plan import License
from core.tx_license import (
    LICENSE_CHOICES, OTHER_EMERGENCY, license_rank, is_amateur_freq,
    tx_privilege, allowed_segments,
)


class TestLicenseRank:
    def test_ordering(self):
        assert (license_rank(License.EXTRA)
                > license_rank(License.GENERAL)
                > license_rank(License.TECHNICIAN))

    def test_all_is_lowest(self):
        # "All" segments are usable by every class → rank 0.
        assert license_rank(License.ALL) == 0

    def test_unknown_class_is_zero(self):
        assert license_rank("Bogus") == 0
        assert license_rank(OTHER_EMERGENCY) == 0


class TestIsAmateurFreq:
    def test_amateur_hf(self):
        assert is_amateur_freq(14_074_000) is True     # 20m

    def test_amateur_vhf(self):
        assert is_amateur_freq(146_520_000) is True     # 2m simplex

    def test_gmrs_not_amateur(self):
        assert is_amateur_freq(462_562_500) is False    # GMRS ch.1

    def test_public_safety_not_amateur(self):
        assert is_amateur_freq(155_000_000) is False

    def test_zero_and_none_safe(self):
        assert is_amateur_freq(0) is False
        assert is_amateur_freq(None) is False


class TestTxPrivilege:
    def test_technician_blocked_on_20m_data(self):
        # Technicians have no 20m phone/data privileges.
        d = tx_privilege(14_074_000, License.TECHNICIAN)
        assert d.in_amateur is True
        assert d.license_ok is False
        assert d.needs_ack is True

    def test_general_ok_on_20m(self):
        d = tx_privilege(14_074_000, License.GENERAL)
        assert d.license_ok is True and d.needs_ack is False

    def test_extra_ok_on_20m(self):
        d = tx_privilege(14_074_000, License.EXTRA)
        assert d.license_ok is True and d.needs_ack is False

    def test_technician_ok_on_2m(self):
        d = tx_privilege(146_520_000, License.TECHNICIAN)
        assert d.in_amateur is True
        assert d.license_ok is True and d.needs_ack is False

    def test_out_of_band_needs_ack(self):
        d = tx_privilege(462_562_500, License.GENERAL)   # GMRS
        assert d.in_amateur is False
        assert d.needs_ack is True

    def test_other_emergency_always_needs_ack(self):
        # Even on a valid amateur freq, the override warns.
        d = tx_privilege(146_520_000, OTHER_EMERGENCY)
        assert d.needs_ack is True
        assert d.license_ok is False

    def test_returns_decision_never_raises(self):
        for f in (0, None, -1, 14_074_000, 462_000_000):
            for lc in LICENSE_CHOICES:
                d = tx_privilege(f, lc)
                assert d.license_class == lc


class TestAllowedSegments:
    def test_extra_covers_more_than_technician(self):
        assert len(allowed_segments(License.EXTRA)) \
            > len(allowed_segments(License.TECHNICIAN))

    def test_other_emergency_is_empty(self):
        assert allowed_segments(OTHER_EMERGENCY) == []

    def test_technician_has_some(self):
        assert len(allowed_segments(License.TECHNICIAN)) > 0


class TestChoices:
    def test_dropdown_order(self):
        assert LICENSE_CHOICES == [
            License.TECHNICIAN, License.GENERAL, License.EXTRA,
            OTHER_EMERGENCY]
