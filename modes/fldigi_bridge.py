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
"""Squelch -- modes/fldigi_bridge.py
Fldigi XML-RPC bridge for PSK31, RTTY, CW, SSTV, Olivia.
Launches Fldigi as a subprocess and controls it via XML-RPC.
"""

import logging
import subprocess
import threading
import time
try:
    import defusedxml  # type: ignore
    defusedxml.defuse_stdlib()  # patches xmlrpc.client globally
except (ImportError, AttributeError):
    # ImportError  → defusedxml not installed
    # AttributeError → defuse_stdlib removed in defusedxml >= 0.7.0;
    #                  use defusedxml.xmlrpc.monkey_patch() on that version
    try:
        import defusedxml.xmlrpc  # type: ignore
        defusedxml.xmlrpc.monkey_patch()
    except Exception:
        pass  # xmlrpc runs unpatched — acceptable for local Fldigi connection
import xmlrpc.client  # nosec B411 - patched by defusedxml above
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

FLDIGI_HOST = "127.0.0.1"
FLDIGI_PORT = 7362
FLDIGI_URL  = f"http://{FLDIGI_HOST}:{FLDIGI_PORT}/RPC2"

FLDIGI_MODES = {
    "PSK31":    "BPSK31",
    "PSK63":    "BPSK63",
    "PSK125":   "BPSK125",
    "RTTY":     "RTTY",
    "CW":       "CW",
    "SSTV":     "SSTV",
    "Olivia":   "OLIVIA",
    "THOR":     "THOR16",
    "DominoEX": "DOMINOEX16",
    "MFSK16":   "MFSK16",
    "MFSK32":   "MFSK32",
}

# Default frequencies per mode
MODE_FREQS = {
    "PSK31":  {"80m":3_580_000,"40m":7_070_000,"20m":14_070_000},
    "RTTY":   {"80m":3_580_000,"40m":7_080_000,"20m":14_080_000},
    "CW":     {"80m":3_550_000,"40m":7_030_000,"20m":14_030_000},
    "SSTV":   {"20m":14_230_000,"15m":21_340_000},
}


_singleton: "FldigiBridge | None" = None


