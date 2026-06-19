"""Tests for band plan dialog helpers (no Qt required)."""
from __future__ import annotations
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from core.band_plan import BANDS, SERVICE_BANDS, ALL_BANDS, License, SegType, SEG_COLORS


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

    def test_all_amateur_bands_have_amateur_category(self):
        for band in BANDS:
            assert band.category == "Amateur", (
                f"{band.name} should have category 'Amateur'")

    def test_new_part97_bands_present(self):
        names = {b.name for b in BANDS}
        for expected in ("1.25m", "33cm", "23cm", "13cm"):
            assert expected in names, f"Part 97 band {expected!r} missing from BANDS"

    def test_part97_bands_have_segments(self):
        for name in ("1.25m", "33cm", "23cm", "13cm"):
            band = next((b for b in BANDS if b.name == name), None)
            assert band is not None
            assert len(band.segments) > 0


class TestServiceBands:
    def test_service_bands_not_empty(self):
        assert len(SERVICE_BANDS) > 0

    def test_service_bands_have_non_amateur_category(self):
        for band in SERVICE_BANDS:
            assert band.category != "Amateur", (
                f"{band.name} service band should not have 'Amateur' category")

    def test_service_bands_have_segments(self):
        for band in SERVICE_BANDS:
            assert len(band.segments) > 0, f"{band.name} has no segments"

    def test_service_band_segment_ranges_within_band(self):
        for band in SERVICE_BANDS:
            for seg in band.segments:
                assert seg.freq_lo >= band.freq_lo, (
                    f"{band.name} segment starts below band edge")
                assert seg.freq_hi <= band.freq_hi, (
                    f"{band.name} segment ends above band edge")

    def test_service_band_names_unique(self):
        names = [b.name for b in SERVICE_BANDS]
        assert len(names) == len(set(names))

    def test_all_bands_contains_amateur_and_service(self):
        assert len(ALL_BANDS) == len(BANDS) + len(SERVICE_BANDS)

    def test_cb_band_present(self):
        cb = next((b for b in SERVICE_BANDS if b.category == "CB"), None)
        assert cb is not None, "CB band missing from SERVICE_BANDS"
        assert 26_900_000 <= cb.freq_lo < 27_500_000

    def test_cb_has_emergency_ch9_segment(self):
        cb = next((b for b in SERVICE_BANDS if b.category == "CB"), None)
        assert cb is not None
        has_guard = any(s.seg_type == SegType.GUARD for s in cb.segments)
        assert has_guard, "CB band missing emergency Ch.9 Guard segment"

    def test_frs_band_present(self):
        frs = next((b for b in SERVICE_BANDS if b.category == "FRS/GMRS"), None)
        assert frs is not None, "FRS/GMRS band missing from SERVICE_BANDS"
        assert 462_000_000 <= frs.freq_lo < 468_000_000

    def test_frs_has_no_license_segments(self):
        frs = next((b for b in SERVICE_BANDS if b.category == "FRS/GMRS"), None)
        assert frs is not None
        frs_segs = [s for s in frs.segments if s.license == License.NONE]
        assert len(frs_segs) > 0, "FRS segments should have License.NONE"

    def test_murs_band_present(self):
        murs = next((b for b in SERVICE_BANDS if b.category == "MURS"), None)
        assert murs is not None, "MURS band missing from SERVICE_BANDS"

    def test_murs_channels_in_151_154_mhz(self):
        murs = next((b for b in SERVICE_BANDS if b.category == "MURS"), None)
        assert murs is not None
        assert 151_000_000 <= murs.freq_lo <= 152_000_000
        assert 154_000_000 <= murs.freq_hi <= 155_000_000

    def test_ism_2_4_ghz_present(self):
        ism = next((b for b in SERVICE_BANDS
                    if "2.4" in b.name or "2_4" in b.name.lower()), None)
        if ism is None:
            ism = next((b for b in SERVICE_BANDS
                        if b.freq_lo == 2_400_000_000), None)
        assert ism is not None, "ISM 2.4 GHz band missing from SERVICE_BANDS"

    def test_ism_900_mhz_present(self):
        ism = next((b for b in SERVICE_BANDS
                    if b.freq_lo == 902_000_000), None)
        assert ism is not None, "ISM 900 MHz band missing from SERVICE_BANDS"

    def test_wifi_5ghz_present(self):
        wifi = next((b for b in SERVICE_BANDS
                     if b.freq_lo == 5_150_000_000), None)
        assert wifi is not None, "UNII 5 GHz band missing from SERVICE_BANDS"

    def test_wifi_6ghz_present(self):
        wifi = next((b for b in SERVICE_BANDS
                     if b.freq_lo >= 5_900_000_000), None)
        assert wifi is not None, "Wi-Fi 6 GHz band missing from SERVICE_BANDS"


class TestNewSegTypesAndLicense:
    def test_new_segtypes_in_seg_colors(self):
        for st in (SegType.FRS, SegType.GMRS_CHAN, SegType.CB,
                   SegType.MURS, SegType.ISM, SegType.WIFI):
            assert st in SEG_COLORS, f"SegType.{st!r} missing from SEG_COLORS"

    def test_license_none_defined(self):
        assert License.NONE == "None required"

    def test_license_gmrs_defined(self):
        assert License.GMRS_LIC == "GMRS License"

    def test_service_band_segments_use_none_or_gmrs_license(self):
        valid = {License.NONE, License.GMRS_LIC}
        for band in SERVICE_BANDS:
            for seg in band.segments:
                assert seg.license in valid, (
                    f"{band.name} segment uses license {seg.license!r}; "
                    f"service bands must use License.NONE or License.GMRS_LIC")
