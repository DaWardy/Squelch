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
"""Squelch -- sdr/iq_recorder.py
IQ recording and playback in SigMF format.
SigMF: .sigmf-data (raw samples) + .sigmf-meta (JSON)
Recordings stored in user-configured recordings/ folder.
"""

import json
import time
import logging
import threading
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional, Callable

log = logging.getLogger(__name__)

from core.config import USER_DIR
from core.constants import IQ_SIGMF_VERSION
RECORDINGS_DIR = USER_DIR / "recordings"


@dataclass
class Recording:
    """A SigMF recording on disk."""
    name:        str
    data_path:   Path
    meta_path:   Path
    center_hz:   int
    sample_rate: int
    datatype:    str     = "cf32_le"
    hardware:    str     = ""
    timestamp:   str     = ""
    notes:       str     = ""
    duration_s:  float   = 0.0
    file_size:   int     = 0

    @property
    def display_name(self) -> str:
        hz  = self.center_hz / 1e6
        dur = self.duration_s
        if dur >= 60:
            dur_str = f"{dur/60:.1f}min"
        else:
            dur_str = f"{dur:.1f}s"
        return (f"{self.name}  "
                f"{hz:.3f}MHz  "
                f"{dur_str}  "
                f"{self.file_size/1e6:.1f}MB")

    @classmethod
    def from_meta_file(cls, meta_path: Path) -> Optional["Recording"]:
        """Load recording info from a .sigmf-meta file."""
        try:
            meta = json.loads(
                meta_path.read_text(encoding='utf-8'))
            g = meta.get("global", {})
            data_path = meta_path.with_suffix(".sigmf-data")
            if not data_path.exists():
                return None
            size     = data_path.stat().st_size
            sr       = int(g.get("core:sample_rate", 0))
            dtype    = g.get("core:datatype", "cf32_le")
            # Duration from file size — bytes/sample depends on the datatype
            # (cf32=8, ci16=4, cu8=2, …), not always cf32.
            from core.sigmf_io import bytes_per_sample as _bps
            bps      = _bps(dtype)
            samples  = size / bps if (sr and bps) else 0
            duration = samples / sr if sr else 0
            return cls(
                name        = meta_path.stem,
                data_path   = data_path,
                meta_path   = meta_path,
                center_hz   = int(g.get(
                    "core:frequency", 0)),
                sample_rate = sr,
                datatype    = dtype,
                hardware    = g.get("core:hw", ""),
                timestamp   = g.get(
                    "core:datetime", ""),
                notes       = g.get(
                    "squelch:notes", ""),
                duration_s  = duration,
                file_size   = size,
            )
        except Exception as e:
            log.debug(f"Recording load {meta_path}: {e}")
            return None


class IQRecorder:
    """
    Records IQ samples to SigMF format files.
    Receives samples from SoapyManager via callback.
    """

    def __init__(self, recordings_dir: Path = RECORDINGS_DIR):
        self._dir       = recordings_dir
        self._recording = False
        self._file      = None
        self._meta:     dict = {}
        self._start_t:  float = 0.0
        self._samples_written: int = 0
        self._lock      = threading.Lock()
        self._on_update: Callable | None = None

    def start(self, center_hz: int, sample_rate: int,
              hardware: str = "",
              notes: str = "",
              lat: float = 0.0,
              lon: float = 0.0) -> str:
        """Start recording. Returns filename stem."""
        if self._recording:
            return ""

        self._dir.mkdir(parents=True, exist_ok=True)

        ts       = datetime.now(timezone.utc)
        ts_str   = ts.strftime("%Y%m%d_%H%M%S")
        hz_str   = f"{center_hz/1e6:.3f}MHz".replace(".", "p")
        stem     = f"squelch_{ts_str}_{hz_str}"

        data_path = self._dir / f"{stem}.sigmf-data"
        meta_path = self._dir / f"{stem}.sigmf-meta"

        self._meta = {
            "global": {
                "core:datatype":    "cf32_le",
                "core:sample_rate": sample_rate,
                "core:frequency":   center_hz,
                "core:datetime":    ts.isoformat(),
                "core:hw":          hardware,
                "core:version":     IQ_SIGMF_VERSION,
                "squelch:notes":    notes,
                "core:latitude":    lat if lat else None,
                "core:longitude":   lon if lon else None,
            },
            "captures": [{
                "core:sample_start": 0,
                "core:frequency":    center_hz,
                "core:datetime":     ts.isoformat(),
            }],
            "annotations": [],
        }

        try:
            self._file   = open(data_path, "wb")
            self._meta_path = meta_path
            self._recording = True
            self._start_t   = time.time()
            self._samples_written = 0
            log.info(f"IQ recording started: {stem}")
            return stem
        except Exception as e:
            log.error(f"IQ record start: {e}")
            return ""

    def write_samples(self, iq: np.ndarray):
        """Called with each IQ buffer during recording."""
        if not self._recording or not self._file:
            return
        with self._lock:
            try:
                iq.astype(np.complex64).tofile(self._file)
                self._samples_written += len(iq)
                if self._on_update:
                    elapsed = time.time() - self._start_t
                    self._on_update(
                        elapsed,
                        self._samples_written,
                        self._file.tell())
            except Exception as e:
                log.error(f"IQ write: {e}")

    def stop(self) -> Recording | None:
        """Stop recording and write metadata."""
        if not self._recording:
            return None
        self._recording = False
        try:
            self._file.close()
            self._file = None
        except Exception:
            pass

        # Write metadata
        try:
            self._meta_path.write_text(
                json.dumps(self._meta, indent=2),
                encoding='utf-8')
            rec = Recording.from_meta_file(
                self._meta_path)
            log.info(
                f"IQ recording saved: "
                f"{self._meta_path.stem} "
                f"{self._samples_written:,} samples")
            return rec
        except Exception as e:
            log.error(f"IQ meta write: {e}")
            return None

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def elapsed(self) -> float:
        if not self._recording:
            return 0.0
        return time.time() - self._start_t

    def on_update(self, cb: Callable):
        self._on_update = cb


