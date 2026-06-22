"""Tests for core/dsp_nb.py — IQ impulse noise blanker.

Needs numpy (array DSP); skips when numpy is absent from the runner.
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

np = pytest.importorskip("numpy")


def _signal(n=1024, amp=1.0):
    # Steady complex tone — uniform magnitude ~amp.
    t = np.arange(n)
    return (amp * np.exp(1j * 2 * np.pi * 0.05 * t)).astype(np.complex64)


class TestNoiseBlank:
    def test_clamps_impulse(self):
        from core.dsp_nb import noise_blank
        iq = _signal()
        iq[100] = 50.0 + 0j           # huge impulse
        out = noise_blank(iq, strength=0.5)
        assert abs(out[100]) < abs(iq[100])         # impulse reduced
        assert abs(out[100]) <= np.median(np.abs(iq)) * 10 + 1e-3

    def test_preserves_clean_samples(self):
        from core.dsp_nb import noise_blank
        iq = _signal()
        iq[100] = 50.0
        out = noise_blank(iq, strength=0.5)
        # A non-impulsive sample is unchanged
        assert np.isclose(out[200], iq[200])

    def test_preserves_phase_of_clamped(self):
        from core.dsp_nb import noise_blank
        iq = _signal()
        iq[100] = 50.0 * np.exp(1j * 1.0)    # impulse with a specific phase
        out = noise_blank(iq, strength=0.5)
        assert np.isclose(np.angle(out[100]), 1.0, atol=1e-3)

    def test_stronger_clamps_more_aggressively(self):
        from core.dsp_nb import noise_blank
        iq = _signal()
        iq[100] = 8.0                 # moderate spike (~8x median)
        gentle = noise_blank(iq, strength=0.0)   # factor 10 → not clamped
        aggr   = noise_blank(iq, strength=1.0)   # factor 2  → clamped
        assert abs(aggr[100]) < abs(gentle[100])

    def test_flat_signal_unchanged(self):
        from core.dsp_nb import noise_blank
        iq = _signal()
        out = noise_blank(iq, strength=0.5)
        assert np.allclose(out, iq)

    def test_empty_safe(self):
        from core.dsp_nb import noise_blank
        out = noise_blank(np.array([], dtype=np.complex64))
        assert out.size == 0

    def test_none_safe(self):
        from core.dsp_nb import noise_blank
        assert noise_blank(None) is None

    def test_zero_median_safe(self):
        from core.dsp_nb import noise_blank
        iq = np.zeros(64, dtype=np.complex64)
        iq[0] = 5.0
        out = noise_blank(iq, strength=0.5)   # median 0 → unchanged
        assert np.allclose(out, iq)

    def test_returns_copy_not_mutate(self):
        from core.dsp_nb import noise_blank
        iq = _signal()
        iq[100] = 50.0
        orig = iq.copy()
        _ = noise_blank(iq, strength=0.8)
        assert np.allclose(iq, orig)          # input not mutated

    def test_strength_clamped(self):
        from core.dsp_nb import noise_blank
        iq = _signal(); iq[10] = 50.0
        # out-of-range strengths must not raise
        noise_blank(iq, strength=5.0)
        noise_blank(iq, strength=-3.0)


class TestImpulseCount:
    def test_counts_impulses(self):
        from core.dsp_nb import impulse_count
        iq = _signal()
        iq[100] = iq[200] = 50.0
        assert impulse_count(iq, strength=0.5) == 2

    def test_flat_zero(self):
        from core.dsp_nb import impulse_count
        assert impulse_count(_signal(), strength=0.5) == 0

    def test_empty_zero(self):
        from core.dsp_nb import impulse_count
        assert impulse_count(np.array([], dtype=np.complex64)) == 0
