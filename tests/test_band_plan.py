from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
#
# This program is free software: you can redistribute it
# and/or modify it under the terms of the GNU General
# Public License as published by the Free Software
# Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General
# Public License along with this program. If not, see
# <https://www.gnu.org/licenses/>.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.constants import (
    PORT_VARA_HF_DATA,
    FFT_SIZE,
    AUDIO_SAMPLE_RATE,
    APP_VERSION,
    APP_URL,
    FT8_FREQUENCIES, FT4_FREQUENCIES, WSPR_FREQUENCIES,
    BAND_EDGES_R1, BAND_EDGES_R2, BAND_EDGES_R3,
    PORT_WSJT_UDP, PORT_HAMLIB_RIGCTLD,
    PORT_DUMP1090_HTTP, PORT_VARA_HF_CMD,
)


class TestBandEdges:

    def test_20m_r2_correct(self):
        lo, hi = BAND_EDGES_R2["20m"]
        assert lo == 14_000_000
        assert hi == 14_350_000

    def test_40m_r1_narrower_than_r2(self):
        """Region 1 40m is 7.0-7.2 MHz, Region 2 is 7.0-7.3 MHz."""
        lo1, hi1 = BAND_EDGES_R1["40m"]
        lo2, hi2 = BAND_EDGES_R2["40m"]
        assert hi1 < hi2, "R1 40m should be narrower than R2"

    def test_all_r2_bands_have_lo_lt_hi(self):
        for band, (lo, hi) in BAND_EDGES_R2.items():
            assert lo < hi, f"{band}: lo={lo} >= hi={hi}"

    def test_all_r1_bands_have_lo_lt_hi(self):
        for band, (lo, hi) in BAND_EDGES_R1.items():
            assert lo < hi, f"{band}: lo={lo} >= hi={hi}"

    def test_hf_below_vhf(self):
        """HF bands should be below 30 MHz."""
        hf_bands = ["160m", "80m", "40m", "30m", "20m",
                    "17m", "15m", "12m", "10m"]
        for band in hf_bands:
            lo, hi = BAND_EDGES_R2[band]
            assert hi < 30_000_000, \
                f"{band} hi={hi} should be below 30MHz"

    def test_2m_in_vhf(self):
        lo, hi = BAND_EDGES_R2["2m"]
        assert 144_000_000 <= lo < hi <= 148_000_000

    def test_70cm_in_uhf(self):
        lo, hi = BAND_EDGES_R2["70cm"]
        assert lo >= 420_000_000
        assert hi <= 450_000_000

    def test_non_overlapping_bands(self):
        """No two HF bands should overlap in R2."""
        hf_bands = ["160m", "80m", "40m", "30m", "20m",
                    "17m", "15m", "12m", "10m"]
        ranges = [BAND_EDGES_R2[b] for b in hf_bands]
        ranges.sort()
        for i in range(len(ranges) - 1):
            assert ranges[i][1] <= ranges[i+1][0], \
                f"Bands overlap: {ranges[i]} and {ranges[i+1]}"


class TestFT8Frequencies:

    def test_20m_ft8_in_band(self):
        freq = FT8_FREQUENCIES["20m"]
        lo, hi = BAND_EDGES_R2["20m"]
        assert lo <= freq <= hi, \
            f"20m FT8 {freq} not in band {lo}-{hi}"

    def test_all_ft8_in_bands(self):
        for band, freq in FT8_FREQUENCIES.items():
            if band in BAND_EDGES_R2:
                lo, hi = BAND_EDGES_R2[band]
                assert lo <= freq <= hi, \
                    f"FT8 {band} {freq} not in {lo}-{hi}"

    def test_all_ft4_in_bands(self):
        for band, freq in FT4_FREQUENCIES.items():
            if band in BAND_EDGES_R2:
                lo, hi = BAND_EDGES_R2[band]
                assert lo <= freq <= hi, \
                    f"FT4 {band} {freq} not in {lo}-{hi}"

    def test_all_wspr_in_bands(self):
        for band, freq in WSPR_FREQUENCIES.items():
            if band in BAND_EDGES_R2:
                lo, hi = BAND_EDGES_R2[band]
                assert lo <= freq <= hi, \
                    f"WSPR {band} {freq} not in {lo}-{hi}"

    def test_20m_known_frequency(self):
        assert FT8_FREQUENCIES["20m"] == 14_074_000

    def test_40m_known_frequency(self):
        assert FT8_FREQUENCIES["40m"] == 7_074_000

    def test_wspr_20m_known_frequency(self):
        assert WSPR_FREQUENCIES["20m"] == 14_097_100


class TestConstants:

    def test_ports_in_valid_range(self):
        for port in [PORT_WSJT_UDP, PORT_HAMLIB_RIGCTLD,
                     PORT_DUMP1090_HTTP, PORT_VARA_HF_CMD]:
            assert 1 <= port <= 65535, \
                f"Port {port} out of valid range"

    def test_wsjt_udp_port(self):
        assert PORT_WSJT_UDP == 2237

    def test_hamlib_port(self):
        assert PORT_HAMLIB_RIGCTLD == 4532

    def test_dump1090_port(self):
        assert PORT_DUMP1090_HTTP == 8080

    def test_vara_ports_sequential(self):
        """VARA control and data ports should be sequential."""
        from core.constants import PORT_VARA_HF_CMD, PORT_VARA_HF_DATA
        assert PORT_VARA_HF_DATA == PORT_VARA_HF_CMD + 1

    def test_app_version_format(self):
        from core.constants import APP_VERSION
        parts = APP_VERSION.split(".")
        assert len(parts) >= 2, \
            f"Version {APP_VERSION} should have major.minor"

    def test_app_url_https(self):
        from core.constants import APP_URL
        assert APP_URL.startswith("https://"), \
            f"App URL should use HTTPS: {APP_URL}"

    def test_audio_sample_rate_standard(self):
        from core.constants import AUDIO_SAMPLE_RATE
        assert AUDIO_SAMPLE_RATE in (44100, 48000, 96000), \
            f"Sample rate {AUDIO_SAMPLE_RATE} not standard"

    def test_fft_size_power_of_two(self):
        from core.constants import FFT_SIZE
        assert FFT_SIZE > 0
        assert (FFT_SIZE & (FFT_SIZE - 1)) == 0, \
            f"FFT_SIZE {FFT_SIZE} must be power of 2"
