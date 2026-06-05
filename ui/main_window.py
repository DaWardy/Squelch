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
"""Squelch -- ui/main_window.py
Main application window.
9 tabs, inline callsign/grid editing, theme system,
tab show/hide, UTC+local clock, safety alerts,
window size/position persistence, plugin tabs.
"""

import logging
from datetime import datetime, timezone

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QFrame, QDialog, QFormLayout, QLineEdit,
    QDialogButtonBox, QMenu, QSizePolicy,
    QCheckBox, QScrollArea, QComboBox, QTextEdit,
    QInputDialog, QSpinBox, QGroupBox, QSplitter,
    QDockWidget, QApplication, QAbstractItemView
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSettings, pyqtSlot
from PyQt6.QtGui import QAction, QActionGroup, QFont, QCursor

import re
from core.rig import RigController, RigStatus
from core.config import Config
from core.location import LocationManager
from core.themes import THEMES, get_stylesheet
from core.plugins import get_plugin_manager
from core.launcher import get_launcher
from ui.dialogs.paths_dialog import PathsDialog
from core.constants import (
    APP_NAME, APP_FULL, APP_VERSION, APP_URL)
VERSION = APP_VERSION

log = logging.getLogger(__name__)


# Tab definitions — key, label, default visible
TABS = [
    ("rig",       "📻  Rig",            True),
    ("modes",     "📡  Modes",          True),
    ("log",       "📒  Log",            True),
    ("bandcond",  "☀️  Band Cond.",     True),
    ("sdr",       "〰️  SDR",            True),
    ("digital",   "🔊  Digital",        True),
    ("localrf",   "📋  Local RF",       True),
    ("map",       "🗺  Map",            True),
    ("winlink",   "✉️  Winlink",        True),
    ("help",      "❓  Help",           True),
]

class ClickableLabel(QLabel):
    """
    Label that becomes a QLineEdit on click.
    Used for callsign and grid in the top bar.
    Never crashes on bad input — validates before committing.
    """

    _PLACEHOLDERS = frozenset({
        "click to set callsign", "click to set grid",
        "no callsign set", "no grid set",
        "callsign", "grid",
    })

    def __init__(self, text: str, placeholder: str,
                 on_commit, max_length: int = 15,
                 parent=None):
        super().__init__(text, parent)
        self._placeholder = placeholder
        self._on_commit   = on_commit
        self._max_length  = max_length
        self._edit:       QLineEdit = None
        self._editing     = False
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self.setToolTip(
            f"Click to edit  ({placeholder})")

    def mousePressEvent(self, event):
        if not self._editing:
            self._start_edit()

    def _start_edit(self):
        self._editing = True
        current = self.text()
        start_text = (
            "" if current.lower() in self._PLACEHOLDERS
            else current)

        self._edit = QLineEdit(self.parent())
        self._edit.setText(start_text)
        self._edit.setPlaceholderText(self._placeholder)
        self._edit.setMaxLength(self._max_length)
        self._edit.setStyleSheet(
            "background:#1a2a1a;border:1px solid #3fbe6f;"
            "border-radius:3px;color:#3fbe6f;"
            "padding:1px 6px;font-family:'Courier New';")
        geo = self.geometry()
        # Make edit field a bit wider than label
        geo.setWidth(max(geo.width(), 120))
        self._edit.setGeometry(geo)
        self._edit.show()
        self._edit.selectAll()
        self._edit.setFocus()
        self._edit.returnPressed.connect(self._commit)

        # Proper focusOutEvent override — no unbound method call
        edit_ref = self._edit
        commit_ref = self._commit
        base_foe = type(self._edit).focusOutEvent

        def _focus_out(ev):
            commit_ref()
            base_foe(edit_ref, ev)

        self._edit.focusOutEvent = _focus_out

    def _commit_callsign(self, val: str):
        """Sanitize and commit a callsign value: [A-Z0-9/] only."""
        import re
        clean = re.sub(r'[^A-Z0-9/]', '', val.upper())
        if not clean:
            return
        self.setText(clean)
        try:
            self._on_commit(clean)
        except Exception as e:
            log.warning(f"Callsign commit: {e}")

    def _commit_location(self, val: str):
        """Sanitize and commit a location/grid value: alphanumeric + common punctuation."""
        import re
        clean = re.sub(r'[^A-Za-z0-9 ,./\-]', '', val).strip()
        if not clean:
            return
        # Don't setText — let _on_grid_edit set the final Maidenhead grid
        try:
            self._on_commit(clean)
        except Exception as e:
            log.warning(f"Location commit: {e}")

    def _commit(self):
        """Finalise in-place edit; route to callsign or location handler."""
        if self._edit is None or self._editing is False:
            return
        self._editing = False
        edit, self._edit = self._edit, None
        raw = edit.text().strip()
        try:
            edit.hide(); edit.deleteLater()
        except Exception:
            pass
        val = raw.strip()
        if not val or val.lower() in self._PLACEHOLDERS:
            return
        if self._placeholder and 'call' in self._placeholder.lower():
            self._commit_callsign(val)
        else:
            self._commit_location(val)

from ui.main_window_profile   import _MainWindowProfileMixin
from ui.main_window_network   import _MainWindowNetworkMixin
from ui.main_window_guest_demo import _MainWindowGuestDemoMixin
from ui.main_window_firstrun  import _MainWindowFirstrunMixin


