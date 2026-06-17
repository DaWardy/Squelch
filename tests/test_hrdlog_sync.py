"""Tests for network/hrdlog_sync.py — HRDLog.net logbook upload."""
from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch


from network.hrdlog_sync import HRDLogSync, HRDLogResult, HRDLOG_UPLOAD_URL


# ── Credential / config helpers ───────────────────────────────────────────────

class _FakeCfg:
    def __init__(self, callsign="W1AW", apikey="testkey123"):
        self._callsign = callsign
        self._apikey   = apikey

    def get(self, key, default=None):
        if key == "apis.hrdlog_callsign":
            return self._callsign
        if key == "profile.name":
            return "default"
        return default


def _make_sync(callsign="W1AW", apikey="testkey123"):
    cfg = _FakeCfg(callsign=callsign, apikey=apikey)
    sync = HRDLogSync(cfg)
    store = MagicMock()
    store.retrieve.return_value = apikey
    with patch("network.hrdlog_sync.record_connection"):
        pass  # just verifying patch target exists
    return sync, store


def _make_log_db(count=5, adif="<CALL:4>W1AW<EOR>"):
    db = MagicMock()
    db.total_qsos.return_value = count
    tmp_path_holder = []

    def fake_export(path):
        path.write_text(adif, encoding="utf-8")
        tmp_path_holder.append(path)
        return count

    db.export_adif.side_effect = fake_export
    return db


# ── Credential checks ─────────────────────────────────────────────────────────

def test_missing_callsign_returns_error():
    cfg = _FakeCfg(callsign="")
    sync = HRDLogSync(cfg)
    with patch("network.hrdlog_sync.record_connection"), \
         patch("core.credentials.get_store") as mock_store:
        mock_store.return_value.retrieve.return_value = "key123"
        result = sync._do_upload(_make_log_db())
    assert not result.success
    assert "callsign" in result.error.lower()


def test_missing_apikey_returns_error():
    cfg = _FakeCfg(apikey="")
    sync = HRDLogSync(cfg)
    with patch("network.hrdlog_sync.record_connection"), \
         patch("core.credentials.get_store") as mock_store:
        mock_store.return_value.retrieve.return_value = ""
        result = sync._do_upload(_make_log_db())
    assert not result.success
    assert "api key" in result.error.lower() or "settings" in result.error.lower()


# ── Successful upload ─────────────────────────────────────────────────────────

def test_upload_ok_response():
    sync = HRDLogSync(_FakeCfg())
    db = _make_log_db(count=3)

    with patch("core.credentials.get_store") as mock_store, \
         patch("network.hrdlog_sync.record_connection"), \
         patch("requests.post") as mock_post:
        mock_store.return_value.retrieve.return_value = "apikey123"
        mock_resp = MagicMock()
        mock_resp.text = "OK"
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = sync._do_upload(db)

    assert result.success
    assert "3" in result.message
    assert "HRDLog" in result.message


def test_upload_posts_to_correct_url():
    sync = HRDLogSync(_FakeCfg())
    db = _make_log_db()

    with patch("core.credentials.get_store") as mock_store, \
         patch("network.hrdlog_sync.record_connection"), \
         patch("requests.post") as mock_post:
        mock_store.return_value.retrieve.return_value = "key"
        mock_resp = MagicMock()
        mock_resp.text = "OK"
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        sync._do_upload(db)

    call_kwargs = mock_post.call_args
    assert HRDLOG_UPLOAD_URL in str(call_kwargs)


def test_upload_includes_callsign_and_key():
    sync = HRDLogSync(_FakeCfg(callsign="K5XYZ", apikey="secret99"))
    db = _make_log_db()

    with patch("core.credentials.get_store") as mock_store, \
         patch("network.hrdlog_sync.record_connection"), \
         patch("requests.post") as mock_post:
        mock_store.return_value.retrieve.return_value = "secret99"
        mock_resp = MagicMock()
        mock_resp.text = "OK"
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        sync._do_upload(db)

    data = mock_post.call_args.kwargs.get("data") or mock_post.call_args[1].get("data", {})
    assert data.get("Callsign") == "K5XYZ"
    assert data.get("Apikey") == "secret99"


