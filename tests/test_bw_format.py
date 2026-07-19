# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""_fmt_bw must round-trip through the same parse logic _bw_hz uses, so a
dragged/typed custom IF bandwidth survives (SDR passband custom-BW fix)."""

import pytest

from ui.tabs.sdr_tab import _fmt_bw


def _parse_like_bw_hz(txt):
    parts = txt.split()
    val = float(parts[0])
    unit = parts[1] if len(parts) > 1 else "Hz"
    if unit == "kHz":
        return int(val * 1_000)
    if unit == "MHz":
        return int(val * 1_000_000)
    return int(val)


@pytest.mark.parametrize("hz", [200, 500, 2700, 3200, 10000, 12500,
                                137400, 200000, 1_500_000])
def test_fmt_bw_round_trips(hz):
    assert _parse_like_bw_hz(_fmt_bw(hz)) == hz


def test_fmt_bw_units():
    assert _fmt_bw(500) == "500 Hz"
    assert _fmt_bw(2700) == "2.7 kHz"
    assert _fmt_bw(200000) == "200 kHz"
    assert _fmt_bw(1_500_000) == "1.5 MHz"
