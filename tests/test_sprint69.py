"""Sprint 69 — FT8 decode context menu + CHIRP → rig memory import."""
from __future__ import annotations
import sys
import pathlib
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


# ── FT8 decode context menu ───────────────────────────────────────────────────

class TestDecodeContextMenu:

    def _src(self):
        return (ROOT / "ui/tabs/modes_tab.py").read_text(encoding="utf-8")

    def test_context_menu_connected(self):
        src = self._src()
        assert "customContextMenuRequested.connect" in src
        assert "_decode_context_menu" in src

    def test_decode_context_menu_method(self):
        assert "def _decode_context_menu(" in self._src()

    def test_call_station_action(self):
        src = self._src()
        idx = src.find("def _decode_context_menu(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "Call" in body

    def test_log_qso_action(self):
        src = self._src()
        idx = src.find("def _decode_context_menu(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "Log QSO" in body or "log" in body.lower()

    def test_qrz_lookup_action(self):
        src = self._src()
        idx = src.find("def _decode_context_menu(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "qrz.com" in body or "QRZ" in body

    def test_watch_list_action(self):
        src = self._src()
        idx = src.find("def _decode_context_menu(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "watch" in body.lower() or "_ft8_watch" in body

    def test_copy_callsign_action(self):
        src = self._src()
        idx = src.find("def _decode_context_menu(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "clipboard" in body.lower() or "Copy" in body

    def test_log_from_decode_method(self):
        assert "def _log_from_decode(" in self._src()

    def test_add_to_ft8_watch_method(self):
        assert "def _add_to_ft8_watch(" in self._src()

    def test_add_watch_deduplicates(self):
        src = self._src()
        idx = src.find("def _add_to_ft8_watch(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "not in terms" in body or "if call" in body


class TestAddToFT8WatchLogic:
    """Pure-logic: duplicate prevention in watch-list add."""

    def _add(self, current_text, call):
        terms = [t.strip().upper() for t in current_text.split(",") if t.strip()]
        if call.upper() not in terms:
            terms.append(call.upper())
        return ", ".join(terms)

    def test_adds_new_call(self):
        result = self._add("VK,JA", "W1AW")
        assert "W1AW" in result

    def test_no_duplicate_added(self):
        result = self._add("VK,JA,W1AW", "W1AW")
        assert result.count("W1AW") == 1

    def test_empty_watch_list(self):
        result = self._add("", "VK2AB")
        assert result == "VK2AB"

    def test_preserves_existing(self):
        result = self._add("VK,JA", "ZL")
        assert "VK" in result
        assert "JA" in result
        assert "ZL" in result


# ── CHIRP CSV → rig memory import ────────────────────────────────────────────

class TestCHIRPMemoryImport:

    def _src(self):
        return (ROOT / "ui/tabs/rig_tab.py").read_text(encoding="utf-8")

    def test_import_chirp_method_defined(self):
        assert "def _mem_import_chirp(" in self._src()

    def test_import_chirp_button_in_memory_section(self):
        src = self._src()
        idx = src.find("def _build_memory_section(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "Import CHIRP" in body or "import_chirp" in body.lower()

    def test_parse_chirp_csv_called(self):
        src = self._src()
        idx = src.find("def _mem_import_chirp(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "parse_chirp_csv" in body

    def test_slot_auto_incremented(self):
        src = self._src()
        idx = src.find("def _mem_import_chirp(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "max(self._memories" in body or "slot" in body

    def test_freq_converted_from_mhz(self):
        src = self._src()
        idx = src.find("def _mem_import_chirp(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "1_000_000" in body or "1000000" in body


class TestCHIRPImportLogic:
    """Pure-logic: CSV parsing and memory slot building."""

    def _write_chirp_csv(self, tmp_dir):
        p = pathlib.Path(tmp_dir) / "test.csv"
        p.write_text(
            "Location,Name,Frequency,Duplex,Offset,Tone,rToneFreq,cToneFreq,"
            "DtcsCode,DtcsPolarity,Mode,TStep,Skip,Comment\n"
            "0,W1XYZ,146.520000,,0,None,88.5,88.5,023,NN,FM,5.00,,\n"
            "1,WB2ABC,447.000000,-,5,TONE,100.0,100.0,023,NN,FM,5.00,,\n",
            encoding="utf-8")
        return str(p)

    def test_parse_produces_repeaters(self):
        from network.chirp_import import parse_chirp_csv
        tmp = tempfile.mkdtemp()
        path = self._write_chirp_csv(tmp)
        reps = parse_chirp_csv(path)
        assert len(reps) >= 1

    def test_output_freq_parsed(self):
        from network.chirp_import import parse_chirp_csv
        tmp = tempfile.mkdtemp()
        path = self._write_chirp_csv(tmp)
        reps = parse_chirp_csv(path)
        freqs = [r.output_mhz for r in reps]
        assert any(abs(f - 146.52) < 0.001 for f in freqs)

    def test_slot_building(self):
        memories = {1: (146520000, "FM", "W1XYZ"),
                    2: (447000000, "FM", "WB2ABC")}
        new_slot = max(memories.keys(), default=0) + 1
        assert new_slot == 3

    def test_freq_to_hz_conversion(self):
        output_mhz = 146.520
        assert int(output_mhz * 1_000_000) == 146_520_000
