"""Sprint 40 — driver reinstall + FEAT-11 exe paths + FEAT-12 log dir."""
from __future__ import annotations
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


class TestDriverReinstall:
    """Installed SDR drivers must remain selectable for reinstall."""

    def test_installed_drivers_not_disabled_in_source(self):
        src = (ROOT / "ui/dialogs/settings_dialog.py").read_text(encoding="utf-8")
        # The old pattern disabled installed driver checkboxes.
        # We must NOT see setEnabled(False) immediately after a found-driver block.
        lines = src.splitlines()
        for i, line in enumerate(lines):
            if "setEnabled(False)" in line:
                # Acceptable only for the install button, not for _sdr_checks
                context = "\n".join(lines[max(0, i-3):i+1])
                assert "_sdr_checks" not in context, (
                    "Found setEnabled(False) on _sdr_checks — "
                    "installed drivers must remain selectable for reinstall")

    def test_reinstall_wording_in_status_label(self):
        src = (ROOT / "ui/dialogs/settings_dialog.py").read_text(encoding="utf-8")
        assert "reinstall" in src.lower(), \
            "Status label should hint that installed drivers can be reinstalled"

    def test_install_btn_label_mentions_reinstall(self):
        src = (ROOT / "ui/dialogs/settings_sdr_tab.py").read_text(encoding="utf-8")
        assert "Reinstall" in src, \
            "Install button label should mention Reinstall"


class TestNewExePaths:
    """FEAT-11 — new exe paths registered in launcher."""

    def test_n1mm_registered(self):
        from core.launcher import APPS
        keys = {a.key for a in APPS}
        assert "paths.n1mm" in keys, "N1MM Logger+ missing from launcher"

    def test_log4om_registered(self):
        from core.launcher import APPS
        keys = {a.key for a in APPS}
        assert "paths.log4om" in keys, "Log4OM missing from launcher"

    def test_hrd_registered(self):
        from core.launcher import APPS
        keys = {a.key for a in APPS}
        assert "paths.hrd" in keys, "Ham Radio Deluxe missing from launcher"

    def test_sdrsharp_registered(self):
        from core.launcher import APPS
        keys = {a.key for a in APPS}
        assert "paths.sdrsharp" in keys, "SDR# missing from launcher"

    def test_gnuradio_registered(self):
        from core.launcher import APPS
        keys = {a.key for a in APPS}
        assert "paths.gnuradio" in keys, "GNU Radio Companion missing from launcher"

    def test_direwolf_registered(self):
        from core.launcher import APPS
        keys = {a.key for a in APPS}
        assert "paths.direwolf" in keys, "Direwolf missing from launcher"

    def test_mmtty_registered(self):
        from core.launcher import APPS
        keys = {a.key for a in APPS}
        assert "paths.mmtty" in keys, "MMTTY missing from launcher"

    def test_all_new_apps_have_required_fields(self):
        from core.launcher import APPS
        new_keys = {"paths.n1mm", "paths.log4om", "paths.hrd",
                    "paths.sdrsharp", "paths.gnuradio",
                    "paths.direwolf", "paths.mmtty"}
        for app in APPS:
            if app.key in new_keys:
                assert app.name, f"{app.key}: missing name"
                assert app.category, f"{app.key}: missing category"
                assert app.description, f"{app.key}: missing description"


class TestLogDirConfig:
    """FEAT-12 — log directory config wired in settings."""

    def test_log_dir_field_in_advanced_tab(self):
        src = (ROOT / "ui/dialogs/settings_advanced_tab.py").read_text(
            encoding="utf-8")
        assert "_log_dir_edit" in src, \
            "_log_dir_edit widget missing from settings_advanced_tab.py"

    def test_browse_log_dir_method_present(self):
        src = (ROOT / "ui/dialogs/settings_advanced_tab.py").read_text(
            encoding="utf-8")
        assert "_browse_log_dir" in src, \
            "_browse_log_dir method missing from settings_advanced_tab.py"

    def test_log_dir_saved_in_dialog(self):
        src = (ROOT / "ui/dialogs/settings_dialog.py").read_text(encoding="utf-8")
        assert "advanced.log_dir" in src, \
            "advanced.log_dir not saved/loaded in settings_dialog.py"

    def test_setup_logging_accepts_log_dir_param(self):
        import inspect
        from main import setup_logging
        sig = inspect.signature(setup_logging)
        assert "log_dir" in sig.parameters, \
            "setup_logging() must accept a log_dir parameter"

    def test_setup_logging_uses_custom_dir(self, tmp_path):
        from main import setup_logging
        import logging
        result = setup_logging(debug=False, log_dir=tmp_path)
        assert result.parent == tmp_path
        assert (tmp_path / "squelch.log").exists()
        # Cleanup handlers so other tests aren't affected
        root = logging.getLogger()
        for h in list(root.handlers):
            if hasattr(h, "baseFilename") and "squelch" in h.baseFilename:
                h.close()
                root.removeHandler(h)
