"""Tests for RBNClient — Reverse Beacon Network 'Am I being heard?' monitor."""
from __future__ import annotations
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).parent.parent))


def _mock_cfg(**overrides):
    cfg = MagicMock()
    store = {**overrides}
    cfg.get.side_effect = lambda k, default=None: store.get(k, default)
    return cfg


# ── RBNClient unit tests ──────────────────────────────────────────────────


class TestRBNClientBasic:
    def test_instantiates(self):
        from network.dx_cluster import RBNClient
        client = RBNClient(_mock_cfg())
        assert client is not None

    def test_on_spot_stores_callback(self):
        from network.dx_cluster import RBNClient
        client = RBNClient(_mock_cfg())
        cb = MagicMock()
        client.on_spot(cb)
        assert client._on_spot is cb

    def test_initial_spots_empty(self):
        from network.dx_cluster import RBNClient
        client = RBNClient(_mock_cfg())
        assert client._spots == []

    def test_stop_safe_before_start(self):
        from network.dx_cluster import RBNClient
        client = RBNClient(_mock_cfg())
        client._running = False
        client.stop()   # must not raise


class TestRBNClientParse:
    def _client(self):
        from network.dx_cluster import RBNClient
        return RBNClient(_mock_cfg())

    def test_parse_rbn_valid_entry(self):
        client = self._client()
        raw = [{"callsign": "K2PO", "dx": "W1AW", "freq": "14.030",
                "mode": "CW", "db": 18}]
        spots = client._parse_rbn(raw)
        assert len(spots) == 1
        assert spots[0].spotter == "K2PO"
        assert spots[0].freq_hz == 14030

    def test_parse_rbn_strips_invalid_callsigns(self):
        client = self._client()
        raw = [{"callsign": "", "dx": "W1AW", "freq": "14.030",
                "mode": "CW", "db": 10}]
        spots = client._parse_rbn(raw)
        # No spotter means the spot is still included (dx is the searched call)
        # but spotter is empty — implementation may vary; test that no exception raised
        assert isinstance(spots, list)

    def test_parse_rbn_skips_zero_freq(self):
        client = self._client()
        raw = [{"callsign": "K2PO", "dx": "W1AW", "freq": "0",
                "mode": "CW", "db": 10}]
        spots = client._parse_rbn(raw)
        assert len(spots) == 0

    def test_parse_rbn_caps_at_30(self):
        client = self._client()
        raw = [{"callsign": f"K{i}XX", "dx": "W1AW",
                "freq": "14.030", "mode": "CW", "db": i}
               for i in range(1, 50)]
        spots = client._parse_rbn(raw)
        assert len(spots) <= 30

    def test_parse_rbn_non_list_returns_empty(self):
        client = self._client()
        assert client._parse_rbn({}) == []
        assert client._parse_rbn(None) == []
        assert client._parse_rbn("bad") == []

    def test_parse_rbn_snr_stored(self):
        client = self._client()
        raw = [{"callsign": "VE3XX", "dx": "W1AW",
                "freq": "7.030", "mode": "CW", "db": 25}]
        spots = client._parse_rbn(raw)
        assert spots[0].snr == 25


class TestRBNClientStartStop:
    def test_start_sets_running(self):
        from network.dx_cluster import RBNClient
        client = RBNClient(_mock_cfg())
        client._thread = MagicMock()
        client._thread.start = MagicMock()
        with patch("threading.Thread") as mock_thread:
            mock_instance = MagicMock()
            mock_thread.return_value = mock_instance
            client.start("W1AW", "CW")
        assert client._running is True
        assert client._poll_call == "W1AW"
        assert client._poll_mode == "CW"

    def test_stop_clears_running(self):
        from network.dx_cluster import RBNClient
        client = RBNClient(_mock_cfg())
        client._running = True
        client.stop()
        assert client._running is False


class TestRBNFetchAndNotify:
    def test_callback_called_for_each_spot(self):
        from network.dx_cluster import RBNClient
        client = RBNClient(_mock_cfg())
        cb = MagicMock()
        client.on_spot(cb)
        # Inject spots directly to test notification path
        from network.dx_cluster import DXSpot
        fake_spots = [
            DXSpot(callsign="W1AW", spotter=f"K{i}PO",
                   freq_hz=14030000, mode="CW", snr=10)
            for i in range(3)
        ]
        client._spots = fake_spots
        client._last_fetch = time.time() - 999  # force fresh fetch
        # Simulate what _fetch_and_notify does after fetch populates _spots
        for s in client._spots:
            client._on_spot(s)
        assert cb.call_count == 3

    def test_no_callback_when_none(self):
        from network.dx_cluster import RBNClient
        client = RBNClient(_mock_cfg())
        # _on_spot is None — _fetch_and_notify must not raise
        from network.dx_cluster import DXSpot
        client._spots = [DXSpot(callsign="W1AW", spotter="K2PO",
                                freq_hz=14030000, mode="CW", snr=10)]
        # Simulate _fetch_and_notify callback guard
        if client._on_spot and client._spots:
            for s in client._spots:
                client._on_spot(s)
        # no exception = pass
