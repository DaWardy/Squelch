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
    level = logging.DEBUG if debug else logging.INFO
    fmt   = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s"

    handlers = [logging.StreamHandler(sys.stdout)]
    log_path = LOG_DIR / "squelch.log"
    try:
        handlers.append(
            logging.FileHandler(str(log_path), encoding="utf-8"))
    except Exception as e:
        print(f"WARNING: could not open log file {log_path}: {e}",
              file=sys.stderr)

    # force=True is CRITICAL: basicConfig is a no-op if the root logger
    # already has handlers (e.g. something logged during import). Without
    # this the FileHandler was never attached and nothing was written.
    logging.basicConfig(
        level=level, format=fmt, handlers=handlers, force=True)

    # Record where logs actually go so it can be surfaced in the UI.
    logging.getLogger().info(f"Diagnostic log: {log_path}")
    return log_path


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




def _light_theme_subs():
    """Return (SUBS, vals) regex substitution tables for the Light theme."""
    import re as _re
    SUBS = [
        (_re.compile(r"background\s*:\s*#(?:0[0-9a-fA-F]{5}|1[0-4][0-9a-fA-F]{4})",
                     _re.I), "background:{t_bg}"),
        (_re.compile(r"background\s*:\s*#(?:1[5-9a-fA-F][0-9a-fA-F]{4}"
                     r"|2[0-9a-fA-F]{5})", _re.I), "background:{t_bg2}"),
        (_re.compile(r"background\s*:\s*#(?:0a1a0a|1a2a1a|1a3a1a|1e2e1e|"
                     r"0d2a0d|0a2a1a|1a4a1a|143a14)", _re.I),
         "background:{t_acc_bg}"),
        (_re.compile(r"background\s*:\s*#(?:1a0808|2a0808|0a0000|3a0808)",
                     _re.I), "background:{t_err_bg}"),
        (_re.compile(r"color\s*:\s*#3fbe6f", _re.I), "color:{t_acc}"),
        (_re.compile(r"color\s*:\s*#(?:7fdf9f|66ff66|44dd44)", _re.I),
         "color:{t_acc}"),
        (_re.compile(r"border(?:-[a-z]+)?\s*:\s*1px solid "
                     r"#(?:1a1a1a|111|222|333|0a0a0a|141414)", _re.I),
         "border:1px solid {t_border}"),
        (_re.compile(r"color\s*:\s*#(?:ffffff|f0f0f0|e0e0e0|dddddd|cccccc)",
                     _re.I), "color:{t_fg}"),
        (_re.compile(r"gridline-color\s*:\s*#(?:0[0-9a-fA-F]{5}|"
                     r"1[0-9a-fA-F]{5}|2[0-9a-fA-F]{5})", _re.I),
         "gridline-color:{t_border}"),
        (_re.compile(r"alternate-background-color\s*:\s*#(?:1[0-9a-fA-F]{5}"
                     r"|0[0-9a-fA-F]{5})", _re.I),
         "alternate-background-color:{t_bg_alt}"),
    ]
    vals = {
        "t_bg": "#f1f3f5", "t_bg2": "#e7ebef", "t_bg_alt": "#eef1f4",
        "t_acc_bg": "#dcefe2", "t_err_bg": "#ffebe9",
        "t_acc": "#1f7a3f", "t_border": "#d0d7de", "t_fg": "#1f2328",
    }
    return SUBS, vals


def _hc_theme_subs():
    """Return (SUBS, vals) regex substitution tables for the High Contrast theme."""
    import re as _re
    SUBS = [
        (_re.compile(r"background\s*:\s*#(?:0[0-9a-fA-F]{5}|1[0-9a-fA-F]{5}"
                     r"|2[0-9a-fA-F]{5}|3[0-3][0-9a-fA-F]{4})",
                     _re.I), "background:#000000"),
        (_re.compile(r"border(?:-[a-z]+)?\s*:\s*(?:\d+px\s+\w+\s+)?"
                     r"#(?:0[0-9a-fA-F]{5}|1[0-4][0-9a-fA-F]{4})",
                     _re.I), "border:2px solid #ffffff"),
        (_re.compile(r"gridline-color\s*:\s*#(?:[0-9a-fA-F]{6})", _re.I),
         "gridline-color:#ffffff"),
        (_re.compile(r"color\s*:\s*#3fbe6f", _re.I), "color:#00ffcc"),
        (_re.compile(r"background\s*:\s*#3fbe6f", _re.I), "background:#00ffcc"),
        (_re.compile(r"color\s*:\s*#(?:55|66|77|88|99|aa|bb)[0-9a-fA-F]{4}",
                     _re.I), "color:#ffffff"),
        (_re.compile(r"alternate-background-color\s*:\s*#[0-9a-fA-F]{6}",
                     _re.I), "alternate-background-color:#0d0d0d"),
    ]
    return SUBS, {}


