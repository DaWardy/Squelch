from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- modes/flrig_bridge.py
FLRig XML-RPC bridge.
FLRig is a free rig control server by W1HKJ.
It provides an XML-RPC API on localhost:12345.
Works as an alternative to rigctld for rigs
that FLRig supports better.
Download: w1hkj.com/files/flrig/
"""

import logging
import threading
import time
from typing import Callable

log = logging.getLogger(__name__)

FLRIG_HOST  = "localhost"
FLRIG_PORT  = 12345
FLRIG_URL   = f"http://{FLRIG_HOST}:{FLRIG_PORT}/RPC2"

try:
    # Patch xmlrpc to prevent XML injection attacks
    import defusedxml.xmlrpc
    defusedxml.xmlrpc.monkey_patch()
    import xmlrpc.client as xmlrpc  # nosec B411
    HAS_XMLRPC = True
except ImportError:
    try:
        # defusedxml not available - use stdlib but warn
        import xmlrpc.client as xmlrpc  # nosec B411
        import logging as _l
        _l.getLogger(__name__).warning(
            "defusedxml not installed — FLRig XML-RPC "
            "is unprotected. pip install defusedxml")
        HAS_XMLRPC = True
    except ImportError:
        HAS_XMLRPC = False


class FLRigBridge:
    """
    XML-RPC client for FLRig rig control server.
    Provides the same interface as RigController
    so it can be used as a drop-in backend.
    """

    def __init__(self, config):
        self.cfg       = config
        self._proxy    = None
        self._running  = False
        self._thread   = None
        self._callbacks: list[Callable] = []

    def connect(self) -> bool:
        if not HAS_XMLRPC:
            log.error("xmlrpc.client not available")
            return False
        try:
            self._proxy = xmlrpc.ServerProxy(
                FLRIG_URL, allow_none=True)
            # Test connection
            version = self._proxy.main.get_version()
            log.info(f"FLRig connected: v{version}")
            self._running = True
            self._thread  = threading.Thread(
                target=self._poll_loop,
                daemon=True, name="FLRigPoll")
            self._thread.start()
            return True
        except Exception as e:
            log.warning(f"FLRig connect: {e}")
            return False

    def disconnect(self):
        self._running = False
        self._proxy   = None

    @property
    def is_connected(self) -> bool:
        return self._running and self._proxy is not None

    # ── Rig control methods ──────────────────────────────────

    def get_freq(self) -> int:
        try:
            return int(self._proxy.rig.get_vfo())
        except Exception:
            return 0

    def set_freq(self, freq_hz: int):
        try:
            self._proxy.rig.set_vfo(float(freq_hz))
        except Exception as e:
            log.debug(f"FLRig set_freq: {e}")

    def get_mode(self) -> str:
        try:
            return str(self._proxy.rig.get_mode())
        except Exception:
            return ""

    def set_mode(self, mode: str, passband: int = 0):
        try:
            self._proxy.rig.set_mode(mode)
            if passband:
                self._proxy.rig.set_bw(str(passband))
        except Exception as e:
            log.debug(f"FLRig set_mode: {e}")

    def set_ptt(self, tx: bool):
        try:
            self._proxy.rig.set_ptt(1 if tx else 0)
        except Exception as e:
            log.debug(f"FLRig set_ptt: {e}")

    def get_smeter(self) -> int:
        try:
            s = self._proxy.rig.get_smeter()
            return int(float(s))
        except Exception:
            return 0

    def get_power(self) -> int:
        """Get TX power level (0-100)."""
        try:
            return int(self._proxy.rig.get_power())
        except Exception:
            return 0

    def set_power(self, pct: int):
        """Set TX power level (0-100)."""
        try:
            self._proxy.rig.set_power(
                max(0, min(100, pct)))
        except Exception as e:
            log.debug(f"FLRig set_power: {e}")

    # ── Poll loop ─────────────────────────────────────────────

    def _poll_loop(self):
        interval = self.cfg.get(
            "rig.poll_interval_ms", 500) / 1000
        while self._running and self._proxy:
            try:
                freq  = self.get_freq()
                mode  = self.get_mode()
                meter = self.get_smeter()
                self._notify(freq, mode, meter)
            except Exception as e:
                log.debug(f"FLRig poll: {e}")
            time.sleep(interval)

    def _notify(self, freq: int, mode: str,
                smeter: int):
        for cb in self._callbacks:
            try:
                cb(freq, mode, smeter)
            except Exception:
                pass

    def on_state_change(self, cb: Callable):
        self._callbacks.append(cb)

    @staticmethod
    def is_running() -> bool:
        """Check if FLRig is running on localhost."""
        try:
            import socket
            s = socket.socket()
            s.settimeout(0.5)
            result = s.connect_ex(
                (FLRIG_HOST, FLRIG_PORT))
            s.close()
            return result == 0
        except Exception:
            return False
