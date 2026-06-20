from __future__ import annotations
"""Hamlib rotctld TCP client — antenna / rotor control.

Connects to a running ``rotctld -m <model> -r <device> -T 0.0.0.0 -t 4533``
daemon using the plain-text Hamlib protocol:

  \\p          → get position  (responds: az_deg\\nel_deg\\n)
  \\P az el    → set position
  \\K          → park rotator

All blocking I/O runs in a daemon thread; ``on_position`` callbacks are
called from that thread — wire them to the UI with QTimer.singleShot(0, …).
"""
import logging
import socket
import threading
import time
from typing import Callable

log = logging.getLogger(__name__)

_POLL_INTERVAL_S = 2.0
_TIMEOUT_S       = 3.0


class RotorController:
    """Thin Hamlib rotctld TCP client with background position polling."""

    def __init__(self, host: str = "localhost", port: int = 4533):
        self._host      = host
        self._port      = port
        self._sock: "socket.socket | None" = None
        self._lock      = threading.Lock()
        self._running   = False
        self._az: float = 0.0
        self._el: float = 0.0
        self._callbacks: list[Callable[[float, float], None]] = []

    # ── Public API ────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._sock is not None

    @property
    def az(self) -> float:
        return self._az

    @property
    def el(self) -> float:
        return self._el

    def on_position(self, cb: Callable[[float, float], None]) -> None:
        self._callbacks.append(cb)

    def connect(self, host: str = "", port: int = 0) -> bool:
        """Open TCP connection to rotctld. Return True on success."""
        if host:
            self._host = host
        if port:
            self._port = port
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(_TIMEOUT_S)
            s.connect((self._host, self._port))
            with self._lock:
                self._sock = s
            self._running = True
            threading.Thread(target=self._poll_loop, daemon=True,
                             name="RotorPoll").start()
            log.info(f"Rotor: connected to {self._host}:{self._port}")
            return True
        except OSError as e:
            log.warning(f"Rotor connect failed: {e}")
            return False

    def disconnect(self) -> None:
        self._running = False
        with self._lock:
            if self._sock:
                try:
                    self._sock.close()
                except OSError:
                    pass
                self._sock = None
        log.info("Rotor: disconnected")

    def set_position(self, az: float, el: float = 0.0) -> bool:
        """Send \\P az el to rotctld. Return True on success."""
        az = max(0.0, min(360.0, float(az)))
        el = max(0.0, min(180.0, float(el)))
        return self._send(f"\\P {az:.1f} {el:.1f}\n")

    def park(self) -> bool:
        """Send the park command (\\K)."""
        return self._send("\\K\n")

    # ── Internal ──────────────────────────────────────────────────────────

    def _send(self, cmd: str) -> bool:
        with self._lock:
            if not self._sock:
                return False
            try:
                self._sock.sendall(cmd.encode())
                return True
            except OSError as e:
                log.warning(f"Rotor send error: {e}")
                self._sock = None
                return False

    def _get_position(self) -> "tuple[float, float] | None":
        """Send \\p and parse az/el response."""
        with self._lock:
            if not self._sock:
                return None
            try:
                self._sock.sendall(b"\\p\n")
                data = b""
                while len(data) < 4:
                    chunk = self._sock.recv(256)
                    if not chunk:
                        break
                    data += chunk
                    if data.count(b"\n") >= 2:
                        break
                lines = data.decode(errors="ignore").strip().splitlines()
                if len(lines) >= 2 and not lines[0].startswith("RPRT"):
                    return float(lines[0]), float(lines[1])
            except (OSError, ValueError):
                self._sock = None
            return None

    def _poll_loop(self) -> None:
        while self._running:
            pos = self._get_position()
            if pos:
                self._az, self._el = pos
                for cb in list(self._callbacks):
                    try:
                        cb(self._az, self._el)
                    except Exception:
                        pass
            elif not self._sock:
                self._running = False
                break
            time.sleep(_POLL_INTERVAL_S)
