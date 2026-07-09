# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/ctcss.py — CTCSS sub-audible tone detection."""
import numpy as np
import pytest

from core.ctcss import (
    detect_ctcss, goertzel_power, nearest_tone, CTCSS_TONES, CTCSSResult,
)

FS = 8000.0


def _tone(freq, dur=0.5, fs=FS, amp=0.3, noise=0.0, seed=0):
    n = int(dur * fs)
    t = np.arange(n) / fs
    sig = amp * np.sin(2 * np.pi * freq * t)
    if noise:
        sig = sig + noise * np.random.default_rng(seed).standard_normal(n)
    return sig


# ── Goertzel ──────────────────────────────────────────────────────────────────

class TestGoertzel:
    def test_peaks_at_the_tone(self):
        sig = _tone(100.0)
        on = goertzel_power(sig, FS, 100.0)
        off = goertzel_power(sig, FS, 250.3)
        assert on > 50 * off

    def test_empty_zero(self):
        assert goertzel_power([], FS, 100.0) == 0.0


# ── detection ─────────────────────────────────────────────────────────────────

class TestDetect:
    def test_detects_a_standard_tone(self):
        r = detect_ctcss(_tone(103.5), FS)
        assert r is not None
        assert r.tone_hz == 103.5
        assert r.confidence > 0.5

    def test_all_standard_tones_round_trip(self):
        # every standard tone should be identified as itself
        for tone in CTCSS_TONES:
            r = detect_ctcss(_tone(tone, dur=1.0), FS)
            assert r is not None, tone
            assert r.tone_hz == tone, (tone, r.tone_hz)

    def test_survives_voice_energy(self):
        # sub-audible CTCSS under a 900 Hz "voice" tone
        audio = _tone(88.5, amp=0.25) + _tone(900.0, amp=0.8)
        r = detect_ctcss(audio, FS)
        assert r is not None and r.tone_hz == 88.5

    def test_survives_light_noise(self):
        r = detect_ctcss(_tone(131.8, amp=0.3, noise=0.05), FS)
        assert r is not None and r.tone_hz == 131.8

    def test_no_tone_returns_none(self):
        noise = 0.2 * np.random.default_rng(1).standard_normal(int(FS))
        assert detect_ctcss(noise, FS) is None

    def test_silence_returns_none(self):
        assert detect_ctcss(np.zeros(int(FS)), FS) is None

    def test_short_audio_returns_none(self):
        assert detect_ctcss(_tone(100.0, dur=0.01), FS) is None

    def test_dc_offset_does_not_false_trigger(self):
        # a big DC offset must not masquerade as the 67 Hz tone
        audio = 5.0 + _tone(146.2, dur=1.0, amp=0.3)
        r = detect_ctcss(audio, FS)
        assert r is not None and r.tone_hz == 146.2


# ── helpers ───────────────────────────────────────────────────────────────────

class TestHelpers:
    def test_tone_table_size(self):
        assert len(CTCSS_TONES) == 38
        assert CTCSS_TONES[0] == 67.0 and CTCSS_TONES[-1] == 250.3

    def test_nearest_tone(self):
        assert nearest_tone(100.4) == 100.0
        assert nearest_tone(104.0) == 103.5
        assert nearest_tone(1000.0) == 250.3       # clamps to the top tone

    def test_result_dataclass(self):
        r = CTCSSResult(tone_hz=100.0, index=11, confidence=0.9)
        assert r.tone_hz == 100.0 and r.index == 11
