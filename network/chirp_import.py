"""CHIRP CSV import — no token, no scraping, fully offline.

CHIRP (chirpmyradio.com) is the de-facto open-source radio programming
tool. It has a blessed partnership with RepeaterBook and can export the
results of a Proximity Query (or any selection) to a generic CSV.

Operators who already use CHIRP to program their radios can drop the same
CSV into Squelch. This avoids requiring our own RepeaterBook token, avoids
scraping, and works fully offline.

CHIRP CSV header (radio-independent generic format):
  Location, Name, Frequency, Duplex, Offset, Tone, rToneFreq, cToneFreq,
  DtcsCode, DtcsPolarity, Mode, TStep, Skip, Comment, URCALL, RPT1CALL,
  RPT2CALL, DVCODE

Reference: chirpmyradio.com/projects/chirp/wiki/CSV_HowTo
"""
from __future__ import annotations
import csv
import logging
from pathlib import Path

from network.repeaterbook import Repeater

log = logging.getLogger(__name__)


# CHIRP "Tone" mode values → which field carries the tone value
# (CHIRP supports separate TX/RX tones and DTCS codes)
_TONE_MODES = {
    "": ("", ""),
    "Tone":  ("CTCSS", "rToneFreq"),    # TX only CTCSS
    "TSQL":  ("CTCSS", "cToneFreq"),    # TX+RX CTCSS (tone squelch)
    "DTCS":  ("DCS",   "DtcsCode"),     # DCS (digital coded squelch)
    "Cross": ("CTCSS", "rToneFreq"),    # complex; take the TX side
}


def _parse_float(v: str) -> float:
    """Tolerant float parse — CHIRP sometimes writes '146.520000' or
    '0.6'. Empty or junk → 0.0 rather than raising."""
    try:
        return float((v or "").strip())
    except (ValueError, TypeError):
        return 0.0


def _mode(chirp_mode: str) -> str:
    """Map CHIRP mode token to Squelch's display mode. Most CHIRP CSVs
    only carry FM/NFM/AM for analog. Digital modes from CHIRP exports are
    rare — usually 'DV' for D-STAR."""
    m = (chirp_mode or "FM").upper().strip()
    if m in ("FM", "NFM", "WFM"):
        return "FM"
    if m == "AM":
        return "AM"
    if m in ("DV", "DSTAR", "D-STAR"):
        return "D-STAR"
    return m or "FM"


def parse_chirp_csv(path: str | Path) -> list[Repeater]:
    """Read a CHIRP-format CSV file and return a list of Repeater records.

    Unknown / malformed rows are skipped with a debug log, not raised, so
    one bad row doesn't kill the whole import.
    """
    path = Path(path)
    out: list[Repeater] = []

    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        # utf-8-sig strips the BOM that some Excel exports leave
        reader = csv.DictReader(fh)
        if not reader.fieldnames or "Frequency" not in reader.fieldnames:
            raise ValueError(
                "Not a CHIRP CSV (missing 'Frequency' header). "
                "Expected columns include Location, Name, Frequency, "
                "Duplex, Offset, Tone, rToneFreq, Mode.")

        for row in reader:
            try:
                freq = _parse_float(row.get("Frequency", ""))
                if freq <= 0:
                    continue       # blank row or invalid

                # Duplex: "" / "+" / "-" / "split" (absolute TX freq)
                duplex = (row.get("Duplex") or "").strip()
                offset = _parse_float(row.get("Offset", ""))
                if duplex == "-":
                    input_mhz = freq - offset
                    offset_signed = -offset
                elif duplex == "+":
                    input_mhz = freq + offset
                    offset_signed = offset
                elif duplex.lower() == "split":
                    # CHIRP stores absolute TX freq in Offset for split
                    input_mhz = offset
                    offset_signed = offset - freq
                else:
                    # simplex
                    input_mhz = freq
                    offset_signed = 0.0

                # Tone: pick the right field based on the Tone-mode column
                tone_mode_raw = (row.get("Tone") or "").strip()
                tone_type, tone_src = _TONE_MODES.get(
                    tone_mode_raw, ("", ""))
                tone_val = (row.get(tone_src, "") or "").strip() \
                    if tone_src else ""
                if tone_type == "DCS" and tone_val:
                    polarity = (row.get("DtcsPolarity") or "NN")[:1]
                    tone_str = f"D{tone_val}{polarity}"
                elif tone_val:
                    tone_str = tone_val
                else:
                    tone_str = ""

                name    = (row.get("Name") or "").strip()
                comment = (row.get("Comment") or "").strip()

                out.append(Repeater(
                    callsign     = name[:12],
                    output_mhz   = freq,
                    input_mhz    = input_mhz,
                    offset_mhz   = offset_signed,
                    tone         = tone_str,
                    tone_type    = tone_type,
                    mode         = _mode(row.get("Mode")),
                    city         = comment[:40],
                    state        = "",
                    notes        = comment,
                    status       = "On-air",
                    use_code     = "OPEN",
                    distance_km  = 0.0,     # CHIRP CSV has no lat/lon
                    last_updated = "",
                ))
            except Exception as e:
                log.debug(f"CHIRP row skipped: {e}")
                continue

    log.info(f"CHIRP CSV: {len(out)} repeaters imported from {path.name}")
    return out
