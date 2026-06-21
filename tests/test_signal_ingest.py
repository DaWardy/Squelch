"""Tests for core/signal_ingest.py — source→Signal converters (SIG-MIGRATE)."""
from __future__ import annotations
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))


def _store():
    from core.signal_model import SignalStore
    return SignalStore(":memory:")


# ── APRS ────────────────────────────────────────────────────────────────────


class TestAprs:
    def test_basic_fields(self):
        from core.signal_ingest import signal_from_aprs, APRS_FREQ_HZ
        pkt = SimpleNamespace(callsign="K1ABC", comment="hello", lat=40.0, lon=-74.0)
        s = signal_from_aprs(pkt)
        assert s.freq_hz == APRS_FREQ_HZ
        assert s.source == "aprs"
        assert s.classification == "APRS"
        assert s.emitter_id == "K1ABC"
        assert s.decoded == "hello"
        assert s.lat == 40.0 and s.lon == -74.0

    def test_missing_fields_safe(self):
        from core.signal_ingest import signal_from_aprs
        s = signal_from_aprs(SimpleNamespace())
        assert s.source == "aprs"
        assert s.emitter_id == ""
        assert s.lat == 0.0

    def test_comment_truncated(self):
        from core.signal_ingest import signal_from_aprs
        pkt = SimpleNamespace(callsign="K1ABC", comment="x" * 500, lat=0, lon=0)
        assert len(signal_from_aprs(pkt).decoded) == 200


# ── FT8 ──────────────────────────────────────────────────────────────────────


class TestFt8:
    def test_basic_fields(self):
        from core.signal_ingest import signal_from_ft8
        dec = SimpleNamespace(freq_hz=14_074_000, snr=-12, callsign="W1AW",
                              grid="", message="CQ W1AW FN31", dxcc="USA")
        s = signal_from_ft8(dec)
        assert s.freq_hz == 14_074_000
        assert s.source == "ft8"
        assert s.modulation == "MFSK"
        assert s.emitter_id == "W1AW"
        assert s.snr_db == -12.0
        assert s.decoded == "CQ W1AW FN31"
        assert s.tags == "USA"

    def test_grid_resolves_to_coords(self):
        from core.signal_ingest import signal_from_ft8
        dec = SimpleNamespace(freq_hz=1, snr=0, callsign="W1AW",
                              grid="FN31", message="", dxcc="")
        s = signal_from_ft8(dec)
        # FN31 is in the NE US — lat positive, lon negative
        assert s.lat != 0.0 or s.lon != 0.0

    def test_missing_fields_safe(self):
        from core.signal_ingest import signal_from_ft8
        s = signal_from_ft8(SimpleNamespace(freq_hz=0, snr=0, message=""))
        assert s.source == "ft8"
        assert s.emitter_id == ""


# ── WSPR ─────────────────────────────────────────────────────────────────────


class TestWspr:
    def test_basic_fields(self):
        from core.signal_ingest import signal_from_wspr
        spot = SimpleNamespace(freq_hz=14_097_000, snr=-20, callsign="W1AW",
                               grid="FN31", power_dbm=37)
        s = signal_from_wspr(spot)
        assert s.source == "wspr"
        assert s.classification == "WSPR"
        assert s.emitter_id == "W1AW"
        assert "37dBm" in s.decoded
        assert "FN31" in s.decoded


# ── DX cluster / RBN ─────────────────────────────────────────────────────────


class TestDxSpot:
    def test_basic_fields(self):
        from core.signal_ingest import signal_from_dx_spot
        spot = SimpleNamespace(callsign="P5DX", freq_hz=14_005_000, snr=15,
                               mode="CW", comment="up 2", country="N Korea",
                               source="dxcluster")
        s = signal_from_dx_spot(spot)
        assert s.freq_hz == 14_005_000
        assert s.source == "dxcluster"
        assert s.classification == "CW"
        assert s.emitter_id == "P5DX"
        assert s.tags == "N Korea"

    def test_source_defaults_when_blank(self):
        from core.signal_ingest import signal_from_dx_spot
        spot = SimpleNamespace(callsign="X", freq_hz=1, source="")
        assert signal_from_dx_spot(spot).source == "dxcluster"

    def test_classification_defaults_to_dx(self):
        from core.signal_ingest import signal_from_dx_spot
        spot = SimpleNamespace(callsign="X", freq_hz=1, mode="")
        assert signal_from_dx_spot(spot).classification == "DX"

    def test_cluster_spot_shape_dxcall_freqkhz(self):
        # The modes_tab DX cluster uses .dx_call and .freq_khz
        from core.signal_ingest import signal_from_dx_spot
        spot = SimpleNamespace(dx_call="JA1XYZ", freq_khz=14025.0,
                               spotter="K1ABC", comment="loud", mode="CW")
        s = signal_from_dx_spot(spot)
        assert s.emitter_id == "JA1XYZ"
        assert s.freq_hz == 14_025_000
        assert s.classification == "CW"


# ── SDR bookmark ─────────────────────────────────────────────────────────────


class TestBookmark:
    def test_freq_hz_key(self):
        from core.signal_ingest import signal_from_bookmark
        s = signal_from_bookmark({"freq_hz": 462_562_500, "name": "FRS 1"})
        assert s.freq_hz == 462_562_500
        assert s.classification == "FRS 1"
        assert s.source == "sdr"

    def test_freq_mhz_key(self):
        from core.signal_ingest import signal_from_bookmark
        s = signal_from_bookmark({"freq_mhz": 446.0, "label": "PMR"})
        assert s.freq_hz == 446_000_000
        assert s.classification == "PMR"

    def test_defaults(self):
        from core.signal_ingest import signal_from_bookmark
        s = signal_from_bookmark({"freq_hz": 100})
        assert s.classification == "bookmark"


# ── ingest() into a store ────────────────────────────────────────────────────


class TestIngest:
    def test_ingest_records(self):
        from core.signal_ingest import ingest, signal_from_aprs
        st = _store()
        pkt = SimpleNamespace(callsign="K1ABC", comment="hi", lat=0, lon=0)
        sid = ingest(signal_from_aprs(pkt), store=st)
        assert sid > 0
        assert st.count_total() == 1

    def test_ingest_merges_repeat_emitter(self):
        from core.signal_ingest import ingest, signal_from_aprs
        st = _store()
        for _ in range(3):
            pkt = SimpleNamespace(callsign="K1ABC", comment="hi", lat=0, lon=0)
            ingest(signal_from_aprs(pkt), store=st)
        assert st.count_total() == 1          # merged by emitter+freq
        assert st.recent()[0].count == 3

    def test_ingest_distinct_emitters_separate(self):
        from core.signal_ingest import ingest, signal_from_aprs
        st = _store()
        for call in ("K1ABC", "W1AW", "N0CALL"):
            pkt = SimpleNamespace(callsign=call, comment="", lat=0, lon=0)
            ingest(signal_from_aprs(pkt), store=st)
        assert st.count_total() == 3

    def test_ingest_never_raises_on_bad_input(self):
        from core.signal_ingest import ingest
        # Passing a non-Signal should be swallowed, returning 0
        assert ingest(object(), store=_store()) == 0
