# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""End-to-end integration test for the founding "hound" pipeline.

One flow exercises seven cores together — a guard against cross-module API
drift that per-module tests can't catch:

    spectrum frame → SurveyEngine (occupancy detect + SOI/SNOI filter)
        → signal_ingest → SignalStore
        → emitter_correlate (group recorded signals into emitters)
        → rf_baseline snapshot + compare (surface an anomaly)

The other founding half — the decode round-trip — is exercised separately
below (encode → slice → frame).
"""
import pytest

from core.live_analysis import SurveyEngine
from core.signal_model import SignalStore
from core.soi_snoi import WatchList, SNOI
from core.emitter_correlate import correlate_from_store

CENTER = 100_000_000
RATE = 2_048_000
NBINS = 1024


def _frame(peak_bins, floor=-100.0, peak=-40.0, n=NBINS, width=3):
    p = [floor] * n
    half = width // 2
    for b in peak_bins:
        for i in range(b - half, b + half + 1):
            if 0 <= i < n:
                p[i] = peak
    return p


def _bin_freq(b, center=CENTER, rate=RATE, n=NBINS):
    return int((center - rate // 2) + b * (rate / n))


# ── the hound pipeline ────────────────────────────────────────────────────────

class TestHoundPipeline:
    def test_survey_to_store_to_emitters_to_anomaly(self):
        store = SignalStore(":memory:")

        # SNOI: ignore whatever sits at bin 200
        wl = WatchList()
        f_snoi = _bin_freq(200)
        wl.add_range(f_snoi - 20_000, f_snoi + 20_000, SNOI, "ignore band")

        eng = SurveyEngine(store=store, watchlist=wl)

        # sweep frame: a real signal at bin 600 and an SNOI signal at bin 200
        dets = eng.offer_frame(_frame([200, 600]), CENTER, RATE)

        # SNOI is silently dropped; only the real signal surfaces + is recorded
        assert len(dets) == 1
        assert store.count_total() == 1
        recorded = store.recent()[0]
        assert recorded.source == "survey"
        assert abs(recorded.freq_hz - _bin_freq(600)) < 5_000

        # correlate the recorded survey signals into emitters
        emitters = correlate_from_store(store)
        assert len(emitters) == 1
        assert emitters[0].n_signals == 1

        # snapshot a baseline, then a NEW emitter appears → compare flags it
        reference = eng.snapshot("baseline")
        eng.reset()
        eng.offer_frame(_frame([600, 800]), CENTER, RATE)   # 800 is new
        diff = eng.compare_to(reference)
        assert diff is not None
        assert diff.anomaly_count == 1
        assert abs(diff.new[0].center_hz - _bin_freq(800)) < 5_000

    def test_repeat_observations_merge_then_correlate(self):
        """Repeat hits on the same channel merge in the store, and the emitter
        reflects the higher observation count."""
        store = SignalStore(":memory:")
        eng = SurveyEngine(store=store)
        for _ in range(3):
            eng.offer_frame(_frame([600]), CENTER, RATE)
        # merged into one row (same source+class+freq), count bumped
        rows = store.recent()
        assert len(rows) == 1
        assert rows[0].count == 3
        emitters = correlate_from_store(store)
        assert emitters[0].n_observations == 3


# ── the decode round-trip half ────────────────────────────────────────────────

class TestDecodePipeline:
    def test_encode_slice_frame_round_trip(self):
        """encode_iq → slice_bits → inspect_frame recovers the payload + CRC."""
        from core.encoder import encode_iq
        from core.bitslicer import slice_bits, OOK
        from core.framing import inspect_frame

        fs, sps = 48_000.0, 40
        res = encode_iq(b"HI", fs, family=OOK, sync_word="D391",
                        crc="CRC-16/CCITT-FALSE", samples_per_symbol=sps)
        got = slice_bits(res.iq, fs, family=OOK, samples_per_symbol=sps)
        report = inspect_frame(got.bits, sync_word="D391", crc_bits=16)
        assert report.crc_ok is True
        assert report.payload.hex == b"HI".hex()

    def test_manchester_line_coding_chain(self):
        """A Manchester-coded frame: encode → slice → line-decode → frame."""
        from core.linecoding import encode_manchester, decode_manchester
        from core.framing import inspect_frame, compute_crc
        from core.bitslicer import bits_to_bytes, slice_bits, OOK
        from core.encoder import modulate

        def _i2b(v, w):
            return [(v >> i) & 1 for i in range(w - 1, -1, -1)]

        payload = [1, 0, 1, 1, 0, 0, 1, 0]
        crc = _i2b(compute_crc(bits_to_bytes(payload), "CRC-8"), 8)
        frame = payload + crc
        chips = encode_manchester(frame)                 # line-code the frame
        iq = modulate(chips, 48_000.0, family=OOK, samples_per_symbol=20)
        chips_rx = slice_bits(iq, 48_000.0, family=OOK,
                              samples_per_symbol=20).bits
        bits = decode_manchester(chips_rx).bits          # line-decode
        assert bits == frame
        report = inspect_frame(bits, crc_bits=8)
        assert report.crc_ok is True
