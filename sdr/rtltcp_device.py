from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- sdr/rtltcp_device.py
RTL-TCP client — the easy Windows path.

rtl_tcp.exe ships with every RTL-SDR Windows package.
No CMake, no Visual Studio, no SoapySDR needed.
Just run rtl_tcp.exe, then connect from Squelch.

rtl_tcp protocol:
  Server listens on TCP (default localhost:1234)
  Client sends 5-byte command packets:
    byte 0:   command code
    bytes 1-4: uint32 big-endian argument
  Server streams raw uint8 IQ samples (I, Q, I, Q...)
  Samples are offset-binary: 127.5 = DC, 0-255 range

Commands:
  0x01  Set center frequency (Hz)
  0x02  Set sample rate (SPS)
  0x03  Set gain mode (0=auto, 1=manual)
  0x04  Set gain (tenths of dB, e.g. 300 = 30.0 dB)
  0x05  Set frequency correction (PPM)
  0x06  Set IF gain (stage 1-6, gain value)
  0x07  Set test mode (0=off)
  0x08  Set AGC mode (0=off, 1=on)
  0x0E  Set direct sampling (0=off, 1=I, 2=Q)
  0x0F  Set offset tuning (0=off, 1=on)

Download rtl_tcp:
  Airspy rtlsdr release (recommended):
    github.com/airspy/airspyone_host/releases
  Osmocom rtl-sdr Windows builds:
    ftp.osmocom.org/binaries/windows/rtl-sdr/
