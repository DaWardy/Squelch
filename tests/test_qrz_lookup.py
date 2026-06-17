from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for network/qrz_lookup.py.

Pure-logic tests run without PyQt6 or network access.
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_lookup():
    """Return a CallsignLookup with a dummy config and no-op store."""
    from network.qrz_lookup import CallsignLookup
    cfg = MagicMock()
    cfg.get.side_effect = lambda key, default="": {
        "apis.qrz_user": "",
        "apis.hamqth_user": "",
        "profile.name": "default",
    }.get(key, default)

    lookup = CallsignLookup(cfg)
    # Inject a store that returns empty strings (no credentials)
    lookup._get_store = lambda: MagicMock(retrieve=lambda k: "")
    return lookup


def _make_lookup_with_creds(qrz_user="W1AW", qrz_pw="secret"):
    """Return a lookup pre-configured with QRZ credentials."""
    from network.qrz_lookup import CallsignLookup
    cfg = MagicMock()
    cfg.get.side_effect = lambda key, default="": {
        "apis.qrz_user": qrz_user,
        "profile.name": "default",
    }.get(key, default)

    store_mock = MagicMock()
    store_mock.retrieve.side_effect = lambda k: qrz_pw if k == "qrz_password" else ""

    lookup = CallsignLookup(cfg)
    lookup._get_store = lambda: store_mock
    return lookup


_QRZ_LOGIN_XML = """<?xml version="1.0" encoding="utf-8" ?>
<QRZDatabase version="1.33" xmlns="urn:xmethods-XCallsign">
  <Session><Key>abc123</Key></Session>
</QRZDatabase>"""

_QRZ_CALL_XML = """<?xml version="1.0" encoding="utf-8" ?>
<QRZDatabase version="1.33" xmlns="urn:xmethods-XCallsign">
  <Callsign>
    <call>W1AW</call>
    <fname>Hiram Percy</fname>
    <name>Maxim</name>
    <country>United States</country>
    <dxcc>291</dxcc>
    <grid>FN31pr</grid>
    <state>CT</state>
    <cqzone>5</cqzone>
    <ituzone>8</ituzone>
    <lat>41.714775</lat>
    <lon>-72.727260</lon>
    <class>E</class>
    <qslmgr>ARRL</qslmgr>
  </Callsign>
</QRZDatabase>"""

_HAMQTH_SESSION_XML = """<?xml version="1.0"?>
<HamQTH version="2.7" xmlns="https://www.hamqth.com">
  <session><session_id>hamqth_tok</session_id></session>
</HamQTH>"""

_HAMQTH_CALL_XML = """<?xml version="1.0"?>
<HamQTH version="2.7" xmlns="https://www.hamqth.com">
  <search>
    <callsign>W1AW</callsign>
    <adr_name>Hiram Percy Maxim</adr_name>
    <country>United States</country>
    <grid>FN31pr</grid>
    <us_state>CT</us_state>
    <cq_zone>5</cq_zone>
    <itu_zone>8</itu_zone>
    <latitude>41.714775</latitude>
    <longitude>-72.727260</longitude>
  </search>
</HamQTH>"""


# ---------------------------------------------------------------------------
# Pure-logic tests — no network, no Qt
# ---------------------------------------------------------------------------

class TestCallsignInfo:

    def test_fields_exist(self):
        from network.qrz_lookup import CallsignInfo
        info = CallsignInfo(callsign="W1AW", name="Hiram", country="USA", grid="FN31pr")
        assert info.callsign == "W1AW"
        assert info.name == "Hiram"
        assert info.grid == "FN31pr"

    def test_is_fresh_default(self):
        from network.qrz_lookup import CallsignInfo
        info = CallsignInfo(callsign="W1AW")
        assert info.is_fresh

    def test_is_stale_after_ttl(self):
        from network.qrz_lookup import CallsignInfo, CACHE_TTL
        info = CallsignInfo(callsign="W1AW", fetched_at=time.time() - CACHE_TTL - 1)
        assert not info.is_fresh

    def test_display_name_fallback(self):
        from network.qrz_lookup import CallsignInfo
        info = CallsignInfo(callsign="W1AW")
        assert info.display_name == "W1AW"

    def test_display_name_from_name(self):
        from network.qrz_lookup import CallsignInfo
        info = CallsignInfo(callsign="W1AW", name="Hiram")
        assert info.display_name == "Hiram"


class TestCallsignLookupNoCredentials:

    def test_no_credentials_returns_none(self):
        """Without QRZ or HamQTH credentials, lookup returns None silently."""
        lookup = _make_lookup()
        result = lookup.lookup("W1AW")
        assert result is None

    def test_empty_callsign_returns_none(self):
        lookup = _make_lookup()
        result = lookup.lookup("")
        assert result is None

    def test_clear_cache(self):
        from network.qrz_lookup import CallsignInfo
        lookup = _make_lookup()
        lookup._cache["W1AW"] = CallsignInfo(callsign="W1AW")
        lookup._session_key = "tok"
        lookup.clear_cache()
        assert lookup._cache == {}
        assert lookup._session_key is None


