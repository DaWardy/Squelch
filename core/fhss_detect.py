# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/fhss_detect.py

Frequency-hopping (FHSS) emitter detection over the survey output (ROADMAP
Phase 3 / SDR-Console-parity). Many covert devices — bugs, trackers,
unauthorised telemetry — hop across a set of channels to spread their footprint;
spotting that pattern is squarely the "hound" mission.

Input is a stream of time-tagged detections `(t_seconds, freq_hz)` — exactly
what a live survey produces (each swept/dwelled frame yields the channels active
at that moment). The discriminator between a hopper and several static signals:

  * a **frequency hopper** sits on ~one channel at any instant (low
    *simultaneity*) but visits many channels over time, revisiting them;
  * **N static signals** are all present continuously, so every time slice shows
    all N channels at once (high simultaneity).

`detect_hopping()` channelises the frequencies, counts channel *transitions*,
measures peak simultaneity, and — when the pattern looks like hopping — returns
a `HopSet` (channel list, hop rate, dwell time, span). Pure Python, never
raises. Full hop-*following* (retune to stay on the signal) is a later HW piece.
"""

import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

DEFAULT_FREQ_TOL_HZ  = 25_000     # channels closer than this are "the same"
DEFAULT_MIN_CHANNELS = 4
DEFAULT_MIN_HOPS     = 6
DEFAULT_MAX_SIMULT   = 2          # a hopper takes turns; tolerate a little noise


@dataclass
class HopSet:
    """A detected frequency-hopping emitter."""
    channels:    list          # representative channel centre freqs (Hz)
    n_channels:  int
    hop_count:   int           # channel transitions observed
    hop_rate:    float         # hops per second
    dwell_s:     float         # mean time per hop
    freq_lo:     int
    freq_hi:     int
    span_s:      float
    n_obs:       int

    def to_signal(self):
        """Bridge to a unified Signal record (source='fhss')."""
        from core.signal_model import Signal
        centre = (self.freq_lo + self.freq_hi) // 2
        return Signal(
            freq_hz=int(centre),
            bandwidth_hz=int(self.freq_hi - self.freq_lo),
            source="fhss", classification="frequency-hopping",
            confidence=0.6,
            decoded=f"{self.n_channels} ch, {self.hop_rate:.1f} hops/s",
            tags="fhss,hopping")


# ── helpers ───────────────────────────────────────────────────────────────────

def _channelise(freqs, tol_hz: int) -> dict:
    """Map each frequency to a representative channel-centre (greedy cluster)."""
    mapping = {}
    centre = None
    for f in sorted(set(int(x) for x in freqs)):
        if centre is None or f - centre > tol_hz:
            centre = f
        mapping[f] = centre
    return mapping


def _median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return 0.0
    m = n // 2
    return s[m] if n % 2 else (s[m - 1] + s[m]) / 2.0


def _max_simultaneity(obs, chan_map: dict, bin_s: float) -> int:
    """Peak number of distinct channels active in any `bin_s` time slice."""
    if bin_s <= 0:
        return len({chan_map[f] for _, f in obs})
    t0 = obs[0][0]
    bins: dict = {}
    for t, f in obs:
        b = int((t - t0) / bin_s)
        bins.setdefault(b, set()).add(chan_map[f])
    return max((len(s) for s in bins.values()), default=0)


# ── detection ─────────────────────────────────────────────────────────────────

def detect_hopping(observations, *, freq_tol_hz: int = DEFAULT_FREQ_TOL_HZ,
                   min_channels: int = DEFAULT_MIN_CHANNELS,
                   min_hops: int = DEFAULT_MIN_HOPS,
                   max_simultaneous: int = DEFAULT_MAX_SIMULT,
                   bin_s: float | None = None):
    """Detect a frequency-hopping emitter in `[(t_s, freq_hz), …]`.

    Returns a `HopSet`, or None if the observations don't look like hopping.

    ASSUMES A STARING OBSERVATION MODEL: every timestamp reflects all channels
    concurrently active in the receiver's view (e.g. one wide FFT frame at a
    fixed centre — SurveyEngine.offer_frame at a fixed tune). Under that model
    the simultaneity test cleanly separates a hopper (≈1 channel at a time) from
    several static carriers (all present at once). It is NOT valid for a
    *frequency-swept* survey (centre moving between frames): there each static
    emitter is only seen while the sweep passes its channel, so static signals
    look one-at-a-time and can masquerade as a hopper. A swept survey needs
    per-channel occupancy-fraction analysis instead (future work).
    """
    obs = [(float(t), int(f)) for t, f in (observations or []) if f]
    if len(obs) < max(min_hops, 2):
        return None
    obs.sort()

    chan_map = _channelise((f for _, f in obs), freq_tol_hz)
    seq = [chan_map[f] for _, f in obs]
    distinct = sorted(set(seq))
    if len(distinct) < min_channels:
        return None

    transitions = sum(1 for a, b in zip(seq, seq[1:]) if a != b)
    if transitions < min_hops:
        return None

    times = [t for t, _ in obs]
    span = times[-1] - times[0]
    if bin_s is None:
        gaps = [b - a for a, b in zip(times, times[1:]) if b > a]
        bin_s = _median(gaps) if gaps else (span / len(obs) if obs else 1.0)
        bin_s = max(bin_s, 1e-9)

    if _max_simultaneity(obs, chan_map, bin_s) > max_simultaneous:
        return None                               # too many channels at once → static

    return HopSet(
        channels=distinct, n_channels=len(distinct),
        hop_count=transitions,
        hop_rate=round(transitions / span, 3) if span > 0 else 0.0,
        dwell_s=round(span / transitions, 5) if transitions else 0.0,
        freq_lo=min(distinct), freq_hi=max(distinct),
        span_s=round(span, 5), n_obs=len(obs))


def observations_from(items, freq_attr: str = "freq_hz",
                      time_attr: str = "t") -> list:
    """Extract `(t, freq)` tuples from freq/time-bearing objects (e.g. DFSample,
    or dicts) for feeding `detect_hopping`."""
    out = []
    for it in items or []:
        f = it.get(freq_attr) if isinstance(it, dict) else getattr(it, freq_attr, 0)
        t = it.get(time_attr) if isinstance(it, dict) else getattr(it, time_attr, 0)
        if f:
            out.append((float(t or 0), int(f)))
    return out
