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
        """Launch DSD+ subprocess.

        DSD+ on Windows expects an interactive console for setup and audio
        device selection. The previous code passed Linux-`dsd`-style flags
        (`-i name -o name`) which DSD+ does not accept, and it captured
        stdout via PIPE which made DSD+ either misbehave or hang.

        Now we launch DSD+ with no synthetic arguments (user-supplied extra
        args optional via config), in its own console window on Windows.
        Audio device selection happens inside DSD+ itself or via the user's
        own DSDPlus.cfg / .bat.
        """
        path = self.cfg.get("paths.dsdplus", "")
        if not path or not Path(path).exists():
            log.warning(
                "DSD+ path not configured. "
                "Set in Settings → Paths & Executables.")
            return False

        try:
            # Optional extra args the user can configure (e.g. "-n" or a
            # custom wave-device index). Default is empty — just the exe.
            extra = (self.cfg.get("dsdplus.extra_args", "") or "").split()
            cmd = [path] + extra

            kw = dict(
                cwd=str(Path(path).parent),    # DSD+ writes logs alongside
                                                # its exe; use its own dir
                shell=False)                   # nosec B603

            # On Windows, give DSD+ its own console window. Without this,
            # DSD+ either shares Squelch's console (none, for GUI) or
            # silently fails. CREATE_NEW_CONSOLE is the Windows flag for
            # "give me a real console of my own."
            import sys as _sys
            if _sys.platform == "win32":
                kw["creationflags"] = (
                    subprocess.CREATE_NEW_CONSOLE
                    if hasattr(subprocess, "CREATE_NEW_CONSOLE")
                    else 0x00000010)

            self._proc = subprocess.Popen(cmd, **kw)

            self._running = True
            # Watcher thread — polls for exit, doesn't try to read stdout
            self._thread  = threading.Thread(
                target=self._watch_loop,
                daemon=True, name="DSDPlus")
            self._thread.start()

            log.info(f"DSD+ started: {path} (PID {self._proc.pid})")
            self._notify_status("running")
            return True

        except Exception as e:
            log.error(f"DSD+ start failed: {e}")
            self._notify_status("error")
            return False

    def _watch_loop(self):
        """Poll DSD+ — set status when it exits. Don't read stdout (the
        old code piped it which caused DSD+ to misbehave on Windows)."""
        import time
        while self._running and self._proc:
            if self._proc.poll() is not None:
                # Process exited
                self._running = False
                self._notify_status("stopped")
                log.info(f"DSD+ exited with code {self._proc.returncode}")
                return
            time.sleep(0.5)

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
