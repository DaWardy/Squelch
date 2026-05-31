from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
from core.constants import APP_VERSION
Squelch -- aprs/aprs_client.py
APRS-IS internet gateway client.
Receives position packets within radius of station.
"""

import socket
import threading
import logging
import time
import re
from dataclasses import dataclass
from typing import Callable

log = logging.getLogger(__name__)

APRS_IS_HOST = "rotate.aprs2.net"
APRS_IS_PORT = 14580
MAX_PACKETS  = 500

_LAT_LON_RE = re.compile(
    r'(\d{4}\.\d{2})([NS]).(\d{5}\.\d{2})([EW])')


@dataclass
class APRSPacket:
    raw:       str
    callsign:  str   = ""
    ssid:      str   = ""
    lat:       float = 0.0
    lon:       float = 0.0
    comment:   str   = ""
    symbol:    str   = ""
    timestamp: float = 0.0

    @property
    def call_ssid(self) -> str:
        return f"{self.callsign}-{self.ssid}" if self.ssid else self.callsign

    @property
    def is_position(self) -> bool:
        return bool(self.lat or self.lon)


def _parse_position(packet: str) -> tuple[float, float]:
    m = _LAT_LON_RE.search(packet)
    if m:
        lat_str, ns, lon_str, ew = m.groups()
        lat = int(lat_str[:2]) + float(lat_str[2:]) / 60
        lon = int(lon_str[:3]) + float(lon_str[3:]) / 60
        if ns == "S": lat = -lat
        if ew == "W": lon = -lon
        return round(lat, 6), round(lon, 6)
    return 0.0, 0.0


def parse_packet(raw: str) -> "APRSPacket | None":
    if not raw or raw.startswith("#"):
        return None
    try:
        if ":" not in raw:
            return None
        header, info = raw.split(":", 1)
        src = header.split(">")[0] if ">" in header else header
        src = src.strip().upper()
        callsign, ssid = (src.split("-", 1) + [""])[:2]
        lat, lon = _parse_position(info)
        m = _LAT_LON_RE.search(info)
        comment = info[m.end():].strip()[:100] if m else info[:100]
        return APRSPacket(
            raw=raw[:300], callsign=callsign, ssid=ssid,
            lat=lat, lon=lon, comment=comment,
            timestamp=time.time())
    except Exception as e:
        log.debug(f"APRS parse: {e}")
        return None


class APRSClient:
    def __init__(self, config):
        self.cfg      = config
        self._sock    = None
        self._running = False
        self._thread  = None
        self._packets: list[APRSPacket] = []
        self._lock    = threading.Lock()
        self._on_packet: Callable = None
        self._on_status: Callable = None

    @property
    def is_connected(self) -> bool:
        return self._running and self._sock is not None

    def connect(self, radius_km: float = 150) -> bool:
        """Open connection to APRS-IS server."""
        callsign = self.cfg.callsign
        if not callsign:
            log.warning("APRS: no callsign")
            return False
        lat = self.cfg.get("location.lat", 0.0) or 0.0
        lon = self.cfg.get("location.lon", 0.0) or 0.0
        filt = (f"r/{lat:.4f}/{lon:.4f}/{radius_km:.0f}"
                if lat and lon else "m/150")
        try:
            self._sock = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(8)
            self._sock.connect((APRS_IS_HOST, APRS_IS_PORT))
            self._sock.sendall(
                f"user {callsign} pass -1 "
                f"vers Squelch 0.9.0 filter {filt}\r\n"
                .encode())
            self._running = True
            self._thread  = threading.Thread(
                target=self._recv_loop, daemon=True, name="APRS-IS")
            self._thread.start()
            log.info(f"APRS-IS connected (filter={filt})")
            self._notify_status("connected")
            return True
        except Exception as e:
            log.warning(f"APRS-IS connect: {e}")
            self._notify_status("error")
            return False

    def disconnect(self):
        """Close connection to APRS-IS server cleanly."""
        self._running = False
        try:
            if self._sock:
                self._sock.close()
        except Exception:
            pass
        self._sock = None
        self._notify_status("disconnected")

    def _recv_loop(self):
        buf = ""
        while self._running:
            try:
                data = self._sock.recv(4096)
                if not data:
                    break
                buf += data.decode("ascii", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    pkt = parse_packet(line)
                    if pkt and pkt.is_position:
                        self._add_packet(pkt)
            except socket.timeout:
                try:
                    self._sock.sendall(b"#keepalive\r\n")
                except Exception:
                    break
            except Exception as e:
                if self._running:
                    log.warning(f"APRS recv: {e}")
                break
        self._running = False
        self._notify_status("disconnected")

    def _add_packet(self, pkt: APRSPacket):
        with self._lock:
            self._packets = [p for p in self._packets
                             if p.call_ssid != pkt.call_ssid]
            self._packets.append(pkt)
            if len(self._packets) > MAX_PACKETS:
                self._packets = self._packets[-MAX_PACKETS:]
        if self._on_packet:
            try:
                self._on_packet(pkt)
            except Exception:
                pass

    def recent_packets(self, limit: int = 100) -> list[APRSPacket]:
        with self._lock:
            return list(self._packets[-limit:])

    def stations_on_map(self) -> list[dict]:
        with self._lock:
            return [{"call": p.call_ssid, "lat": p.lat,
                     "lon": p.lon, "comment": p.comment}
                    for p in self._packets if p.is_position]

    def _notify_status(self, status: str):
        if self._on_status:
            try:
                self._on_status(status)
            except Exception:
                pass

    def on_packet(self, cb: Callable): self._on_packet = cb
    def on_status(self, cb: Callable): self._on_status = cb

    @staticmethod
    def compute_passcode(callsign: str) -> int:
        cs = callsign.upper().split("-")[0]
        code = 0x73E2
        for i, ch in enumerate(cs):
            if i % 2 == 0: code ^= ord(ch) << 8
            else:           code ^= ord(ch)
        return code & 0x7FFF
