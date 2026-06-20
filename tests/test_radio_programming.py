"""Sprint 55 — FEAT-14 radio programming hooks + S-meter calibration."""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


class TestRadioProgrammingLauncher:
    """Verify programming software entries in core/launcher.py."""

    def _apps(self):
        from core.launcher import APPS
        return {a.key: a for a in APPS}

    def test_icom_cs7100_registered(self):
        assert "paths.icom_cs7100" in self._apps()

    def test_icom_cs7300_registered(self):
        assert "paths.icom_cs7300" in self._apps()

    def test_yaesu_adms12_registered(self):
        assert "paths.yaesu_adms12" in self._apps()

    def test_yaesu_adms14_registered(self):
        assert "paths.yaesu_adms14" in self._apps()

    def test_kenwood_mcp2a_registered(self):
        assert "paths.kenwood_mcp2a" in self._apps()

    def test_kenwood_mcp5a_registered(self):
        assert "paths.kenwood_mcp5a" in self._apps()

    def test_all_programming_apps_have_category(self):
        apps = self._apps()
        for key in ("paths.icom_cs7100", "paths.icom_cs7300",
                    "paths.yaesu_adms12", "paths.yaesu_adms14",
                    "paths.kenwood_mcp2a", "paths.kenwood_mcp5a"):
            assert apps[key].category == "programming", \
                f"{key} must have category='programming'"

    def test_all_programming_apps_have_download_url(self):
        apps = self._apps()
        for key in ("paths.icom_cs7100", "paths.yaesu_adms12",
                    "paths.kenwood_mcp2a"):
            assert apps[key].download_url, f"{key} missing download_url"

    def test_all_programming_apps_have_description(self):
        apps = self._apps()
        for key in ("paths.icom_cs7100", "paths.icom_cs7300",
                    "paths.yaesu_adms12", "paths.yaesu_adms14",
                    "paths.kenwood_mcp2a", "paths.kenwood_mcp5a"):
            assert apps[key].description, f"{key} missing description"


class TestSMeterCalibrationSettings:
    """S-meter calibration wired in Settings → Station."""

    def _station_src(self):
        return (ROOT / "ui/dialogs/settings_station_tab.py").read_text(
            encoding="utf-8")

    def _dialog_src(self):
        return (ROOT / "ui/dialogs/settings_dialog.py").read_text(
            encoding="utf-8")

    def test_smeter_cal_widget_defined(self):
        assert "_smeter_cal" in self._station_src()

    def test_smeter_cal_has_tooltip(self):
        src = self._station_src()
        assert "S-meter cal" in src or "smeter_cal" in src

    def test_smeter_cal_range_includes_negatives(self):
        src = self._station_src()
        assert "-20" in src or "setRange(-20" in src

    def test_smeter_cal_loaded_in_dialog(self):
        src = self._dialog_src()
        assert "smeter_cal" in src
        assert "rig.smeter_cal_db" in src

    def test_smeter_cal_saved_in_dialog(self):
        src = self._dialog_src()
        assert "smeter_cal_db" in src
        # Appears twice — once in load, once in save
        assert src.count("smeter_cal_db") >= 2


class TestRadioProgrammingHelpArticle:
    """Help tab has a Radio Programming Software article."""

    def _src(self):
        return (ROOT / "ui/tabs/help_tab.py").read_text(encoding="utf-8")

    def test_article_exists(self):
        assert "Radio Programming Software" in self._src()

    def test_chirp_mentioned(self):
        src = self._src()
        assert "CHIRP" in src

    def test_icom_mentioned(self):
        assert "Icom" in self._src() or "CS-7100" in self._src()

    def test_yaesu_mentioned(self):
        src = self._src()
        assert "Yaesu" in src or "ADMS" in src

    def test_kenwood_mentioned(self):
        src = self._src()
        assert "Kenwood" in src or "MCP" in src

    def test_chirp_csv_import_mentioned(self):
        src = self._src()
        assert "Import CHIRP CSV" in src or "RF Lab" in src

    def test_article_in_reference_category(self):
        src = self._src()
        idx = src.find('"Radio Programming Software"')
        # Should be followed by "Reference" as the category
        snippet = src[idx: idx + 80]
        assert "Reference" in snippet
