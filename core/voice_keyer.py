from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""
Voice Keyer — 8-slot phone/SSB voice macro player.

Clips are WAV files stored on disk. Paths and labels are persisted in
config under voice_keyer.v1..v8. Playback and recording are handled on
background threads via sounddevice so the UI never blocks.
"""
import logging
import os
import pathlib
import threading

log = logging.getLogger(__name__)

_DEFAULT_LABELS = [
    "CQ Call", "My Call", "5-9 Report", "Thank You",
    "QRZ?", "73 Goodbye", "QSY Up 5", "Station Info",
]


class VoiceKeyer:
    """Manage 8 voice clip slots for phone/SSB operation."""

    KEYS = [f"v{i}" for i in range(1, 9)]
    _SAMPLE_RATE = 44_100
    _CHANNELS = 1

    def __init__(self, cfg) -> None:
        self._cfg = cfg
        self._playing = False
        self._recording = False
        self._play_thread: threading.Thread | None = None
        self._rec_thread: threading.Thread | None = None

    # ── public API ────────────────────────────────────────────────────────

    def get_clip(self, key: str) -> dict:
        """Return {label, path} for a key such as 'v1'..'v8'."""
        idx = self.KEYS.index(key)
        label = self._cfg.get(f"voice_keyer.{key}.label",
                              _DEFAULT_LABELS[idx])
        path = self._cfg.get(f"voice_keyer.{key}.path", "") or ""
        return {"label": label, "path": path}

    def set_clip(self, key: str, label: str, path: str) -> None:
        """Persist label and file path for a slot."""
        self._cfg.set(f"voice_keyer.{key}.label", label.strip())
        self._cfg.set(f"voice_keyer.{key}.path", path)

    def all_clips(self) -> list[tuple[str, dict]]:
        """Return [(key, clip_dict), ...] for v1..v8 in order."""
        return [(k, self.get_clip(k)) for k in self.KEYS]

    def play(self, key: str) -> bool:
        """Start async WAV playback for the given slot. Returns False when
        no file is configured, the file is missing, or sounddevice is absent."""
        clip = self.get_clip(key)
        path = clip.get("path", "")
        if not path or not os.path.isfile(path):
            return False
        try:
            import wave as _wave
            import numpy as _np
            import sounddevice as _sd
        except ImportError:
            log.warning("voice_keyer: sounddevice/numpy not available — cannot play")
            return False
        self.stop()
        def _run() -> None:
            self._playing = True
            try:
                with _wave.open(path) as wf:
                    rate = wf.getframerate()
                    nch  = wf.getnchannels()
                    raw  = wf.readframes(wf.getnframes())
                data = _np.frombuffer(raw, dtype=_np.int16).astype(_np.float32) / 32768.0
                if nch > 1:
                    data = data.reshape(-1, nch)
                _sd.play(data, rate)
                _sd.wait()
            except Exception as exc:
                log.debug("voice_keyer play error: %s", exc)
            finally:
                self._playing = False
        self._play_thread = threading.Thread(target=_run, daemon=True)
        self._play_thread.start()
        return True

    def record(self, key: str, duration: float = 8.0,
               on_done: "callable | None" = None) -> bool:
        """Record from default mic for `duration` seconds and save as WAV.
        Calls on_done(path) on the worker thread when finished."""
        try:
            import wave as _wave
            import numpy as _np
            import sounddevice as _sd
        except ImportError:
            log.warning("voice_keyer: sounddevice/numpy not available — cannot record")
            return False
        clip_dir = _clip_dir(self._cfg)
        path = str(clip_dir / f"{key}.wav")
        self.stop()
        def _run() -> None:
            self._recording = True
            try:
                frames = int(duration * self._SAMPLE_RATE)
                data = _sd.rec(frames, samplerate=self._SAMPLE_RATE,
                               channels=self._CHANNELS, dtype="int16")
                _sd.wait()
                with _wave.open(path, "wb") as wf:
                    wf.setnchannels(self._CHANNELS)
                    wf.setsampwidth(2)
                    wf.setframerate(self._SAMPLE_RATE)
                    wf.writeframes(data.tobytes())
                if on_done:
                    on_done(path)
            except Exception as exc:
                log.debug("voice_keyer record error: %s", exc)
            finally:
                self._recording = False
        self._rec_thread = threading.Thread(target=_run, daemon=True)
        self._rec_thread.start()
        return True

    def stop(self) -> None:
        """Stop any active playback or recording immediately."""
        try:
            import sounddevice as _sd
            _sd.stop()
        except Exception:
            pass
        self._playing = False
        self._recording = False

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def is_recording(self) -> bool:
        return self._recording


def _clip_dir(cfg) -> pathlib.Path:
    """Return (and create) the directory where voice clips are stored."""
    base = cfg.get("advanced.log_dir", "") or str(pathlib.Path.home())
    d = pathlib.Path(base) / "voice_clips"
    d.mkdir(parents=True, exist_ok=True)
    return d
