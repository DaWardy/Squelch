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




def _apply_theme_fixes(window, theme_name: str):
    """Post-load pass that corrects widgets with hardcoded dark inline stylesheets.

    Widget-level setStyleSheet() overrides the QApplication stylesheet, so
    light/high-contrast themes get dark backgrounds from the inline styles.
    We walk every widget, detect dark hex colors via regex, and substitute
    with the active theme's semantic colors.

    This also re-applies via a helper so newly-created panels (e.g. SDR
    device panels built on connect) can call _reapply_theme(widget) directly.
    """
    if theme_name not in ("Light", "High Contrast"):
        return

    import re as _re
    from PyQt6.QtWidgets import QWidget

    if theme_name == "Light":
        # Map dark hex → light-theme semantic equivalents. The palette here
        # mirrors the LIGHT Theme dataclass in core/themes.py — calmer
        # off-white instead of pure white to match what the global QSS does.
        SUBS = [
            # Very dark backgrounds (#000000-#14ffff) → light panel
            (_re.compile(r"background\s*:\s*#(?:0[0-9a-fA-F]{5}|1[0-4][0-9a-fA-F]{4})",
                         _re.I), "background:{t_bg}"),
            # Mid-dark backgrounds (#15-#2f) → slightly deeper panel
            (_re.compile(r"background\s*:\s*#(?:1[5-9a-fA-F][0-9a-fA-F]{4}"
                         r"|2[0-9a-fA-F]{5})", _re.I), "background:{t_bg2}"),
            # Dark green tinted backgrounds → soft green tint
            (_re.compile(r"background\s*:\s*#(?:0a1a0a|1a2a1a|1a3a1a|1e2e1e|"
                         r"0d2a0d|0a2a1a|1a4a1a|143a14)", _re.I),
             "background:{t_acc_bg}"),
            # Dark red tint → light red tint
            (_re.compile(r"background\s*:\s*#(?:1a0808|2a0808|0a0000|3a0808)",
                         _re.I), "background:{t_err_bg}"),
            # Bright accent green text → muted dark green
            (_re.compile(r"color\s*:\s*#3fbe6f", _re.I), "color:{t_acc}"),
            # Console / waterfall text that was bright-green-on-black
            # — keep it readable on light by darkening
            (_re.compile(r"color\s*:\s*#(?:7fdf9f|66ff66|44dd44)", _re.I),
             "color:{t_acc}"),
            # Dark borders
            (_re.compile(r"border(?:-[a-z]+)?\s*:\s*1px solid "
                         r"#(?:1a1a1a|111|222|333|0a0a0a|141414)", _re.I),
             "border:1px solid {t_border}"),
            # Light text that was readable on dark but now invisible on light
            (_re.compile(r"color\s*:\s*#(?:ffffff|f0f0f0|e0e0e0|dddddd|cccccc)",
                         _re.I), "color:{t_fg}"),
            # gridline-color used by QTableWidget — was #1a1a1a (dark line on
            # dark bg, visible). On light bg, that's a hard black line.
            (_re.compile(r"gridline-color\s*:\s*#(?:0[0-9a-fA-F]{5}|"
                         r"1[0-9a-fA-F]{5}|2[0-9a-fA-F]{5})", _re.I),
             "gridline-color:{t_border}"),
            # alternate-background-color (table zebra stripes)
            (_re.compile(r"alternate-background-color\s*:\s*#(?:1[0-9a-fA-F]{5}"
                         r"|0[0-9a-fA-F]{5})", _re.I),
             "alternate-background-color:{t_bg_alt}"),
        ]
        vals = {
            "t_bg":      "#f1f3f5",     # matches LIGHT.bg_secondary
            "t_bg2":     "#e7ebef",     # matches LIGHT.bg_tertiary
            "t_bg_alt":  "#eef1f4",     # matches LIGHT.bg_alt
            "t_acc_bg":  "#dcefe2",     # soft green tint
            "t_err_bg":  "#ffebe9",     # soft red tint
            "t_acc":     "#1f7a3f",     # matches LIGHT.accent
            "t_border":  "#d0d7de",     # matches LIGHT.border
            "t_fg":      "#1f2328",     # matches LIGHT.fg_primary
        }
    else:
        # High Contrast: substitute inline dark colours with HC palette so
        # widget setStyleSheet() calls don't drown out the global QSS.
        # Dark theme is fine as-is — skip it.
        if theme_name != "High Contrast":
            return
        SUBS = [
            # Dark backgrounds → pure black
            (_re.compile(r"background\s*:\s*#(?:0[0-9a-fA-F]{5}|1[0-9a-fA-F]{5}"
                         r"|2[0-9a-fA-F]{5}|3[0-3][0-9a-fA-F]{4})",
                         _re.I), "background:#000000"),
            # Dark borders → white for maximum visibility
            (_re.compile(r"border(?:-[a-z]+)?\s*:\s*(?:\d+px\s+\w+\s+)?"
                         r"#(?:0[0-9a-fA-F]{5}|1[0-4][0-9a-fA-F]{4})",
                         _re.I), "border:2px solid #ffffff"),
            # gridline-color → white
            (_re.compile(r"gridline-color\s*:\s*#(?:[0-9a-fA-F]{6})", _re.I),
             "gridline-color:#ffffff"),
            # Soft green accent → vivid cyan
            (_re.compile(r"color\s*:\s*#3fbe6f", _re.I), "color:#00ffcc"),
            (_re.compile(r"background\s*:\s*#3fbe6f", _re.I), "background:#00ffcc"),
            # Muted grey text that is unreadable on black → pure white
            (_re.compile(r"color\s*:\s*#(?:55|66|77|88|99|aa|bb)[0-9a-fA-F]{4}",
                         _re.I), "color:#ffffff"),
            # alternate-background → near-black
            (_re.compile(r"alternate-background-color\s*:\s*#[0-9a-fA-F]{6}",
                         _re.I), "alternate-background-color:#0d0d0d"),
        ]
        vals = {}  # no format placeholders needed — literals only above

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

    # Fix pyqtgraph spectrum/waterfall background (its own API, not QSS).
    _pg_bg = {"Light": "#fafbfc", "High Contrast": "#000000"}.get(theme_name)
    _pg_fg = {"Light": "#1f2328", "High Contrast": "#ffffff"}.get(theme_name)
    if _pg_bg:
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

    # Expose as a module-level helper for panels built after startup
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

    # Qt can't drag-select across separate label widgets (title vs body are
    # different QLabels). For troubleshooting, give every label a right-click
    # "Copy section text" that grabs ALL label text in its surrounding panel
    # at once — so the whole block can be pasted in one go.
    def _copy_section(lbl):
        try:
            # Walk up to a meaningful container (group box / panel / tab)
            container = lbl.parentWidget()
            for _ in range(4):
                if container is None:
                    break
                nxt = container.parentWidget()
                if nxt is None:
                    break
                container = nxt
            root = container or lbl
            texts = []
            for sub in root.findChildren(QLabel):
                if sub.isVisible():
                    t = sub.text().strip()
                    if t:
                        texts.append(t)
            if texts:
                QApplication.clipboard().setText("\n".join(texts))
        except Exception:
            pass

    def _install_label_menu(lbl):
        from PyQt6.QtWidgets import QMenu
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
                _copy_section(_lbl)
        lbl.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        lbl.customContextMenuRequested.connect(_show_menu)

    for lbl in window.findChildren(QLabel):
        try:
            _install_label_menu(lbl)
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
        # Use .ico on Windows (multi-resolution) for best taskbar quality;
        # fall back to .png on Linux/macOS.
        _ico = _P(__file__).parent / "assets" / "squelch.ico"
        _png = _P(__file__).parent / "assets" / "squelch.png"
        _icon_path = _ico if _ico.exists() else _png
        if _icon_path.exists():
            app.setWindowIcon(QIcon(str(_icon_path)))
    except Exception:
        pass
    app.setApplicationName("Squelch")
    app.setApplicationVersion(APP_VERSION)

    # Windows taskbar icon fix: set the AppUserModelID so Windows groups and
    # shows our icon correctly rather than the generic Python/document icon.
    # Must be called before any window is shown. (P2 — guarded to Windows only)
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                f"dawardy.squelch.{APP_VERSION}")
        except Exception:
            pass

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
