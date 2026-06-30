from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""Squelch -- core/gps.py
Live position source for the station grid/lat/lon.

Two optional backends, both degrade gracefully when their dependency or
hardware is absent:

  * **Windows Location API** (WinRT ``Windows.Devices.Geolocation``) — a
    one-shot OS position read.  Requests access and returns ``None`` cleanly
    when the user denies it or the package/runtime is unavailable.
  * **NMEA-over-serial GPS** — reads ``$GPGGA`` / ``$GPRMC`` sentences from a
    serial port via pyserial in a daemon thread and delivers each parsed fix
    through a Qt signal (``fix_received``).  Workers NEVER touch the GUI
    directly and never use ``QTimer.singleShot`` from the read thread.

The NMEA parsing is pure (no hardware, no Qt) so it is fully unit-tested.

This feeds ``core.location.LocationManager`` and ties into ROADMAP Phase 3
(direction finding — DF-RSSI-GPS), which needs a live position source.
"""
import logging
import threading

log = logging.getLogger(__name__)

try:
    import serial as _serial                       # type: ignore
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

# 4800 baud 8N1 is the classic NMEA-0183 default; newer USB pucks use 9600.
DEFAULT_BAUD = 4800
COMMON_BAUDS = [4800, 9600, 19200, 38400, 57600, 115200]
_READ_TIMEOUT_S = 1.0          # so the read loop wakes to check the stop flag


# ── NMEA parsing (pure — no hardware, no Qt) ───────────────────────────────

from dataclasses import dataclass
from typing import Optional


@dataclass
class GPSFix:
    """A single position fix from any backend."""
    lat:         float
    lon:         float
    fix_quality: int            = 1     # 0=invalid, 1=GPS, 2=DGPS
    satellites:  int            = 0
    altitude_m:  Optional[float] = None
    utc:         str            = ""
    source:      str            = "gps"
    valid:       bool           = True

    @property
    def grid(self) -> str:
        """Maidenhead grid for this fix (uses core.location math)."""
        try:
            from core.location import _latlon_to_grid
            return _latlon_to_grid(self.lat, self.lon)
        except Exception:
            return ""


def nmea_checksum_ok(sentence: str) -> bool:
    """Validate the ``*HH`` XOR checksum of an NMEA sentence.

    Sentences without a ``*`` checksum are treated as valid (some receivers
    omit it); a present-but-wrong checksum returns False.
    """
    s = sentence.strip()
    if s.startswith("$"):
        s = s[1:]
    if "*" not in s:
        return True
    body, _, csum = s.partition("*")
    csum = csum.strip()[:2]
    if len(csum) < 2:
        return False
    calc = 0
    for ch in body:
        calc ^= ord(ch)
    try:
        return calc == int(csum, 16)
    except ValueError:
        return False


def nmea_to_decimal(raw: str, hemi: str) -> Optional[float]:
    """Convert an NMEA ``ddmm.mmmm`` (or ``dddmm.mmmm``) field to decimal degrees.

    ``hemi`` is one of N/S/E/W; S and W return a negative value.  Returns None
    if the field is empty or unparseable.
    """
    if not raw:
        return None
    try:
        v = float(raw)
    except ValueError:
        return None
    deg = int(v // 100)
    minutes = v - deg * 100
    dec = deg + minutes / 60.0
    if hemi.upper() in ("S", "W"):
        dec = -dec
    return dec


def _split_nmea(sentence: str) -> Optional[list[str]]:
    """Return the comma-split fields of a checksum-valid sentence, or None."""
    s = sentence.strip()
    if not s.startswith("$") or not nmea_checksum_ok(s):
        return None
    body = s[1:].split("*", 1)[0]
    return body.split(",")


def parse_gpgga(sentence: str) -> Optional[GPSFix]:
    """Parse a $--GGA sentence (any talker: GP/GN/GL/GA…) to a GPSFix."""
    f = _split_nmea(sentence)
    if not f or len(f) < 10 or not f[0].endswith("GGA"):
        return None
    try:
        quality = int(f[6]) if f[6] else 0
    except ValueError:
        quality = 0
    lat = nmea_to_decimal(f[2], f[3])
    lon = nmea_to_decimal(f[4], f[5])
    if lat is None or lon is None or quality == 0:
        return None
    try:
        sats = int(f[7]) if f[7] else 0
    except ValueError:
        sats = 0
    try:
        alt = float(f[9]) if f[9] else None
    except ValueError:
        alt = None
    return GPSFix(lat=lat, lon=lon, fix_quality=quality, satellites=sats,
                  altitude_m=alt, utc=f[1], source="gps", valid=True)


def parse_gprmc(sentence: str) -> Optional[GPSFix]:
    """Parse a $--RMC sentence to a GPSFix (only when status is 'A' = valid)."""
    f = _split_nmea(sentence)
    if not f or len(f) < 7 or not f[0].endswith("RMC"):
        return None
    if (f[2] or "").upper() != "A":
        return None      # 'V' = navigation receiver warning (no valid fix)
    lat = nmea_to_decimal(f[3], f[4])
    lon = nmea_to_decimal(f[5], f[6])
    if lat is None or lon is None:
        return None
    return GPSFix(lat=lat, lon=lon, fix_quality=1, utc=f[1],
                  source="gps", valid=True)


def parse_nmea(sentence: str) -> Optional[GPSFix]:
    """Parse one NMEA line into a GPSFix, dispatching on sentence type.

    Returns None for unsupported types, malformed input, or 'no fix'.
    """
    if not sentence:
        return None
    head = sentence.strip()[:6].upper()
    if head.endswith("GGA"):
        return parse_gpgga(sentence)
    if head.endswith("RMC"):
        return parse_gprmc(sentence)
    return None


# ── Windows Location API (WinRT) ───────────────────────────────────────────

def windows_location_available() -> bool:
    """True if a WinRT geolocation package (winsdk or winrt) is importable."""
    for mod in ("winsdk.windows.devices.geolocation",
                "winrt.windows.devices.geolocation"):
        try:
            __import__(mod)
            return True
        except Exception:
            continue
    return False


def _import_geolocation():
    """Return the WinRT geolocation module (winsdk preferred), or None."""
    for mod in ("winsdk.windows.devices.geolocation",
                "winrt.windows.devices.geolocation"):
        try:
            return __import__(mod, fromlist=["Geolocator"])
        except Exception:
            continue
    return None


def _coord_to_fix(coord) -> Optional[GPSFix]:
    """Extract lat/lon/alt from a WinRT Geocoordinate (handling API versions)."""
    lat = lon = None
    alt = None
    # Win10+ nests under .point.position; older builds expose flat attributes.
    point = getattr(coord, "point", None)
    pos = getattr(point, "position", None) if point is not None else None
    if pos is not None:
        lat = getattr(pos, "latitude", None)
        lon = getattr(pos, "longitude", None)
        alt = getattr(pos, "altitude", None)
    if lat is None or lon is None:
        lat = getattr(coord, "latitude", None)
        lon = getattr(coord, "longitude", None)
    if lat is None or lon is None:
        return None
    return GPSFix(lat=float(lat), lon=float(lon),
                  altitude_m=float(alt) if alt is not None else None,
                  source="windows", valid=True)


def get_windows_fix(timeout_s: float = 10.0) -> Optional[GPSFix]:
    """One-shot read of the OS location via the Windows Location API.

    Returns a GPSFix, or None if the package/runtime is missing, the user
    denied access, or the read times out.  Never raises.
    """
    geo = _import_geolocation()
    if geo is None:
        log.debug("Windows location: WinRT geolocation package not available")
        return None
    try:
        import asyncio

        async def _read():
            access = await geo.Geolocator.request_access_async()
            allowed = getattr(geo.GeolocationAccessStatus, "ALLOWED", None)
            if allowed is not None and access != allowed:
                log.info("Windows location access not granted by user")
                return None
            locator = geo.Geolocator()
            position = await locator.get_geoposition_async()
            return _coord_to_fix(position.coordinate)

        return asyncio.run(asyncio.wait_for(_read(), timeout=timeout_s))
    except Exception as e:
        log.debug(f"Windows location read failed: {e}")
        return None


# ── Serial-port enumeration ────────────────────────────────────────────────

def list_serial_ports() -> list[str]:
    """Return available serial port device names (empty if pyserial absent)."""
    if not HAS_SERIAL:
        return []
    try:
        from serial.tools import list_ports
        return [p.device for p in list_ports.comports()]
    except Exception:
        return []


# ── Signal plumbing (Qt when present, lightweight shim otherwise) ───────────

try:
    from PyQt6.QtCore import QObject, pyqtSignal
    _HAS_QT = True
except Exception:                       # pragma: no cover - headless test path
    _HAS_QT = False


class _FallbackSignal:
    """Minimal connect/emit shim used when PyQt6 is unavailable (headless).

    Keeps the worker API identical to the Qt build so the read loop can be
    tested without Qt installed.
    """

    def __init__(self):
        self._subs: list = []

    def connect(self, fn):
        self._subs.append(fn)

    def emit(self, *args):
        for fn in list(self._subs):
            try:
                fn(*args)
            except Exception as e:
                log.debug(f"GPS signal callback: {e}")


class _SerialReadLoop:
    """Shared NMEA-over-serial read loop.

    Subclasses provide ``fix_received`` and ``error_occurred`` signals (either
    real pyqtSignals or _FallbackSignal).  The loop runs in a daemon thread,
    parses each line, and emits valid fixes.  ``readline`` uses a 1 s timeout
    so ``stop()`` is honoured promptly.
    """

    def __init__(self):
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._serial = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, port: str, baud: int = DEFAULT_BAUD) -> bool:
        """Open *port* and begin reading. Returns False if it cannot start."""
        if not HAS_SERIAL:
            self._emit_error("pyserial not installed — GPS serial unavailable")
            return False
        if not port:
            self._emit_error("No serial port selected")
            return False
        if self.is_running:
            return True
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, args=(port, int(baud)),
            daemon=True, name="gps-serial")
        self._thread.start()
        return True

    def stop(self) -> None:
        """Signal the read loop to exit and wait briefly for the thread."""
        self._stop.set()
        try:
            if self._serial is not None:
                self._serial.close()        # unblock a pending readline
        except Exception as e:
            log.debug(f"GPS serial close on stop: {e}")
        t = self._thread
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=2.0)
        self._thread = None

    def _run(self, port: str, baud: int) -> None:
        try:
            self._serial = _serial.Serial(port, baud, timeout=_READ_TIMEOUT_S)
        except Exception as e:
            self._emit_error(f"GPS serial open failed ({port}): {e}")
            return
        log.info(f"GPS serial: reading NMEA on {port} @ {baud}")
        try:
            while not self._stop.is_set():
                try:
                    raw = self._serial.readline()
                except Exception as e:
                    self._emit_error(f"GPS serial read error: {e}")
                    break
                if not raw:
                    continue            # timeout tick — re-check stop flag
                try:
                    line = raw.decode("ascii", errors="ignore").strip()
                except Exception:
                    continue
                fix = parse_nmea(line)
                if fix is not None and fix.valid:
                    self._emit_fix(fix)
        finally:
            try:
                if self._serial is not None:
                    self._serial.close()
            except Exception as e:
                log.debug(f"GPS serial close: {e}")
            self._serial = None
            log.info("GPS serial: read loop stopped")

    def _emit_fix(self, fix: GPSFix) -> None:
        self.fix_received.emit(fix)

    def _emit_error(self, msg: str) -> None:
        log.debug(msg)
        self.error_occurred.emit(msg)


if _HAS_QT:

    class SerialGPSReader(_SerialReadLoop, QObject):
        """NMEA-over-serial GPS reader. Emits ``fix_received(GPSFix)``."""
        fix_received = pyqtSignal(object)
        error_occurred = pyqtSignal(str)

        def __init__(self, parent=None):
            QObject.__init__(self, parent)
            _SerialReadLoop.__init__(self)

    class WindowsLocationWorker(QObject):
        """One-shot Windows Location API read, off the GUI thread."""
        fix_received = pyqtSignal(object)
        error_occurred = pyqtSignal(str)

        def __init__(self, parent=None):
            QObject.__init__(self, parent)

        def request_fix(self, timeout_s: float = 10.0) -> None:
            threading.Thread(
                target=self._run, args=(timeout_s,),
                daemon=True, name="gps-winloc").start()

        def _run(self, timeout_s: float) -> None:
            fix = get_windows_fix(timeout_s)
            if fix is not None:
                self.fix_received.emit(fix)
            else:
                self.error_occurred.emit(
                    "Windows location unavailable or access denied")

else:                                   # pragma: no cover - headless test path

    class SerialGPSReader(_SerialReadLoop):
        def __init__(self, parent=None):
            self.fix_received = _FallbackSignal()
            self.error_occurred = _FallbackSignal()
            _SerialReadLoop.__init__(self)

    class WindowsLocationWorker:
        def __init__(self, parent=None):
            self.fix_received = _FallbackSignal()
            self.error_occurred = _FallbackSignal()

        def request_fix(self, timeout_s: float = 10.0) -> None:
            threading.Thread(
                target=self._run, args=(timeout_s,),
                daemon=True, name="gps-winloc").start()

        def _run(self, timeout_s: float) -> None:
            fix = get_windows_fix(timeout_s)
            if fix is not None:
                self.fix_received.emit(fix)
            else:
                self.error_occurred.emit(
                    "Windows location unavailable or access denied")