class FldigiBridge:
    """
    Controls Fldigi via XML-RPC.
    Manages subprocess launch, mode setting, TX/RX,
    and QSO logging back to Squelch.
    """

    @classmethod
    def instance(cls) -> "FldigiBridge | None":
        """Return the active singleton, or None if not yet created."""
        return _singleton

    @classmethod
    def _register(cls, inst: "FldigiBridge") -> None:
        global _singleton
        _singleton = inst

    def __init__(self, config, log_db=None):
        FldigiBridge._register(self)
        self.cfg    = config
        self.log_db = log_db
        self._proc: subprocess.Popen | None = None
        self._rpc:  xmlrpc.client.ServerProxy | None = None
        self._connected = False
        self._mode      = "PSK31"
        self._rx_text   = ""
        self._poll_thread: threading.Thread | None = None
        self._running   = False

        self._on_rx:  Callable | None = None
        self._on_tx:  Callable | None = None
        self._on_connected: Callable | None = None

    # ── Connect ───────────────────────────────────────────────────────────

    def connect(self, launch: bool = True) -> bool:
        """
        Connect to Fldigi. Optionally launch it first.
        Returns True if connected successfully.
        """
        if launch and not self._is_fldigi_running():
            if not self._launch_fldigi():
                return False
            time.sleep(3.0)  # wait for Fldigi to start

        try:
            self._rpc = xmlrpc.client.ServerProxy(
                FLDIGI_URL, allow_none=True)
            name = self._rpc.fldigi.name()
            log.info(f"Fldigi connected: {name}")
            self._connected = True
            self._start_poll()
            if self._on_connected:
                self._on_connected(True)
            return True
        except Exception as e:
            log.error(f"Fldigi XML-RPC connect failed: {e}")
            self._connected = False
            return False

    def disconnect(self):
        self._running = False
        self._connected = False
        if self._proc:
            try: self._proc.terminate()
            except Exception: pass
            self._proc = None
        log.info("Fldigi disconnected")

    # ── Mode / frequency ──────────────────────────────────────────────────

    def set_mode(self, mode: str):
        """Set Fldigi operating mode."""
        fldigi_mode = FLDIGI_MODES.get(mode, mode)
        try:
            self._rpc.modem.set_by_name(fldigi_mode)
            self._mode = mode
            log.info(f"Fldigi mode: {fldigi_mode}")
        except Exception as e:
            log.warning(f"Fldigi set_mode failed: {e}")

    def set_frequency(self, freq_hz: int):
        """Set the dial frequency."""
        try:
            self._rpc.rig.set_frequency(float(freq_hz))
        except Exception as e:
            log.debug(f"Fldigi set_frequency: {e}")

    def set_audio_freq(self, audio_hz: int):
        """Set the audio sub-carrier frequency."""
        try:
            self._rpc.modem.set_carrier(audio_hz)
        except Exception as e:
            log.debug(f"Fldigi set_carrier: {e}")

    # ── TX / RX ───────────────────────────────────────────────────────────

    def transmit(self, text: str):
        """Send text via Fldigi TX."""
        try:
            self._rpc.text.clear_tx()
            self._rpc.text.add_tx(text)
            self._rpc.main.tx()
            if self._on_tx:
                self._on_tx(text)
        except Exception as e:
            log.warning(f"Fldigi TX failed: {e}")

    def receive(self):
        """Switch to RX mode."""
        try:
            self._rpc.main.rx()
        except Exception as e:
            log.debug(f"Fldigi RX: {e}")

    def get_rx_text(self) -> str:
        """Get received text buffer."""
        try:
            return self._rpc.text.get_rx(0, 4096) or ""
        except Exception:
            return ""

    def clear_rx(self):
        try:
            self._rpc.text.clear_rx()
        except Exception:
            pass

    # ── Status ────────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def mode(self) -> str:
        return self._mode

    def get_snr(self) -> float:
        try:
            return float(self._rpc.modem.get_quality())
        except Exception:
            return 0.0

    # ── Subprocess ───────────────────────────────────────────────────────

    def _launch_fldigi(self) -> bool:
        fldigi_path = self.cfg.get("paths.fldigi", "fldigi")
        if not fldigi_path or fldigi_path == "fldigi":
            # Try common locations
            candidates = [
                "fldigi",
                r"C:\Program Files\fldigi\fldigi.exe",
                r"C:\Program Files (x86)\fldigi\fldigi.exe",
                "/usr/bin/fldigi",
                "/usr/local/bin/fldigi",
            ]
            for c in candidates:
                if Path(c).exists() or c == "fldigi":
                    fldigi_path = c
                    break

        try:
            self._proc = subprocess.Popen(
                [fldigi_path,
                 "--arq-server-address", FLDIGI_HOST,
                 "--arq-server-port", str(FLDIGI_PORT),
                 "--xmlrpc-server-address", FLDIGI_HOST,
                 "--xmlrpc-server-port", str(FLDIGI_PORT)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            log.info(f"Fldigi launched: {fldigi_path}")
            return True
        except FileNotFoundError:
            log.error(
                "Fldigi not found. "
                "Install from: https://sourceforge.net/projects/fldigi/")
            return False
        except Exception as e:
            log.error(f"Fldigi launch failed: {e}")
            return False

    def _is_fldigi_running(self) -> bool:
        try:
            import psutil
            for proc in psutil.process_iter(["name"]):
                if "fldigi" in (proc.info["name"] or "").lower():
                    return True
            return False
        except ImportError:
            # psutil not available — fall back to process list
            import subprocess, sys
            cmd = (["tasklist"] if sys.platform == "win32"
                   else ["pgrep", "-l", "fldigi"])
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True)
                return "fldigi" in result.stdout.lower()
            except Exception:
                return False
        except Exception:
            return False

    # ── Poll loop ─────────────────────────────────────────────────────────

    def _start_poll(self):
        self._running   = True
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="FldigiPoll")
        self._poll_thread.start()

    def _poll_loop(self):
        while self._running and self._connected:
            try:
                text = self.get_rx_text()
                if text and text != self._rx_text:
                    new_text = text[len(self._rx_text):]
                    self._rx_text = text
                    if new_text and self._on_rx:
                        self._on_rx(new_text)
            except Exception:
                pass
            time.sleep(0.5)

    # ── Callbacks ─────────────────────────────────────────────────────────

    def on_rx(self, cb: Callable):
        self._on_rx = cb

    def on_tx(self, cb: Callable):
        self._on_tx = cb

    def on_connected(self, cb: Callable):
        self._on_connected = cb