class IQPlayer:
    """
    Plays back SigMF recordings.
    Delivers samples at correct timing to simulate live SDR.
    """

    def __init__(self):
        self._recording: Recording | None = None
        self._running    = False
        self._paused     = False
        self._position   = 0    # sample offset
        self._speed      = 1.0
        self._thread:    threading.Thread | None = None

        self._on_samples: Callable | None = None
        self._on_progress: Callable | None = None
        self._on_end:     Callable | None = None

    def load(self, recording: Recording) -> bool:
        """Load a recording for playback."""
        if not recording.data_path.exists():
            return False
        self._recording = recording
        self._position  = 0
        return True

    def play(self, speed: float = 1.0):
        """Start or resume playback."""
        if not self._recording:
            return
        self._speed   = max(0.1, min(4.0, speed))
        self._paused  = False
        self._running = True
        self._thread  = threading.Thread(
            target=self._play_loop,
            daemon=True, name="IQPlayer")
        self._thread.start()

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def stop(self):
        self._running = False
        self._position = 0

    def seek(self, position_samples: int):
        self._position = max(0, position_samples)

    @property
    def is_playing(self) -> bool:
        return self._running and not self._paused

    @property
    def position_seconds(self) -> float:
        if not self._recording or \
                not self._recording.sample_rate:
            return 0.0
        return (self._position /
                self._recording.sample_rate)

    @property
    def duration_seconds(self) -> float:
        return (self._recording.duration_s
                if self._recording else 0.0)

    def _play_loop(self):
        """Read and deliver samples at correct rate.

        Datatype-aware: honours the recording's `datatype` (cf32/ci16/cu8/…)
        via core.sigmf_io so ANY SigMF or foreign IQ capture plays back, not
        just Squelch's own cf32 recordings. Bytes-per-sample and the → complex64
        conversion both come from the tested sigmf_io codec."""
        if not self._recording:
            return

        from core.sigmf_io import bytes_per_sample, decode_iq_bytes
        dtype    = getattr(self._recording, "datatype", "cf32_le")
        bps      = bytes_per_sample(dtype)          # bytes per complex sample
        chunk    = 16384
        sr       = self._recording.sample_rate
        interval = chunk / sr / self._speed

        try:
            with open(self._recording.data_path,
                      "rb") as f:
                f.seek(self._position * bps)
                while self._running:
                    if self._paused:
                        time.sleep(0.05)
                        continue
                    raw = f.read(chunk * bps)
                    if not raw:
                        break
                    samples = decode_iq_bytes(raw, dtype)
                    if len(samples) == 0:
                        break
                    self._position += len(samples)
                    if self._on_samples:
                        try:
                            self._on_samples(
                                samples, sr,
                                self._recording.center_hz)
                        except Exception:
                            pass
                    if self._on_progress:
                        try:
                            self._on_progress(
                                self.position_seconds,
                                self.duration_seconds)
                        except Exception:
                            pass
                    time.sleep(interval)
        except Exception as e:
            log.error(f"IQ playback: {e}")

        self._running = False
        if self._on_end:
            try:
                self._on_end()
            except Exception:
                pass

    def on_samples(self, cb: Callable):
        self._on_samples = cb

    def on_progress(self, cb: Callable):
        self._on_progress = cb

    def on_end(self, cb: Callable):
        self._on_end = cb


def list_recordings(
        directory: Path = RECORDINGS_DIR
        ) -> list[Recording]:
    """List all SigMF recordings in a directory."""
    if not directory.exists():
        return []
    recordings = []
    for meta_file in sorted(
            directory.glob("*.sigmf-meta"),
            key=lambda f: f.stat().st_mtime,
            reverse=True):
        rec = Recording.from_meta_file(meta_file)
        if rec:
            recordings.append(rec)
    return recordings
