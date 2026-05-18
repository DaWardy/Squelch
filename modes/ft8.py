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
"""Squelch -- modes/ft8.py
FT8 and FT4 auto-sequence engine.
Controls WSJT-X via UDP and shared log file.
Full auto-sequence state machine matching WSJT-X behavior plus enhancements.
"""

import socket
import struct
import logging
import threading
import time
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Callable
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# WSJT-X UDP port
WSJTX_UDP_HOST = "127.0.0.1"
WSJTX_UDP_PORT = 2237

# FT8/FT4 cycle lengths in seconds
CYCLE = {
    "FT8": 15.0,
    "FT4": 7.5,
    "WSPR": 120.0,
}

# SNR display range
SNR_MIN = -24
SNR_MAX = +24


class AutoSeqState(Enum):
    IDLE          = "Idle — monitoring"
    CQ_SENT       = "CQ transmitted"
    WAITING_REPLY = "Waiting for reply"
    REPLY_DECODED = "Reply decoded"
    REPORT_SENT   = "Signal report sent"
    WAITING_RRR   = "Waiting for RRR/RR73"
    RRR_SENT      = "RRR transmitted"
    LOGGING       = "Logging QSO"
    QSO_COMPLETE  = "QSO complete"
    NEXT_CALLER   = "Moving to next caller"


@dataclass
class DecodedSignal:
    """Single decoded FT8/FT4 signal."""
    snr:        int
    dt:         float
    freq_hz:    int
    message:    str
    callsign:   str    = ""
    grid:       str    = ""
    dxcc:       str    = ""
    country:    str    = ""
    distance_km:float  = 0.0
    bearing_deg:float  = 0.0
    is_cq:      bool   = False
    is_reply_to:str    = ""   # callsign this is directed to
    worked:     bool   = False  # already in log
    new_dxcc:   bool   = False
    new_grid:   bool   = False
    new_band:   bool   = False
    timestamp:  float  = field(default_factory=time.time)

    @property
    def display_freq(self) -> str:
        return f"{self.freq_hz:,} Hz"

    @property
    def display_snr(self) -> str:
        return f"{self.snr:+d}"

    @property
    def display_dist(self) -> str:
        if self.distance_km > 0:
            return f"{self.distance_km:,.0f} km"
        return "—"


@dataclass
class QSOInProgress:
    their_call: str    = ""
    their_grid: str    = ""
    their_snr:  int    = 0
    their_freq: int    = 0
    my_report:  str    = ""
    their_report: str  = ""
    start_time: float  = field(default_factory=time.time)
    state:      AutoSeqState = AutoSeqState.IDLE


