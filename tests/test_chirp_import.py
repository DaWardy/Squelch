from __future__ import annotations
"""Unit tests for network/chirp_import — CHIRP CSV parser."""
import tempfile
from pathlib import Path
import pytest

from network.chirp_import import parse_chirp_csv


CHIRP_HEADER = (
    "Location,Name,Frequency,Duplex,Offset,Tone,rToneFreq,cToneFreq,"
    "DtcsCode,DtcsPolarity,Mode,TStep,Skip,Comment,URCALL,RPT1CALL,"
    "RPT2CALL,DVCODE")


def _write_csv(content: str) -> str:
    p = tempfile.NamedTemporaryFile(
        delete=False, suffix=".csv", mode="w", encoding="utf-8")
    p.write(content); p.close()
    return p.name


def test_simplex_row():
    """Simplex (no duplex, offset 0) — most common CHIRP row."""
    body = (CHIRP_HEADER + "\n"
            "1,2m Call,146.520000,,0.000000,,88.5,88.5,023,NN,FM,5.00,,"
            "Calling Freq,,,,\n")
    r = parse_chirp_csv(_write_csv(body))
    assert len(r) == 1
    assert r[0].callsign == "2m Call"
    assert r[0].output_mhz == 146.52
    assert r[0].input_mhz  == 146.52
    assert r[0].offset_mhz == 0.0
    assert r[0].mode == "FM"


def test_minus_duplex_with_tone():
    """Standard 2m repeater: 600 kHz negative offset, TSQL 100 Hz."""
    body = (CHIRP_HEADER + "\n"
            "1,KK6QXJ,145.380000,-,0.600000,TSQL,100.0,100.0,023,NN,"
            "FM,5.00,,Auburn,,,,\n")
    r = parse_chirp_csv(_write_csv(body))
    assert len(r) == 1
    assert r[0].output_mhz == 145.38
    assert abs(r[0].input_mhz - 144.78) < 1e-6
    assert r[0].offset_mhz == -0.6
    assert r[0].tone == "100.0"
    assert r[0].tone_type == "CTCSS"


def test_plus_duplex_70cm():
    """440 MHz repeater with +5 MHz offset, Tone (TX-only CTCSS)."""
    body = (CHIRP_HEADER + "\n"
            "1,W6RXD,442.075000,+,5.000000,Tone,123.0,88.5,023,NN,"
            "FM,5.00,,Repeater,,,,\n")
    r = parse_chirp_csv(_write_csv(body))
    assert r[0].input_mhz == 447.075
    assert r[0].offset_mhz == 5.0
    assert r[0].tone == "123.0"


def test_dtcs_code_with_polarity():
    """DTCS (DCS) row — code + polarity should round-trip."""
    body = (CHIRP_HEADER + "\n"
            "1,W6XYZ,146.94,-,0.6,DTCS,88.5,88.5,156,NR,FM,5.00,,,,,,\n")
    r = parse_chirp_csv(_write_csv(body))
    assert r[0].tone_type == "DCS"
    assert r[0].tone == "D156N"


def test_dstar_mode_mapped():
    """DV mode → D-STAR."""
    body = (CHIRP_HEADER + "\n"
            "1,W6DV,438.5,-,5.0,,88.5,88.5,023,NN,DV,5.00,,,,,,\n")
    r = parse_chirp_csv(_write_csv(body))
    assert r[0].mode == "D-STAR"


def test_blank_and_invalid_rows_skipped():
    """Empty frequency / junk rows should be skipped, not raise."""
    body = (CHIRP_HEADER + "\n"
            "1,,,,,,,,,,,,,,,,,\n"                       # all blank
            "2,Good,146.52,,0,,88.5,88.5,023,NN,FM,5.00,,,,,,\n"
            "3,BadFreq,not-a-number,,0,,88.5,88.5,023,NN,FM,5,,,,,,\n")
    r = parse_chirp_csv(_write_csv(body))
    assert len(r) == 1
    assert r[0].callsign == "Good"


def test_utf8_bom_handled():
    """Excel sometimes saves with a UTF-8 BOM; must not break parsing."""
    body = ("\ufeff" + CHIRP_HEADER + "\n"
            "1,Test,146.52,,0,,88.5,88.5,023,NN,FM,5.00,,,,,,\n")
    r = parse_chirp_csv(_write_csv(body))
    assert len(r) == 1


def test_rejects_non_chirp_file():
    """A random CSV without the Frequency column should raise clearly."""
    body = "Name,Description\nfoo,bar\n"
    with pytest.raises(ValueError, match="Frequency"):
        parse_chirp_csv(_write_csv(body))
