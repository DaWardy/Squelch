# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- sdr/sim_source.py

Simulated signal source — a synthetic wideband IQ generator so the whole SDR
stack (waterfall, survey/hound, signal-ID, signal history, alerts) comes alive
with **no hardware and no capture file**. Pick "Simulated signal (no hardware)"
in the SDR device list, hit Connect, and a live spectrum appears with several
distinct signals — some steady, one pulsing on/off so the survey/alert/history
features have something to react to.

The generator places each signal at a fixed **offset from the tuned centre**, so
wherever you tune, the scene stays in view (a reliable demo). Each frame is
complex64 noise floor + band-limited signal bumps, delivered to an
`on_samples(iq, sample_rate, center_hz)` callback on a background thread — the
same interface `SoapyManager` and `IQPlayer` use, so it drops straight into the
SDR tab's stream path.

`generate()` is pure numpy and deterministic given a seed (peaks land at the
requested offsets; on/off signals honour their duty cycle) — so it's fully
testable headless. Never raises in the stream loop.
"""

import time
import logging
import threading
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

log = logging.getLogger(__name__)

CHUNK = 8192                # samples per delivered frame (> FFT_SIZE)
FPS   = 12                  # delivered frames per second


@dataclass
class SimSignal:
    """One synthetic signal, placed at a fixed offset from the tuned centre."""
    offset_hz: int                     # + above / − below the centre
    width_hz:  int   = 8_000
    power_db:  float = 24.0            # peak above the noise floor
    period_s:  float = 0.0            # 0 = always on; else on/off cycle length
    duty:      float = 0.6            # fraction of the period the signal is on
    label:     str   = ""

    def is_on(self, t: float) -> bool:
        if self.period_s <= 0:
            return True
        return (t % self.period_s) < (self.period_s * self.duty)


def default_scene() -> list:
    """A believable starter scene: four steady signals of varying width plus one
    that pulses on/off (to exercise survey detection, alerts, and history)."""
    return [
        SimSignal(-820_000, width_hz=180_000, power_db=26, label="wideband"),
        SimSignal(-300_000, width_hz=12_000,  power_db=30, label="carrier"),
        SimSignal(150_000,  width_hz=6_000,   power_db=22, label="narrow"),
        SimSignal(520_000,  width_hz=40_000,  power_db=20, label="data"),
        SimSignal(780_000,  width_hz=10_000,  power_db=28,
                  period_s=8.0, duty=0.4, label="intermittent"),
    ]


class SimSource:
    """Threaded synthetic IQ source with the SoapyManager/IQPlayer interface."""

    def __init__(self, *, sample_rate: int = 2_400_000,
                 get_center: Optional[Callable[[], int]] = None,
                 scene: Optional[list] = None, seed: int = 1,
                 noise_amp: float = 0.05):
        self.sample_rate = int(sample_rate)
        self._get_center = get_center or (lambda: 100_000_000)
        self.scene = scene if scene is not None else default_scene()
        self.noise_amp = float(noise_amp)
        self._rng = np.random.RandomState(int(seed))
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._on_samples: Optional[Callable] = None
        self._t = 0.0

    # ── generation (pure, deterministic) ──────────────────────────────────
    def generate(self, n: int, center_hz: int, t: float) -> np.ndarray:
        """One complex64 frame of `n` samples: noise floor + active signals.

        Signals are placed at their offset from `center_hz`; the frame spans
        `sample_rate`, so an offset within ±sample_rate/2 is visible."""
        n = int(n)
        iq = (self._rng.randn(n) + 1j * self._rng.randn(n)).astype(np.complex64)
        iq *= self.noise_amp
        idx = np.arange(n)
        for sig in self.scene:
            if not sig.is_on(t):
                continue
            if abs(sig.offset_hz) >= self.sample_rate / 2:
                continue                       # outside the visible window
            amp = self.noise_amp * (10.0 ** (sig.power_db / 20.0))
            band = self._band_limited(n, sig.width_hz)
            shift = np.exp(2j * np.pi * (sig.offset_hz / self.sample_rate) * idx)
            iq += (amp * band * shift).astype(np.complex64)
        return iq.astype(np.complex64)

    def _band_limited(self, n: int, width_hz: int) -> np.ndarray:
        """Unit-ish complex noise low-passed to ~`width_hz` (a spectral bump)."""
        white = (self._rng.randn(n) + 1j * self._rng.randn(n))
        taps = max(1, int(self.sample_rate / max(1, width_hz)))
        taps = min(taps, max(1, n // 2))
        if taps > 1:
            kernel = np.ones(taps) / taps
            white = np.convolve(white, kernel, mode="same")
        # normalise so the bump's amplitude is ~1 regardless of tap count
        rms = np.sqrt(np.mean(np.abs(white) ** 2)) or 1.0
        return white / rms

    # ── streaming (thread) ────────────────────────────────────────────────
    def on_samples(self, cb: Callable) -> None:
        self._on_samples = cb

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._t = 0.0
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="SimSource")
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def _loop(self) -> None:
        interval = 1.0 / FPS
        dt = CHUNK / self.sample_rate
        while self._running:
            try:
                center = int(self._get_center())
                iq = self.generate(CHUNK, center, self._t)
                self._t += dt
                if self._on_samples:
                    self._on_samples(iq, self.sample_rate, center)
            except Exception as exc:                # pragma: no cover
                log.debug("sim source frame failed: %s", exc)
            time.sleep(interval)
