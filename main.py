# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
#
# This program is free software: you can redistribute it
# and/or modify it under the terms of the GNU General
# Public License as published by the Free Software
# Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General
# Public License along with this program. If not, see
# <https://www.gnu.org/licenses/>.

from __future__ import annotations
"""Squelch -- main.py
Amateur Radio Operations Platform entry point.

Usage:
    python main.py
    python main.py --lab-mode
    python main.py --debug
    python main.py --config PATH
"""

import sys
import os
import logging
import argparse
from pathlib import Path
from core.config import LOG_DIR
from core.constants import APP_VERSION
from core.netlog import set_log_path as _set_netlog_path
from typing import Optional, Callable, List, Dict, Tuple  # safety net for module imports

os.chdir(Path(__file__).parent)


def setup_logging(debug: bool = False):
    # Ensure log directory exists before FileHandler tries to open it
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    level = logging.DEBUG if debug else logging.INFO
    fmt   = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s"
    logging.basicConfig(
        level=level, format=fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(str(LOG_DIR / "squelch.log"), encoding="utf-8"),
        ])


def parse_args():
    p = argparse.ArgumentParser(description="Squelch Amateur Radio Operations Platform")
    p.add_argument("--lab-mode", action="store_true",
                   help="Start in classroom lab mode")
    from core.config import CONFIG_PATH
    p.add_argument("--config",
                   default=str(CONFIG_PATH),
                   help="Config file path")
    p.add_argument("--debug", action="store_true",
                   help="Verbose debug logging")
    return p.parse_args()



def _make_text_selectable(window):
    """Make all QLabels selectable and all tables Ctrl+C copyable.
    Users expect to copy text from any view (callsigns, frequencies, etc)."""
    from PyQt6.QtWidgets import QLabel, QTableWidget, QTreeWidget, QApplication
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QKeySequence, QShortcut

    # Make every QLabel selectable
    for lbl in window.findChildren(QLabel):
        try:
            lbl.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse |
                Qt.TextInteractionFlag.TextSelectableByKeyboard)
        except Exception:
            pass

    # Add Ctrl+C copy to every table and tree
    def _copy_selection(table):
        try:
            sel = table.selectedItems()
            if not sel:
                return
            # Group by row
            rows = {}
            for item in sel:
                rows.setdefault(item.row(), []).append(item.text())
            text = "\n".join("\t".join(rows[r]) for r in sorted(rows))
            QApplication.clipboard().setText(text)
        except Exception:
            pass

    for table in window.findChildren(QTableWidget):
        sc = QShortcut(QKeySequence.StandardKey.Copy, table)
        sc.activated.connect(lambda t=table: _copy_selection(t))


def _wiring_smoke_test(window):
    """Verify critical wiring at startup. Catches regressions early.
    These are bugs that have shown up multiple times during development."""
    import logging
    log = logging.getLogger(__name__)
    issues = []

    # 1. Location signals must be connected (grid stuck on "Searching...")
    try:
        if hasattr(window, "_location_found"):
            sig = window._location_found
            # Check the signal has at least one connected slot
            try:
                # PyQt6 receiver count
                n = window.receivers(sig)
                if n == 0:
                    issues.append(
                        "_location_found signal has no connected slots - "
                        "grid search will hang at 'Searching...'")
            except Exception:
                pass
    except Exception:
        pass

    # 2. Settings dialog can be opened (stale-dialog crash)
    if not hasattr(window, "_open_settings"):
        issues.append("_open_settings method missing")

    # 3. Critical tabs exist
    if hasattr(window, "tabs"):
        n_tabs = window.tabs.count()
        if n_tabs < 5:
            issues.append(f"Only {n_tabs} tabs loaded — expected 8+")

    for issue in issues:
        log.warning(f"STARTUP CHECK: {issue}")

    return len(issues) == 0


def main():
    from core.config import LOG_DIR as _LD
    try:
        _set_netlog_path(_LD / "network.log")
    except Exception:
        pass
    args = parse_args()
    setup_logging(args.debug)
    # Apply log level from config if not in debug mode
    if not args.debug:
        from core.config import CONFIG_PATH, Config
        _tmp_cfg = Config(CONFIG_PATH)
        level_str = _tmp_cfg.get("advanced.log_level", "INFO")
        import logging as _lg
        _lg.getLogger().setLevel(
            getattr(_lg, level_str, _lg.INFO))
    log = logging.getLogger(__name__)
    log.info("=" * 56)
    log.info(f"Squelch starting  lab={args.lab_mode}  debug={args.debug}")
    log.info("=" * 56)

    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
    except ImportError:
        print(
            "\nERROR: PyQt6 not found.\n"
            "Run bootstrap.bat to install dependencies.\n"
        )
        sys.exit(1)

    # High-DPI MUST be set before QApplication — do not move
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except AttributeError:
        pass

    app = QApplication(sys.argv)
    # Application icon (taskbar, window, alt-tab)
    try:
        from PyQt6.QtGui import QIcon
        from pathlib import Path as _P
        _icon = _P(__file__).parent / "assets" / "squelch.png"
        if _icon.exists():
            app.setWindowIcon(QIcon(str(_icon)))
    except Exception:
        pass
    app.setApplicationName("Squelch")
    app.setApplicationVersion(APP_VERSION)

    from core.config   import Config
    from core.safety   import get_safety
    from core.rig      import RigController
    from core.location import LocationManager

    config   = Config(
        Path(args.config).expanduser().resolve())
    rig      = RigController(config)
    location = LocationManager(config)

    if args.lab_mode:
        config.set("classroom.lab_mode", True)
        log.info("Guest Operator mode active")

    location.load_from_config()

    # Start safety systems
    safety = get_safety()
    safety.set_rig(rig)
    safety.start_watchdog()
    log.info("Safety watchdog active")

    from ui.main_window import MainWindow
    window = MainWindow(config, rig, location)
    _wiring_smoke_test(window)
    window.show()
    _make_text_selectable(window)
    window.raise_()
    window.activateWindow()
    log.info("Window ready")

    ret = app.exec()

    try:
        get_safety().stop_watchdog()
    except Exception:
        pass
    rig.disconnect()
    config.save_if_dirty()
    log.info("Shutdown complete")
    sys.exit(ret)


if __name__ == "__main__":
    main()
