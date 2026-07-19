# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/audio_record.py

Record demodulated audio to a WAV file (ROADMAP §14.7, SDR-Console parity). This
is the first path by which a user can actually **hear** a signal: point the
demodulator at a VFO, record, and open the `.wav` in any media player — no audio
output device or UI required. It works with no hardware, driven by the simulated
source or a played-back capture.

`AudioRecorder.feed(iq, sr, center)` demodulates each incoming IQ frame
(`core/demod`), optionally auto-notches it (`core/audio_dsp`), and accumulates
the audio; `stop(path)` writes a mono 16-bit PCM WAV via the stdlib `wave`
module (no new dependency). Pure Python + numpy; never raises in the stream path
(a recorder must not crash the receiver).
"""

import wave
import logging
from pathlib import Path

import numpy as np

from core.demod import demodulate, AUDIO_RATE

log = logging.getLogger(__name__)


def write_wav(path, audio, sample_rate: int) -> bool:
    """Write float audio (~[-1, 1]) to a mono 16-bit PCM WAV. Never raises."""
    try:
        a = np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0)
        pcm = (a * 32767.0).astype("<i2")
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(p), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(int(sample_rate))
            w.writeframes(pcm.tobytes())
        return True
    except Exception as exc:                        # pragma: no cover
        log.debug("write_wav failed: %s", exc)
        return False


class AudioRecorder:
    """Demodulate a VFO frame-by-frame and record the audio to a WAV."""

    def __init__(self, *, mode: str = "FM", offset_hz: float = 0.0,
                 bandwidth_hz: float = 0.0, audio_rate: int = AUDIO_RATE,
                 auto_notch: bool = False):
        self.mode = mode
        self.offset_hz = float(offset_hz)
        self.bandwidth_hz = float(bandwidth_hz)
        self.audio_rate = int(audio_rate)
        self.auto_notch = bool(auto_notch)
        self._chunks: list = []
        self._recording = False

    def start(self) -> None:
        self._chunks = []
        self._recording = True

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def sample_count(self) -> int:
        return sum(len(c) for c in self._chunks)

    @property
    def duration_s(self) -> float:
        return self.sample_count / self.audio_rate if self.audio_rate else 0.0

    def feed(self, iq, sample_rate: float, center_hz: int = 0) -> None:
        """Demodulate one IQ frame and append its audio. Never raises."""
        if not self._recording:
            return
        try:
            audio = demodulate(iq, sample_rate, self.mode,
                               offset_hz=self.offset_hz,
                               bandwidth_hz=self.bandwidth_hz,
                               audio_rate=self.audio_rate)
            if audio.size and self.auto_notch:
                from core.audio_dsp import auto_notch as _an
                audio, _ = _an(audio, self.audio_rate)
            if audio.size:
                self._chunks.append(np.asarray(audio, dtype=np.float32))
        except Exception as exc:                    # pragma: no cover
            log.debug("audio record feed failed: %s", exc)

    def stop(self, path) -> "Path | None":
        """Stop recording and write the accumulated audio to `path` (WAV).

        Returns the written Path, or None if nothing was captured / write fails."""
        self._recording = False
        if not self._chunks:
            return None
        audio = np.concatenate(self._chunks)
        if write_wav(path, audio, self.audio_rate):
            return Path(path)
        return None
