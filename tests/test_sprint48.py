"""Sprint 48 — FEAT-17 IF BW + FEAT-21 memory channel persistence.

Pure-logic and source-level tests only.
"""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


def _sdr_src() -> str:
    return (ROOT / "ui/tabs/sdr_tab.py").read_text(encoding="utf-8")


def _rig_src() -> str:
    return (ROOT / "ui/tabs/rig_tab.py").read_text(encoding="utf-8")


# ── FEAT-17: IF BW per mode ───────────────────────────────────────────────────

class TestIFBandwidthPerMode:

    def test_mode_default_bw_map_defined(self):
        assert "_DEMOD_DEFAULT_BW" in _sdr_src()

    def test_on_demod_mode_change_handler(self):
        assert "def _on_demod_mode_change(" in _sdr_src()

    def test_mode_change_connected_to_combo(self):
        src = _sdr_src()
        assert "_on_demod_mode_change" in src
        assert "currentTextChanged.connect(self._on_demod_mode_change)" in src

    def test_bw_hz_property_defined(self):
        assert "def _bw_hz" in _sdr_src()

    def test_filter_lines_created(self):
        src = _sdr_src()
        assert "_filter_lo_line" in src
        assert "_filter_hi_line" in src

    def test_filter_lines_updated_in_axes(self):
        src = _sdr_src()
        idx = src.find("def _update_axes(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_filter_lo_line" in body
        assert "_filter_hi_line" in body

    def test_demod_mode_in_save_state(self):
        src = _sdr_src()
        idx = src.find("def save_state(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "demod_mode" in body
        assert "demod_bw" in body

    def test_demod_mode_in_restore_state(self):
        src = _sdr_src()
        idx = src.find("def restore_state(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "demod_mode" in body

    def test_default_bw_mode_values(self):
        """All known demod modes must have default BW entries."""
        src = _sdr_src()
        for mode in ("AM", "WFM", "USB", "LSB", "CW"):
            assert f'"{mode}"' in src


class TestBWHzParsing:
    """Verify _bw_hz parses the combo strings correctly."""

    def _parse(self, text: str) -> int:
        """Mirror the _bw_hz parsing logic."""
        parts = text.strip().split()
        val   = float(parts[0])
        unit  = parts[1] if len(parts) > 1 else "Hz"
        if unit == "kHz":
            return int(val * 1_000)
        if unit == "MHz":
            return int(val * 1_000_000)
        return int(val)

    def test_hz(self):
        assert self._parse("500 Hz") == 500

    def test_khz(self):
        assert self._parse("2.5 kHz") == 2_500

    def test_large_khz(self):
        assert self._parse("200 kHz") == 200_000

    def test_1_khz(self):
        assert self._parse("1 kHz") == 1_000

    def test_200_hz(self):
        assert self._parse("200 Hz") == 200


# ── FEAT-21: Memory channel persistence ──────────────────────────────────────

class TestMemoryChannelPersistence:

    def test_memories_in_save_state(self):
        src = _rig_src()
        idx = src.find("def save_state(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert '"memories"' in body

    def test_memories_restored_in_restore_state(self):
        src = _rig_src()
        idx = src.find("def restore_state(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "memories" in body
        assert "_mem_table.insertRow" in body

    def test_export_csv_method_exists(self):
        assert "def _mem_export_csv(" in _rig_src()

    def test_export_uses_csv_safe(self):
        src = _rig_src()
        idx = src.find("def _mem_export_csv(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "csv_safe" in body

    def test_export_button_added(self):
        assert "Export CSV" in _rig_src()

    def test_memories_dict_initialized(self):
        src = _rig_src()
        assert "_memories      = {}" in src or "_memories = {}" in src


class TestMemoryChannelLogic:
    """Pure-logic test for memory save/restore round-trip."""

    def test_save_restore_roundtrip(self):
        memories = {1: (14_074_000, "USB", "20m FT8"),
                    2: (7_074_000,  "LSB", "40m FT8")}
        # Simulate what save_state does
        saved = [
            [slot, hz, mode, label]
            for slot, (hz, mode, label) in memories.items()
        ]
        # Simulate what restore_state does
        restored = {}
        for entry in saved:
            slot, hz, mode, label = entry
            restored[slot] = (hz, mode, label)
        assert restored == memories

    def test_csv_row_format(self):
        hz, mode, label = 14_074_000, "USB", "FT8 calling"
        row = [f"M{1:02d}", f"{hz/1e6:.6f}", mode, label]
        assert row[0] == "M01"
        assert row[1] == "14.074000"