def _fix_pyqtgraph_theme(window, theme_name: str):
    """Apply pyqtgraph background/foreground colors for Light and High Contrast."""
    _pg_bg = {"Light": "#fafbfc", "High Contrast": "#000000"}.get(theme_name)
    _pg_fg = {"Light": "#1f2328", "High Contrast": "#ffffff"}.get(theme_name)
    if not _pg_bg:
        return
    try:
        import pyqtgraph as pg
        pg.setConfigOption("background", _pg_bg)
        pg.setConfigOption("foreground", _pg_fg)
        from pyqtgraph import PlotWidget, GraphicsLayoutWidget
        for w in window.findChildren(PlotWidget):
            try:
                w.setBackground(_pg_bg)
            except Exception:
                pass
        for w in window.findChildren(GraphicsLayoutWidget):
            try:
                w.setBackground(_pg_bg)
            except Exception:
                pass
    except Exception:
        pass


def _apply_theme_fixes(window, theme_name: str):
    """Post-load regex pass that corrects widgets with hardcoded dark inline stylesheets.

    Widget setStyleSheet() overrides the global QApplication QSS, so light /
    high-contrast themes get dark backgrounds from inline styles. We walk every
    widget, detect dark hex colors, and substitute with the active theme's colors.
    """
    if theme_name not in ("Light", "High Contrast"):
        return
    from PyQt6.QtWidgets import QWidget
    SUBS, vals = (_light_theme_subs() if theme_name == "Light"
                  else _hc_theme_subs())

    def _fix_widget(w: QWidget):
        try:
            ss = w.styleSheet()
            if not ss:
                return
            fixed = ss
            for pat, repl in SUBS:
                fixed = pat.sub(repl.format(**vals), fixed)
            if fixed != ss:
                w.setStyleSheet(fixed)
        except Exception:
            pass

    for w in window.findChildren(QWidget):
        _fix_widget(w)
    _fix_pyqtgraph_theme(window, theme_name)
    # Expose as module-level helper for panels built after startup
    import main as _main
    _main._reapply_theme_to = lambda w: _fix_widget(w)

def _fix_combo_sizing(window):
    """Make every dropdown size to its content so labels aren't clipped.
    Several combos had fixed widths narrower than their text (user report)."""
    from PyQt6.QtWidgets import QComboBox
    for combo in window.findChildren(QComboBox):
        try:
            combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToContents)
            fm = combo.fontMetrics()
            longest = 0
            for i in range(combo.count()):
                longest = max(longest,
                              fm.horizontalAdvance(combo.itemText(i)))
            if longest:
                combo.view().setMinimumWidth(longest + 40)
                want = min(longest + 30, 240)
                if combo.minimumWidth() < want:
                    combo.setMinimumWidth(want)
        except Exception:
            pass


def _copy_section_text(lbl):
    """Copy all visible label text in the surrounding panel to the clipboard."""
    try:
        from PyQt6.QtWidgets import QLabel, QApplication
        container = lbl.parentWidget()
        for _ in range(4):
            if container is None:
                break
            nxt = container.parentWidget()
            if nxt is None:
                break
            container = nxt
        root = container or lbl
        texts = [sub.text().strip()
                 for sub in root.findChildren(QLabel)
                 if sub.isVisible() and sub.text().strip()]
        if texts:
            QApplication.clipboard().setText("\n".join(texts))
    except Exception:
        pass


def _install_label_context_menu(lbl):
    """Attach right-click context menu to a QLabel for copy actions."""
    from PyQt6.QtWidgets import QMenu, QApplication
    from PyQt6.QtCore import Qt

    def _show_menu(pos, _lbl=lbl):
        menu = QMenu(_lbl)
        act_sel = menu.addAction("Copy selected text")
        act_sec = menu.addAction("Copy section text (all of this panel)")
        chosen = menu.exec(_lbl.mapToGlobal(pos))
        if chosen == act_sel:
            sel = _lbl.selectedText()
            if sel:
                QApplication.clipboard().setText(sel)
        elif chosen == act_sec:
            _copy_section_text(_lbl)

    lbl.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    lbl.customContextMenuRequested.connect(_show_menu)


