# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Tests for core/iq_ring.IQRing — rolling raw-IQ buffer that lets a past
waterfall selection be re-extracted (right-click workbench enabler)."""

import numpy as np

from core.iq_ring import IQRing


def _fill(ring, n=10, sr=1_000_000, chunk=1000, dt=0.1):
    for i in range(n):
        ring.add(np.full(chunk, i, np.complex64), sr, 100_000_000, t=i * dt)


def test_add_and_counts():
    r = IQRing(max_seconds=5)
    _fill(r)
    assert r.frame_count == 10
    assert r.span() == (0.0, 0.9)
    assert r.duration_s > 0.9


def test_extract_time_window():
    r = IQRing(max_seconds=5)
    _fill(r)                                   # frames at t=0.0..0.9
    ex = r.extract(0.25, 0.55)                 # frames 3,4,5
    assert ex is not None
    iq, sr, center = ex
    assert len(iq) == 3000 and sr == 1_000_000 and center == 100_000_000
    # the frames carry their index as the value
    assert set(np.unique(iq.real)) == {3.0, 4.0, 5.0}


def test_extract_recent():
    r = IQRing(max_seconds=5)
    _fill(r)
    ex = r.extract_recent(0.25)                # last ~0.25 s → frames 7,8,9
    assert ex is not None
    assert set(np.unique(ex[0].real)) == {7.0, 8.0, 9.0}


def test_prune_by_age():
    r = IQRing(max_seconds=0.35)
    _fill(r, n=10)                             # only the last ~0.35 s survive
    assert r.frame_count <= 5
    lo, hi = r.span()
    assert (hi - lo) <= 0.35 + 1e-9


def test_extract_empty_window_is_none():
    r = IQRing()
    _fill(r)
    assert r.extract(100.0, 200.0) is None
    assert IQRing().extract_recent(1.0) is None


def test_add_safe_on_bad_input():
    r = IQRing()
    r.add(np.zeros(0, np.complex64), 1_000_000, 100_000_000, t=0.0)   # empty
    r.add(np.ones(10, np.complex64), 0, 0, t=0.0)                     # sr<=0
    assert r.frame_count == 0


def test_reset():
    r = IQRing()
    _fill(r)
    r.reset()
    assert r.frame_count == 0 and r.span() is None