def test_upload_uses_timeout():
    sync = HRDLogSync(_FakeCfg())
    db = _make_log_db()

    with patch("core.credentials.get_store") as mock_store, \
         patch("network.hrdlog_sync.record_connection"), \
         patch("requests.post") as mock_post:
        mock_store.return_value.retrieve.return_value = "key"
        mock_resp = MagicMock()
        mock_resp.text = "OK"
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        sync._do_upload(db)

    kwargs = mock_post.call_args.kwargs or mock_post.call_args[1]
    assert "timeout" in kwargs and kwargs["timeout"] > 0


# ── Error cases ───────────────────────────────────────────────────────────────

def test_server_returns_error_text():
    sync = HRDLogSync(_FakeCfg())
    db = _make_log_db()

    with patch("core.credentials.get_store") as mock_store, \
         patch("network.hrdlog_sync.record_connection"), \
         patch("requests.post") as mock_post:
        mock_store.return_value.retrieve.return_value = "key"
        mock_resp = MagicMock()
        mock_resp.text = "Error: Invalid API key"
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = sync._do_upload(db)

    assert not result.success
    assert "Invalid API key" in result.error


def test_network_error_returns_failure():
    sync = HRDLogSync(_FakeCfg())
    db = _make_log_db()

    with patch("core.credentials.get_store") as mock_store, \
         patch("network.hrdlog_sync.record_connection"), \
         patch("requests.post", side_effect=ConnectionError("timeout")):
        mock_store.return_value.retrieve.return_value = "key"
        result = sync._do_upload(db)

    assert not result.success
    assert "Network error" in result.error


def test_empty_log_returns_success_with_no_qso_message():
    sync = HRDLogSync(_FakeCfg())
    db = MagicMock()
    db.total_qsos.return_value = 0

    def _empty_export(path):
        path.write_text("", encoding="utf-8")
        return 0

    db.export_adif.side_effect = _empty_export

    with patch("core.credentials.get_store") as mock_store, \
         patch("network.hrdlog_sync.record_connection"):
        mock_store.return_value.retrieve.return_value = "key"
        result = sync._do_upload(db)

    assert result.success
    assert "No QSOs" in result.message


# ── Progress callbacks ────────────────────────────────────────────────────────

def test_progress_callback_fired():
    sync = HRDLogSync(_FakeCfg())
    progress_calls = []
    sync.on_progress(lambda msg, pct: progress_calls.append((msg, pct)))

    db = _make_log_db(count=2)

    with patch("core.credentials.get_store") as mock_store, \
         patch("network.hrdlog_sync.record_connection"), \
         patch("requests.post") as mock_post:
        mock_store.return_value.retrieve.return_value = "key"
        mock_resp = MagicMock()
        mock_resp.text = "OK"
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        sync._do_upload(db)

    assert len(progress_calls) >= 2
    final_pct = max(pct for _, pct in progress_calls)
    assert final_pct == 100


def test_complete_callback_fired():
    sync = HRDLogSync(_FakeCfg())
    done = []
    sync.on_complete(lambda r: done.append(r))

    db = _make_log_db()

    with patch("core.credentials.get_store") as mock_store, \
         patch("network.hrdlog_sync.record_connection"), \
         patch("requests.post") as mock_post:
        mock_store.return_value.retrieve.return_value = "key"
        mock_resp = MagicMock()
        mock_resp.text = "OK"
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        sync._upload_worker(db)

    assert len(done) == 1
    assert done[0].success


# ── C-12 compliance ───────────────────────────────────────────────────────────

def test_record_connection_called():
    """C-12: all outbound calls must be logged via core.netlog.record_connection."""
    sync = HRDLogSync(_FakeCfg())
    db = _make_log_db()

    with patch("core.credentials.get_store") as mock_store, \
         patch("network.hrdlog_sync.record_connection") as mock_log, \
         patch("requests.post") as mock_post:
        mock_store.return_value.retrieve.return_value = "key"
        mock_resp = MagicMock()
        mock_resp.text = "OK"
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        sync._do_upload(db)

    mock_log.assert_called_once()
    args = mock_log.call_args[0]
    assert HRDLOG_UPLOAD_URL in args or HRDLOG_UPLOAD_URL in str(mock_log.call_args)