def _copy_table_selection(table):
    """Copy selected table rows to clipboard as tab-separated text."""
    try:
        from PyQt6.QtWidgets import QApplication
        sel = table.selectedItems()
        if not sel:
            return
        rows: "dict[int, list[str]]" = {}
        for item in sel:
            rows.setdefault(item.row(), []).append(item.text())
        text = "\n".join("\t".join(rows[r]) for r in sorted(rows))
        QApplication.clipboard().setText(text)
    except Exception:
        pass


def _make_text_selectable(window):
    """Make all QLabels selectable and all tables Ctrl+C copyable."""
    from PyQt6.QtWidgets import QLabel, QTableWidget
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QKeySequence, QShortcut

    for lbl in window.findChildren(QLabel):
        try:
            lbl.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse |
                Qt.TextInteractionFlag.TextSelectableByKeyboard)
        except Exception:
            pass

    # Qt can't drag-select across separate label widgets (title vs body are
    # different QLabels) — right-click grabs all panel text in one shot.
    for lbl in window.findChildren(QLabel):
        try:
            _install_label_context_menu(lbl)
        except Exception:
            pass

    for table in window.findChildren(QTableWidget):
        sc = QShortcut(QKeySequence.StandardKey.Copy, table)
        sc.activated.connect(lambda t=table: _copy_table_selection(t))


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


def _setup_qt_app() -> "QApplication":
    """Create and configure QApplication. Must be called before any Qt object.

    Sets High-DPI policy, application icon (taskbar/alt-tab), and the Windows
    AppUserModelID so the taskbar entry shows the Squelch icon, not Python's.
    Returns the QApplication instance.
    """
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
    except ImportError:
        print("\nERROR: PyQt6 not found.\nRun bootstrap.bat to install dependencies.\n")
        sys.exit(1)
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except AttributeError:
        pass
    app = QApplication(sys.argv)
    try:
        from PyQt6.QtGui import QIcon
        _ico = Path(__file__).parent / "assets" / "squelch.ico"
        _png = Path(__file__).parent / "assets" / "squelch.png"
        _icon_path = _ico if _ico.exists() else _png
        if _icon_path.exists():
            app.setWindowIcon(QIcon(str(_icon_path)))
    except Exception:
        pass
    app.setApplicationName("Squelch")
    app.setApplicationVersion(APP_VERSION)
    # AUMID: alphanumeric+dots only (no hyphens) — stable across versions
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "dawardy.squelch")
        except Exception:
            pass
    return app


def main():
    from core.config import LOG_DIR as _LD
    try:
        _set_netlog_path(_LD / "network.log")
    except Exception:
        pass
    args = parse_args()
    setup_logging(args.debug)
    if not args.debug:
        from core.config import CONFIG_PATH, Config as _C
        level_str = _C(CONFIG_PATH).get("advanced.log_level", "INFO")
        import logging as _lg
        _lg.getLogger().setLevel(getattr(_lg, level_str, _lg.INFO))
    log = logging.getLogger(__name__)
    log.info("=" * 56)
    log.info(f"Squelch starting  lab={args.lab_mode}  debug={args.debug}")
    log.info("=" * 56)

    app = _setup_qt_app()

    from core.config   import Config
    from core.safety   import get_safety
    from core.rig      import RigController
    from core.location import LocationManager

    config   = Config(Path(args.config).expanduser().resolve())
    rig      = RigController(config)
    location = LocationManager(config)

    if args.lab_mode:
        config.set("classroom.lab_mode", True)
        log.info("Guest Operator mode active")

    location.load_from_config()
    safety = get_safety()
    safety.set_rig(rig)
    safety.start_watchdog()
    log.info("Safety watchdog active")

    from ui.main_window import MainWindow
    window = MainWindow(config, rig, location)
    _wiring_smoke_test(window)
    window.show()
    _make_text_selectable(window)
    _fix_combo_sizing(window)
    _apply_theme_fixes(window, config.get("ui.theme", "Dark"))
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
