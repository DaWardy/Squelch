# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/decode_workbench.py

The decode workbench — one call that takes an IQ slice (from a waterfall
right-click selection via `core/iq_ring`) and runs it through the whole existing
analysis chain to answer "what is this, and can we read it?":

  1. isolate the selected sub-band          (core/demod frequency_shift+decimate)
  2. classify the modulation                (core/modulation_classify)
  3. look up candidate identities offline   (core/sigid_db — builtin + Artemis)
  4. if it's an on/off/FSK/PSK carrier, recover symbols → bits → frame:
        core/bitslicer → core/framing  (preamble/sync/payload/CRC)

Returns a flat `WorkbenchResult` the UI can drop onto a Signal record
(`Signal.modulation` / `.classification` / `.decoded` / `.confidence`) and show
in the Signal Log. Pure Python over the existing cores; never raises — a bad
selection yields an empty-ish result, not a crash.
"""

import logging
from dataclasses import dataclass, field

import numpy as np

log = logging.getLogger(__name__)

_MAX_HEX = 512          # cap the decoded payload preview


def _family_for(modulation: str):
    """Map a (possibly compound) modulation label to a bit-slicer family, or
    None if it isn't generically bit-decodable. Substring match handles labels
    like 'OOK/ASK', '2-FSK', and CW (on/off keying → treat as OOK)."""
    m = (modulation or "").upper()
    if "FSK" in m:
        return "FSK"
    if "PSK" in m:
        return "PSK"
    if "OOK" in m or "ASK" in m or m == "CW":
        return "OOK"
    return None


@dataclass
class WorkbenchResult:
    center_hz:      int   = 0
    bandwidth_hz:   int   = 0
    modulation:     str   = ""
    mod_confidence: float = 0.0
    occupied_bw_hz: int   = 0
    identities:     list  = field(default_factory=list)   # [{name, score, url}]
    decodable:      bool  = False
    family:         str   = ""
    n_symbols:      int   = 0
    bit_confidence: float = 0.0
    symbol_rate:    float = 0.0
    payload_hex:    str   = ""
    frame_ok:       bool  = False
    crc_matches:    list  = field(default_factory=list)
    text:           str   = ""     # human-readable decode (CW/RTTY/DTMF)
    decoder:        str   = ""     # which text decoder produced `text`
    notes:          list  = field(default_factory=list)

    @property
    def best_identity(self) -> str:
        return self.identities[0]["name"] if self.identities else ""

    def summary(self) -> str:
        """A one-line human summary for a status bar / Signal Log cell."""
        bits = [self.modulation or "?"]
        if self.best_identity:
            bits.append(f"= {self.best_identity}")
        if self.text:
            bits.append(f"[{self.decoder}] {self.text[:40]}")
        elif self.decodable and self.n_symbols:
            bits.append(f"{self.n_symbols} sym"
                        + (" CRC✓" if self.frame_ok else ""))
        return "  ".join(bits)


def analyze(iq, sample_rate: float, center_hz: int, *,
            freq_hz: int = 0, bandwidth_hz: int = 0,
            sigid_db=None) -> WorkbenchResult:
    """Analyse an IQ slice → WorkbenchResult. Never raises.

    If `freq_hz`+`bandwidth_hz` are given, the sub-band is isolated first (tune
    to it and low-pass to the bandwidth) so the classifier/decoder see only the
    wanted signal."""
    res = WorkbenchResult(center_hz=int(center_hz), bandwidth_hz=int(bandwidth_hz))
    try:
        x = np.asarray(iq, dtype=np.complex64)
        fs = float(sample_rate)
        if x.size < 8 or fs <= 0:
            res.notes.append("selection too short")
            return res
        center_used = int(center_hz)
        if bandwidth_hz > 0 and freq_hz:
            x, fs = _isolate(x, fs, int(freq_hz) - int(center_hz), int(bandwidth_hz))
            center_used = int(freq_hz)
        _classify(res, x, fs, bandwidth_hz)
        _identify(res, sigid_db, center_used, bandwidth_hz or res.occupied_bw_hz)
        _decode(res, x, fs)
        _text_decode(res, x, fs)
    except Exception as exc:                        # pragma: no cover
        log.debug("decode_workbench.analyze failed: %s", exc)
        res.notes.append(f"analyze error: {exc}")
    return res


# ── stages ───────────────────────────────────────────────────────────────────
def _isolate(iq, fs, offset_hz, bandwidth_hz):
    from core.demod import frequency_shift, lowpass_decimate
    bb = frequency_shift(iq, fs, offset_hz)
    target = max(float(bandwidth_hz) * 4.0, 8_000.0)
    bb, new_fs = lowpass_decimate(bb, fs, bandwidth_hz, target)
    return bb, new_fs


def _classify(res, iq, fs, bandwidth_hz):
    from core.modulation_classify import classify_modulation
    m = classify_modulation(iq, fs)
    res.modulation = m.modulation
    res.mod_confidence = round(float(m.confidence), 3)
    occ = getattr(getattr(m, "features", None), "occ_bw", 0.0) or 0.0
    res.occupied_bw_hz = int(occ * fs) if occ else int(bandwidth_hz or 0)
    if m.note:
        res.notes.append(m.note)


def _identify(res, sigid_db, freq_hz, bw_hz):
    if sigid_db is None:
        return
    try:
        for m in sigid_db.identify(int(freq_hz), int(bw_hz or 0), res.modulation):
            res.identities.append({"name": m.entry.name,
                                   "score": round(float(m.score), 3),
                                   "url": getattr(m.entry, "url", "")})
    except Exception as exc:                        # pragma: no cover
        log.debug("identify failed: %s", exc)


def _decode(res, iq, fs):
    family = _family_for(res.modulation)
    if not family:
        return
    res.decodable = True
    res.family = family
    from core.bitslicer import slice_bits, bits_to_hex
    sr = slice_bits(iq, fs, family=family)
    res.n_symbols = int(sr.n_symbols)
    res.bit_confidence = round(float(sr.confidence), 3)
    res.symbol_rate = round(float(sr.symbol_rate), 1)
    if not sr.bits:
        return
    res.payload_hex = bits_to_hex(sr.bits)[:_MAX_HEX]
    try:
        from core.framing import inspect_frame
        rep = inspect_frame(sr.bits)
        res.frame_ok = bool(rep.crc_ok)
        res.crc_matches = list(rep.crc_matches or [])
        res.notes.extend(rep.notes or [])
    except Exception as exc:                        # pragma: no cover
        log.debug("framing failed: %s", exc)


def _readable(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 2:
        return False
    alnum = sum(1 for c in t if c.isalnum())
    return alnum >= 2 and alnum >= 0.4 * len(t)


def _text_decode(res, iq, fs):
    """Try a protocol text decoder matched to the modulation (best-effort):
    FSK→RTTY, CW/OOK→Morse, AM/FM→DTMF touch-tones."""
    mod = (res.modulation or "").upper()
    try:
        if "FSK" in mod:
            from core.rtty import decode_rtty
            t = decode_rtty(iq, fs)
            if _readable(t):
                res.text, res.decoder = t.strip(), "RTTY"
        elif "CW" in mod or "OOK" in mod or "ASK" in mod:
            from core.cw_decode import decode_cw
            t = decode_cw(iq, fs)
            if _readable(t):
                res.text, res.decoder = t.strip(), "CW"
        elif "AM" in mod or "FM" in mod:
            from core.demod import demodulate
            from core.dtmf import decode_dtmf
            audio = demodulate(iq, fs, "NBFM" if "FM" in mod else "AM",
                               audio_rate=8000)
            d = decode_dtmf(audio, 8000)
            if d:
                res.text, res.decoder = d, "DTMF"
    except Exception as exc:                         # pragma: no cover
        log.debug("text decode failed: %s", exc)
