# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- core/modulation_classify.py

Heuristic modulation classifier from complex-baseband IQ (pure DSP, no Qt, no
hardware). Given a chunk of IQ centred on a signal, guess its modulation:

    None/Noise · CW · AM · SSB · FM · OOK/ASK · FSK · PSK · OFDM/Digital

This is the ROADMAP Phase-2 IDENTIFY step — it complements the frequency-based
allocation classifier (core/signal_classify.py) and the demod suggester
(core/auto_demod.py) by looking at the *signal itself*. It is a heuristic,
not an ML model: decisions come from the classic Azzouz-&-Nandi instantaneous
features (amplitude / phase / frequency statistics) plus spectral shape. Clean
signals classify well; low-SNR or overlapping signals are best-effort with a
confidence score the caller can threshold.

Feed it IQ from an SDR capture or an occupancy segment. `confidence` is a rough
0..1 self-assessment, not a probability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

log = logging.getLogger(__name__)

# Modulation labels (stable strings — used in UI, Signal records, tests).
NONE   = "None/Noise"
CW     = "CW"
AM     = "AM"
SSB    = "SSB"
FM     = "FM"
OOK    = "OOK/ASK"
FSK    = "FSK"
PSK    = "PSK"
OFDM   = "OFDM/Digital"


@dataclass
class ModFeatures:
    """Instantaneous + spectral features extracted from an IQ chunk."""
    amp_cv:         float = 0.0    # amplitude coefficient of variation (std/mean)
    gamma_max:      float = 0.0    # peak spectral density of centred amplitude
    on_off_ratio:   float = 0.0    # fraction of samples in the "off" (silent) state
    sigma_af:       float = 0.0    # std of normalised inst. freq (strong samples)
    sigma_dp:       float = 0.0    # std of detrended inst. phase (strong samples)
    freq_bimodality:float = 0.0    # Sarle's bimodality coeff of inst. freq (FSK≈>0.6)
    freq_duty:      float = 0.0    # fraction of time inst. freq is "far from centre"
                                   #   FSK≈1 (sits at tones); PSK≈0 (spikes at edges)
    spectral_flatness: float = 0.0 # 0=tonal, 1=flat (noise/OFDM)
    occ_bw:         float = 0.0    # fraction of band holding 90% of energy
    n_peaks:        int   = 0      # significant spectral peaks


@dataclass
class ModResult:
    """Outcome of a modulation classification."""
    modulation: str = NONE
    confidence: float = 0.0
    features: ModFeatures = field(default_factory=ModFeatures)
    note: str = ""


def _spectral_flatness(psd: np.ndarray) -> float:
    """Wiener entropy over the OCCUPIED band (bins above 5% of the peak).

    Measured in-band so a band-limited flat signal (OFDM) reads flat, rather
    than being crushed toward 0 by the many near-zero out-of-band bins.
    """
    if psd.size < 2:
        return 0.0
    band = psd[psd > 0.05 * psd.max()]
    if band.size < 2:
        return 0.0
    gm = np.exp(np.mean(np.log(band)))
    am = np.mean(band)
    return float(gm / am) if am > 0 else 0.0


def _count_peaks(psd: np.ndarray, rel_thresh: float = 0.25) -> int:
    """Count spectral peaks above rel_thresh * max, merged if adjacent."""
    if psd.size < 3:
        return 0
    thr = psd.max() * rel_thresh
    above = psd > thr
    edges = np.diff(above.astype(np.int8))
    return int(np.count_nonzero(edges == 1)) + (1 if above[0] else 0)


def _occupied_bw(psd: np.ndarray, frac: float = 0.90) -> float:
    """Fraction of spectrum bins that hold *frac* of the total energy.

    Small for a band-limited signal, ≈1 for noise that fills the whole span.
    """
    total = psd.sum()
    if total <= 0:
        return 0.0
    order = np.sort(psd)[::-1]
    cum = np.cumsum(order)
    k = int(np.searchsorted(cum, frac * total)) + 1
    return float(k / psd.size)


