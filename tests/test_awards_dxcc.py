"""Tests for core/awards.py _prefix_to_dxcc — CTY.DAT integration."""
from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock
from core.awards import AwardTracker


# ── Fallback table (no CTY.DAT) ──────────────────────────────────────────────

def _dxcc(call: str) -> str:
    """Helper: call the static method directly."""
    return AwardTracker._prefix_to_dxcc(call)


def _with_no_cty():
    """Context: CTY_LOCAL does not exist so fallback table is used."""
    mock_path = MagicMock()
    mock_path.exists.return_value = False
    return patch("network.cty_data.CTY_LOCAL", mock_path)


def test_empty_callsign_returns_empty():
    assert _dxcc("") == ""


def test_usa_w_prefix():
    with _with_no_cty():
        assert _dxcc("W1AW") == "K"


def test_usa_k_prefix():
    with _with_no_cty():
        assert _dxcc("K1JT") == "K"


def test_usa_n_prefix():
    with _with_no_cty():
        assert _dxcc("N5ZM") == "K"


def test_usa_aa_prefix():
    with _with_no_cty():
        assert _dxcc("AA4MM") == "K"


def test_canada_ve_prefix():
    with _with_no_cty():
        assert _dxcc("VE3XYZ") == "VE"


def test_canada_va_prefix():
    with _with_no_cty():
        assert _dxcc("VA3ABC") == "VE"


def test_england_g_prefix():
    with _with_no_cty():
        assert _dxcc("G3ZVW") == "G"


def test_germany_dl_prefix():
    with _with_no_cty():
        assert _dxcc("DL3YEL") == "DL"


def test_france_f_prefix():
    with _with_no_cty():
        assert _dxcc("F5LEN") == "F"


def test_japan_ja_prefix():
    with _with_no_cty():
        assert _dxcc("JA1AAA") == "JA"


def test_australia_vk_prefix():
    with _with_no_cty():
        assert _dxcc("VK2QR") == "VK"


def test_brazil_py_prefix():
    with _with_no_cty():
        assert _dxcc("PY3RHM") == "PY"


def test_russia_ua_prefix():
    with _with_no_cty():
        assert _dxcc("UA9XQR") == "UA"


def test_unknown_prefix_returns_two_chars():
    with _with_no_cty():
        result = _dxcc("ZZ9XYZ")
        assert result == "ZZ"


def test_single_char_callsign_returns_single_char():
    with _with_no_cty():
        result = _dxcc("Z")
        assert result == "Z"


# ── CTY.DAT integration ───────────────────────────────────────────────────────

def test_cty_dat_used_when_loaded():
    """When CTY.DAT singleton is loaded, its result should be returned."""
    mock_path = MagicMock()
    mock_path.exists.return_value = True

    mock_entity = MagicMock()

    mock_cty = MagicMock()
    mock_cty.is_loaded = True
    mock_cty.dxcc_name.return_value = "Czech Republic"

    with patch("network.cty_data.CTY_LOCAL", mock_path), \
         patch("network.cty_data.get_cty", return_value=mock_cty):
        result = _dxcc("OK1XYZ")

    assert result == "Czech Republic"
    mock_cty.dxcc_name.assert_called_once_with("OK1XYZ")


def test_fallback_used_when_cty_not_loaded():
    """When CTY.DAT singleton exists but is_loaded=False, use fallback."""
    mock_path = MagicMock()
    mock_path.exists.return_value = True

    mock_cty = MagicMock()
    mock_cty.is_loaded = False

    with patch("network.cty_data.CTY_LOCAL", mock_path), \
         patch("network.cty_data.get_cty", return_value=mock_cty):
        result = _dxcc("W1AW")

    assert result == "K"


def test_fallback_used_when_cty_returns_empty():
    """When CTY.DAT has no match, fall through to manual table."""
    mock_path = MagicMock()
    mock_path.exists.return_value = True

    mock_cty = MagicMock()
    mock_cty.is_loaded = True
    mock_cty.dxcc_name.return_value = ""

    with patch("network.cty_data.CTY_LOCAL", mock_path), \
         patch("network.cty_data.get_cty", return_value=mock_cty):
        result = _dxcc("K1JT")

    assert result == "K"


def test_cty_exception_falls_back_gracefully():
    """If CTY import/lookup raises, manual fallback is used."""
    with patch("network.cty_data.CTY_LOCAL",
               side_effect=Exception("import error")):
        result = _dxcc("VE3XYZ")
    assert result == "VE"
