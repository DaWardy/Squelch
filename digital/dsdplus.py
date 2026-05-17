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
Squelch -- digital/dsdplus.py
DSD+ subprocess manager for Windows.
Handles P25 Phase 1/2, DMR, NXDN, YSF, D-STAR decode.
DSD+ reads audio from a virtual audio device and outputs
decoded text/audio via stdout and an audio device.
"""

import subprocess
import threading
import logging
import time
from dataclasses import dataclass, field
from typing import Callable
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class DecodeEvent:
    """A single digital voice decode event from DSD+."""
    timestamp:    float
    protocol:     str      # P25, DMR, NXDN, YSF, DSTAR
    talkgroup:    str      = ""
    source_id:    str      = ""
    dest_id:      str      = ""
    text:         str      = ""    # decoded text / voice label
    freq_hz:      int      = 0
    color_code:   int      = 0    # DMR color code
    slot:         int      = 0    # DMR timeslot
    encrypted:    bool     = False
    raw_line:     str      = ""


# DSD+ output line patterns
PROTOCOL_MARKERS = {
    "P25":   ["P25", "IMBE", "AMBE"],
    "DMR":   ["DMR", "ETSI"],
    "NXDN":  ["NXDN", "IDAS"],
    "YSF":   ["YSF", "C4FM", "Fusion"],
    "DSTAR": ["D-STAR", "DSTAR", "DVSI"],
}


class DSDPlusManager:
    """
    Manages a DSD+ subprocess for digital voice decode.
    DSD+ is Windows-only freeware — on Linux use OP25.
    Audio routing: SDR/rig audio device → DSD+ input.
    """

    def __init__(self, config):
        self.cfg        = config
        self._proc:     subprocess.Popen = None
        self._running   = False
        self._thread:   threading.Thread = None
        self._events:   list[DecodeEvent] = []
        self._lock      = threading.Lock()

        self._on_decode:  Callable = None
        self._on_status:  Callable = None

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> bool:
        """Launch DSD+ subprocess."""
        path = self.cfg.get("paths.dsdplus", "")
        if not path or not Path(path).exists():
            log.warning(
                "DSD+ path not configured. "
                "Set in Settings → Paths & Executables.")
            return False

        try:
            # DSD+ command line for scanner input mode
            cmd = [
                path,
                "-i", self._get_input_device(),
                "-o", self._get_output_device(),
                "-n",  # no-repeat mode
            ]
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                shell=False)  # nosec B603

            self._running = True
            self._thread  = threading.Thread(
                target=self._read_loop,
                daemon=True, name="DSDPlus")
            self._thread.start()

            log.info(f"DSD+ started: {path}")
            self._notify_status("running")
            return True

        except Exception as e:
            log.error(f"DSD+ start failed: {e}")
            self._notify_status("error")
            return False

    def stop(self):
        self._running = False
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self._proc = None
        self._notify_status("stopped")
        log.info("DSD+ stopped")

    @property
    def is_running(self) -> bool:
        return (self._running and
                self._proc is not None and
                self._proc.poll() is None)

    # ── Output parsing ────────────────────────────────────────────────────

    def _read_loop(self):
        """Read DSD+ stdout and parse decode events."""
        if not self._proc:
            return
        try:
            for line in self._proc.stdout:
                if not self._running:
                    break
                line = line.rstrip()
                if not line:
                    continue
                event = self._parse_line(line)
                if event:
                    with self._lock:
                        self._events.append(event)
                        if len(self._events) > 500:
                            self._events = self._events[-500:]
                    if self._on_decode:
                        try:
                            self._on_decode(event)
                        except Exception as e:
                            log.debug(f"Decode callback: {e}")
        except Exception as e:
            if self._running:
                log.warning(f"DSD+ read loop: {e}")
        self._running = False
        self._notify_status("stopped")

    def _parse_line(self, line: str) -> DecodeEvent | None:
        """Parse a DSD+ output line into a DecodeEvent."""
        # Detect protocol
        protocol = ""
        line_upper = line.upper()
        for proto, markers in PROTOCOL_MARKERS.items():
            if any(m.upper() in line_upper for m in markers):
                protocol = proto
                break

        if not protocol:
            return None

        event = DecodeEvent(
            timestamp = time.time(),
            protocol  = protocol,
            raw_line  = line[:200],
        )

        # Parse common fields
        # DMR: "DMR slot1 CC1 TG12345 -> 16777215"
        import re
        tg_match = re.search(r'TG(\d+)', line, re.IGNORECASE)
        if tg_match:
            event.talkgroup = tg_match.group(1)

        src_match = re.search(r'(\d{6,9})\s*->', line)
        if src_match:
            event.source_id = src_match.group(1)

        cc_match = re.search(r'CC(\d+)', line, re.IGNORECASE)
        if cc_match:
            event.color_code = int(cc_match.group(1))

        slot_match = re.search(r'slot(\d)', line, re.IGNORECASE)
        if slot_match:
            event.slot = int(slot_match.group(1))

        if 'encrypt' in line.lower() or 'enc' in line_upper:
            event.encrypted = True

        return event

    def _get_input_device(self) -> str:
        """Get audio input device name for DSD+."""
        return self.cfg.get(
            "audio.digital_input",
            "CABLE Output (VB-Audio Virtual Cable)")

    def _get_output_device(self) -> str:
        """Get audio output device for decoded voice."""
        return self.cfg.get(
            "audio.digital_output", "default")

    def _notify_status(self, status: str):
        if self._on_status:
            try:
                self._on_status(status)
            except Exception:
                pass

    # ── Callbacks ─────────────────────────────────────────────────────────

    def on_decode(self, cb: Callable):
        self._on_decode = cb

    def on_status(self, cb: Callable):
        self._on_status = cb

    @property
    def recent_events(self) -> list[DecodeEvent]:
        with self._lock:
            return list(self._events[-100:])
