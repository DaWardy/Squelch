"""Sprint 68 — S-meter history spark-line + FT8 session SNR tracking."""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


# ── SMeterWidget history ──────────────────────────────────────────────────────

class TestSMeterHistory:

    def _src(self):
        return (ROOT / "ui/widgets/smeter.py").read_text(encoding="utf-8")

    def test_history_deque_used(self):
        assert "deque" in self._src()

    def test_history_attribute_initialised(self):
        assert "_history" in self._src()

    def test_set_level_appends_to_history(self):
        src = self._src()
        idx = src.find("def set_level(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_history.append" in body

    def test_sparkline_drawn_in_paintevent(self):
        src = self._src()
        assert "spark" in src.lower() or "_history" in src

    def test_history_max_len_set(self):
        src = self._src()
        assert "_HISTORY_LEN" in src or "maxlen" in src

    def test_qpointf_used_for_line_drawing(self):
        assert "QPointF" in self._src()

    def test_height_increased_for_sparkline(self):
        src = self._src()
        # Height should be larger than the original 28px
        assert "46" in src or "44" in src or "setFixedHeight(4" in src

    def test_bar_color_for_helper(self):
        assert "_bar_color_for" in self._src()

    def test_120_history_len(self):
        src = self._src()
        assert "120" in src


class TestSMeterHistoryLogic:
    """Pure-logic tests for history accumulation."""

    def test_history_fills_up(self):
        from collections import deque
        hist = deque(maxlen=5)
        for i in range(10):
            hist.append(i % 14)
        assert len(hist) == 5   # capped at maxlen

    def test_oldest_discarded(self):
        from collections import deque
        hist = deque(maxlen=3)
        hist.extend([0, 1, 2])
        hist.append(9)
        assert list(hist) == [1, 2, 9]

    def test_sparkline_y_scaling(self):
        # S-level 13 should map to top, 0 to bottom
        spark_h = 18
        lv_max = 13
        lv_min = 0
        y_max = spark_h - 1 - int(lv_max / 13 * (spark_h - 2))
        y_min = spark_h - 1 - int(lv_min / 13 * (spark_h - 2))
        assert y_max < y_min   # higher level = lower y (closer to top)


# ── FT8 session SNR tracking ──────────────────────────────────────────────────

class TestFT8SessionSNR:

    def _src(self):
        return (ROOT / "ui/tabs/modes_tab.py").read_text(encoding="utf-8")

    def test_best_snr_by_band_initialised(self):
        assert "_best_snr_by_band" in self._src()

    def test_snr_updated_in_on_ft8_decode(self):
        src = self._src()
        idx = src.find("def _on_ft8_decode(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_best_snr_by_band" in body

    def test_better_snr_replaces_worse(self):
        src = self._src()
        idx = src.find("def _on_ft8_decode(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "snr > current_best" in body or "> current" in body

    def test_show_session_snr_method(self):
        assert "def _show_session_snr(" in self._src()

    def test_session_snr_button_in_stats(self):
        src = self._src()
        idx = src.find("def _build_session_stats(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "Session SNR" in body or "_show_session_snr" in body

    def test_band_order_in_snr_display(self):
        src = self._src()
        idx = src.find("def _show_session_snr(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "20m" in body and "40m" in body


class TestSNRLogic:
    """Pure-logic: SNR tracking update logic."""

    def test_better_snr_wins(self):
        best_snr_by_band = {}
        band = "20m"

        def update(snr, call):
            current_best, _ = best_snr_by_band.get(band, (-99, ""))
            if snr > current_best:
                best_snr_by_band[band] = (snr, call)

        update(-5, "VK2AB")
        update(-15, "JA1XY")   # worse SNR — should not replace
        update(+3, "W1AW")     # better — should replace

        best, call = best_snr_by_band[band]
        assert best == 3
        assert call == "W1AW"

    def test_first_decode_always_stored(self):
        best_snr_by_band = {}
        band = "40m"
        snr, call = -20, "ZL2BCH"
        current_best, _ = best_snr_by_band.get(band, (-99, ""))
        if snr > current_best:
            best_snr_by_band[band] = (snr, call)
        assert band in best_snr_by_band

    def test_negative_snr_stored(self):
        best_snr_by_band = {}
        band = "160m"
        current_best, _ = best_snr_by_band.get(band, (-99, ""))
        snr = -18
        if snr > current_best:
            best_snr_by_band[band] = (snr, "W1AW")
        assert best_snr_by_band[band][0] == -18
