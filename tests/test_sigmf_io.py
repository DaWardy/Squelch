# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/sigmf_io.py — IQ ↔ SigMF codec."""
import json
import numpy as np
import pytest

from core.sigmf_io import (
    parse_datatype, DataType, SigMFMeta, read_iq, read_meta, write_iq,
    make_annotation, SIGMF_VERSION,
)


# ── datatype parsing ──────────────────────────────────────────────────────────

class TestParseDatatype:
    def test_cf32_le(self):
        dt = parse_datatype("cf32_le")
        assert dt.is_complex and dt.kind == "f" and dt.bits == 32
        assert dt.np_dtype == np.dtype("<f4")

    def test_cu8_rtlsdr(self):
        dt = parse_datatype("cu8")
        assert dt.is_complex and dt.kind == "u" and dt.bits == 8

    def test_ci16_be(self):
        dt = parse_datatype("ci16_be")
        assert dt.np_dtype == np.dtype(">i2")

    def test_real_type(self):
        dt = parse_datatype("rf32_le")
        assert not dt.is_complex

    def test_unsupported_raises(self):
        for bad in ("", "zz32", "cf99", "cx16"):
            with pytest.raises(ValueError):
                parse_datatype(bad)


# ── write / read round-trip ───────────────────────────────────────────────────

class TestRoundTrip:
    def _iq(self, n=256):
        rng = np.random.default_rng(0)
        return (rng.standard_normal(n) * 0.4
                + 1j * rng.standard_normal(n) * 0.4).astype(np.complex64)

    def test_cf32_round_trip(self, tmp_path):
        iq = self._iq()
        write_iq(iq, tmp_path / "rec", sample_rate=2_048_000,
                 center_hz=100_000_000, description="test")
        back, meta = read_iq(tmp_path / "rec")
        assert back.dtype == np.complex64
        assert np.allclose(back, iq, atol=1e-6)
        assert meta.sample_rate == 2_048_000
        assert meta.center_hz == 100_000_000
        assert meta.datatype == "cf32_le"
        assert meta.version == SIGMF_VERSION

    def test_creates_both_files(self, tmp_path):
        meta_p, data_p = write_iq(self._iq(), tmp_path / "r",
                                  sample_rate=1_000_000)
        assert meta_p.exists() and data_p.exists()
        assert meta_p.suffix == ".sigmf-meta"

    def test_path_accepts_any_suffix(self, tmp_path):
        iq = self._iq()
        write_iq(iq, tmp_path / "r", sample_rate=1_000_000)
        # read via base, .sigmf-meta, and .sigmf-data all resolve the same
        for p in ("r", "r.sigmf-meta", "r.sigmf-data"):
            back, _ = read_iq(tmp_path / p)
            assert np.allclose(back, iq, atol=1e-6)

    def test_meta_json_has_core_keys(self, tmp_path):
        meta_p, _ = write_iq(self._iq(), tmp_path / "r",
                             sample_rate=1_000_000, center_hz=145_000_000)
        raw = json.loads(meta_p.read_text(encoding="utf-8"))
        assert raw["global"]["core:datatype"] == "cf32_le"
        assert raw["global"]["core:sample_rate"] == 1_000_000
        assert raw["captures"][0]["core:frequency"] == 145_000_000


# ── reading foreign datatypes ─────────────────────────────────────────────────

class TestForeignDatatypes:
    def _write_raw(self, tmp_path, datatype, raw_array):
        base = tmp_path / "foreign"
        (base.with_suffix(".sigmf-data")).write_bytes(raw_array.tobytes())
        meta = {"global": {"core:datatype": datatype,
                           "core:sample_rate": 2_400_000,
                           "core:frequency": 100_000_000,
                           "core:version": SIGMF_VERSION},
                "captures": [{"core:sample_start": 0}], "annotations": []}
        (base.with_suffix(".sigmf-meta")).write_text(json.dumps(meta))
        return base

    def test_reads_cu8_rtlsdr(self, tmp_path):
        # cu8: 127/128 ≈ 0 → after (x-128)/128; 255→~1, 0→-1
        raw = np.array([128, 128, 255, 0], dtype=np.uint8)   # (0+0j), (~1 - 1j)
        base = self._write_raw(tmp_path, "cu8", raw)
        iq, meta = read_iq(base)
        assert meta.datatype == "cu8"
        assert len(iq) == 2
        assert abs(iq[0]) < 0.02                     # centre → ~0
        assert iq[1].real > 0.9 and iq[1].imag < -0.9

    def test_reads_ci16(self, tmp_path):
        # ci16: full-scale 32767 → ~1.0
        raw = np.array([32767, 0, -32768, 16384], dtype="<i2")
        base = self._write_raw(tmp_path, "ci16_le", raw)
        iq, _ = read_iq(base)
        assert len(iq) == 2
        assert abs(iq[0].real - 1.0) < 0.01
        assert abs(iq[1].real + 1.0) < 0.01


# ── annotations ───────────────────────────────────────────────────────────────

class TestAnnotations:
    def test_annotation_round_trip(self, tmp_path):
        ann = [make_annotation(144_000_000, 148_000_000,
                               sample_start=0, sample_count=100, label="2m")]
        write_iq(np.zeros(64, np.complex64), tmp_path / "r",
                 sample_rate=1_000_000, annotations=ann)
        meta = read_meta(tmp_path / "r")
        assert len(meta.annotations) == 1
        assert meta.annotations[0]["core:label"] == "2m"
        assert meta.annotations[0]["core:freq_lower_edge"] == 144_000_000


# ── decode-chain integration ──────────────────────────────────────────────────

class TestDecodeIntegration:
    def test_encode_write_read_decode(self, tmp_path):
        """encoder → write_iq → read_iq → slice_bits → inspect_frame."""
        from core.encoder import encode_iq
        from core.bitslicer import slice_bits, OOK
        from core.framing import inspect_frame

        fs, sps = 48_000.0, 40
        res = encode_iq(b"HI", fs, family=OOK, sync_word="D391",
                        crc="CRC-16/CCITT-FALSE", samples_per_symbol=sps)
        write_iq(res.iq, tmp_path / "cap", sample_rate=fs, center_hz=433_000_000)
        iq, meta = read_iq(tmp_path / "cap")
        assert meta.center_hz == 433_000_000
        got = slice_bits(iq, meta.sample_rate, family=OOK,
                         samples_per_symbol=sps)
        report = inspect_frame(got.bits, sync_word="D391", crc_bits=16)
        assert report.crc_ok is True
        assert report.payload.hex == b"HI".hex()


# ── robustness ────────────────────────────────────────────────────────────────

class TestRobustness:
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_iq(tmp_path / "nope")

    def test_bad_datatype_raises(self, tmp_path):
        base = tmp_path / "bad"
        base.with_suffix(".sigmf-data").write_bytes(b"\x00\x00")
        base.with_suffix(".sigmf-meta").write_text(json.dumps(
            {"global": {"core:datatype": "bogus99"}}))
        with pytest.raises(ValueError):
            read_iq(base)

    def test_empty_iq_writes_and_reads(self, tmp_path):
        write_iq(np.zeros(0, np.complex64), tmp_path / "e",
                 sample_rate=1_000_000)
        iq, _ = read_iq(tmp_path / "e")
        assert len(iq) == 0