class FT8Engine:
    """
    FT8/FT4 decoder/encoder and auto-sequence controller.
    Interfaces with WSJT-X via UDP multicast.
    """

    def __init__(self, config, log_db=None):
        self.cfg      = config
        self.log_db   = log_db
        self.mode     = "FT8"
        self.band     = "20m"
        self.freq_hz  = 14_074_000
        self.tx_freq  = 1500    # audio offset Hz

        self._state           = AutoSeqState.IDLE
        self._wsjtx_connected = False
        self._cq_timeout      = 0   # cycles remaining before CQ timeout
        self._qso         = QSOInProgress()
        self._decodes:    list[DecodedSignal] = []
        self._tx_even     = True
        self._auto_seq    = True
        self._auto_cq     = False
        self._hold_tx     = False
        self._dx_only     = False
        self._halted      = False
        self._priority_calls: list[str] = []
        self._lockout:    set[str]  = set()

        self._sock:       socket.socket | None = None
        self._rx_thread:  threading.Thread | None = None
        self._running     = False

        # Callbacks
        self._on_decode:   Callable | None = None
        self._on_state:    Callable | None = None
        self._on_tx:       Callable | None = None
        self._on_qso_done: Callable | None = None

        # Cycle tracking
        self._cycle_timer = threading.Event()
        self._in_tx       = False
        self._tx_message  = ""
        self._cycle_count = 0
        self._session_qsos: list[str] = []  # callsigns worked this session

    # ── Public API ────────────────────────────────────────────────────────

    def start(self, mode: str = "FT8"):
        self.mode = mode
        self._running = True
        self._rx_thread = threading.Thread(
            target=self._rx_loop,
            daemon=True,
            name=f"{mode}RxThread")
        self._rx_thread.start()
        log.info(f"{mode} engine started")

    def stop(self):
        self._running = False
        if self._sock:
            try: self._sock.close()
            except Exception: pass
        log.info(f"{self.mode} engine stopped")

    def set_auto_sequence(self, enabled: bool):
        self._auto_seq = enabled
        if not enabled:
            self._set_state(AutoSeqState.IDLE)

    def set_auto_cq(self, enabled: bool):
        self._auto_cq = enabled

    def set_hold_tx_freq(self, hold: bool):
        self._hold_tx = hold

    def set_dx_only(self, dx_only: bool):
        self._dx_only = dx_only

    def set_tx_even(self, even: bool):
        self._tx_even = even

    def set_tx_freq(self, freq_hz: int):
        self.tx_freq = freq_hz

    def set_priority_calls(self, calls: list[str]):
        self._priority_calls = [c.upper() for c in calls]

    def call_station(self, decode: DecodedSignal):
        """Initiate a QSO with a decoded station."""
        if self._state != AutoSeqState.IDLE:
            log.warning("Auto-sequence busy, cannot start new QSO")
            return
        self._qso = QSOInProgress(
            their_call = decode.callsign,
            their_grid = decode.grid,
            their_snr  = decode.snr,
            their_freq = decode.freq_hz,
        )
        self._set_state(AutoSeqState.REPLY_DECODED)
        self._send_report()

    def send_cq(self):
        """Transmit a CQ call."""
        # Guard: need callsign
        cs = self.cfg.callsign
        if not cs or cs in ("No callsign set", ""):
            log.warning("Cannot CQ — no callsign configured")
            return
        # Guard: need WSJT-X running (UDP socket active)
        if not self._wsjtx_connected:
            log.warning(
                "Cannot CQ — WSJT-X not connected. "
                "Launch WSJT-X from the Modes tab.")
            if self._on_state:
                self._on_state(AutoSeqState.IDLE,
                               "WSJT-X not connected")
            return
        grid = self.cfg.grid[:4] if self.cfg.grid else ""
        msg  = f"CQ {cs} {grid}"
        self._queue_tx(msg)
        self._set_state(AutoSeqState.CQ_SENT)
        # Schedule timeout — if no decodes come back,
        # return to IDLE after 2 cycles (30 seconds)
        self._cq_timeout = 2

    def _check_cq_timeout(self):
        """
        Called each decode cycle.
        Decrements timeout counter and returns to IDLE if expired.
        """
        if self._state == AutoSeqState.CQ_SENT:
            if self._cq_timeout > 0:
                self._cq_timeout -= 1
            else:
                import logging as _log
                _log.getLogger(__name__).info(
                    "CQ timeout — no response. Returning to IDLE.")
                self._set_state(AutoSeqState.IDLE)

    def reconnect(self):
        """Called by Rescan button — reset connection state."""
        self._wsjtx_connected = False
        self._cq_timeout = 0
        if self._state != AutoSeqState.IDLE:
            self._set_state(AutoSeqState.IDLE)
        log.info("FT8 engine reconnect requested")

    def halt_tx(self):
        """Stop transmitting after current transmission."""
        self._halted = True
        self._in_tx  = False

    def resume(self):
        self._halted = False

    # ── WSJT-X UDP interface ──────────────────────────────────────────────

    def _rx_loop(self):
        """Receive and parse WSJT-X UDP datagrams."""
        try:
            self._sock = socket.socket(
                socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind((WSJTX_UDP_HOST, WSJTX_UDP_PORT))
            self._sock.settimeout(1.0)
            log.info(f"Listening for WSJT-X UDP on port {WSJTX_UDP_PORT}")
        except Exception as e:
            log.error(f"UDP bind failed: {e}")
            return

        while self._running:
            try:
                data, addr = self._sock.recvfrom(65536)
                self._parse_wsjtx_packet(data)
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    log.warning(f"UDP receive error: {e}")

    def _parse_wsjtx_packet(self, data: bytes):
        # Mark WSJT-X as connected on first packet
        if not self._wsjtx_connected:
            self._wsjtx_connected = True
            log.info("WSJT-X UDP connected")

        """
        Parse WSJT-X UDP protocol packets.
        Packet format: magic(4) + schema(4) + type(4) + id_len(4) + id + payload
        """
        if len(data) < 12:
            return
        try:
            offset = 0
            magic  = struct.unpack_from(">I", data, offset)[0]
            offset += 4
            if magic != 0xADBCCBDA:
                return

            schema = struct.unpack_from(">I", data, offset)[0]
            offset += 4
            ptype  = struct.unpack_from(">I", data, offset)[0]
            offset += 4

            # Skip ID string
            id_len = struct.unpack_from(">I", data, offset)[0]
            offset += 4 + id_len

            if ptype == 2:    # Decode packet
                self._handle_decode(data, offset)
            elif ptype == 5:  # QSO logged packet
                self._handle_qso_logged(data, offset)
            elif ptype == 12: # Heartbeat
                pass

        except Exception as e:
            log.debug(f"Packet parse error: {e}")

    def _handle_decode(self, data: bytes, offset: int):
        """Parse a decode packet from WSJT-X."""
        try:
            # new (bool), time(uint), snr(int), dt(float64),
            # df(uint), mode(str), msg(str), low_conf(bool)
            new    = struct.unpack_from(">?", data, offset)[0]; offset += 1
            _time  = struct.unpack_from(">I", data, offset)[0]; offset += 4
            snr    = struct.unpack_from(">i", data, offset)[0]; offset += 4
            dt     = struct.unpack_from(">d", data, offset)[0]; offset += 8
            df     = struct.unpack_from(">I", data, offset)[0]; offset += 4

            # Mode string
            mlen   = struct.unpack_from(">I", data, offset)[0]; offset += 4
            mode   = data[offset:offset+mlen].decode(); offset += mlen

            # Message string
            msglen = struct.unpack_from(">I", data, offset)[0]; offset += 4
            msg    = data[offset:offset+msglen].decode(); offset += msglen

            if not new:
                return

            decode = self._parse_ft8_message(msg, snr, dt, int(df))
            if decode:
                self._decodes.append(decode)
                # Keep last 200 decodes per cycle
                if len(self._decodes) > 200:
                    self._decodes = self._decodes[-200:]
                if self._on_decode:
                    self._on_decode(decode)
                if self._auto_seq and not self._halted:
                    self._auto_sequence_step(decode)

        except Exception as e:
            log.debug(f"Decode parse error: {e}")

    def _parse_ft8_message(self, msg: str, snr: int,
                            dt: float, df: int) -> DecodedSignal | None:
        """Parse an FT8 message string into a DecodedSignal."""
        parts = msg.strip().split()
        if not parts:
            return None

        my_call = self.cfg.callsign.upper()
        decode  = DecodedSignal(
            snr=snr, dt=dt, freq_hz=df, message=msg)

        # CQ call: "CQ [MODE] CALLSIGN GRID" or "CQ CALLSIGN GRID"
        if parts[0] == "CQ":
            idx = 1
            if len(parts) > idx and not _looks_like_call(parts[idx]):
                idx += 1  # skip DX/mode designator
            if len(parts) > idx:
                decode.callsign = parts[idx]
                decode.is_cq    = True
            if len(parts) > idx + 1:
                decode.grid = parts[idx + 1]

        # Direct call: "THEIRCALL MYCALL GRID_OR_REPORT"
        elif len(parts) >= 2:
            decode.callsign   = parts[0]
            decode.is_reply_to = parts[1]
            if len(parts) > 2:
                token = parts[2]
                if len(token) == 4 and token[0].isalpha():
                    decode.grid = token
                elif token.startswith(("+","-","R+","R-","RR73","73","RRR")):
                    pass

        if not decode.callsign:
            return None

        # Check if this is directed at us
        if decode.is_reply_to == my_call:
            decode.worked = decode.callsign in self._session_qsos

        # Calculate distance/bearing if we have grids
        if decode.grid and self.cfg.grid:
            try:
                from core.location import _grid_to_latlon
                my_lat, my_lon   = _grid_to_latlon(self.cfg.grid)
                their_lat, their_lon = _grid_to_latlon(decode.grid)
                decode.distance_km = _haversine(
                    my_lat, my_lon, their_lat, their_lon)
                decode.bearing_deg = _bearing(
                    my_lat, my_lon, their_lat, their_lon)
            except Exception:
                pass

        return decode

    def _handle_qso_logged(self, data: bytes, offset: int):
        """WSJT-X has logged a QSO — mirror to Squelch log."""
        try:
            # Parse QSO fields from packet
            # (simplified — real implementation parses full packet)
            log.info("WSJT-X QSO logged — mirroring to Squelch log")
            if self.log_db and self._qso.their_call:
                from core.log_db import QSO
                qso = QSO(
                    call      = self._qso.their_call,
                    band      = self.band,
                    freq_hz   = self.freq_hz,
                    mode      = self.mode,
                    submode   = self.mode,
                    rst_sent  = self._qso.my_report or "+00",
                    rst_rcvd  = self._qso.their_report or "+00",
                    grid      = self._qso.their_grid,
                    my_call   = self.cfg.callsign,
                    my_grid   = self.cfg.grid,
                    tx_pwr_w  = _dbm_to_w(
                        self.cfg.get("ft8.tx_power_dbm", 37)),
                    source    = f"{self.mode.lower()}_auto",
                )
                self.log_db.log_qso(qso)
                self._session_qsos.append(self._qso.their_call)
                if self._on_qso_done:
                    self._on_qso_done(qso)
        except Exception as e:
            log.error(f"QSO log mirror failed: {e}")

    # ── Auto-sequence state machine ───────────────────────────────────────

    def _auto_sequence_step(self, decode: DecodedSignal):
        """
        Drive the auto-sequence state machine on each decode.
        This is the core of the WSJT-X-equivalent behavior.
        """
        if not self._auto_seq or self._halted:
            return

        my_call = self.cfg.callsign.upper()
        state   = self._state

        if state == AutoSeqState.IDLE:
            # Look for CQ calls to answer or replies to our CQ
            if decode.is_reply_to == my_call:
                # Someone answered our CQ
                self._qso = QSOInProgress(
                    their_call = decode.callsign,
                    their_grid = decode.grid,
                    their_snr  = decode.snr,
                    their_freq = decode.freq_hz,
                )
                self._set_state(AutoSeqState.REPLY_DECODED)
                self._send_report()

            elif decode.is_cq and self._auto_cq:
                # Auto-answer CQ based on priority
                if self._should_call(decode):
                    self._qso = QSOInProgress(
                        their_call = decode.callsign,
                        their_grid = decode.grid,
                        their_snr  = decode.snr,
                        their_freq = decode.freq_hz,
                    )
                    self._set_state(AutoSeqState.REPLY_DECODED)
                    self._send_report()

        elif state == AutoSeqState.CQ_SENT:
            if decode.is_reply_to == my_call:
                self._qso.their_call   = decode.callsign
                self._qso.their_grid   = decode.grid
                self._qso.their_snr    = decode.snr
                self._set_state(AutoSeqState.REPLY_DECODED)
                self._send_report()

        elif state == AutoSeqState.REPORT_SENT:
            if (decode.callsign == self._qso.their_call and
                    decode.is_reply_to == my_call):
                msg = decode.message.upper()
                if any(x in msg for x in ["RR73","RRR","73"]):
                    self._set_state(AutoSeqState.WAITING_RRR)
                    self._send_rrr()

        elif state == AutoSeqState.RRR_SENT:
            if (decode.callsign == self._qso.their_call and
                    "73" in decode.message.upper()):
                self._complete_qso()

    def _send_report(self):
        """Send signal report to the station we're working."""
        cs  = self.cfg.callsign
        snr = self._qso.their_snr
        report = f"{snr:+03d}"
        msg = f"{self._qso.their_call} {cs} {report}"
        self._qso.my_report = report
        self._queue_tx(msg)
        self._set_state(AutoSeqState.REPORT_SENT)

    def _send_rrr(self):
        cs  = self.cfg.callsign
        msg = f"{self._qso.their_call} {cs} RR73"
        self._queue_tx(msg)
        self._set_state(AutoSeqState.RRR_SENT)

    def _complete_qso(self):
        self._set_state(AutoSeqState.QSO_COMPLETE)
        log.info(
            f"QSO complete: {self._qso.their_call} "
            f"{self.band} {self.mode}")
        # Log is handled by _handle_qso_logged via WSJT-X
        # Reset for next QSO
        time.sleep(0.5)
        self._qso  = QSOInProgress()
        self._halted = False
        self._set_state(AutoSeqState.IDLE)

    def _queue_tx(self, message: str):
        """Send a TX message command to WSJT-X via UDP."""
        self._tx_message = message
        self._in_tx      = True
        log.info(f"TX: {message}")
        if self._on_tx:
            self._on_tx(message)
        # Send to WSJT-X via UDP Reply packet (type 4)
        self._send_reply_packet(message)

    def _send_reply_packet(self, message: str):
        """Build and send a WSJT-X Reply UDP packet."""
        try:
            if not self._sock:
                return
            # WSJT-X Reply packet type 4
            magic  = struct.pack(">I", 0xADBCCBDA)
            schema = struct.pack(">I", 2)
            ptype  = struct.pack(">I", 4)
            id_str = b"Squelch"
            id_pkt = struct.pack(">I", len(id_str)) + id_str
            msg_b  = message.encode()
            msg_pkt = struct.pack(">I", len(msg_b)) + msg_b
            packet = magic + schema + ptype + id_pkt + msg_pkt
            self._sock.sendto(
                packet, (WSJTX_UDP_HOST, WSJTX_UDP_PORT))
        except Exception as e:
            log.warning(f"TX packet send failed: {e}")

    def _should_call(self, decode: DecodedSignal) -> bool:
        """Decide whether to auto-answer a CQ."""
        if decode.callsign in self._lockout:
            return False
        if decode.callsign in self._session_qsos:
            return False
        if self._dx_only and decode.country == "United States":
            return False
        if self._priority_calls:
            return decode.callsign in self._priority_calls
        return True

    def _set_state(self, state: AutoSeqState):
        self._state = state
        log.debug(f"Auto-seq: {state.value}")
        if self._on_state:
            self._on_state(state)

    # ── Callback registration ─────────────────────────────────────────────

    def on_decode(self, cb: Callable):
        self._on_decode = cb

    def on_state_change(self, cb: Callable):
        self._on_state = cb

    def on_tx(self, cb: Callable):
        self._on_tx = cb

    def on_qso_complete(self, cb: Callable):
        self._on_qso_done = cb

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def state(self) -> AutoSeqState:
        return self._state

    @property
    def decodes(self) -> list[DecodedSignal]:
        return list(self._decodes)

    @property
    def current_qso(self) -> QSOInProgress:
        return self._qso

    @property
    def session_count(self) -> int:
        return len(self._session_qsos)


# ── Math helpers ──────────────────────────────────────────────────────────

import math

def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def _bearing(lat1, lon1, lat2, lon2) -> float:
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(math.radians(lat2))
    y = (math.cos(math.radians(lat1)) *
         math.sin(math.radians(lat2)) -
         math.sin(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.cos(dlon))
    return (math.degrees(math.atan2(x, y)) + 360) % 360

def _looks_like_call(s: str) -> bool:
    return len(s) >= 3 and any(c.isdigit() for c in s)

def _dbm_to_w(dbm: float) -> float:
    return 10 ** ((dbm - 30) / 10)
