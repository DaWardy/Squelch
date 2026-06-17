# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
#
# This program is free software: you can redistribute it
# and/or modify it under the terms of the GNU General
# Public License as published by the Free Software
# Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General
# Public License along with this program. If not, see
# <https://www.gnu.org/licenses/>.

from __future__ import annotations
"""Squelch -- network/qrz_lookup.py
Callsign lookup via QRZ XML API (primary) and HamQTH (fallback).
Results cached to minimize API calls.
Credentials never logged or displayed after entry.
"""

import logging
import time
import threading
import requests
from core.credentials import get_store
from core.netlog import record_connection
try:
    import defusedxml.ElementTree as ET  # type: ignore
except ImportError:
    import xml.etree.ElementTree as ET  # fallback
from dataclasses import dataclass, field
from core.validator import api_string, api_callsign, api_float

log = logging.getLogger(__name__)

QRZ_XML_URL   = "https://xmldata.qrz.com/xml/current/"
HAMQTH_URL    = "https://www.hamqth.com/xml.php"
CACHE_TTL     = 3600 * 24   # 24 hours
MAX_CACHE     = 1000


@dataclass
class CallsignInfo:
    callsign:    str
    name:        str        = ""
    country:     str        = ""
    dxcc:        str        = ""
    grid:        str        = ""
    state:       str        = ""
    county:      str        = ""
    cq_zone:     int        = 0
    itu_zone:    int        = 0
    lat:         float      = 0.0
    lon:         float      = 0.0
    license_class: str      = ""
    qsl_via:     str        = ""
    email:       str        = ""
    url:         str        = ""
    image_url:   str        = ""
    source:      str        = ""
    fetched_at:  float      = field(default_factory=time.time)

    @property
    def is_fresh(self) -> bool:
        return (time.time() - self.fetched_at) < CACHE_TTL

    @property
    def display_name(self) -> str:
        return self.name or self.callsign