def _bimodality(v: np.ndarray) -> float:
    """Sarle's bimodality coefficient (≈0.55+ ⇒ two clusters, e.g. 2-FSK)."""
    v = v[np.isfinite(v)]
    n = v.size
    if n < 8:
        return 0.0
    s = np.std(v)
    if s < 1e-12:
        return 0.0
    z = (v - np.mean(v)) / s
    g = np.mean(z ** 3)                       # skewness
    k = np.mean(z ** 4) - 3.0                 # excess kurtosis
    denom = k + 3.0 * (n - 1) ** 2 / ((n - 2) * (n - 3))
    return float((g ** 2 + 1.0) / denom) if denom > 0 else 0.0


def extract_features(iq: np.ndarray, fs: float) -> ModFeatures:
    """Compute the classifier features from a complex IQ chunk at rate *fs*."""
    f = ModFeatures()
    x = np.asarray(iq).astype(np.complex64)
    n = x.size
    if n < 64 or fs <= 0:
        return f

    amp = np.abs(x)
    a_mean = float(np.mean(amp))
    if a_mean <= 1e-12:
        return f   # dead air

    # Amplitude statistics (constant-envelope test + AM depth).
    f.amp_cv = float(np.std(amp) / a_mean)
    a_cn = amp / a_mean - 1.0                       # normalised, centred
    A = np.abs(np.fft.fft(a_cn))
    f.gamma_max = float((A ** 2).max() / n)

    # On/off keying: fraction of samples well below the median envelope.
    med_amp = np.median(amp[amp > 0]) if np.any(amp > 0) else 0.0
    f.on_off_ratio = float(np.mean(amp < 0.25 * med_amp))

    # Instantaneous phase / frequency — computed on STRONG samples only so that
    # noise-filled gaps (keyed signals) don't corrupt the frequency statistics.
    strong = amp > (0.5 * a_mean)
    phase = np.unwrap(np.angle(x))
    t = np.arange(n)
    slope = np.polyfit(t, phase, 1)[0]              # dominant carrier offset
    phase_nl = phase - slope * t
    if np.count_nonzero(strong) > 8:
        f.sigma_dp = float(np.std(phase_nl[strong]))
    inst_freq = np.diff(phase_nl) / (2.0 * np.pi) * fs
    strong_pair = strong[:-1] & strong[1:]
    fstrong = inst_freq[strong_pair]
    if fstrong.size > 8:
        fabs = np.abs(fstrong)
        scale = np.percentile(fabs, 95) + 1e-9
        f.sigma_af = float(np.std(fstrong / scale))
        f.freq_bimodality = _bimodality(fstrong)
        # Duty: how much of the time the freq sits AWAY from centre. FSK holds
        # its tones (high duty); PSK sits at the carrier with brief spikes at
        # symbol transitions (low duty).
        peak = fabs.max()
        f.freq_duty = float(np.mean(fabs > 0.5 * peak)) if peak > 0 else 0.0

    # Spectrum shape.
    win = np.hanning(n)
    S = np.abs(np.fft.fftshift(np.fft.fft(x * win))) ** 2
    f.spectral_flatness = _spectral_flatness(S)
    f.occ_bw = _occupied_bw(S)
    f.n_peaks = _count_peaks(S)
    return f


