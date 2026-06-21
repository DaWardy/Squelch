"""Tests for core/signal_model.py — the unified Signal record + store (Phase 1)."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _store():
    from core.signal_model import SignalStore
    return SignalStore(":memory:")


def _sig(**kw):
    from core.signal_model import Signal
    return Signal(**kw)


# ── Signal dataclass ───────────────────────────────────────────────────────


class TestSignalDataclass:
    def test_timestamps_autofilled(self):
        s = _sig(freq_hz=144_390_000)
        assert s.first_seen
        assert s.last_seen == s.first_seen

    def test_explicit_timestamps_kept(self):
        s = _sig(freq_hz=1, first_seen="2026-01-01T00:00:00Z",
                 last_seen="2026-01-02T00:00:00Z")
        assert s.first_seen == "2026-01-01T00:00:00Z"
        assert s.last_seen == "2026-01-02T00:00:00Z"

    def test_emitter_id_stripped(self):
        s = _sig(freq_hz=1, emitter_id="  K1ABC  ")
        assert s.emitter_id == "K1ABC"

    def test_defaults(self):
        s = _sig(freq_hz=1)
        assert s.count == 1
        assert s.confidence == 0.0
        assert s.source == ""


# ── add / get round-trip ────────────────────────────────────────────────────


class TestAddGet:
    def test_add_returns_id(self):
        st = _store()
        sid = st.add(_sig(freq_hz=14_074_000, source="ft8"))
        assert sid > 0

    def test_get_roundtrip(self):
        st = _store()
        sid = st.add(_sig(freq_hz=14_074_000, source="ft8",
                          emitter_id="K1ABC", classification="FT8",
                          snr_db=-12.0, decoded="CQ K1ABC FN42"))
        got = st.get(sid)
        assert got is not None
        assert got.freq_hz == 14_074_000
        assert got.emitter_id == "K1ABC"
        assert got.classification == "FT8"
        assert got.snr_db == -12.0
        assert got.decoded == "CQ K1ABC FN42"
        assert got.id == sid

    def test_get_missing_returns_none(self):
        st = _store()
        assert st.get(999) is None

    def test_count_total(self):
        st = _store()
        st.add(_sig(freq_hz=1, source="a"))
        st.add(_sig(freq_hz=2, source="a"))
        assert st.count_total() == 2

    def test_add_always_inserts(self):
        st = _store()
        st.add(_sig(freq_hz=144_390_000, source="aprs", emitter_id="K1ABC"))
        st.add(_sig(freq_hz=144_390_000, source="aprs", emitter_id="K1ABC"))
        assert st.count_total() == 2   # add() never merges


# ── record() merge / correlation ────────────────────────────────────────────


class TestRecordMerge:
    def test_record_inserts_when_no_match(self):
        st = _store()
        st.record(_sig(freq_hz=144_390_000, source="aprs", emitter_id="K1ABC"))
        assert st.count_total() == 1

    def test_record_merges_same_emitter_and_freq(self):
        st = _store()
        sid = st.record(_sig(freq_hz=144_390_000, source="aprs",
                             emitter_id="K1ABC"))
        sid2 = st.record(_sig(freq_hz=144_390_050, source="aprs",
                              emitter_id="K1ABC"))   # within 500 Hz tol
        assert sid == sid2
        assert st.count_total() == 1
        assert st.get(sid).count == 2

    def test_record_advances_last_seen(self):
        st = _store()
        sid = st.record(_sig(freq_hz=1, source="aprs", emitter_id="K1ABC",
                             first_seen="2026-01-01T00:00:00Z",
                             last_seen="2026-01-01T00:00:00Z"))
        st.record(_sig(freq_hz=1, source="aprs", emitter_id="K1ABC",
                       last_seen="2026-06-01T00:00:00Z"))
        got = st.get(sid)
        assert got.last_seen == "2026-06-01T00:00:00Z"

    def test_record_fills_blank_text_fields(self):
        st = _store()
        sid = st.record(_sig(freq_hz=1, source="aprs", emitter_id="K1ABC"))
        st.record(_sig(freq_hz=1, source="aprs", emitter_id="K1ABC",
                       decoded="hello", modulation="FM"))
        got = st.get(sid)
        assert got.decoded == "hello"
        assert got.modulation == "FM"

    def test_record_refreshes_measurements(self):
        st = _store()
        sid = st.record(_sig(freq_hz=1, source="aprs", emitter_id="K1ABC",
                             snr_db=5.0))
        st.record(_sig(freq_hz=1, source="aprs", emitter_id="K1ABC",
                       snr_db=9.0, lat=40.0, lon=-74.0))
        got = st.get(sid)
        assert got.snr_db == 9.0
        assert got.lat == 40.0

    def test_record_no_merge_outside_freq_tol(self):
        st = _store()
        st.record(_sig(freq_hz=144_390_000, source="aprs", emitter_id="K1ABC"))
        st.record(_sig(freq_hz=144_400_000, source="aprs", emitter_id="K1ABC"))
        assert st.count_total() == 2

    def test_record_no_merge_different_source(self):
        st = _store()
        st.record(_sig(freq_hz=1, source="aprs", emitter_id="K1ABC"))
        st.record(_sig(freq_hz=1, source="ft8", emitter_id="K1ABC"))
        assert st.count_total() == 2

    def test_record_merge_by_classification_when_no_emitter(self):
        st = _store()
        sid = st.record(_sig(freq_hz=1, source="sdr", classification="beacon"))
        sid2 = st.record(_sig(freq_hz=1, source="sdr", classification="beacon"))
        assert sid == sid2
        assert st.get(sid).count == 2

    def test_record_no_merge_different_classification(self):
        st = _store()
        st.record(_sig(freq_hz=1, source="sdr", classification="beacon"))
        st.record(_sig(freq_hz=1, source="sdr", classification="pager"))
        assert st.count_total() == 2


# ── search / query ──────────────────────────────────────────────────────────


class TestSearch:
    def _seed(self, st):
        st.add(_sig(freq_hz=144_390_000, source="aprs", emitter_id="K1ABC",
                    classification="APRS", modulation="FM"))
        st.add(_sig(freq_hz=14_074_000, source="ft8", emitter_id="W1AW",
                    classification="FT8", modulation="MFSK"))
        st.add(_sig(freq_hz=446_000_000, source="sdr", classification="unknown"))

    def test_search_by_freq_range(self):
        st = _store(); self._seed(st)
        out = st.search(freq_min=1_000_000, freq_max=30_000_000)
        assert len(out) == 1 and out[0].source == "ft8"

    def test_search_by_source(self):
        st = _store(); self._seed(st)
        assert len(st.search(source="aprs")) == 1

    def test_search_by_emitter(self):
        st = _store(); self._seed(st)
        out = st.search(emitter_id="W1AW")
        assert len(out) == 1 and out[0].freq_hz == 14_074_000

    def test_search_by_modulation(self):
        st = _store(); self._seed(st)
        assert len(st.search(modulation="FM")) == 1

    def test_search_no_filters_returns_all(self):
        st = _store(); self._seed(st)
        assert len(st.search()) == 3

    def test_recent_orders_by_last_seen(self):
        st = _store()
        st.add(_sig(freq_hz=1, source="a", last_seen="2026-01-01T00:00:00Z"))
        st.add(_sig(freq_hz=2, source="b", last_seen="2026-06-01T00:00:00Z"))
        out = st.recent()
        assert out[0].source == "b"   # newest first

    def test_distinct_emitters(self):
        st = _store(); self._seed(st)
        em = st.distinct_emitters()
        assert "K1ABC" in em and "W1AW" in em

    def test_distinct_emitters_by_source(self):
        st = _store(); self._seed(st)
        assert st.distinct_emitters(source="aprs") == ["K1ABC"]


# ── delete / clear ──────────────────────────────────────────────────────────


class TestDeleteClear:
    def test_delete(self):
        st = _store()
        sid = st.add(_sig(freq_hz=1, source="a"))
        assert st.delete(sid) is True
        assert st.get(sid) is None

    def test_delete_missing(self):
        st = _store()
        assert st.delete(123) is False

    def test_clear(self):
        st = _store()
        st.add(_sig(freq_hz=1, source="a"))
        st.add(_sig(freq_hz=2, source="a"))
        st.clear()
        assert st.count_total() == 0


# ── SQL-injection safety (parameterized queries) ────────────────────────────


class TestInjectionSafety:
    def test_malicious_emitter_in_search_is_safe(self):
        st = _store()
        st.add(_sig(freq_hz=1, source="a", emitter_id="K1ABC"))
        # Must not raise or drop the table — treated as a literal value.
        out = st.search(emitter_id="'; DROP TABLE signal;--")
        assert out == []
        assert st.count_total() == 1

    def test_malicious_decoded_payload_roundtrips_literally(self):
        st = _store()
        sid = st.add(_sig(freq_hz=1, source="a",
                          decoded="'); DROP TABLE signal;--"))
        assert st.get(sid).decoded == "'); DROP TABLE signal;--"
        assert st.count_total() == 1
