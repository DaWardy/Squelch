from __future__ import annotations
"""WinKeyer USB serial-port CW keyer client.

Implements the minimal WinKeyer 3 host-mode protocol over a serial port
(default 1200 baud 8N1).  Falls back gracefully if pyserial is not installed.

Typical usage:
    wk = WinKeyerClient()
    if wk.connect("COM3"):
        wk.set_speed(20)
        wk.send_text("CQ CQ DE W1AW K")
        ...
        wk.disconnect()

WinKeyer command bytes used here:
    0x00 len  — Admin (sub-command follows)
    0x02 wpm  — Set speed
    0x04      — Send text (followed by ASCII bytes)
    0x0A      — Clear transmit buffer (abort)

Admin sub-commands:
    0x02      — Open (host mode)
    0x03      — Close
"""
import logging
import threading

log = logging.getLogger(__name__)

try:
    import serial as _serial      # type: ignore
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

BAUD_RATE = 1200


class WinKeyerClient:
    """Minimal WinKeyer USB host-mode interface."""

    def __init__(self):
        self._port = None
        self._lock = threading.Lock()

    @property
    def is_connected(self) -> bool:
        return self._port is not None

    def connect(self, port: str) -> bool:
        """Open serial connection to WinKeyer. Return True on success."""
        if not HAS_SERIAL:
            log.warning("WinKeyer: pyserial not installed — "
                        "install with: pip install pyserial")
            return False
        try:
            ser = _serial.Serial(port, BAUD_RATE, timeout=1.0)
            # Send Admin Open (host mode)
            ser.write(bytes([0x00, 0x02]))
            with self._lock:
                self._port = ser
            log.info(f"WinKeyer: connected on {port}")
            return True
        except Exception as e:
            log.warning(f"WinKeyer connect failed ({port}): {e}")
            return False

    def disconnect(self) -> None:
        with self._lock:
            if self._port:
                try:
                    self._port.write(bytes([0x00, 0x03]))  # Admin Close
                    self._port.close()
                except Exception:
                    pass
                self._port = None
        log.info("WinKeyer: disconnected")

    def set_speed(self, wpm: int) -> bool:
        """Set CW speed (5–99 WPM)."""
        with self._lock:
            if not self._port:
                return False
            try:
                self._port.write(bytes([0x02, max(5, min(99, int(wpm)))]))
                return True
            except Exception as e:
                log.warning(f"WinKeyer set_speed: {e}")
                self._port = None
                return False

    def send_text(self, text: str) -> bool:
        """Queue ASCII text for CW transmission."""
        with self._lock:
            if not self._port:
                return False
            try:
                payload = text.upper().encode("ascii", errors="ignore")
                self._port.write(bytes([0x04]) + payload)
                return True
            except Exception as e:
                log.warning(f"WinKeyer send_text: {e}")
                self._port = None
                return False

    def stop(self) -> bool:
        """Abort current transmission immediately."""
        with self._lock:
            if not self._port:
                return False
            try:
                self._port.write(bytes([0x0A]))   # Clear buffer
                return True
            except Exception:
                return False
