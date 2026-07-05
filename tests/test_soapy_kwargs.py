from __future__ import annotations
# Squelch — RF / SDR signal platform
# Licensed under GNU GPL v3 — see LICENSE
"""Regression: SoapySDR enumerate() returns SoapySDRKwargs objects that lack a
.get() method — parsing them crashed enumeration and reported 0 devices even
when a dongle was found. `_kwargs_to_dict` must normalise them robustly."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from sdr.soapy_device import _kwargs_to_dict


class _FakeKwargs:
    """Mimics SoapySDRKwargs: map-like via keys()/[], but NO .get()."""
    def __init__(self, data):
        self._d = dict(data)

    def keys(self):
        return list(self._d.keys())

    def __getitem__(self, k):
        return self._d[k]

    # deliberately no .get() — this is the whole point


class TestKwargsToDict:
    def test_kwargs_without_get_normalised(self):
        kw = _FakeKwargs({"driver": "rtlsdr", "label": "Generic RTL2832U",
                          "serial": "dongle2222"})
        d = _kwargs_to_dict(kw)
        assert d["driver"] == "rtlsdr"
        assert d["label"] == "Generic RTL2832U"
        # the normalised dict supports .get() (the call that used to crash)
        assert d.get("serial") == "dongle2222"
        assert d.get("missing", "x") == "x"

    def test_plain_dict_passthrough(self):
        d = _kwargs_to_dict({"driver": "hackrf"})
        assert d["driver"] == "hackrf"

    def test_values_stringified(self):
        d = _kwargs_to_dict(_FakeKwargs({"index": 0}))
        assert d["index"] == "0"

    def test_garbage_is_safe(self):
        assert _kwargs_to_dict(object()) == {}
        assert _kwargs_to_dict(None) == {}


class TestEnumerateUsesNormaliser:
    def test_enumerate_source_no_longer_calls_get_on_raw(self):
        src = (Path(__file__).parent.parent
               / "sdr/soapy_device.py").read_text(encoding="utf-8")
        # the raw enumerate result must be normalised before .get() is used
        assert "_kwargs_to_dict(raw)" in src
