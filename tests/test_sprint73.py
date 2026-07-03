"""Sprint 73 — Log auto-backup + APRS callsign labels on map."""
from __future__ import annotations
import sys
import pathlib
import tempfile
import shutil

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

ROOT = pathlib.Path(__file__).parent.parent


# ── core/backup.py ───────────────────────────────────────────────────────────

class TestBackupManager:

    def _make_db(self, tmp_dir):
        from pathlib import Path
        db = Path(tmp_dir) / "log.db"
        db.write_bytes(b"SQLite test content " * 100)
        return db

    def test_backup_creates_file(self):
        from core.backup import backup_log
        tmp = tempfile.mkdtemp()
        db  = self._make_db(tmp)
        result = backup_log(db)
        assert result is not None
        assert result.exists()

    def test_backup_in_backups_subdir(self):
        from core.backup import backup_log
        tmp = tempfile.mkdtemp()
        db  = self._make_db(tmp)
        result = backup_log(db)
        assert "backups" in str(result)

    def test_backup_filename_has_timestamp(self):
        from core.backup import backup_log
        tmp = tempfile.mkdtemp()
        db  = self._make_db(tmp)
        result = backup_log(db)
        assert result.name.startswith("log_")
        assert result.suffix == ".db"

    def test_missing_source_returns_none(self):
        from core.backup import backup_log
        from pathlib import Path
        result = backup_log(Path("/nonexistent/log.db"))
        assert result is None

    def test_rotation_keeps_max_copies(self):
        from core.backup import backup_log, _rotate, MAX_BACKUPS
        import time
        tmp = tempfile.mkdtemp()
        db  = self._make_db(tmp)
        # Create more backups than MAX_BACKUPS
        for _ in range(MAX_BACKUPS + 3):
            backup_log(db, max_copies=MAX_BACKUPS)
            time.sleep(0.01)  # ensure unique timestamps
        from pathlib import Path
        copies = list((Path(tmp) / "backups").glob("log_*.db"))
        assert len(copies) <= MAX_BACKUPS

    def test_last_backup_info(self):
        from core.backup import backup_log, last_backup_info
        tmp = tempfile.mkdtemp()
        db  = self._make_db(tmp)
        backup_log(db)
        result = last_backup_info(db)
        assert result is not None
        ts, size = result
        assert "UTC" in str(ts) or len(str(ts)) > 5
        assert size > 0

    def test_no_backup_returns_none(self):
        from core.backup import last_backup_info
        tmp = tempfile.mkdtemp()
        from pathlib import Path
        result = last_backup_info(Path(tmp) / "nonexistent.db")
        assert result is None

    def test_backup_module_exists(self):
        src = (ROOT / "core/backup.py").read_text(encoding="utf-8")
        assert "def backup_log(" in src
        assert "def _rotate(" in src
        assert "def last_backup_info(" in src

    def test_max_backups_constant(self):
        from core.backup import MAX_BACKUPS
        assert MAX_BACKUPS >= 5


class TestMainPyBackupWiring:

    def _src(self):
        return (ROOT / "main.py").read_text(encoding="utf-8")

    def test_backup_called_on_startup(self):
        src = self._src()
        idx = src.find("def main(")
        body = src[idx:]
        assert "backup_log" in body

    def test_backup_called_on_shutdown(self):
        src = self._src()
        # Should appear at least twice (startup + shutdown)
        assert src.count("backup_log") >= 2


# ── APRS labels on map ────────────────────────────────────────────────────────

class TestAPRSLabels:

    def _map_src(self):
        return (ROOT / "network/map_data.py").read_text(encoding="utf-8")

    def _tab_src(self):
        return (ROOT / "ui/tabs/map_tab.py").read_text(encoding="utf-8")

    def test_show_aprs_labels_param(self):
        src = self._map_src()
        assert "show_aprs_labels" in src

    def test_tooltip_in_aprs_foreach(self):
        src = self._map_src()
        assert "bindTooltip" in src

    def test_permanent_label_option(self):
        src = self._map_src()
        assert "permanent" in src

    def test_aprs_label_css_class(self):
        src = self._map_src()
        assert "aprs-label" in src

    def test_show_aprs_labels_checkbox_in_toolbar(self):
        src = self._tab_src()
        assert "_show_aprs_labels" in src

    def test_show_aprs_labels_passed_to_build_map(self):
        src = self._tab_src()
        idx = src.find("def _do_refresh_map(")
        body = src[idx: src.find("\n    def ", idx + 10)]
        assert "show_aprs_labels" in body


class TestMapHTMLLabels:
    """Verify labels render correctly in generated HTML."""

    def _html(self, show_labels=False):
        from network.map_data import build_map_html
        import tempfile
        from pathlib import Path
        from core.config import Config
        tmp = tempfile.mkdtemp()
        cfg = Config(Path(tmp) / "c.json")
        cfg.callsign = "W1AW"
        return build_map_html(cfg, show_adsb=False, show_grayline=False,
                              show_aprs_labels=show_labels)

    def test_labels_disabled_by_default(self):
        html = self._html(show_labels=False)
        assert "SHOW_APRS_LABELS = false" in html

    def test_labels_enabled_when_true(self):
        html = self._html(show_labels=True)
        assert "SHOW_APRS_LABELS = true" in html

    def test_tooltip_js_in_html(self):
        html = self._html(show_labels=True)
        assert "bindTooltip" in html
