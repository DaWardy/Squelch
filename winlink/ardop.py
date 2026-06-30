from __future__ import annotations
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
"""ARDOP soundcard-TNC control interface (ardopcf / ardopc).

ARDOP (Amateur Radio Digital Open Protocol) exposes a line-oriented TCP
control channel (default port 8515) and a separate binary data channel
(8516). This module speaks the control protocol only — enough to connect,
report state, and drive a session — mirroring ``winlink.vara.VARAModem`` so
the Winlink tab can treat both modems the same way.

Offline-testable: every method that touches the network is mockable, and the
protocol parser (``_handle_response``) is pure, so state transitions can be
exercised with no hardware (see ``tests/test_ardop.py``).
"""
import socket
import threading
import logging
import time
from enum import Enum

log = logging.getLogger(__name__)

ARDOP_CMD_PORT  = 8515   # control channel (line protocol)
ARDOP_DATA_PORT = 8516   # data channel (binary)
LOCALHOST       = "127.0.0.1"
TIMEOUT_S       = 5.0


class ARDOPState(Enum):
    DISCONNECTED = "Disconnected"
    IDLE         = "Idle"
    CONNECTING   = "Connecting"
    CONNECTED    = "Connected"
    BUSY         = "Busy"
    ERROR        = "Error"


class ARDOPModem:
    """TCP client for an ARDOP TNC control port.

    State mirrors :class:`ARDOPState`. ``DISCONNECTED`` means no link to the
    TNC process; ``IDLE`` means connected to the TNC but no on-air session;
    ``CONNECTED`` means an ARQ session is up; ``BUSY`` means the channel is
    occupied (carrier detected). Register a callback with :meth:`on_state`.
    """

    def __init__(self, host: str = LOCALHOST, port: int = ARDOP_CMD_PORT):
        self._host     = host or LOCALHOST
        self._cmd_port = int(port) if port else ARDOP_CMD_PORT
        self._dat_port = self._cmd_port + 1
        self._cmd_sock = None
        self._state    = ARDOPState.DISCONNECTED
        self._thread   = None
        self._running  = False
        self._version  = ""
        self._on_state   = None
        self._on_connect = None
        self._on_data    = None

    @property
    def name(self) -> str:
        return "ARDOP"

    @property
    def state(self) -> ARDOPState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._state in (ARDOPState.CONNECTED, ARDOPState.BUSY)

    @property
    def version(self) -> str:
        return self._version

    def connect(self) -> bool:
        """Open the ARDOP TNC control socket and start the read loop."""
        try:
            from core.netlog import record_connection
            record_connection(f"{self._host}:{self._cmd_port}",
                              purpose="ARDOP TNC control",
                              user_initiated=True)
        except Exception as e:
            log.debug(f"{self.name} netlog: {e}")
        try:
            self._cmd_sock = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM)
            self._cmd_sock.settimeout(TIMEOUT_S)
            self._cmd_sock.connect((self._host, self._cmd_port))
            self._running = True
            self._thread  = threading.Thread(
                target=self._read_loop, daemon=True)
            self._thread.start()
            self._set_state(ARDOPState.IDLE)
            self._send("INITIALIZE")
            self._send("LISTEN TRUE")
            self._send("VERSION")
            log.info(f"{self.name} connected ({self._host}:{self._cmd_port})")
            return True
        except Exception as e:
            log.warning(f"{self.name} connect: {e}")
            self._set_state(ARDOPState.ERROR)
            return False

    def disconnect(self):
        """Close the ARDOP TCP connection cleanly."""
        self._running = False
        try:
            if self._cmd_sock:
                self._send("DISCONNECT")
                time.sleep(0.2)
                self._cmd_sock.close()
        except Exception as e:
            log.debug(f"{self.name} disconnect: {e}")
        self._cmd_sock = None
        self._set_state(ARDOPState.DISCONNECTED)

    def _send(self, cmd: str):
        try:
            if self._cmd_sock:
                self._cmd_sock.sendall((cmd + "\r").encode())
        except Exception as e:
            log.debug(f"{self.name} send: {e}")

    def _read_loop(self):
        buf = ""
        while self._running:
            try:
                data = self._cmd_sock.recv(1024)
                if not data:
                    break
                buf += data.decode(errors="replace")
                # ARDOP terminates control lines with CR (some builds CRLF).
                buf = buf.replace("\n", "\r")
                while "\r" in buf:
                    line, buf = buf.split("\r", 1)
                    self._handle_response(line.strip())
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    log.warning(f"{self.name} read: {e}")
                break
        self._set_state(ARDOPState.DISCONNECTED)

    def _handle_response(self, line: str):
        """Parse one control line into a state transition. Pure / testable."""
        if not line:
            return
        upper = line.upper()
        if upper.startswith("VERSION"):
            self._version = line[7:].strip()
        elif upper.startswith("CONNECTED"):
            self._set_state(ARDOPState.CONNECTED)
            if self._on_connect:
                self._on_connect(line[9:].strip())
        elif upper.startswith("DISCONNECTED"):
            self._set_state(ARDOPState.IDLE)
        elif upper.startswith("NEWSTATE") or upper.startswith("STATE"):
            self._apply_tnc_state(upper.split(None, 1)[-1].strip())
        elif upper.startswith("BUSY"):
            busy = "TRUE" in upper
            # Only override IDLE→BUSY; never clobber an active ARQ session.
            if busy and self._state == ARDOPState.IDLE:
                self._set_state(ARDOPState.BUSY)
            elif not busy and self._state == ARDOPState.BUSY:
                self._set_state(ARDOPState.IDLE)
        elif upper.startswith("FAULT") or upper.startswith("REJECT"):
            self._set_state(ARDOPState.ERROR)

    def _apply_tnc_state(self, tnc: str):
        """Map an ARDOP NEWSTATE/STATE token to an ARDOPState."""
        tnc = tnc.upper()
        if tnc in ("ISS", "IRS", "ISSMOD", "IRSMOD"):
            self._set_state(ARDOPState.CONNECTED)
        elif tnc in ("DISC", "OFFLINE"):
            # Connected to the TNC but no on-air link.
            if self._state != ARDOPState.DISCONNECTED:
                self._set_state(ARDOPState.IDLE)
        elif tnc == "IDLE":
            if not self.is_connected:
                self._set_state(ARDOPState.IDLE)

    def _set_state(self, state: ARDOPState):
        self._state = state
        if self._on_state:
            try:
                self._on_state(state)
            except Exception as e:
                log.debug(f"{self.name} on_state cb: {e}")

    def set_callsign(self, cs: str):
        self._send(f"MYCALL {cs.upper()}")

    def set_bandwidth(self, hz: int):
        """ARDOP ARQ bandwidth — e.g. 200/500/1000/2000 (MAX)."""
        self._send(f"ARQBW {int(hz)}MAX")

    def listen(self, enable: bool = True):
        self._send("LISTEN TRUE" if enable else "LISTEN FALSE")

    def connect_to(self, remote: str, repeats: int = 5):
        self._set_state(ARDOPState.CONNECTING)
        self._send(f"ARQCALL {remote.upper()} {int(repeats)}")

    def abort(self):
        self._send("ABORT")

    def on_state(self, cb):
        self._on_state = cb

    def on_connect(self, cb):
        self._on_connect = cb

    @staticmethod
    def is_running(host: str = LOCALHOST,
                   port: int = ARDOP_CMD_PORT) -> bool:
        """True if something is listening on the ARDOP control port."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex((host or LOCALHOST, int(port)))
            s.close()
            return result == 0
        except Exception:
            return False
