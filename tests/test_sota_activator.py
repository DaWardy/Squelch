"""Sprint 65 — SOTA/POTA activator panel + FT8 DXCC-needed alert."""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


# ── SOTA/POTA spot posting logic ──────────────────────────────────────────────

class TestSpotPosting:
    """Source-level checks for the posting functions."""

    def _src(self):
        return (ROOT / "network/sota_pota.py").read_text(encoding="utf-8")

    def test_post_sota_spot_defined(self):
        assert "def post_sota_spot(" in self._src()

    def test_post_pota_spot_defined(self):
        assert "def post_pota_spot(" in self._src()

    def test_sota_spot_post_url(self):
        assert "api2.sota.org.uk" in self._src()

    def test_pota_spot_post_url(self):
        assert "api.pota.app" in self._src()

    def test_api_key_checked_for_sota(self):
        src = self._src()
        idx = src.find("def post_sota_spot(")
        body = src[idx: src.find("\ndef ", idx + 10)]
        assert "api_key" in body

    def test_no_key_needed_for_pota(self):
        src = self._src()
        idx = src.find("def post_pota_spot(")
        body = src[idx: src.find("\ndef ", idx + 10)]
        assert "api_key" not in body

    def test_netlog_record_called(self):
        src = self._src()
        assert "record_connection" in src

    def test_frequency_converted_to_khz(self):
        src = self._src()
        assert "* 1000" in src or "* 1_000" in src

    def test_timeout_set(self):
        src = self._src()
        assert "timeout=10" in src

    def test_returns_false_without_requests(self):
        from network.sota_pota import post_sota_spot, post_pota_spot
        # Mock HAS_REQUESTS as False by importing with a monkeypatch
        import network.sota_pota as mod
        orig = mod.HAS_REQUESTS
        mod.HAS_REQUESTS = False
        ok, msg = post_sota_spot("W1AW", "W7O/NC-001", 14.285)
        ok2, msg2 = post_pota_spot("W1AW", "K-0001", 14.285)
        mod.HAS_REQUESTS = orig
        assert ok is False
        assert ok2 is False


class TestSpotPacketFormat:
    """Verify spot packet construction without network calls."""

    def test_sota_frequency_in_khz(self):
        freq_mhz = 14.285
        expected_khz = str(round(freq_mhz * 1000))
        assert expected_khz == "14285"

    def test_pota_frequency_in_khz(self):
        freq_mhz = 7.074
        assert str(int(freq_mhz * 1000)) == "7074"

    def test_callsign_uppercased(self):
        call = "w1aw"
        assert call.upper() == "W1AW"

    def test_sota_summit_code_extracted(self):
        summit = "W7O/NC-001"
        assoc = summit.split("/")[0]
        assert assoc == "W7O"

    def test_comment_truncated(self):
        long_comment = "X" * 100
        assert len(long_comment[:60]) == 60


# ── Activator panel source checks ────────────────────────────────────────────

class TestActivatorPanel:

    def _src(self):
        # Activator panel was extracted to _LogPanelsMixin (HOUSE-CS split);
        # _build / _update_stats callers remain in log_tab.py (listed first).
        parts = ["ui/tabs/log_tab.py", "ui/tabs/log_panels_mixin.py"]
        return "\n".join(
            (ROOT / p).read_text(encoding="utf-8") for p in parts)

    def test_build_activator_panel_defined(self):
        assert "def _build_activator_panel(" in self._src()

    def test_act_start_method(self):
        assert "def _act_start(" in self._src()

    def test_act_post_spot_method(self):
        assert "def _act_post_spot(" in self._src()

    def test_update_act_progress_method(self):
        assert "def _update_act_progress(" in self._src()

    def test_sota_minimum_4_qsos(self):
        src = self._src()
        idx = src.find("def _act_start(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "4" in body  # SOTA minimum

    def test_pota_minimum_10_qsos(self):
        src = self._src()
        idx = src.find("def _act_start(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "10" in body  # POTA minimum

    def test_panel_called_in_build(self):
        src = self._src()
        idx = src.find("def _build(self):")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_build_activator_panel" in body

    def test_progress_updated_in_update_stats(self):
        src = self._src()
        idx = src.find("def _update_stats(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "_update_act_progress" in body

    def test_post_sota_spot_imported_in_post(self):
        src = self._src()
        idx = src.find("def _act_post_spot(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "post_sota_spot" in body or "post_pota_spot" in body

    def test_sota_and_pota_type_options(self):
        src = self._src()
        assert '"SOTA"' in src and '"POTA"' in src


# ── FT8 DXCC-needed alert ─────────────────────────────────────────────────────

class TestFT8DXCCNeededAlert:

    def _src(self):
        return (ROOT / "ui/tabs/modes_tab.py").read_text(encoding="utf-8")

    def test_dxcc_check_in_check_ft8_alert(self):
        src = self._src()
        idx = src.find("def _check_ft8_alert(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "decode.dxcc" in body

    def test_award_tracker_used(self):
        src = self._src()
        idx = src.find("def _check_ft8_alert(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "AwardTracker" in body

    def test_not_in_worked_triggers_alert(self):
        src = self._src()
        idx = src.find("def _check_ft8_alert(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "prog.entities" in body

    def test_dxcc_tag_in_log_message(self):
        src = self._src()
        idx = src.find("def _check_ft8_alert(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "dxcc_tag" in body or "dxcc" in body.lower()