"""

import logging
import socket
import struct
import threading

log = logging.getLogger(__name__)

RTL_TCP_HOST    = "127.0.0.1"
RTL_TCP_PORT    = 1234
CHUNK_SIZE      = 65536    # uint8 IQ bytes per read
MAX_QUEUE       = 8        # ring buffer depth

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# Command codes
CMD_SET_FREQ      = 0x01
CMD_SET_RATE      = 0x02
CMD_SET_GAIN_MODE = 0x03
CMD_SET_GAIN      = 0x04
CMD_SET_PPM       = 0x05
CMD_SET_AGC       = 0x08


class RTLTCPDevice:
    """
    RTL-SDR via rtl_tcp server.
    Works without SoapySDR — just needs rtl_tcp.exe running.

    Usage:
        dev = RTLTCPDevice()
        dev.open()                        # connect to rtl_tcp
        dev.set_center_freq(144_390_000)
        dev.set_sample_rate(2_048_000)
        dev.set_gain(30.0)
        dev.start_rx()                    # begin streaming
        dev.on_samples = my_callback      # samples as CF32
        ...
        dev.stop_rx()
        dev.close()
    """

    def __init__(self, host: str = RTL_TCP_HOST,
                 port: int = RTL_TCP_PORT):
        self._host        = host
        self._port        = port
        self._sock        = None
        self._running     = False
        self._thread      = None
        self._on_samples  = None

        # State
        self._center_hz   = 100_000_000
        self._sample_rate = 2_048_000
        self._gain_db     = 30.0
        self._ppm         = 0
        self._agc         = False

        # Streaming stats
        self.bytes_received = 0
        self.samples_delivered = 0

    # ── Connection ────────────────────────────────────────────

    def open(self) -> bool:
        """
        Connect to rtl_tcp server.
        Returns False if rtl_tcp is not running.
        """
        try:
            self._sock = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(5.0)
            self._sock.connect((self._host, self._port))

            # Read the 12-byte magic header
            # "RTL0" + tuner type (4 bytes) + gain count (4 bytes)
            header = self._sock.recv(12)
            if len(header) >= 4:
                magic = header[:4].decode("ascii",
                                          errors="replace")
                if magic.startswith("RTL"):
                    log.info(
                        f"RTL-TCP connected: "
                        f"{self._host}:{self._port}")
                else:
                    log.warning(
                        f"RTL-TCP unexpected header: "
                        f"{header!r}")

            self._sock.settimeout(2.0)
            return True

        except ConnectionRefusedError:
            log.warning(
                f"RTL-TCP: connection refused at "
                f"{self._host}:{self._port}\n"
                "Is rtl_tcp running? "
                "Start it with: rtl_tcp.exe")
            self._sock = None
            return False
        except Exception as e:
            log.warning(f"RTL-TCP connect: {e}")
            self._sock = None
            return False

    def close(self):
        self.stop_rx()
        try:
            if self._sock:
                self._sock.close()
        except Exception:
            pass
        self._sock = None

    @property
    def is_connected(self) -> bool:
        return self._sock is not None

    # ── Commands ──────────────────────────────────────────────

    def _send_cmd(self, cmd: int, arg: int):
        """Send a 5-byte command to rtl_tcp."""
        if not self._sock:
            return
        try:
            packet = struct.pack(">BI", cmd, arg)
            self._sock.sendall(packet)
        except Exception as e:
            log.debug(f"RTL-TCP cmd 0x{cmd:02x}: {e}")

    def set_center_freq(self, freq_hz: int):
        """Set tuner center frequency in Hz."""
        self._center_hz = int(freq_hz)
        self._send_cmd(CMD_SET_FREQ, self._center_hz)
        log.debug(f"RTL-TCP freq: {freq_hz/1e6:.3f}MHz")

    def set_sample_rate(self, rate: int):
        """
        Set sample rate.
        Supported rates: 225001–300000, 900001–3200000 SPS.
        2048000 and 2400000 are most stable.
        """
        self._sample_rate = int(rate)
        self._send_cmd(CMD_SET_RATE, self._sample_rate)
        log.debug(f"RTL-TCP rate: {rate/1e6:.3f}MSPS")

    def set_gain(self, gain_db: float):
        """
        Set manual tuner gain.
        Disables AGC automatically.
        """
        self._gain_db = float(gain_db)
        self._agc     = False
        # Gain mode: 1 = manual
        self._send_cmd(CMD_SET_GAIN_MODE, 1)
        # Gain in tenths of dB
        self._send_cmd(CMD_SET_GAIN,
                       int(gain_db * 10))

    def set_auto_gain(self, enable: bool = True):
        """Enable or disable automatic gain control."""
        self._agc = enable
        self._send_cmd(CMD_SET_GAIN_MODE,
                       0 if enable else 1)
        self._send_cmd(CMD_SET_AGC,
                       1 if enable else 0)

    def set_ppm(self, ppm: int):
        """Set frequency correction in PPM."""
        self._ppm = int(ppm)
        # rtl_tcp expects signed int as unsigned
        self._send_cmd(CMD_SET_PPM,
                       ppm & 0xFFFFFFFF)

    # ── Streaming ─────────────────────────────────────────────

    def start_rx(self):
        """Start receiving IQ samples."""
        if self._running or not self._sock:
            return
        self._running = True
        self._thread  = threading.Thread(
            target=self._rx_loop,
            daemon=True, name="RTLTCPRx")
        self._thread.start()

    def stop_rx(self):
        self._running = False

    def _rx_loop(self):
        """
        Receive uint8 IQ pairs from rtl_tcp and
        convert to CF32 numpy arrays before delivery.
        """
        buf = bytearray()
        target = CHUNK_SIZE  # bytes per callback

        while self._running and self._sock:
            try:
                data = self._sock.recv(4096)
                if not data:
                    log.warning("RTL-TCP: server closed")
                    break
                buf += data
                self.bytes_received += len(data)

                while len(buf) >= target:
                    chunk = bytes(buf[:target])
                    buf   = buf[target:]

                    if HAS_NUMPY and self._on_samples:
                        # Convert uint8 IQ → complex64
                        samples = self._to_cf32(chunk)
                        self.samples_delivered += len(
                            samples)
                        try:
                            self._on_samples(
                                samples,
                                self._sample_rate,
                                self._center_hz)
                        except Exception as e:
                            log.debug(
                                f"RTL-TCP callback: {e}")

            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    log.warning(f"RTL-TCP rx: {e}")
                break

        self._running = False
        log.info("RTL-TCP rx loop ended")

    @staticmethod
    def _to_cf32(raw: bytes):
        """
        Convert raw uint8 IQ bytes to complex float32.
        rtl_tcp IQ format: I0 Q0 I1 Q1 ... uint8
        Range 0-255, center at 127.5
        """
        arr = np.frombuffer(raw, dtype=np.uint8
                            ).astype(np.float32)
        arr = (arr - 127.5) / 127.5
        return (arr[0::2] +
                1j * arr[1::2]).astype(np.complex64)

    # ── Properties ────────────────────────────────────────────

    @property
    def on_samples(self):
        return self._on_samples

    @on_samples.setter
    def on_samples(self, cb):
        self._on_samples = cb

    @property
    def center_freq(self) -> int:
        return self._center_hz

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def display_name(self) -> str:
        return (f"RTL-TCP @ "
                f"{self._host}:{self._port}")


# ── Detection ─────────────────────────────────────────────────────────────

def rtltcp_is_running(host: str = RTL_TCP_HOST,
                       port: int = RTL_TCP_PORT) -> bool:
    """
    Quick check: is rtl_tcp listening on this port?
    Returns True in ~50ms if running, False otherwise.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        result = s.connect_ex((host, port))
        s.close()
        return result == 0
    except Exception:
        return False