class TestQRZXMLParse:

    def test_login_success(self):
        lookup = _make_lookup_with_creds()
        mock_resp = MagicMock()
        mock_resp.text = _QRZ_LOGIN_XML
        mock_resp.content = _QRZ_LOGIN_XML.encode()
        with patch("requests.get", return_value=mock_resp) as mock_get:
            with patch("network.qrz_lookup.record_connection"):
                key = lookup._qrz_login()
        assert key == "abc123"

    def test_login_calls_record_connection(self):
        lookup = _make_lookup_with_creds()
        mock_resp = MagicMock()
        mock_resp.text = _QRZ_LOGIN_XML
        mock_resp.content = _QRZ_LOGIN_XML.encode()
        with patch("requests.get", return_value=mock_resp):
            with patch("network.qrz_lookup.record_connection") as mock_log:
                lookup._qrz_login()
        mock_log.assert_called()

    def test_qrz_xml_parse_callsign(self):
        lookup = _make_lookup_with_creds()
        lookup._session_key = "abc123"
        mock_resp = MagicMock()
        mock_resp.text = _QRZ_CALL_XML
        mock_resp.content = _QRZ_CALL_XML.encode()
        with patch("requests.get", return_value=mock_resp):
            with patch("network.qrz_lookup.record_connection"):
                info = lookup._lookup_qrz("W1AW")
        assert info is not None
        assert info.name == "Hiram Percy Maxim"
        assert info.grid == "FN31pr"
        assert info.country == "United States"
        assert info.cq_zone == 5
        assert info.source == "qrz"

    def test_lookup_qrz_calls_record_connection(self):
        lookup = _make_lookup_with_creds()
        lookup._session_key = "abc123"
        mock_resp = MagicMock()
        mock_resp.text = _QRZ_CALL_XML
        mock_resp.content = _QRZ_CALL_XML.encode()
        with patch("requests.get", return_value=mock_resp):
            with patch("network.qrz_lookup.record_connection") as mock_log:
                lookup._lookup_qrz("W1AW")
        mock_log.assert_called()

    def test_hamqth_parse(self):
        from network.qrz_lookup import CallsignLookup
        cfg = MagicMock()
        cfg.get.side_effect = lambda key, default="": {
            "apis.hamqth_user": "W1AW",
            "profile.name": "default",
        }.get(key, default)
        lookup = CallsignLookup(cfg)
        store_mock = MagicMock()
        store_mock.retrieve.return_value = "secret"
        lookup._get_store = lambda: store_mock
        lookup._hamqth_session = "hamqth_tok"

        mock_resp = MagicMock()
        mock_resp.text = _HAMQTH_CALL_XML
        mock_resp.content = _HAMQTH_CALL_XML.encode()
        with patch("requests.get", return_value=mock_resp):
            with patch("network.qrz_lookup.record_connection"):
                info = lookup._lookup_hamqth("W1AW")
        assert info is not None
        assert info.name == "Hiram Percy Maxim"
        assert info.grid == "FN31pr"
        assert info.source == "hamqth"

    def test_hamqth_login_calls_record_connection(self):
        from network.qrz_lookup import CallsignLookup
        cfg = MagicMock()
        cfg.get.side_effect = lambda key, default="": {
            "apis.hamqth_user": "W1AW",
            "profile.name": "default",
        }.get(key, default)
        lookup = CallsignLookup(cfg)
        store_mock = MagicMock()
        store_mock.retrieve.return_value = "secret"
        lookup._get_store = lambda: store_mock

        mock_sess = MagicMock()
        mock_sess.text = _HAMQTH_SESSION_XML
        mock_sess.content = _HAMQTH_SESSION_XML.encode()
        with patch("requests.get", return_value=mock_sess):
            with patch("network.qrz_lookup.record_connection") as mock_log:
                lookup._hamqth_login()
        mock_log.assert_called()

    def test_reads_password_from_keyring_not_cfg(self):
        """Credential bug: password must come from keyring, not cfg."""
        from network.qrz_lookup import CallsignLookup
        cfg = MagicMock()
        cfg.get.side_effect = lambda key, default="": {
            "apis.qrz_user": "W1AW",
            "profile.name": "default",
            # qrz_pass should NOT be in cfg — only in keyring
        }.get(key, default)
        lookup = CallsignLookup(cfg)
        store_mock = MagicMock()
        store_mock.retrieve.return_value = "keyring_secret"
        lookup._get_store = lambda: store_mock

        mock_resp = MagicMock()
        mock_resp.text = _QRZ_LOGIN_XML
        mock_resp.content = _QRZ_LOGIN_XML.encode()
        with patch("requests.get", return_value=mock_resp) as mock_get:
            with patch("network.qrz_lookup.record_connection"):
                key = lookup._qrz_login()
        # Password passed in the GET params must be the keyring value
        call_kwargs = mock_get.call_args
        params = call_kwargs[1].get("params") or call_kwargs[0][1] if len(call_kwargs[0]) > 1 else {}
        if not params:
            params = call_kwargs.kwargs.get("params", {})
        assert params.get("password") == "keyring_secret"
        assert key == "abc123"
