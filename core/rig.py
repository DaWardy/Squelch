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

"""
Squelch -- core/rig.py
IC-7100 (and any Hamlib rig) control via rigctld subprocess.
Auto COM detection, PTT, VFO, mode, preamp/att/filter, S-meter.
"""

import subprocess
import socket
import time
import logging
import threading
import serial.tools.list_ports
from enum import Enum
from typing import Optional, Callable
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

RIGCTLD_HOST    = "127.0.0.1"
RIGCTLD_PORT    = 4532
RIGCTLD_TIMEOUT = 2.0
IC7100_MODEL    = 370

MODES = ["USB", "LSB", "FM", "AM", "CW", "CW-R",
         "RTTY", "RTTY-R", "PKTUSB", "PKTLSB", "PKTFM", "DV"]

BAND_EDGES = {
    "160m": (1_800_000,    2_000_000),
    "80m":  (3_500_000,    4_000_000),
    "60m":  (5_330_500,    5_405_000),
    "40m":  (7_000_000,    7_300_000),
    "30m":  (10_100_000,  10_150_000),
    "20m":  (14_000_000,  14_350_000),
    "17m":  (18_068_000,  18_168_000),
    "15m":  (21_000_000,  21_450_000),
    "12m":  (24_890_000,  24_990_000),
    "10m":  (28_000_000,  29_700_000),
    "6m":   (50_000_000,  54_000_000),
    "2m":   (144_000_000, 148_000_000),
    "70cm": (420_000_000, 450_000_000),
}

SMETER_LABELS = [
    "S0","S1","S2","S3","S4","S5","S6","S7",
    "S8","S9","S9+10","S9+20","S9+40","S9+60"
]


class RigStatus(Enum):
    DISCONNECTED = "Disconnected"
    CONNECTING   = "Connecting..."
    CONNECTED    = "Connected"
    ERROR        = "Error"
    PTT_TX       = "TX"


@dataclass
class RigState:
    freq_hz:    int       = 14_074_000
    mode:       str       = "USB"
    ptt:        bool      = False
    status:     RigStatus = RigStatus.DISCONNECTED
    port:       str       = ""
    model:      str       = "IC-7100"
    power_pct:  int       = 100
    preamp:     int       = 0        # 0=off, 1=preamp1, 2=preamp2
    attenuator: int       = 0        # dB
    filter_num: int       = 1        # 1/2/3
    s_meter:    int       = 0        # 0-13
    band:       str       = "20m"
    lat:        float     = 0.0
    lon:        float     = 0.0
    grid:       str       = ""
    error_msg:  str       = ""