class CallsignLookup:
    """
    Lookup callsign info from QRZ XML or HamQTH.
    Thread-safe in-memory cache. Non-blocking via callbacks.
    """

    def __init__(self, config):
        self.cfg      = config
        self._cache:  dict[str, CallsignInfo] = {}
        self._session_key: str | None = None
        self._hamqth_session: str | None = None
        self._lock    = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────────

    def lookup_async(self, callsign: str,
                     callback) -> None:
        """Non-blocking lookup. Calls callback(CallsignInfo) when done."""
        def _do():
            info = self.lookup(callsign)
            if callback:
                try:
                    callback(info)
                except Exception as e:
                    log.debug(f"Lookup callback: {e}")
        threading.Thread(target=_do, daemon=True).start()

    def lookup(self, callsign: str) -> CallsignInfo | None:
        """Synchronous lookup. Returns None if not found."""
        callsign = callsign.upper().strip()
        if not callsign:
            return None

        # Check cache
        with self._lock:
            cached = self._cache.get(callsign)
            if cached and cached.is_fresh:
                return cached

        # Try QRZ first
        info = self._lookup_qrz(callsign)
        if not info:
            # Fall back to HamQTH
            info = self._lookup_hamqth(callsign)

        if info:
            with self._lock:
                self._cache[callsign] = info
                # Trim cache
                if len(self._cache) > MAX_CACHE:
                    oldest = sorted(
                        self._cache.items(),
                        key=lambda x: x[1].fetched_at)[:100]
                    for k, _ in oldest:
                        del self._cache[k]

        return info

    def clear_cache(self):
        with self._lock:
            self._cache.clear()
        self._session_key = None

    # ── QRZ XML ───────────────────────────────────────────────────────────

    def _get_store(self):
        return get_store(self.cfg.get("profile.name", "default"))

    def _qrz_login(self) -> str | None:
        user = self.cfg.get("apis.qrz_user", "")
        pw   = self._get_store().retrieve("qrz_password") or ""
        if not user or not pw:
            return None
        try:
            record_connection(QRZ_XML_URL)
            resp = requests.get(
                QRZ_XML_URL,
                params={"username": user, "password": pw,
                        "agent": "Squelch/1.0"},
                timeout=10)
            if len(resp.content) > 50_000:
                return None  # response too large
            root = ET.fromstring(resp.text)  # nosec B314
            ns   = {"q": "urn:xmethods-XCallsign"}
            sess = root.find(".//q:Session", ns)
            if sess is not None:
                key = sess.findtext("q:Key", namespaces=ns)
                if key:
                    return key.strip()
            log.warning("QRZ login failed — check credentials")
            return None
        except Exception as e:
            log.debug(f"QRZ login: {e}")
            return None

    def _lookup_qrz(self, callsign: str) -> CallsignInfo | None:
        if not self._session_key:
            self._session_key = self._qrz_login()
        if not self._session_key:
            return None
        try:
            record_connection(QRZ_XML_URL)
            resp = requests.get(
                QRZ_XML_URL,
                params={"s": self._session_key,
                        "callsign": callsign},
                timeout=10)
            if len(resp.content) > 50_000:
                return None  # response too large
            root = ET.fromstring(resp.text)  # nosec B314
            ns   = {"q": "urn:xmethods-XCallsign"}

            # Check for session expiry
            sess = root.find(".//q:Session", ns)
            if sess is not None:
                err = sess.findtext("q:Error", namespaces=ns)
                if err and "session" in err.lower():
                    self._session_key = self._qrz_login()
                    return None

            rec = root.find(".//q:Callsign", ns)
            if rec is None:
                return None

            def _t(tag):
                v = rec.findtext(f"q:{tag}", namespaces=ns) or ""
                return api_string(v)

            return CallsignInfo(
                callsign      = callsign,
                name          = f"{_t('fname')} {_t('name')}".strip(),
                country       = _t("country"),
                dxcc          = _t("dxcc"),
                grid          = _t("grid"),
                state         = _t("state"),
                county        = _t("county"),
                cq_zone       = int(_t("cqzone") or 0),
                itu_zone      = int(_t("ituzone") or 0),
                lat           = api_float(_t("lat")),
                lon           = api_float(_t("lon")),
                license_class = _t("class"),
                qsl_via       = _t("qslmgr"),
                email         = _t("email"),
                url           = _t("url"),
                image_url     = _t("image"),
                source        = "qrz",
            )
        except Exception as e:
            log.debug(f"QRZ lookup {callsign}: {e}")
            self._session_key = None  # Force re-login next time
            return None

    # ── HamQTH ────────────────────────────────────────────────────────────

    def _hamqth_login(self) -> str | None:
        user = self.cfg.get("apis.hamqth_user", "")
        pw   = self._get_store().retrieve("hamqth_password") or ""
        if not user or not pw:
            return None
        try:
            record_connection(HAMQTH_URL)
            resp = requests.get(
                HAMQTH_URL,
                params={"u": user, "p": pw},
                timeout=10)
            if len(resp.content) > 50_000:
                return None  # response too large
            root = ET.fromstring(resp.text)  # nosec B314
            ns   = {"h": "https://www.hamqth.com"}
            sess = root.find(".//h:session_id", ns)
            if sess is not None and sess.text:
                return sess.text.strip()
            return None
        except Exception as e:
            log.debug(f"HamQTH login: {e}")
            return None

    def _lookup_hamqth(self, callsign: str) -> CallsignInfo | None:
        if not self._hamqth_session:
            self._hamqth_session = self._hamqth_login()
        if not self._hamqth_session:
            return None
        try:
            record_connection(HAMQTH_URL)
            resp = requests.get(
                HAMQTH_URL,
                params={"id": self._hamqth_session,
                        "callsign": callsign,
                        "prg": "Squelch"},
                timeout=10)
            if len(resp.content) > 50_000:
                return None  # response too large
            root = ET.fromstring(resp.text)  # nosec B314
            ns   = {"h": "https://www.hamqth.com"}
            rec  = root.find(".//h:search", ns)
            if rec is None:
                return None

            def _t(tag):
                v = rec.findtext(f"h:{tag}", namespaces=ns) or ""
                return api_string(v)

            return CallsignInfo(
                callsign  = callsign,
                name      = _t("adr_name"),
                country   = _t("country"),
                grid      = _t("grid"),
                state     = _t("us_state"),
                cq_zone   = int(_t("cq_zone") or 0),
                itu_zone  = int(_t("itu_zone") or 0),
                lat       = api_float(_t("latitude")),
                lon       = api_float(_t("longitude")),
                qsl_via   = _t("qsl_via"),
                source    = "hamqth",
            )
        except Exception as e:
            log.debug(f"HamQTH lookup {callsign}: {e}")
            self._hamqth_session = None
            return None


_lookup: CallsignLookup | None = None

def get_lookup(config=None) -> CallsignLookup:
    global _lookup
    if _lookup is None:
        if config is None:
            from core.config import get_config
            config = get_config()
        _lookup = CallsignLookup(config)
    return _lookup