def classify_modulation(iq: np.ndarray, fs: float) -> ModResult:
    """Classify the modulation of an IQ chunk. Never raises.

    Note: CW (keyed Morse) and OOK/ASK are the same on/off-keyed modulation and
    differ only in keying rate — the classifier reports the more likely of the
    two but that particular split is best-effort. Continuous CW (an unkeyed
    carrier / beacon) is distinct and reliable.
    """
    x = np.asarray(iq)
    if x.size < 64 or fs <= 0:
        return ModResult(NONE, 1.0, ModFeatures(), "insufficient data")
    finite = np.isfinite(x)
    if not finite.any():
        return ModResult(NONE, 1.0, ModFeatures(), "no finite samples")
    if float(np.max(np.abs(x[finite]))) < 1e-9:
        return ModResult(NONE, 1.0, ModFeatures(), "silent / dead air")
    try:
        feats = extract_features(x, fs)
    except Exception:
        return ModResult(NONE, 0.0, ModFeatures(), "feature extraction failed")

    f = feats
    # 1. Noise — a flat spectrum whose energy is spread across the whole span
    #    (a real signal, even OFDM, concentrates energy in a sub-band → low occ).
    if f.occ_bw > 0.45 and f.spectral_flatness > 0.35:
        return ModResult(NONE, _conf(0.6 + f.occ_bw * 0.3), f,
                         "flat spectrum filling the band")

    # 2. On/off amplitude keying — CW (keyed single tone) vs OOK/ASK (data).
    if f.on_off_ratio > 0.15:
        if f.n_peaks <= 2 and f.sigma_af < 0.20:
            return ModResult(CW, _conf(0.7 + f.on_off_ratio), f,
                             "keyed single tone (Morse)")
        return ModResult(OOK, _conf(0.6 + f.on_off_ratio), f,
                         "on/off amplitude keying")

    # 3. Constant-envelope family (amplitude ~flat) → CW / FSK / PSK / FM.
    if f.amp_cv < 0.20:
        # Single narrow spectral line → CW (checked first; a clean tone's
        # residual inst-freq is pure noise, so sigma_af is unreliable here).
        if f.n_peaks <= 1:
            return ModResult(CW, _conf(0.8), f, "continuous single tone")
        # Two-valued instantaneous frequency held over time → FSK. PSK also
        # has a bimodal inst-freq (transition spikes), so require a high DUTY
        # (freq actually SITS at the tones, not just spikes at symbol edges).
        if f.freq_bimodality > 0.55 and f.freq_duty > 0.55 and f.n_peaks >= 2:
            return ModResult(FSK, _conf(0.55 + f.freq_bimodality * 0.4), f,
                             "two discrete tones held over time (FSK)")
        # Phase jumps at a fixed carrier: high phase spread, low freq duty.
        if f.sigma_dp > 0.7 and f.freq_duty < 0.35:
            return ModResult(PSK, _conf(0.6 + min(f.sigma_dp, 2.0) * 0.1), f,
                             "phase jumps at a fixed carrier (PSK)")
        # Otherwise continuous frequency variation → FM.
        return ModResult(FM, _conf(0.55 + min(f.sigma_af, 0.4)), f,
                         "continuous frequency modulation")

    # 4. Flat, band-limited spectrum with a full/varying envelope → OFDM.
    if f.spectral_flatness > 0.35 and f.n_peaks >= 4:
        return ModResult(OFDM, _conf(0.5 + f.spectral_flatness * 0.4), f,
                         "flat, band-limited multi-carrier")

    # 5. Amplitude-varying family → AM vs SSB.
    #    AM has a dominant carrier and its phase stays ~constant (low sigma_dp);
    #    SSB (analytic audio) modulates BOTH amplitude and phase (high sigma_dp).
    if f.sigma_dp < 0.20:
        return ModResult(AM, _conf(0.6 + min(f.gamma_max, 4.0) * 0.08), f,
                         "amplitude modulation (steady carrier phase)")
    return ModResult(SSB, _conf(0.55 + min(f.sigma_dp, 1.0) * 0.25), f,
                     "single-sideband (amplitude + phase vary)")


def _conf(v: float) -> float:
    return float(max(0.0, min(1.0, v)))


def apply_modulation(sig, iq, fs, *, min_confidence: float = 0.4):
    """Enrich a Signal record in place with the measured modulation from its IQ.

    The ID-DBWRITE step: runs classify_modulation() and, when it finds a real
    modulation (not None) at or above *min_confidence*, writes sig.modulation
    (an IQ measurement overrides an allocation-*guessed* default from
    signal_classify.apply_classification), lifts sig.confidence, and fills
    sig.bandwidth_hz from the occupied bandwidth when it is still unknown.

    Returns the same Signal for chaining. Never raises. Pairs with
    signal_classify.apply_classification (freq→label): call that for the
    allocation label, this for the on-air modulation.
    """
    try:
        r = classify_modulation(iq, fs)
        if r.modulation != NONE and r.confidence >= min_confidence:
            sig.modulation = r.modulation
            sig.confidence = max(
                float(getattr(sig, "confidence", 0.0) or 0.0), r.confidence)
            if not getattr(sig, "bandwidth_hz", 0):
                bw = int(r.features.occ_bw * fs)
                if bw > 0:
                    sig.bandwidth_hz = bw
    except Exception as exc:
        log.debug("apply_modulation failed: %s", exc)
    return sig