class RigController:
    """
    Controls any Hamlib rig via rigctld TCP socket.
    Spawns rigctld subprocess, polls rig state on background thread,
    fires callbacks on state changes.
    """

    def __init__(self, config):
        self.cfg   = config
        self.state = RigState()
        self._proc: Optional[subprocess.Popen] = None
        self._sock: Optional[socket.socket]    = None
        self._lock    = threading.Lock()
        self._poll_th: Optional[threading.Thread] = None
        self._running = False
        self._callbacks: list[Callable] = []

    # ── Connect / Disconnect ──────────────────────────────────────────────

    def connect(self, port: str = "AUTO") -> bool:
        self.state.status = RigStatus.CONNECTING
        self._notify()

        if port == "AUTO":
            port = self._detect_port()
            if not port:
                self._error(
                    "IC-7100 not detected on any serial port.\n\n"
                    "Check that:\n"
                    "  • USB cable is connected\n"
                    "  • IC-7100 is powered on\n"
                    "  • CP210x Universal Windows Driver is installed\n"
                    "    (CP210x Universal Windows Driver v11.5.0)\n"
                    "    https://www.silabs.com/documents/public/software/"
                    "CP210x_Universal_Windows_Driver.zip\n\n"
                    "Or select the COM port manually from the dropdown."
                )
                return False

        self.state.port = port
        self.cfg.set("rig.port", port)

        if not self._start_rigctld(port):
            return False

        time.sleep(1.2)

        if not self._open_socket():
            return False

        self.state.status = RigStatus.CONNECTED
        self._notify()
        self._start_poll()
        log.info(f"Rig connected on {port}")
        return True

    def disconnect(self):
        self._running = False
        try:
            self._set_ptt_raw(False)
        except Exception:
            pass
        if self._sock:
            try: self._sock.close()
            except Exception: pass
            self._sock = None
        if self._proc:
            try: self._proc.terminate()
            except Exception: pass
            self._proc = None
        self.state.status = RigStatus.DISCONNECTED
        self._notify()
        log.info("Rig disconnected.")

    # ── Commands ──────────────────────────────────────────────────────────

    def set_freq(self, freq_hz: int):
        if self._cmd(f"F {freq_hz}") is not None:
            self.state.freq_hz = freq_hz
            self.state.band = _freq_to_band(freq_hz)
            self._notify()

    def set_mode(self, mode: str, passband: int = 0):
        if self._cmd(f"M {mode} {passband}") is not None:
            self.state.mode = mode
            self._notify()

    def set_ptt(self, tx: bool):
        self._set_ptt_raw(tx)

    def set_preamp(self, level: int):
        """0=off, 1=Preamp1, 2=Preamp2"""
        if self._cmd(f"L PREAMP {level}") is not None:
            self.state.preamp = level
            self._notify()

    def set_attenuator(self, db: int):
        """0, 6, 12, 18 dB"""
        if self._cmd(f"L ATT {db}") is not None:
            self.state.attenuator = db
            self._notify()

    def set_filter(self, num: int):
        """1=FIL1, 2=FIL2, 3=FIL3"""
        if self._cmd(f"U FILTER {num}") is not None:
            self.state.filter_num = num
            self._notify()

    def get_freq(self) -> int:
        r = self._cmd("f")
        if r:
            try: return int(r.strip())
            except ValueError: pass
        return self.state.freq_hz

    def get_mode(self) -> str:
        r = self._cmd("m")
        if r:
            parts = r.strip().split("\n")
            if parts: return parts[0].strip()
        return self.state.mode

    def get_smeter(self) -> int:
        r = self._cmd("l STRENGTH")
        if r:
            try: return int(float(r.strip()))
            except ValueError: pass
        return 0

    # ── Port detection ────────────────────────────────────────────────────

    @staticmethod
    def list_ports() -> list[dict]:
        out = []
        for p in serial.tools.list_ports.comports():
            desc = (p.description or "").upper()
            likely = any(x in desc for x in
                         ["CP210", "FTDI", "CI-V", "IC-7100",
                          "USB SERIAL", "UART", "USB2.0"])
            out.append({
                "port": p.device,
                "description": p.description or "",
                "hwid": p.hwid or "",
                "likely_rig": likely,
            })
        return sorted(out, key=lambda x: (not x["likely_rig"], x["port"]))

    def _detect_port(self) -> Optional[str]:
        candidates = self.list_ports()
        log.info(f"Serial ports: {[p['port'] for p in candidates]}")
        for p in candidates:
            if p["likely_rig"]:
                log.info(f"Auto-detected: {p['port']} ({p['description']})")
                return p["port"]
        if candidates:
            log.warning(f"No obvious rig port; trying {candidates[0]['port']}")
            return candidates[0]["port"]
        return None

    # ── rigctld ───────────────────────────────────────────────────────────

    def _start_rigctld(self, port: str) -> bool:
        model  = self.cfg.get("rig.hamlib_model", IC7100_MODEL)
        baud   = self.cfg.get("rig.baud", 19200)
        binary = self.cfg.get("paths.hamlib_rigctld", "rigctld")
        cmd = [binary, "-m", str(model), "-r", port, "-s", str(baud),
               "-T", RIGCTLD_HOST, "-t", str(RIGCTLD_PORT),
               "--no-restore-ai"]
        log.info(f"Starting: {' '.join(cmd)}")
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except FileNotFoundError:
            self._error(
                "rigctld not found.\n\n"
                "Install Hamlib and add its bin\\ folder to your PATH.\n"
                "Download: https://github.com/Hamlib/Hamlib/releases\n\n"
                "After installing, REBOOT so the PATH change takes effect.\n"
                "Then try connecting again."
            )
            return False
        except Exception as e:
            self._error(str(e))
            return False

    # ── Socket ────────────────────────────────────────────────────────────

    def _open_socket(self) -> bool:
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(RIGCTLD_TIMEOUT)
            self._sock.connect((RIGCTLD_HOST, RIGCTLD_PORT))
            return True
        except Exception as e:
            self._error(f"Cannot connect to rigctld: {e}")
            return False

    def _cmd(self, command: str) -> Optional[str]:
        with self._lock:
            if not self._sock:
                return None
            try:
                self._sock.sendall((command + "\n").encode())
                response = b""
                while True:
                    chunk = self._sock.recv(1024)
                    if not chunk: break
                    response += chunk
                    if b"RPRT" in response or response.endswith(b"\n"):
                        break
                decoded = response.decode(errors="replace").strip()
                if decoded.startswith("RPRT 0"):
                    return ""
                if decoded.startswith("RPRT"):
                    log.debug(f"Rig cmd '{command}' -> {decoded}")
                    return None
                return decoded
            except socket.timeout:
                return None
            except Exception as e:
                log.error(f"Rig socket error: {e}")
                self._error(str(e))
                return None

    def _set_ptt_raw(self, tx: bool):
        val = "1" if tx else "0"
        method = self.cfg.get("rig.ptt_method", "CAT")
        if method == "CAT":
            self._cmd(f"T {val}")
        self.state.ptt    = tx
        self.state.status = RigStatus.PTT_TX if tx else RigStatus.CONNECTED
        self._notify()

    # ── Poll loop ─────────────────────────────────────────────────────────

    def _start_poll(self):
        self._running  = True
        self._poll_th  = threading.Thread(
            target=self._poll_loop, daemon=True, name="RigPoll")
        self._poll_th.start()

    def _poll_loop(self):
        interval = self.cfg.get("rig.poll_interval_ms", 500) / 1000.0
        while self._running:
            try:
                freq    = self.get_freq()
                mode    = self.get_mode()
                smeter  = self.get_smeter()
                if (freq   != self.state.freq_hz or
                    mode   != self.state.mode or
                    smeter != self.state.s_meter):
                    self.state.freq_hz = freq
                    self.state.mode    = mode
                    self.state.s_meter = smeter
                    self.state.band    = _freq_to_band(freq)
                    self._notify()
            except Exception as e:
                log.debug(f"Poll: {e}")
            time.sleep(interval)

    # ── Helpers ───────────────────────────────────────────────────────────

    def on_state_change(self, cb: Callable):
        self._callbacks.append(cb)

    def _notify(self):
        for cb in self._callbacks:
            try: cb(self.state)
            except Exception as e: log.debug(f"Rig cb error: {e}")

    def _error(self, msg: str):
        self.state.status    = RigStatus.ERROR
        self.state.error_msg = msg
        self._notify()

    @property
    def is_connected(self) -> bool:
        return self.state.status in (RigStatus.CONNECTED, RigStatus.PTT_TX)


def _freq_to_band(freq_hz: int) -> str:
    for band, (lo, hi) in BAND_EDGES.items():
        if lo <= freq_hz <= hi:
            return band
    return "OOB"
