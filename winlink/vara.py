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
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- winlink/vara.py
VARA HF and VARA FM modem control via TCP sockets.
"""

import socket
import threading
import logging
import time
from enum import Enum
from typing import Callable

log = logging.getLogger(__name__)

VARA_HF_CMD  = 8300
VARA_FM_CMD  = 8400
VARA_HF_DATA = 8301
VARA_FM_DATA = 8401
LOCALHOST    = "127.0.0.1"
TIMEOUT_S    = 5.0


class VARAState(Enum):
    DISCONNECTED = "Disconnected"
    IDLE         = "Idle"
    CONNECTING   = "Connecting"
    CONNECTED    = "Connected"
    BUSY         = "Busy"
    ERROR        = "Error"


class VARAModem:
    def __init__(self, is_fm: bool = False):
        self._is_fm    = is_fm
        self._cmd_port = VARA_FM_CMD  if is_fm else VARA_HF_CMD
        self._dat_port = VARA_FM_DATA if is_fm else VARA_HF_DATA
        self._cmd_sock = None
        self._state    = VARAState.DISCONNECTED
        self._thread   = None
        self._running  = False
        self._version  = ""
        self._on_state   = None
        self._on_connect = None
        self._on_data    = None

    @property
    def name(self) -> str:
        return "VARA FM" if self._is_fm else "VARA HF"

    @property
    def state(self) -> VARAState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._state in (VARAState.CONNECTED, VARAState.BUSY)

    @property
    def version(self) -> str:
        return self._version

    def connect(self) -> bool:
        try:
            self._cmd_sock = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM)
            self._cmd_sock.settimeout(TIMEOUT_S)
            self._cmd_sock.connect((LOCALHOST, self._cmd_port))
            self._running = True
            self._thread  = threading.Thread(
                target=self._read_loop, daemon=True)
            self._thread.start()
            self._set_state(VARAState.IDLE)
            self._send("VERSION")
            log.info(f"{self.name} connected")
            return True
        except Exception as e:
            log.warning(f"{self.name} connect: {e}")
            self._set_state(VARAState.ERROR)
            return False

    def disconnect(self):
        self._running = False
        try:
            if self._cmd_sock:
                self._send("DISCONNECT")
                time.sleep(0.2)
                self._cmd_sock.close()
        except Exception:
            pass
        self._cmd_sock = None
        self._set_state(VARAState.DISCONNECTED)

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
                while "\r" in buf:
                    line, buf = buf.split("\r", 1)
                    self._handle_response(line.strip())
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    log.warning(f"{self.name} read: {e}")
                break
        self._set_state(VARAState.DISCONNECTED)

    def _handle_response(self, line: str):
        if not line:
            return
        if line.startswith("VERSION"):
            self._version = line.replace("VERSION ", "")
        elif line == "IAMALIVE":
            self._send("IAMALIVE")
        elif line.startswith("CONNECTED"):
            self._set_state(VARAState.CONNECTED)
            if self._on_connect:
                self._on_connect(line.replace("CONNECTED ", ""))
        elif line == "DISCONNECTED":
            self._set_state(VARAState.IDLE)

    def _set_state(self, state: VARAState):
        self._state = state
        if self._on_state:
            try:
                self._on_state(state)
            except Exception:
                pass

    def set_callsign(self, cs: str):
        self._send(f"MYCALL {cs.upper()}")

    def set_bandwidth(self, hz: int):
        self._send(f"BW{hz}")

    def listen(self, enable: bool = True):
        self._send("LISTEN ON" if enable else "LISTEN OFF")

    def connect_to(self, remote: str, via: str = ""):
        if via:
            self._send(f"CONNECT {remote} VIA {via}")
        else:
            self._send(f"CONNECT {remote}")

    def abort(self):
        self._send("ABORT")

    def on_state(self, cb):
        self._on_state = cb

    def on_connect(self, cb):
        self._on_connect = cb

    @staticmethod
    def is_running(is_fm: bool = False) -> bool:
        port = VARA_FM_CMD if is_fm else VARA_HF_CMD
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex((LOCALHOST, port))
            s.close()
            return result == 0
        except Exception:
            return False
