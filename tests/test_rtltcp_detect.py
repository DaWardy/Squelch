from __future__ import annotations
# Squelch — RF / SDR signal platform
# Licensed under GNU GPL v3 — see LICENSE
"""Tests for rtl_tcp liveness detection (sdr/rtltcp_device.rtltcp_is_running)."""
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from sdr.rtltcp_device import rtltcp_is_running


def _free_port_listener():
    """A bound, listening TCP socket on a free localhost port."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    return srv, srv.getsockname()[1]


class TestRtltcpIsRunning:
    def test_detects_a_listener(self):
        srv, port = _free_port_listener()
        try:
            assert rtltcp_is_running("127.0.0.1", port) is True
        finally:
            srv.close()

    def test_false_when_nothing_listening(self):
        # bind to grab a free port, then close it so nothing is listening
        srv, port = _free_port_listener()
        srv.close()
        assert rtltcp_is_running("127.0.0.1", port, attempts=2) is False

    def test_single_attempt_works(self):
        srv, port = _free_port_listener()
        try:
            assert rtltcp_is_running("127.0.0.1", port, attempts=1) is True
        finally:
            srv.close()

    def test_retries_do_not_raise_on_bad_host(self):
        # invalid host must fail closed, not raise
        assert rtltcp_is_running("256.256.256.256", 1234, attempts=2) is False


class TestDeviceConnectLogging:
    def test_populate_logs_rtltcp_state(self):
        src = (Path(__file__).parent.parent
               / "ui/tabs/sdr_device_connect.py").read_text(encoding="utf-8")
        # the 0-device branch must record why the RTL-TCP fallback did/didn't fire
        assert "rtltcp_running=%s" in src
        assert "rtltcp_up" in src
