from __future__ import annotations
"""Tests for first_contact_keys() — first QSO per DXCC entity (pure-logic)."""
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.log_db import first_contact_keys


@dataclass
class _Q:
    """Minimal QSO stub — only the fields first_contact_keys() accesses."""
    call: str
    datetime_on: str
    dxcc: str = ""


class TestFirstContactKeys:
    def test_empty_list_returns_empty_frozenset(self):
        assert first_contact_keys([]) == frozenset()

    def test_returns_frozenset_type(self):
        assert isinstance(first_contact_keys([]), frozenset)

    def test_single_qso_with_dxcc_returned(self):
        q = _Q("W1AW", "2024-01-01T12:00:00Z", "United States")
        result = first_contact_keys([q])
        assert ("2024-01-01T12:00:00Z", "W1AW") in result

    def test_single_qso_empty_dxcc_ignored(self):
        q = _Q("W1AW", "2024-01-01T12:00:00Z", "")
        assert first_contact_keys([q]) == frozenset()

    def test_whitespace_dxcc_ignored(self):
        q = _Q("W1AW", "2024-01-01T12:00:00Z", "   ")
        assert first_contact_keys([q]) == frozenset()

    def test_none_dxcc_ignored(self):
        q = _Q("W1AW", "2024-01-01T12:00:00Z")
        q.dxcc = None  # type: ignore
        assert first_contact_keys([q]) == frozenset()

    def test_two_qsos_same_dxcc_only_earliest_key_returned(self):
        q1 = _Q("W1AW", "2024-01-01T12:00:00Z", "United States")
        q2 = _Q("K1ABC", "2024-02-01T12:00:00Z", "United States")
        result = first_contact_keys([q1, q2])
        assert len(result) == 1
        assert ("2024-01-01T12:00:00Z", "W1AW") in result
        assert ("2024-02-01T12:00:00Z", "K1ABC") not in result

    def test_chronological_order_overrides_list_order(self):
        # q1 is listed first but has a later datetime — q2 should win
        q1 = _Q("K1ABC", "2024-02-01T12:00:00Z", "United States")
        q2 = _Q("W1AW", "2024-01-01T12:00:00Z", "United States")
        result = first_contact_keys([q1, q2])
        assert ("2024-01-01T12:00:00Z", "W1AW") in result
        assert ("2024-02-01T12:00:00Z", "K1ABC") not in result

    def test_two_distinct_entities_both_returned(self):
        q1 = _Q("W1AW", "2024-01-01T12:00:00Z", "United States")
        q2 = _Q("JA1XYZ", "2024-01-02T12:00:00Z", "Japan")
        result = first_contact_keys([q1, q2])
        assert len(result) == 2
        assert ("2024-01-01T12:00:00Z", "W1AW") in result
        assert ("2024-01-02T12:00:00Z", "JA1XYZ") in result

    def test_four_distinct_entities_all_returned(self):
        entities = ["Germany", "Japan", "Australia", "Brazil"]
        qsos = [_Q(f"X{i}", f"2024-0{i + 1}-01T00:00:00Z", e)
                for i, e in enumerate(entities)]
        result = first_contact_keys(qsos)
        assert len(result) == 4

    def test_three_contacts_same_entity_only_earliest_in_result(self):
        q1 = _Q("W1AW", "2024-03-01T00:00:00Z", "United States")
        q2 = _Q("K2BC", "2024-01-01T00:00:00Z", "United States")
        q3 = _Q("N3CD", "2024-02-01T00:00:00Z", "United States")
        result = first_contact_keys([q1, q2, q3])
        assert len(result) == 1
        assert ("2024-01-01T00:00:00Z", "K2BC") in result

    def test_key_structure_is_datetime_call_tuple(self):
        q = _Q("JA1XYZ", "2024-06-15T08:30:00Z", "Japan")
        result = first_contact_keys([q])
        key = next(iter(result))
        assert key == ("2024-06-15T08:30:00Z", "JA1XYZ")
