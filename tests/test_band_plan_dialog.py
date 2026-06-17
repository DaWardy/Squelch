"""Tests for band plan dialog helpers (no Qt required)."""
from __future__ import annotations
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from core.band_plan import BANDS, License, SegType


# ── _freq_label (mirror) ──────────────────────────────────────────────────

def _freq_label(hz: int) -> str:
    if hz >= 1_000_000:
        mhz = hz / 1_000_000
        return f"{mhz:.3f}".rstrip("0").rstrip(".") + " MHz"
    return f"{hz / 1000:.1f} kHz"


class TestFreqLabel:
    def test_mhz_round(self):
        assert _freq_label(14_000_000) == "14 MHz"

    def test_mhz_decimal(self):
        assert _freq_label(14_074_000) == "14.074 MHz"

    def test_khz(self):
        assert _freq_label(472_000) == "472.0 kHz"

    def test_1_mhz(self):
        assert _freq_label(1_800_000) == "1.8 MHz"


# ── privilege check (mirror) ──────────────────────────────────────────────

_LICENSE_RANK = {"Technician": 0, "General": 1, "Extra": 2, "Other / Non-US": 2}
_SEG_RANK = {
    License.ALL:        0,
    License.TECHNICIAN: 0,
    License.NOVICE:     0,
    License.GENERAL:    1,
    License.EXTRA:      2,
}


def _is_accessible(license_class: str, seg_license: str) -> bool:
    user_rank = _LICENSE_RANK.get(license_class, 2)
    seg_rank  = _SEG_RANK.get(seg_license, 0)
    return user_rank >= seg_rank


class TestPrivilegeCheck:
    def test_extra_accesses_all(self):
        for lic in [License.ALL, License.GENERAL, License.EXTRA]:
            assert _is_accessible("Extra", lic)

    def test_general_cannot_use_extra_segments(self):
        assert not _is_accessible("General", License.EXTRA)

    def test_general_can_use_general_segments(self):
        assert _is_accessible("General", License.GENERAL)

    def test_technician_cannot_use_general(self):
        assert not _is_accessible("Technician", License.GENERAL)

    def test_technician_can_use_all(self):
        assert _is_accessible("Technician", License.ALL)

    def test_other_treated_as_extra(self):
        assert _is_accessible("Other / Non-US", License.EXTRA)


# ── BANDS data integrity ──────────────────────────────────────────────────

class TestBandsIntegrity:
    def test_bands_not_empty(self):
        assert len(BANDS) > 0

    def test_each_band_has_segments(self):
        for band in BANDS:
            assert len(band.segments) > 0, f"{band.name} has no segments"

    def test_segment_ranges_do_not_exceed_band(self):
        for band in BANDS:
            for seg in band.segments:
                assert seg.freq_lo >= band.freq_lo, (
                    f"{band.name} segment starts below band edge")
                assert seg.freq_hi <= band.freq_hi, (
                    f"{band.name} segment ends above band edge")

    def test_segment_lo_not_greater_than_hi(self):
        for band in BANDS:
            for seg in band.segments:
                assert seg.freq_lo <= seg.freq_hi, (
                    f"Degenerate segment in {band.name}")

    def test_band_names_unique(self):
        names = [b.name for b in BANDS]
        assert len(names) == len(set(names))
