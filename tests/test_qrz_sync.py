"""Tests for network/qrz_sync.py — QRZ Logbook API integration."""
from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch, call
from network.qrz_sync import QRZSync, QRZSyncResult, _parse_qrz_response


# ── _parse_qrz_response ───────────────────────────────────────────────────────

def test_parse_ok_response():
    result = _parse_qrz_response("status=OK;LOGIDS=1234567")
    assert result["status"] == "OK"
    assert result["logids"] == "1234567"


def test_parse_fail_duplicate():
    result = _parse_qrz_response("status=FAIL;REASON=Duplicate record")
    assert result["status"] == "FAIL"
    assert "duplicate" in result["reason"].lower()


def test_parse_fail_bad_key():
    result = _parse_qrz_response("status=FAIL;REASON=Invalid API Key")
    assert result["status"] == "FAIL"
    assert "invalid" in result["reason"].lower()


def test_parse_empty_response():
    result = _parse_qrz_response("")
    assert result == {}


def test_parse_case_insensitive_keys():
    result = _parse_qrz_response("STATUS=OK;LogIDs=999")
    assert result["status"] == "OK"
    assert result["logids"] == "999"


def test_parse_whitespace_tolerance():
    result = _parse_qrz_response("  status=OK ; LOGIDS=42  ")
    assert result["status"] == "OK"
    assert result["logids"] == "42"


# ── QRZSync._do_upload ────────────────────────────────────────────────────────

def _make_cfg(has_key: bool = True) -> MagicMock:
    cfg = MagicMock()
    cfg.get.return_value = "default"
    return cfg


def _make_qso(call: str = "W1AW", qso_id: int = 1) -> MagicMock:
    q = MagicMock()
    q.call   = call
    q.id     = qso_id
    q.datetime_on = "2026-01-15 12:00:00"
    q.band   = "20m"
    q.freq_hz = 14074000
    q.mode   = "FT8"
    q.submode = ""
    q.rst_sent = "+00"
    q.rst_rcvd = "-05"
    q.name   = ""
    q.grid   = "FN42"
    q.lat    = None
    q.lon    = None
    q.dxcc   = 291
    q.country = "United States"
    q.state  = "CT"
    q.cqz    = 5
    q.ituz   = 8
    q.tx_pwr_w = 100
    q.comment = ""
    q.my_call = "W1AW"
    q.my_grid = "FN42"
    q.adif_extra = ""
    return q


def _make_sync(has_key: bool = True) -> QRZSync:
    sync = QRZSync(_make_cfg())
    if has_key:
        sync._get_api_key = lambda: "TEST_API_KEY_12345"
    else:
        sync._get_api_key = lambda: ""
    return sync


def test_upload_no_api_key():
    sync = _make_sync(has_key=False)
    log_db = MagicMock()
    result = sync._do_upload(log_db, [_make_qso()])
    assert not result.success
    assert "API key" in result.error


def test_upload_ok_single_qso():
    sync = _make_sync()
    log_db = MagicMock()
    qso = _make_qso("K1JT", 42)

    mock_resp = MagicMock()
    mock_resp.text = "status=OK;LOGIDS=9876543"
    mock_resp.raise_for_status.return_value = None

    with patch("network.qrz_sync.record_connection"), \
         patch("requests.post", return_value=mock_resp) as mock_post:
        result = sync._do_upload(log_db, [qso])

    assert result.success
    assert result.uploaded == 1
    assert result.skipped == 0
    assert result.failed == 0
    log_db.mark_qrz_uploaded.assert_called_once_with(42)
    assert "1 uploaded" in result.message


def test_upload_duplicate_treated_as_skipped():
    sync = _make_sync()
    log_db = MagicMock()
    qso = _make_qso("K1JT", 7)

    mock_resp = MagicMock()
    mock_resp.text = "status=FAIL;REASON=Duplicate record"
    mock_resp.raise_for_status.return_value = None

    with patch("network.qrz_sync.record_connection"), \
         patch("requests.post", return_value=mock_resp):
        result = sync._do_upload(log_db, [qso])

    assert result.success
    assert result.skipped == 1
    assert result.uploaded == 0
    assert result.failed == 0
    log_db.mark_qrz_uploaded.assert_called_once_with(7)


def test_upload_real_fail_counts_as_failed():
    sync = _make_sync()
    log_db = MagicMock()
    qso = _make_qso("W1AW", 99)

    mock_resp = MagicMock()
    mock_resp.text = "status=FAIL;REASON=Invalid API Key"
    mock_resp.raise_for_status.return_value = None

    with patch("network.qrz_sync.record_connection"), \
         patch("requests.post", return_value=mock_resp):
        result = sync._do_upload(log_db, [qso])

    assert result.failed == 1
    assert result.uploaded == 0
    log_db.mark_qrz_uploaded.assert_not_called()
    assert "Invalid API Key" in result.error


def test_upload_network_error_counted_as_failed():
    sync = _make_sync()
    log_db = MagicMock()
    qso = _make_qso()

    with patch("network.qrz_sync.record_connection"), \
         patch("requests.post", side_effect=Exception("Connection refused")):
        result = sync._do_upload(log_db, [qso])

    assert result.failed == 1
    log_db.mark_qrz_uploaded.assert_not_called()


def test_upload_mixed_results():
    sync = _make_sync()
    log_db = MagicMock()
    qsos = [_make_qso("W1AW", 1), _make_qso("K1JT", 2), _make_qso("N1RL", 3)]

    responses = [
        MagicMock(text="status=OK;LOGIDS=1", raise_for_status=lambda: None),
        MagicMock(text="status=FAIL;REASON=Duplicate record",
                  raise_for_status=lambda: None),
        MagicMock(text="status=FAIL;REASON=Invalid API Key",
                  raise_for_status=lambda: None),
    ]

    with patch("network.qrz_sync.record_connection"), \
         patch("requests.post", side_effect=responses):
        result = sync._do_upload(log_db, qsos)

    assert result.uploaded == 1
    assert result.skipped == 1
    assert result.failed == 1
    assert log_db.mark_qrz_uploaded.call_count == 2
    assert "1 uploaded" in result.message
    assert "1 already in QRZ" in result.message
    assert "1 failed" in result.message


def test_progress_callbacks_called():
    sync = _make_sync()
    log_db = MagicMock()
    messages = []
    sync.on_progress(lambda msg, pct: messages.append((msg, pct)))

    mock_resp = MagicMock()
    mock_resp.text = "status=OK;LOGIDS=1"
    mock_resp.raise_for_status.return_value = None

    with patch("network.qrz_sync.record_connection"), \
         patch("requests.post", return_value=mock_resp):
        sync._do_upload(log_db, [_make_qso()])

    assert len(messages) >= 2
    final_pct = messages[-1][1]
    assert final_pct == 100


def test_requests_uses_timeout():
    sync = _make_sync()
    log_db = MagicMock()

    mock_resp = MagicMock()
    mock_resp.text = "status=OK;LOGIDS=1"
    mock_resp.raise_for_status.return_value = None

    with patch("network.qrz_sync.record_connection"), \
         patch("requests.post", return_value=mock_resp) as mock_post:
        sync._do_upload(log_db, [_make_qso()])

    _, kwargs = mock_post.call_args
    assert "timeout" in kwargs
    assert kwargs["timeout"] > 0
