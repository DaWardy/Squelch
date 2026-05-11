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

"""
Squelch -- main.py
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

os.chdir(Path(__file__).parent)


def setup_logging(debug: bool = False):
    Path("logs").mkdir(exist_ok=True)
    level = logging.DEBUG if debug else logging.INFO
    fmt   = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s"
    logging.basicConfig(
        level=level, format=fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("logs/squelch.log", encoding="utf-8"),
        ])


def parse_args():
    p = argparse.ArgumentParser(description="Squelch Amateur Radio Operations Platform")
    p.add_argument("--lab-mode", action="store_true",
                   help="Start in classroom lab mode")
    p.add_argument("--config", default="config.json",
                   help="Config file path")
    p.add_argument("--debug", action="store_true",
                   help="Verbose debug logging")
    return p.parse_args()


def main():
    args = parse_args()
    setup_logging(args.debug)
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
    app.setApplicationName("Squelch")
    app.setApplicationVersion("1.5.0")

    from core.config   import Config
    from core.safety   import get_safety
    from core.rig      import RigController
    from core.location import LocationManager

    config   = Config(Path(args.config))
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
    window.show()
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
