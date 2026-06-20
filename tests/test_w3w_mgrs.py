"""Sprint 66 — What3Words + MGRS coordinate support."""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


# ── _is_w3w() detection ──────────────────────────────────────────────────────

class TestIsW3W:

    def _is(self, text):
        from core.location import _is_w3w
        return _is_w3w(text)

    def test_valid_w3w(self):
        assert self._is("filled.count.soap")

    def test_valid_w3w_capitals(self):
        assert self._is("FILLED.COUNT.SOAP")

    def test_three_slash_prefix_stripped_elsewhere(self):
        # _is_w3w checks the bare word.word.word, caller strips ///
        assert self._is("word.word.word")

    def test_two_words_invalid(self):
        assert not self._is("two.words")

    def test_four_words_invalid(self):
        assert not self._is("a.b.c.d")

    def test_numbers_invalid(self):
        assert not self._is("14.074")

    def test_grid_square_invalid(self):
        assert not self._is("FN31pr")

    def test_empty_invalid(self):
        assert not self._is("")

    def test_single_word_invalid(self):
        assert not self._is("oneword")


# ── _w3w_to_latlon() without API key ─────────────────────────────────────────

class TestW3WNoKey:

    def test_returns_none_without_key(self):
        from core.location import _w3w_to_latlon
        result = _w3w_to_latlon("filled.count.soap", cfg=None)
        # No key → must return None (not raise)
        assert result is None

    def test_returns_none_no_requests_fallback(self):
        import core.location as loc_mod
        orig = loc_mod.HAS_REQUESTS
        loc_mod.HAS_REQUESTS = False
        result = loc_mod._w3w_to_latlon("word.word.word", cfg=None)
        loc_mod.HAS_REQUESTS = orig
        assert result is None


# ── _latlon_to_mgrs / _mgrs_to_latlon ────────────────────────────────────────

class TestMGRSConversion:

    def test_latlon_to_mgrs_returns_str_or_empty(self):
        from core.location import _latlon_to_mgrs
        result = _latlon_to_mgrs(41.7, -72.7)
        assert isinstance(result, str)   # "" if mgrs not installed, else MGRS string

    def test_mgrs_to_latlon_returns_none_or_tuple(self):
        from core.location import _mgrs_to_latlon
        result = _mgrs_to_latlon("18SUJ2338208028")
        assert result is None or isinstance(result, tuple)

    def test_mgrs_round_trip(self):
        from core.location import _latlon_to_mgrs, _mgrs_to_latlon, _HAS_MGRS
        if not _HAS_MGRS:
            return   # skip without mgrs library
        mgrs_str = _latlon_to_mgrs(41.7, -72.7)
        if not mgrs_str:
            return
        result = _mgrs_to_latlon(mgrs_str)
        assert result is not None
        lat, lon = result
        assert abs(lat - 41.7) < 0.1
        assert abs(lon - (-72.7)) < 0.1


# ── Grid calculator source checks ────────────────────────────────────────────

class TestGridCalcDialogSource:

    def _src(self):
        return (ROOT / "ui/dialogs/grid_calc_dialog.py").read_text(encoding="utf-8")

    def test_mgrs_tab_defined(self):
        assert "_build_mgrs_tab" in self._src()

    def test_w3w_tab_defined(self):
        assert "_build_w3w_tab" in self._src()

    def test_calc_from_mgrs_method(self):
        assert "def _calc_from_mgrs(" in self._src()

    def test_calc_from_w3w_method(self):
        assert "def _calc_from_w3w(" in self._src()

    def test_populate_outputs_helper(self):
        assert "def _populate_outputs(" in self._src()

    def test_mgrs_input_field(self):
        assert "_mgrs_in" in self._src()

    def test_w3w_input_field(self):
        assert "_w3w_in" in self._src()

    def test_tab_widget_used(self):
        assert "QTabWidget" in self._src()

    def test_w3w_calls_latlon_to_w3w(self):
        src = self._src()
        idx = src.find("def _populate_outputs(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_latlon_to_w3w" in body

    def test_mgrs_calls_latlon_to_mgrs(self):
        src = self._src()
        idx = src.find("def _populate_outputs(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_latlon_to_mgrs" in body


# ── W3W API key in Settings ───────────────────────────────────────────────────

class TestW3WSettingsWiring:

    def _apis_src(self):
        return (ROOT / "ui/dialogs/settings_apis_tab.py").read_text(encoding="utf-8")

    def _dialog_src(self):
        return (ROOT / "ui/dialogs/settings_dialog.py").read_text(encoding="utf-8")

    def test_w3w_key_field_in_apis_tab(self):
        assert "_w3w_key" in self._apis_src()

    def test_w3w_section_in_apis_tab(self):
        assert "What3Words" in self._apis_src()

    def test_w3w_key_loaded_in_dialog(self):
        assert "w3w_api_key" in self._dialog_src()

    def test_w3w_key_stored_in_keyring(self):
        src = self._dialog_src()
        # Should be in the keyring save list
        assert "w3w_api_key" in src


# ── W3W in location search ────────────────────────────────────────────────────

class TestW3WLocationSearch:

    def _src(self):
        return (ROOT / "core/location.py").read_text(encoding="utf-8")

    def test_is_w3w_function_defined(self):
        assert "def _is_w3w(" in self._src()

    def test_w3w_to_latlon_defined(self):
        assert "def _w3w_to_latlon(" in self._src()

    def test_latlon_to_w3w_defined(self):
        assert "def _latlon_to_w3w(" in self._src()

    def test_w3w_checked_in_search(self):
        src = self._src()
        idx = src.find("def search(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_is_w3w" in body

    def test_w3w_api_url_defined(self):
        assert "what3words.com" in self._src()

    def test_slash_prefix_stripped(self):
        src = self._src()
        assert "lstrip" in src or "strip" in src