class MainWindow(
        _MainWindowProfileMixin,
        _MainWindowNetworkMixin,
        _MainWindowGuestDemoMixin,
        _MainWindowFirstrunMixin,
        QMainWindow):
    # Thread-safe signals — emit() from any thread, slot runs on GUI thread
    _location_found  = pyqtSignal(str, str, float, float)  # grid, display, lat, lon
    _location_failed = pyqtSignal(str)                      # error message

    def __init__(self, config: Config,
                 rig: RigController,
                 location: LocationManager):
        super().__init__()
        # ── DO NOT REMOVE: thread-safe location signals must be wired here ──
        # If these .connect() lines disappear, the grid label gets stuck on
        # "Searching..." forever because emit() from the background thread
        # has nothing connected to it. See _on_location_found below.
        self._location_found.connect(self._on_location_found)
        self._location_failed.connect(self._on_location_failed)
        # ────────────────────────────────────────────────────────────────
        self.setDockOptions(
            QMainWindow.DockOption.AllowTabbedDocks |
            QMainWindow.DockOption.AllowNestedDocks |
            QMainWindow.DockOption.AnimatedDocks)
        self.cfg      = config
        self.rig      = rig
        self.location = location

        self.setWindowTitle(
            f"{APP_NAME}  v{VERSION}  —  {APP_FULL}")
        try:
            from PyQt6.QtGui import QIcon
            from pathlib import Path as _P
            _ic = _P(__file__).resolve().parent.parent / "assets" / "squelch.png"
            if _ic.exists():
                self.setWindowIcon(QIcon(str(_ic)))
        except Exception:
            pass
        self.setMinimumSize(900, 600)

        # Restore window geometry
        self._settings = QSettings("Squelch", "squelch")
        geo = self._settings.value("window/geometry")
        if geo:
            self.restoreGeometry(geo)
        else:
            self.resize(1300, 840)

        # Apply theme
        theme_name = self.cfg.get("ui.theme", "Dark")
        font_size  = max(8, min(20,
            self.cfg.get("ui.font_size", 11)))
        self.setStyleSheet(get_stylesheet(theme_name, font_size))

        self._build_ui()
        self._build_menu()
        self._build_statusbar()
        self._wire()
        self._start_clock()
        self._check_first_run()
        self._load_plugins()
        self._apply_saved_font_size()
        self._apply_station_settings()
        self._init_aprs()
        self._init_pskreporter()
        self._init_satellites()
        QTimer.singleShot(100, self._wire_sdr_to_digital)
        self._auto_detect_software()
        # Populate operator profiles
        self._populate_profiles()

        # Show location on startup if already configured
        QTimer.singleShot(800, self._restore_location)

        # Apply saved Guest Operator mode (C-06) once the window is built
        self._apply_saved_guest_mode()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)
        self._central_layout = vbox
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        vbox.addWidget(self._build_topbar())

        self.tabs = QTabWidget()
        locked = self.cfg.get("ui.layout_locked", False)
        self.tabs.tabBar().setMovable(not locked)
        self.tabs.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.customContextMenuRequested.connect(
            self._tab_context_menu)
        self.tabs.tabBarDoubleClicked.connect(self._undock_tab)
        # Right-click on a tab → context menu (makes pop-out discoverable)
        self.tabs.tabBar().setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(
            self._tab_context_menu)

        self.tabs.currentChanged.connect(self._update_spectrum_action)
        vbox.addWidget(self.tabs)

        self._tab_map: dict[str, QWidget] = {}
        self._tab_visibility: dict[str, bool] = {}

        for key, label, default_visible in TABS:
            w = self._make_tab(key, label)
            self._tab_map[key] = w
            self.tabs.addTab(w, label)
            visible = self.cfg.get(
                f"ui.tab_visible.{key}", default_visible)
            self._tab_visibility[key] = visible
            self.tabs.setTabVisible(
                self.tabs.indexOf(w), visible)

        # Restore the last-used tab (C-09, Marcus)
        try:
            last = self._settings.value("window/last_tab")
            if last is not None:
                idx = int(last)
                if 0 <= idx < self.tabs.count() and self.tabs.isTabVisible(idx):
                    self.tabs.setCurrentIndex(idx)
        except Exception:
            pass


    def _tab_context_menu(self, pos):
        """Right-click on a tab bar item → pop-out / hide / reorder hint."""
        from PyQt6.QtWidgets import QMenu
        bar = self.tabs.tabBar()
        idx = bar.tabAt(pos)
        menu = QMenu(self)

        if idx >= 0:
            label = self.tabs.tabText(idx)
            popout_act = menu.addAction(
                f"⧉  Pop out  '{label}'  (or double-click tab)")
            popout_act.triggered.connect(
                lambda: self._undock_tab(idx))

            menu.addSeparator()
            hide_act = menu.addAction(f"✕  Hide  '{label}'")
            hide_act.triggered.connect(
                lambda: self._hide_tab(idx))

        menu.addSeparator()
        hint = menu.addAction(
            "↔  Drag tabs to reorder  (unlock in View → Layout)")
        hint.setEnabled(False)

        locked = self.cfg.get("ui.layout_locked", False)
        lock_act = menu.addAction(
            "🔒 Lock layout" if not locked else "🔓 Unlock layout")
        lock_act.triggered.connect(
            lambda: self._toggle_ui_lock(not locked))

        menu.exec(bar.mapToGlobal(pos))

    def _hide_tab(self, index: int):
        """Hide a tab from the tab bar (re-enable from View → Tabs)."""
        if index < 0 or index >= self.tabs.count():
            return
        label = self.tabs.tabText(index)
        widget = self.tabs.widget(index)
        key = next((k for k, w in self._tab_map.items()
                    if w is widget), None)
        if key:
            self.cfg.set(f"ui.tab_visible.{key}", False)
            self.cfg.save()
        self.tabs.setTabVisible(index, False)
        self.statusBar().showMessage(
            f"'{label}' hidden — restore from View → Tabs", 4000)

    def _undock_tab(self, index: int):
        """Pop a tab out into a floating window. Double-click tab bar to trigger."""
        if index < 0:
            return
        widget = self.tabs.widget(index)
        label  = self.tabs.tabText(index)
        if widget is None:
            return

        # Find the key for this widget
        key = next((k for k, w in self._tab_map.items()
                    if w is widget), None)

        main_window = self

        def _redock():
            """Put the widget back into the tab bar at its original position."""
            if self.tabs.indexOf(widget) >= 0:
                return   # already docked
            original_idx = next(
                (i for i, (k, _, _) in enumerate(TABS) if k == key),
                self.tabs.count())
            self.tabs.insertTab(
                min(original_idx, self.tabs.count()), widget, label)
            self.tabs.setCurrentWidget(widget)

        # QDockWidget subclass that re-docks (instead of destroying the
        # widget) when its close button is pressed. Without this, closing a
        # popped-out window destroyed the tab's widget and the tab could not
        # be brought back even via the View menu (user report).
        class _FloatingTab(QDockWidget):
            def closeEvent(self_inner, event):
                # Detach the widget so it isn't destroyed with the dock, then
                # re-dock it into the tab bar.
                self_inner.setWidget(None)
                widget.setParent(main_window)
                _redock()
                try:
                    main_window._floating_windows.remove(self_inner)
                except (ValueError, AttributeError):
                    pass
                event.accept()

        win = _FloatingTab(label, self)
        win.setWidget(widget)
        win.setFloating(True)
        win.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable)
        # Force a visible close/float button regardless of theme. The default
        # icon was rendering near-white-on-white in Light theme (user report).
        win.setStyleSheet("""
            QDockWidget::title {
                background: #2a2a2a;
                color: #f0f0f0;
                padding: 4px 8px;
                font-weight: bold;
            }
            QDockWidget::close-button, QDockWidget::float-button {
                background: #4a4a4a;
                border: 1px solid #888;
                border-radius: 2px;
                padding: 1px;
                icon-size: 12px;
            }
            QDockWidget::close-button:hover, QDockWidget::float-button:hover {
                background: #a04040;
            }
        """)
        win.resize(900, 650)
        win.show()

        # Re-dock when dragged back onto the main window too
        win.topLevelChanged.connect(
            lambda floating: (not floating) and _redock())

        # Track floating windows
        if not hasattr(self, '_floating_windows'):
            self._floating_windows = []
        self._floating_windows.append(win)

        # Remove from tab bar while floating
        self.tabs.removeTab(index)
        if key:
            self.statusBar().showMessage(
                f"{label} undocked — close it or drag it back "
                "to re-dock", 4000)

    # Registry for simple tabs: key → (module_path, class_name, args_lambda)
    # args_lambda(self, ldb) → tuple of constructor args
    _TAB_REGISTRY = {
        "rig":      ("ui.tabs.rig_tab",             "RigTab",            lambda s, _: (s.rig, s.cfg)),
        "modes":    ("ui.tabs.modes_tab",           "ModesTab",          lambda s, ldb: (s.rig, s.cfg, ldb)),
        "log":      ("ui.tabs.log_tab",             "LogTab",            lambda s, _: (s.cfg,)),
        "bandcond": ("ui.tabs.band_conditions_tab", "BandConditionsTab", lambda s, _: (s.cfg,)),
        "sdr":      ("ui.tabs.sdr_tab",             "SDRTab",            lambda s, _: (s.cfg, s.rig)),
        "digital":  ("ui.tabs.digital_tab",         "DigitalTab",        lambda s, _: (s.cfg, s.rig)),
        "localrf":  ("ui.tabs.localrf_tab",         "LocalRFTab",        lambda s, _: (s.cfg, s.rig)),
        "winlink":  ("ui.tabs.winlink_tab",         "WinlinkTab",        lambda s, _: (s.cfg, s.rig)),
        "help":     ("ui.tabs.help_tab",            "HelpTab",           lambda s, _: (s.cfg,)),
    }

    def _make_map_tab(self, ldb) -> "QWidget":
        """Build MapTab and wire the location-change callback."""
        from ui.tabs.map_tab import MapTab
        tab = MapTab(self.cfg, ldb)
        self.location.on_location_change(tab.on_location_change)
        return tab

    def _build_tab(self, key: str, label: str, ldb) -> "QWidget":
        """Instantiate one tab widget. Imports are lazy (local)."""
        if key == "map":
            return self._make_map_tab(ldb)
        entry = self._TAB_REGISTRY.get(key)
        if entry:
            import importlib
            mod_path, cls_name, args_fn = entry
            cls = getattr(importlib.import_module(mod_path), cls_name)
            return cls(*args_fn(self, ldb))
        from ui.tabs.stub_tab import StubTab
        return StubTab(label, key, self.cfg)

    def _make_tab(self, key: str, label: str) -> "QWidget":
        """Lazy-load tab widgets — each tab is isolated so one failure
        never crashes the whole application."""
        ldb = self._get_log_db()
        try:
            return self._build_tab(key, label, ldb)
        except Exception as e:
            log.error(f"Tab '{key}' failed to load: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return self._make_tab_error_widget(key, e)

    def _make_tab_error_widget(self, key: str, exc: Exception) -> QWidget:
        """Return a visible placeholder widget when a tab fails to load."""
        err_w = QWidget()
        err_w.setObjectName("tab_load_error")   # smoke tests detect this
        err_l = QVBoxLayout(err_w)
        err_l.setContentsMargins(30, 30, 30, 30)
        t = QLabel(f"Tab failed to load: {key}")
        t.setStyleSheet("color:#cc4444;font-weight:bold;")
        err_l.addWidget(t)
        d = QLabel(f"{type(exc).__name__}: {exc}\n\nCheck logs/squelch.log for details.")
        d.setWordWrap(True)
        err_l.addWidget(d)
        err_l.addStretch()
        return err_w

    def _build_topbar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(38)
        bar.setObjectName("topbar")
        bar.setStyleSheet(
            "QFrame#topbar{border-bottom:1px solid #1a1a1a;}")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(12)

        title = QLabel(APP_NAME)
        title.setStyleSheet(
            "color:#3fbe6f;font-weight:bold;"
            "font-family:'Courier New';")
        lay.addWidget(title)
        lay.addWidget(_vsep())

        # Inline-editable callsign
        self._cs_lbl = ClickableLabel(
            self.cfg.callsign or "No callsign set",
            "e.g. W4XYZ",
            self._on_callsign_edit,
            max_length=12)
        self._cs_lbl.setStyleSheet(
            ""
            "font-family:'Courier New';")
        self._cs_lbl.setToolTip(
            "Your FCC callsign\n"
            "Click to edit\n"
            "Used in all transmissions, logs, and beacons")
        lay.addWidget(self._cs_lbl)

        # Operator profile switcher
        self._profile_combo = QComboBox()
        self._profile_combo.setFixedWidth(120)
        self._profile_combo.setFixedHeight(24)
        self._profile_combo.setStyleSheet(
            "QComboBox{"
            "background:#141414;"
            "border:1px solid #222;border-radius:3px;"
            "padding:2px 6px;}"
            "QComboBox::drop-down{border:none;width:16px;}"
            "QComboBox QAbstractItemView{"
            "background:#141414;"
            "selection-background-color:#1a3a1a;}")
        self._profile_combo.setToolTip(
            "Operator profile switcher\n"
            "Each profile has its own callsign,\n"
            "credentials, and settings.\n"
            "Click '+' to create a new profile\n"
            "Useful for club stations with multiple ops")
        self._profile_combo.currentIndexChanged.connect(
            self._on_profile_change)
        lay.addWidget(self._profile_combo)
        lay.addWidget(_vsep())

        # Inline-editable grid
        self._grid_lbl = ClickableLabel(
            self.cfg.grid or "No grid set",
            "Maidenhead grid (DM79rr), ZIP (22030), "
            "city (Denver CO), or MGRS. "
            "All formats resolve to Maidenhead grid square.",
            self._on_grid_edit,
            max_length=30)
        self._grid_lbl.setStyleSheet(
            ""
            "font-family:'Courier New';")
        lay.addWidget(self._grid_lbl)
        lay.addWidget(_vsep())

        self._loc_lbl = QLabel("—")
        self._loc_lbl.setStyleSheet(
            "color:#4a4a4a;")
        lay.addWidget(self._loc_lbl)
        lay.addStretch()

        # Clock display
        self._utc_lbl = QLabel("00:00:00 UTC")
        self._utc_lbl.setStyleSheet(
            "color:#3fbe6f;font-family:'Courier New';"
            "")
        self._utc_lbl.setToolTip(
            "Click to toggle UTC / Local time")
        self._utc_lbl.mousePressEvent = self._toggle_clock
        self._show_utc = True
        lay.addWidget(self._utc_lbl)
        lay.addWidget(_vsep())

        self._rig_pill = QLabel("● RIG")
        self._rig_pill.setStyleSheet(
            ""
            "font-family:'Courier New';")
        lay.addWidget(self._rig_pill)

        return bar

    # ── Menu ──────────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = self.menuBar()

        # ── File ──────────────────────────────────────────────────────────
        fm = mb.addMenu(self.tr("&File"))

        sa = QAction(self.tr("Settings…"), self)
        sa.setShortcut("Ctrl+,")
        sa.triggered.connect(self._open_settings)
        fm.addAction(sa)

        pa = QAction(self.tr("Paths && Executables…"), self)
        pa.triggered.connect(self._open_paths)
        fm.addAction(pa)
        fm.addSeparator()

        qa = QAction(self.tr("Quit"), self)
        qa.setShortcut("Ctrl+Q")
        qa.triggered.connect(self.close)
        fm.addAction(qa)

        # ── Rig ───────────────────────────────────────────────────────────
        rm = mb.addMenu(self.tr("&Rig"))

        select_rig = QAction(
            self.tr("Select Radio Model…"), self)
        select_rig.triggered.connect(self._select_rig_model)
        rm.addAction(select_rig)

        connect_rig = QAction(
            self.tr("Connect Rig"), self)
        connect_rig.triggered.connect(
            lambda: self.tabs.setCurrentWidget(
                self._tab_map["rig"]))
        rm.addAction(connect_rig)

        # ── View ──────────────────────────────────────────────────────────
        vm = mb.addMenu(self.tr("&View"))

        # Workspace mode toggle
        ws_act = QAction(self.tr("🖥  Workspace Mode"), self)
        ws_act.setToolTip(
            "Switch to free-form workspace layout.\n"
            "Each panel becomes a dockable, resizable window.\n"
            "Drag panels anywhere, save custom layouts.")
        ws_act.setShortcut("Ctrl+Shift+W")
        ws_act.triggered.connect(self._enter_workspace_mode)
        vm.addAction(ws_act)
        vm.addSeparator()

        # Theme submenu
        theme_menu = vm.addMenu(self.tr("Theme"))
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        current_theme = self.cfg.get("ui.theme", "Dark")
        for theme_name in THEMES:
            a = QAction(theme_name, self)
            a.setCheckable(True)
            a.setChecked(theme_name == current_theme)
            a.triggered.connect(
                lambda _, n=theme_name: self._set_theme(n))
            theme_group.addAction(a)
            theme_menu.addAction(a)

        # Font size submenu
        font_menu = vm.addMenu(self.tr("Font Size"))
        current_fs = self.cfg.get("ui.font_size", 11)
        fs_group = QActionGroup(self)
        fs_group.setExclusive(True)
        for size in [9, 10, 11, 12, 13, 14]:
            a = QAction(f"{size}pt", self)
            a.setCheckable(True)
            a.setChecked(size == current_fs)
            a.triggered.connect(
                lambda _, s=size: self._set_font_size(s))
            fs_group.addAction(a)
            font_menu.addAction(a)

        vm.addSeparator()

        # Spectrum toggle
        spec_a = QAction(
            self.tr("Toggle Spectrum / Waterfall"), self)
        spec_a.setShortcut("Ctrl+W")
        spec_a.triggered.connect(self._toggle_spectrum)
        self._spectrum_action = spec_a
        vm.addAction(spec_a)

        vm.addSeparator()

        # Tab visibility submenu
        tabs_menu = vm.addMenu(self.tr("Show / Hide Tabs"))
        self._tab_actions: dict[str, QAction] = {}
        for key, label, _ in TABS:
            clean_label = label.split("  ", 1)[-1] \
                if "  " in label else label
            a = QAction(clean_label, self)
            a.setCheckable(True)
            a.setChecked(self._tab_visibility.get(key, True))
            a.triggered.connect(
                lambda checked, k=key: self._set_tab_visible(
                    k, checked))
            self._tab_actions[key] = a
            tabs_menu.addAction(a)

        vm.addSeparator()

        # Clock toggle
        clock_a = QAction(
            self.tr("Toggle UTC / Local Time"), self)
        clock_a.triggered.connect(
            lambda: self._toggle_clock(None))
        vm.addAction(clock_a)

        vm.addSeparator()

        # Demo Mode — disables ALL transmit (for lectures/demos, C-06 Elena)
        demo_a = QAction(self.tr("Demo Mode (disable transmit)"), self)
        demo_a.setCheckable(True)
        demo_a.setChecked(self.cfg.get("demo.mode", False))
        demo_a.triggered.connect(self._toggle_demo_mode)
        self._demo_action = demo_a
        vm.addAction(demo_a)

        # Guest Operator — a student/visitor operates; TX stays ENABLED.
        guest_a = QAction(self.tr("Guest Operator…"), self)
        guest_a.triggered.connect(self._open_guest_operator)
        vm.addAction(guest_a)

        # ── Help ──────────────────────────────────────────────────────────
        hm = mb.addMenu(self.tr("&Help"))

        open_help = QAction(
            self.tr("Open Help Window"), self)
        open_help.setShortcut("Ctrl+H")
        open_help.triggered.connect(self._open_help)
        hm.addAction(open_help)

        open_logs = QAction(
            self.tr("Open Diagnostic Logs"), self)
        open_logs.setToolTip("Open the folder containing the software diagnostic log "
            "(not the QSO logbook)")
        open_logs.triggered.connect(self._open_log_folder)
        hm.addAction(open_logs)

        hm.addSeparator()

        about_a = QAction(self.tr("About Squelch"), self)
        about_a.triggered.connect(self._about)
        hm.addAction(about_a)

    # ── Status bar ────────────────────────────────────────────────────────

    def _build_statusbar(self):
        sb = self.statusBar()
        self._sb_msg  = QLabel(self.tr("Ready"))
        self._sb_rig  = QLabel(self.tr("Rig: Disconnected"))
        self._sb_loc  = QLabel("Location: —")
        sb.addWidget(self._sb_msg, 1)
        sb.addPermanentWidget(self._sb_loc)
        sb.addPermanentWidget(self._sb_rig)

    # ── Wire ──────────────────────────────────────────────────────────────

    def _wire(self):
        # Global keyboard shortcuts
        f1 = QAction(self)
        f1.setShortcut("F1")
        f1.triggered.connect(self._open_help)
        self.addAction(f1)

        self.rig.on_state_change(self._on_rig)
        self.location.on_location_change(self._on_loc)
        # Safety alerts
        try:
            from core.safety import get_safety
            get_safety().on_alert(self._on_safety_alert)
        except Exception as e:
            log.warning(f"Safety wire: {e}")

    def _start_clock(self):
        t = QTimer(self)
        t.setInterval(1000)
        t.timeout.connect(self._tick)
        t.start()

    # ── Clock ─────────────────────────────────────────────────────────────

    @pyqtSlot()
    def _tick(self):
        now_utc = datetime.now(timezone.utc)
        if self._show_utc:
            self._utc_lbl.setText(
                now_utc.strftime("%H:%M:%S UTC"))
            self._utc_lbl.setToolTip(
                "Click to show local time")
        else:
            # Use local system time - works on all platforms
            from datetime import datetime as dt
            now_local = dt.now()
            self._utc_lbl.setText(
                now_local.strftime("%H:%M:%S LCL"))
            self._utc_lbl.setToolTip(
                "Click to show UTC time")

    def _toggle_clock(self, _event=None):
        self._show_utc = not self._show_utc
        # Force immediate update
        self._tick()

    # ── Rig state ─────────────────────────────────────────────────────────

    def _on_rig(self, state):
        QTimer.singleShot(0,
            lambda s=state: self._apply_rig(s))

    def _apply_rig(self, state):
        if state.status == RigStatus.PTT_TX:
            col, txt = "#ff4444", "● TX"
        elif state.status == RigStatus.CONNECTED:
            col, txt = "#3fbe6f", "● RIG"
        elif state.status == RigStatus.CONNECTING:
            col, txt = "#aaaa22", "◌ RIG"
        elif state.status == RigStatus.ERROR:
            col, txt = "#cc4444", "● ERR"
        else:
            col, txt = "#444444", "● RIG"
        self._rig_pill.setText(txt)
        self._rig_pill.setStyleSheet(
            f"color:{col};"
            "font-family:'Courier New';")
        connected = self.rig.is_connected
        freq_str = (
            f"  {state.freq_hz/1e6:.4f} MHz  {state.mode}"
            if connected else "")
        self._sb_rig.setText(
            f"Rig: {state.status.value}{freq_str}")

    # ── Location ──────────────────────────────────────────────────────────

    def _on_loc(self, loc, _rr_refresh):
        QTimer.singleShot(0,
            lambda l=loc: self._apply_loc(l))

    def _apply_loc(self, loc):
        disp = loc.display if loc.is_valid else "—"
        self._loc_lbl.setText(disp)
        self._sb_loc.setText(f"Location: {disp}")
        # Update dump1090 station marker whenever location changes
        if loc.is_valid:
            import threading
            threading.Thread(
                target=self.location.write_dump1090_receiver_json,
                daemon=True).start()
        # Always show Maidenhead grid in the grid label
        if loc.grid:
            self._grid_lbl.setText(loc.grid)
            self._grid_lbl.setStyleSheet(
                "color:#3fbe6f;"
                "font-family:'Courier New';")
        elif loc.is_valid:
            # Have lat/lon, compute grid
            from core.location import _latlon_to_grid
            try:
                grid = _latlon_to_grid(loc.lat, loc.lon)
                self._grid_lbl.setText(grid)
                self._grid_lbl.setStyleSheet(
                    "color:#3fbe6f;"
                    "font-family:'Courier New';")
            except Exception:
                pass

    # ── Callsign / Grid edits ─────────────────────────────────────────────

    def _on_callsign_edit(self, val: str):
        """Save inline callsign edit to cfg AND the active profile so a
        profile switch does not overwrite what the user just typed."""
        self.cfg.callsign = val
        self.cfg.save()
        # Also update the profile record so switch_to() doesn't overwrite
        try:
            from core.profiles import get_profile_manager
            pm = get_profile_manager()
            cur = pm.current   # @property — access without ()
            if cur:
                cur.callsign = val
                pm.save()
        except Exception:
            pass
        # Keep the label in sync (belt + braces — _commit already calls setText)
        try:
            self._cs_lbl.setText(val)
        except Exception:
            pass
        log.info(f"Callsign updated to: {val}")

    def _on_location_found(self, grid: str, display: str,
                            lat: float, lon: float):
        """Slot — always called on main thread via signal."""
        if not grid:
            return
        grid = grid.upper()
        self._grid_lbl.setText(grid)
        self._grid_lbl.setStyleSheet(
            "color:#3fbe6f;"
            "font-family:'Courier New';")
        if display and hasattr(self, "_loc_lbl"):
            self._loc_lbl.setText(display)
        self.cfg.grid = grid
        if lat:
            self.cfg.set("location.lat", lat)
            self.cfg.set("location.lon", lon)
        self.cfg.save()
        for tab in self._tab_map.values():
            if hasattr(tab, "on_location_change"):
                try:
                    tab.on_location_change(self.location)
                except Exception:
                    pass

    def _on_location_failed(self, msg: str):
        """Slot — location search failed, update label."""
        self._grid_lbl.setText(msg)
        self._grid_lbl.setStyleSheet(
            "color:#cc6644;"
            "font-family:'Courier New';")

    def _on_grid_edit(self, val: str):
        """
        Handle grid/ZIP/city/MGRS entry from top bar.
        All inputs resolve to Maidenhead grid square.
        Label always settles on a grid — never stays as
        a ZIP code or city name.
        """
        from core.location import _valid_grid, _latlon_to_grid
        import threading

        val = val.strip()
        if not val:
            return

        def _set_grid(grid: str, display: str = "",
                       lat: float = 0.0, lon: float = 0.0):
            """Final step — always show Maidenhead grid."""
            if not grid:
                return
            grid = grid.upper()
            self._grid_lbl.setText(grid)
            self._grid_lbl.setStyleSheet(
                "color:#3fbe6f;"
                "font-family:'Courier New';")
            if display:
                if hasattr(self, "_loc_lbl"):
                    self._loc_lbl.setText(display)
                if hasattr(self, "_sb_loc"):
                    self._sb_loc.setText(
                        f"Location: {display}")
            self.cfg.grid = grid
            if lat:
                self.cfg.set("location.lat", lat)
                self.cfg.set("location.lon", lon)
            self.cfg.save()
            # Notify all tabs of location change
            for key, tab in self._tab_map.items():
                if hasattr(tab, "on_location_change"):
                    try:
                        tab.on_location_change(
                            self.location)
                    except Exception:
                        pass

        if _valid_grid(val):
            # Already a valid grid square
            self.location.set_from_grid(val.upper())
            QTimer.singleShot(0,
                lambda g=val.upper(): _set_grid(g))
        else:
            # ZIP, city, address — search via Nominatim
            self._grid_lbl.setText("Searching…")
            self._grid_lbl.setStyleSheet(
                ""
                "font-family:'Courier New';")

            def _search(q=val):
                try:
                    loc = self.location.search(q)
                    if loc and loc.is_valid:
                        grid = loc.grid or ""
                        if not grid and loc.lat:
                            try:
                                grid = _latlon_to_grid(
                                    loc.lat, loc.lon)
                            except Exception:
                                pass
                        if grid:
                            self.location.apply(loc)
                            city  = getattr(loc, "city",  "") or ""
                            state = getattr(loc, "state", "") or ""
                            disp  = ", ".join(
                                filter(None, [city, state]))
                            lat_v = float(
                                getattr(loc, "lat", 0.0) or 0.0)
                            lon_v = float(
                                getattr(loc, "lon", 0.0) or 0.0)
                            # Thread-safe: emit signal, not QTimer
                            self._location_found.emit(
                                grid, disp, lat_v, lon_v)
                        else:
                            self._location_failed.emit(
                                "Not found — try grid square")
                    else:
                        self._location_failed.emit("Not found")
                except Exception as e:
                    log.debug(f"Location search: {e}")
                    self._location_failed.emit("Search failed")
            import threading
            threading.Thread(
                target=_search, daemon=True).start()

    def _on_safety_alert(self, title: str,
                          message: str, severity: str):
        QTimer.singleShot(0, lambda t=title, m=message,
                          s=severity: self._show_alert(t, m, s))

    def _show_alert(self, title: str,
                     message: str, severity: str):
        if severity == "error":
            QMessageBox.critical(self, title, message)
        else:
            QMessageBox.warning(self, title, message)

    # ── Tab management ────────────────────────────────────────────────────

    def _set_tab_visible(self, key: str, visible: bool):
        widget = self._tab_map.get(key)
        if widget:
            idx = self.tabs.indexOf(widget)
            if idx >= 0:
                self.tabs.setTabVisible(idx, visible)
        self._tab_visibility[key] = visible
        self.cfg.set(f"ui.tab_visible.{key}", visible)
        self.cfg.save()

    def _tab_context_menu(self, pos):
        idx = self.tabs.tabBar().tabAt(pos)
        if idx < 0:
            return
        menu = QMenu(self)
        if idx > 0:
            ml = menu.addAction("← Move left")
            ml.triggered.connect(
                lambda: self.tabs.tabBar().moveTab(idx, idx-1))
        if idx < self.tabs.count() - 1:
            mr = menu.addAction("→ Move right")
            mr.triggered.connect(
                lambda: self.tabs.tabBar().moveTab(idx, idx+1))
        menu.addSeparator()
        hide = menu.addAction("Hide this tab")
        tab_key = list(self._tab_map.keys())[idx] \
            if idx < len(self._tab_map) else None
        if tab_key:
            hide.triggered.connect(
                lambda: self._set_tab_visible(tab_key, False))
        menu.addSeparator()
        show_all = menu.addAction("Show all tabs")
        show_all.triggered.connect(self._show_all_tabs)
        menu.exec(self.tabs.tabBar().mapToGlobal(pos))

    def _show_all_tabs(self):
        for key in self._tab_map:
            self._set_tab_visible(key, True)
            if key in self._tab_actions:
                self._tab_actions[key].setChecked(True)

    # ── View actions ──────────────────────────────────────────────────────

    def _set_theme(self, name: str):
        fs = max(8, min(20, self.cfg.get("ui.font_size", 11)))
        self.setStyleSheet(get_stylesheet(name, fs))
        self.cfg.set("ui.theme", name)
        self.cfg.save()

    def _set_font_size(self, size: int):
        size = max(8, min(20, size))
        theme = self.cfg.get("ui.theme", "Dark")
        self.setStyleSheet(get_stylesheet(theme, size))
        # QSS font-size is overridden by inline widget stylesheets, so also
        # set the application default font — this cascades to every widget
        # that doesn't explicitly set its own font, making the size setting
        # actually take effect app-wide.
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtGui import QFont
            app = QApplication.instance()
            if app:
                f = app.font()
                f.setPointSize(size)
                app.setFont(f)
        except Exception:
            pass
        self.cfg.set("ui.font_size", size)
        self.cfg.save()


    def _update_spectrum_action(self, index: int = -1):
        """Enable the Spectrum/Waterfall toggle only on tabs that have one."""
        act = getattr(self, '_spectrum_action', None)
        if act is None:
            return
        # Only Rig and SDR tabs have a spectrum/waterfall display
        widget = self.tabs.currentWidget()
        has_spectrum = False
        if widget is not None:
            has_spectrum = (
                hasattr(widget, '_spectrum') or
                hasattr(widget, '_waterfall') or
                hasattr(widget, 'toggle_spectrum') or
                hasattr(widget, '_toggle_spectrum'))
        act.setEnabled(has_spectrum)
        act.setVisible(has_spectrum)

    def _toggle_spectrum(self):
        rig_tab = self._tab_map.get("rig")
        if rig_tab and hasattr(rig_tab, '_spectrum_widget'):
            sw = rig_tab._spectrum_widget
            if sw:
                visible = not sw.isVisible()
                sw.setVisible(visible)
                if hasattr(rig_tab, '_spec_toggle'):
                    rig_tab._spec_toggle.setChecked(visible)

    def _set_font_size(self, size: int):
        """
        Change application font size globally.
        Affects tooltips, labels, help text, everything.
        Persisted to config.
        """
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            f = app.font()
            f.setPointSize(size)
            app.setFont(f)
            # Also update tooltip font
            app.setStyleSheet(
                app.styleSheet() +
                f"QToolTip{{font-size:{size}pt;"
                f"padding:6px;border:1px solid #333;"
                f"background:#1a1a1a;}}")
        self.cfg.set("ui.font_size", size)
        self.cfg.save()
        log.info(f"Font size set to {size}pt")

    def _toggle_ui_lock(self, locked: bool):
        """Lock/unlock UI layout — prevent accidental tab moves."""
        self.cfg.set("ui.layout_locked", locked)
        self.cfg.save()
        # Enable/disable tab drag reordering
        self.tabs.tabBar().setMovable(not locked)
        # Lock/unlock splitters
        from PyQt6.QtWidgets import QSplitter
        for splitter in self.findChildren(QSplitter):
            for i in range(splitter.count()):
                splitter.handle(i).setEnabled(not locked)
        icon = "🔒" if locked else "🔓"
        self._lock_action.setText(
            f"{icon} {'Lock' if not locked else 'Unlock'} UI Layout")


    # ── Workspace mode ────────────────────────────────────────────────────

    def _enter_workspace_mode(self):
        """Hand panels to PanelShell and show the workspace window."""
        from ui.panel_shell import PanelShell
        from ui.panel import SquelchPanel
        # Collect all SquelchPanel instances from the tab map
        panels = {
            pid: tab
            for pid, tab in self._tab_map.items()
            if isinstance(tab, SquelchPanel) and
               getattr(tab, "panel_id", "")
        }
        if not panels:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "Workspace mode",
                "No panels found. This build may need updating.")
            return
        # Temporarily remove panels from the tab widget
        for pid, panel in panels.items():
            idx = self.tabs.indexOf(panel)
            if idx >= 0:
                self.tabs.removeTab(idx)
        self._panel_shell = PanelShell(panels, self.cfg, parent=self)
        self._panel_shell.resize(1400, 900)
        self._panel_shell.show()
        self._panel_shell.raise_()
        self.statusBar().showMessage(
            "Workspace mode active — use Workspace menu to save layouts, "
            "View → Back to tab mode to return", 6000)

    def exit_workspace_mode(self):
        """Re-adopt panels from PanelShell back into the tab bar."""
        if not hasattr(self, "_panel_shell"):
            return
        for pid, panel in self._panel_shell._panels.items():
            # Find original tab label from TABS list
            label = next(
                (lbl for k, lbl, _ in TABS if k == pid), pid)
            if self.tabs.indexOf(panel) < 0:
                self.tabs.addTab(panel, label)
                self._tab_map[pid] = panel
        self._panel_shell = None
        self.show(); self.raise_()
        self.statusBar().showMessage(
            "Returned to tab mode", 3000)

    def _open_log_folder(self):
        """Open the folder containing squelch.log in the system file manager."""
        import sys, subprocess
        from core.config import LOG_DIR
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            path = str(LOG_DIR)
            if sys.platform == "win32":
                import os
                os.startfile(path)            # noqa: only exists on Windows
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "Log Folder",
                f"Logs are stored at:\n{LOG_DIR}\n\n({e})")

    def _open_help(self):
        """Jump to Help tab — F1."""
        help_tab = self._tab_map.get("help")
        if help_tab:
            idx = self.tabs.indexOf(help_tab)
            if idx >= 0:
                self.tabs.setCurrentIndex(idx)

    def _rearrange_hint(self):
        """Show tab rearrange instructions."""
        locked = self.cfg.get("ui.layout_locked", False)
        if locked:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, self.tr("Rearrange Tabs"),
                self.tr(
                    "UI is currently locked.\n\n"
                    "Unlock via View → Unlock UI Layout "
                    "to drag tabs into a different order."))
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, self.tr("Rearrange Tabs"),
                self.tr(
                    "Drag tabs to reorder them.\n\n"
                    "Right-click a tab to hide it.\n"
                    "View → Show/Hide Tabs to restore "
                    "hidden tabs.\n\n"
                    "Lock your layout via View → "
                    "Lock UI Layout when done."))




    def _show_network_log(self):
        """C-12 (Priya): show the network activity log so the user can audit
        exactly what Squelch connected to, when, and whether they started it."""
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTextEdit,
                                     QLabel, QPushButton, QHBoxLayout)
        from core.netlog import recent_events, auto_connection_count
        dlg = QDialog(self)
        dlg.setWindowTitle("Network Activity")
        dlg.resize(640, 420)
        lay = QVBoxLayout(dlg)
        auto_n = auto_connection_count()
        summary = QLabel(
            f"Outbound connections this session — {auto_n} automatic.\n"
            "AUTO = app-initiated (band conditions, satellites, optional "
            "geolocation). USER = you clicked something.")
        summary.setWordWrap(True)
        lay.addWidget(summary)
        view = QTextEdit()
        view.setReadOnly(True)
        lines = []
        for e in recent_events():
            tag = "USER" if e["user_initiated"] else "AUTO"
            lines.append(f'{e["ts_utc"]}  [{tag}]  {e["host"]}'
                         f'  — {e["purpose"]}')
        view.setPlainText("\n".join(lines) or "No connections recorded yet.")
        lay.addWidget(view)
        row = QHBoxLayout()
        row.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(dlg.accept)
        row.addWidget(close)
        lay.addLayout(row)
        dlg.exec()





    # ── Rig model selector ────────────────────────────────────────────────


    # ── First run ─────────────────────────────────────────────────────────



            # Don't crash — just skip it


    # ── Settings ──────────────────────────────────────────────────────────

    def _close_stale_settings_dialog(self) -> bool:
        """Close any existing settings dialog. Returns True if one was visible
        (caller should skip opening a new one)."""
        old_dlg = getattr(self, '_settings_dlg', None)
        if old_dlg is None:
            return False
        try:
            from PyQt6 import sip
        except ImportError:
            import sip
        try:
            if not sip.isdeleted(old_dlg) and old_dlg.isVisible():
                old_dlg.raise_()
                old_dlg.activateWindow()
                return True
        except Exception:
            pass
        try:
            if not sip.isdeleted(old_dlg):
                old_dlg.hide()
                old_dlg.close()
                old_dlg.deleteLater()
        except Exception:
            pass
        self._settings_dlg = None
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()  # let deleteLater() complete
        return False

    def _open_settings(self):
        """Open full settings editor (Ctrl+,)."""
        if self._close_stale_settings_dialog():
            return
        try:
            from ui.dialogs.settings_dialog import SettingsDialog
            self._settings_dlg = SettingsDialog(self.cfg, parent=self)
            dlg = self._settings_dlg
        except Exception as e:
            log.error(f"Settings dialog failed to open: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Settings",
                                f"Could not open settings: {e}\n\nTry restarting Squelch.")
            return
        if dlg.exec():
            self._apply_station_settings()
            if self.cfg.callsign:
                self._cs_lbl.setText(self.cfg.callsign)
            if self.cfg.grid:
                self._grid_lbl.setText(self.cfg.grid)
            from core.themes import get_stylesheet
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                app.setStyleSheet(get_stylesheet(
                    self.cfg.get("ui.theme", "Dark"),
                    self.cfg.get("ui.font_size", 11)))

    # ── Help window ───────────────────────────────────────────────────────

    def _open_help(self):
        """Open help as floating window — Chunk 9."""
        help_tab = self._tab_map.get("help")
        if help_tab:
            self.tabs.setCurrentWidget(help_tab)

    # ── Plugins ───────────────────────────────────────────────────────────

    def _wire_sdr_to_digital(self):
        """Wire SDR tab IQ routing to Digital tab."""
        try:
            sdr_tab     = self._tab_map.get("sdr")
            digital_tab = self._tab_map.get("digital")
            if sdr_tab and digital_tab and                     hasattr(sdr_tab, 'set_decoder_callback') and                     hasattr(digital_tab, 'receive_iq_samples'):
                sdr_tab.set_decoder_callback(
                    digital_tab.receive_iq_samples)
                log.info("SDR → Digital routing wired")
        except Exception as e:
            log.debug(f"SDR→Digital wire: {e}")

    def _load_plugins(self):
        try:
            pm = get_plugin_manager()
            pm.load_all()
            for name, widget in pm.get_plugin_tabs():
                self.tabs.addTab(widget, f"🔌  {name}")
                log.info(f"Plugin tab added: {name}")
        except Exception as e:
            log.warning(f"Plugin load: {e}")

    # ── About ─────────────────────────────────────────────────────────────

    def _about(self):
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<b>{APP_NAME}  v{VERSION}</b><br>"
            f"<i>{APP_FULL}</i><br><br>"
            f"Amateur radio operations platform.<br>"
            f"Multi-rig CAT (Icom, Yaesu, Kenwood &amp; more via Hamlib)<br>"f"FT8/FT4/WSPR/JS8 · PSK/RTTY/CW · SDR · Winlink · QSO logging<br>"
            f"SDR · P25/DMR · Winlink/VARA · APRS<br><br>"
            "<a href='https://github.com/dawardy/squelch'"
            " style='color:#3fbe6f'>"
            "github.com/dawardy/squelch</a><br><br>"
            "Licensed under GNU General Public License v3<br>"
            "Copyright (C) 2026 github.com/dawardy/squelch<br><br>"
            "<b>Integrated projects:</b><br>"
            "Hamlib (LGPL) · SoapySDR (Boost) · PyQt6 (GPL)<br>"
            "WSJT-X (GPL) · Fldigi (GPL) · OP25 (GPL)<br>"
            "dump1090-fa (GPL) · DSD+ (freeware)<br>"
            "VARA/VARA HF (EA5HVK, freeware/paid)<br><br>"
            "<i>Amateur radio education and operations platform.</i>")

    # ── Save / Close ──────────────────────────────────────────────────────

    def _open_paths(self):
        dlg = PathsDialog(self.cfg, self)
        dlg.exec()






    def _restore_location(self):
        """
        Show previously saved location on startup.
        Fires after UI is fully ready.
        """
        grid = self.cfg.get("location.grid_square", "") or                self.cfg.grid or ""
        if grid:
            self._grid_lbl.setText(grid)
            self._grid_lbl.setStyleSheet(
                "color:#3fbe6f;"
                "font-family:'Courier New';")
            # Restore full location display
            city  = self.cfg.get("location.city", "")
            state = self.cfg.get("location.state", "")
            if city and state:
                disp = f"{grid}  |  {city}, {state}"
            elif city:
                disp = f"{grid}  |  {city}"
            else:
                disp = grid
            self._loc_lbl.setText(disp)
            self._sb_loc.setText(f"Location: {disp}")
        elif self.cfg.get("callsign"):
            # Have callsign but no location — prompt
            self._loc_lbl.setText("No location set — click grid to set")
            self._loc_lbl.setStyleSheet("")






    def _apply_saved_font_size(self):
        """Apply saved font size preference on startup."""
        size = self.cfg.get("ui.font_size", 0)
        if size and isinstance(size, int) and 8 <= size <= 24:
            self._set_font_size(size)

    def _auto_detect_software(self):
        """Silent startup scan for external programs."""
        import threading
        def _scan():
            launcher = get_launcher(self.cfg)
            found = launcher.auto_detect_all()
            if found:
                log.info(
                    f"Auto-detected {len(found)} "
                    f"external programs")
        threading.Thread(
            target=_scan, daemon=True).start()

    def closeEvent(self, event):
        # Confirm if transmitting
        from core.safety import get_safety
        if get_safety().is_transmitting():
            reply = QMessageBox.question(
                self,
                "Confirm Exit",
                "Currently transmitting.\n"
                "PTT will be released. Exit anyway?",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

        # Save window geometry
        self._settings.setValue(
            "window/geometry", self.saveGeometry())
        # Save the current tab so we can restore it next launch (C-09, Marcus)
        try:
            self._settings.setValue(
                "window/last_tab", self.tabs.currentIndex())
        except Exception:
            pass

        # Unload plugins
        try:
            pm = get_plugin_manager()
            for name in list(pm.loaded_plugins.keys()):
                pm.unload(name)
        except Exception:
            pass

        self.rig.disconnect()
        self.cfg.save_if_dirty()
        event.accept()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _get_log_db(self):
        try:
            from core.log_db import get_log_db
            return get_log_db()
        except Exception:
            return None

import re  # used in _first_run_dialog and ClickableLabel

def _vsep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setFixedWidth(1)
    f.setStyleSheet("color:#1e1e1e;")
    return f
