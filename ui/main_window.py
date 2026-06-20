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
    QDockWidget, QApplication, QAbstractItemView, QToolButton,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSettings, pyqtSlot
from PyQt6.QtGui import QAction, QActionGroup, QFont, QCursor

import re
from core.rig import RigController, RigStatus
from core.config import Config
from core.location import LocationManager
from core.themes import THEMES, get_stylesheet, get_theme
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
    ("sdr",       "〰️  SDR",            True),
    ("modes",     "📡  Weak Signal",    True),
    ("digital",   "🔊  Digital Voice",  True),
    ("winlink",   "✉️  Winlink",        True),
    ("log",       "📒  Log",            True),
    ("localrf",   "📋  Local RF",       True),
    ("map",       "🗺  Map",            True),
    ("bandcond",  "☀️  Band Cond.",     True),
    ("rf_lab",    "🔬  RF Lab",         False),
    ("help",      "❓  Help",           True),
]

# Tabs hidden in RF Lab / Education mode (no rig required)
_RF_LAB_HIDDEN = {"rig", "modes", "log", "digital", "winlink", "localrf"}
# Tabs shown in RF Lab mode (rest inherit their saved visibility)
_RF_LAB_SHOWN  = {"sdr", "rf_lab", "bandcond", "map", "help"}

# Built-in tab visibility presets; None means "show all"
TAB_PRESETS: dict = {
    "HF Ops":             ["rig", "modes", "bandcond", "log"],
    "Digital Monitoring": ["sdr", "digital", "map", "modes"],
    "Winlink":            ["winlink", "bandcond", "localrf", "rig"],
    "Full Station":       None,
}

from ui.tab_utils import tab_insert_position as _tab_insert_position


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
from ui.main_window_view      import _MainWindowViewMixin
from ui.main_window_location  import _MainWindowLocationMixin


class MainWindow(
        _MainWindowProfileMixin,
        _MainWindowNetworkMixin,
        _MainWindowGuestDemoMixin,
        _MainWindowFirstrunMixin,
        _MainWindowViewMixin,
        _MainWindowLocationMixin,
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
        self._setup_window()
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
        QTimer.singleShot(200, self._apply_saved_rf_lab_mode)
        self._auto_detect_software()
        self._populate_profiles()
        QTimer.singleShot(800, self._restore_location)
        self._apply_saved_guest_mode()
        QTimer.singleShot(3000, self._load_cty_background)

    def _setup_window(self) -> None:
        """Set window title, icon, geometry, and stylesheet from saved config."""
        self.setWindowTitle(f"{APP_NAME}  v{VERSION}  —  {APP_FULL}")
        try:
            from PyQt6.QtGui import QIcon
            from pathlib import Path as _P
            _ic = _P(__file__).resolve().parent.parent / "assets" / "squelch.png"
            if _ic.exists():
                self.setWindowIcon(QIcon(str(_ic)))
        except Exception:
            pass
        self.setMinimumSize(900, 600)
        self._settings = QSettings("Squelch", "squelch")
        geo = self._settings.value("window/geometry")
        if geo:
            self.restoreGeometry(geo)
        else:
            self.resize(1300, 840)
        theme_name = self.cfg.get("ui.theme", "Dark")
        font_size  = max(8, min(20, self.cfg.get("ui.font_size", 11)))
        self.setStyleSheet(get_stylesheet(theme_name, font_size))

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

        self.tabs.currentChanged.connect(self._on_tab_switched)
        vbox.addWidget(self.tabs)

        # Custom tab tracking
        self._custom_tabs: dict = {}   # tab_id → CustomLayoutTab

        # "+" corner button — styled like a browser new-tab button
        _add_tab_btn = QToolButton()
        _add_tab_btn.setText("＋ New Tab")
        _add_tab_btn.setToolTip(
            "Add a custom tab — view multiple panels side by side\n"
            "Panels stay accessible from their own tabs too")
        _add_tab_btn.setStyleSheet(
            "QToolButton{background:#1e5c8a;color:#fff;border:none;"
            "font-size:12px;font-weight:bold;padding:2px 10px;"
            "border-radius:3px;margin:2px;}"
            "QToolButton:hover{background:#2a7ab8;}"
            "QToolButton:pressed{background:#144066;}")
        _add_tab_btn.clicked.connect(self._add_custom_tab)
        self.tabs.setCornerWidget(
            _add_tab_btn, Qt.Corner.TopRightCorner)

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
            saved = self.cfg.get(f"panels.state.{key}", {})
            if saved and hasattr(w, "restore_state"):
                try:
                    w.restore_state(saved)
                except Exception:
                    pass

        self._restore_custom_tabs()

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
        """Right-click on a tab bar item → pop-out / move / hide / lock."""
        from PyQt6.QtWidgets import QMenu, QInputDialog
        bar = self.tabs.tabBar()
        idx = bar.tabAt(pos)
        menu = QMenu(self)

        if idx >= 0:
            label = self.tabs.tabText(idx)
            widget = self.tabs.widget(idx)
            custom_id = next(
                (tid for tid, ct in self._custom_tabs.items()
                 if ct is widget), None)

            if custom_id:
                # Custom tab context menu
                rename_act = menu.addAction(f"✏  Rename  '{label}'")
                rename_act.triggered.connect(
                    lambda: self._rename_custom_tab(custom_id, idx))
                menu.addSeparator()
                remove_act = menu.addAction(
                    f"🗑  Remove tab  '{label}'  (panels return to tab bar)")
                remove_act.triggered.connect(
                    lambda: self._remove_custom_tab(custom_id))
            else:
                popout_act = menu.addAction(
                    f"⧉  Pop out  '{label}'  (or double-click tab)")
                popout_act.triggered.connect(
                    lambda: self._undock_tab(idx))

                menu.addSeparator()
                if idx > 0:
                    ml = menu.addAction("← Move left")
                    ml.triggered.connect(
                        lambda: self.tabs.tabBar().moveTab(idx, idx - 1))
                if idx < self.tabs.count() - 1:
                    mr = menu.addAction("→ Move right")
                    mr.triggered.connect(
                        lambda: self.tabs.tabBar().moveTab(idx, idx + 1))

                menu.addSeparator()
                hide_act = menu.addAction(f"✕  Hide  '{label}'")
                hide_act.triggered.connect(
                    lambda: self._hide_tab(idx))

        menu.addSeparator()
        show_all = menu.addAction("Show all tabs")
        show_all.triggered.connect(self._show_all_tabs)

        menu.addSeparator()
        locked = self.cfg.get("ui.layout_locked", False)
        lock_act = menu.addAction(
            "🔒 Lock tab order" if not locked else "🔓 Unlock tab order")
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
        key = next((k for k, w in self._tab_map.items() if w is widget), None)

        def _redock():
            """Put the widget back into the tab bar at its original position."""
            if self.tabs.indexOf(widget) >= 0:
                return
            original_idx = next(
                (i for i, (k, _, _) in enumerate(TABS) if k == key),
                self.tabs.count())
            self.tabs.insertTab(
                min(original_idx, self.tabs.count()), widget, label)
            self.tabs.setCurrentWidget(widget)

        win = self._make_floating_dock(widget, label, _redock)
        self.tabs.removeTab(index)
        if key:
            self.statusBar().showMessage(
                f"{label} undocked — close it or drag it back to re-dock", 4000)

    def _make_floating_dock(self, widget, label: str, redock_fn) -> QDockWidget:
        """Create a floating QDockWidget that re-docks instead of destroying widget."""
        main_window = self

        # QDockWidget subclass that re-docks (instead of destroying the widget)
        # when its close button is pressed. Without this, closing a popped-out
        # window destroyed the tab's widget (user report).
        class _FloatingTab(QDockWidget):
            def closeEvent(self_inner, event):
                self_inner.setWidget(None)
                widget.setParent(main_window)
                redock_fn()
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
        # Force visible close/float buttons regardless of theme.
        # Default icons rendered near-white-on-white in Light theme (user report).
        win.setStyleSheet(
            "QDockWidget::title{"
            "background:#2a2a2a;color:#f0f0f0;padding:4px 8px;font-weight:bold;}"
            "QDockWidget::close-button,QDockWidget::float-button{"
            "background:#4a4a4a;border:1px solid #888;"
            "border-radius:2px;padding:1px;icon-size:12px;}"
            "QDockWidget::close-button:hover,QDockWidget::float-button:hover{"
            "background:#a04040;}")
        win.resize(900, 650)
        win.show()
        win.topLevelChanged.connect(
            lambda floating: (not floating) and redock_fn())
        if not hasattr(self, '_floating_windows'):
            self._floating_windows = []
        self._floating_windows.append(win)
        return win

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
        "rf_lab":   ("ui.tabs.rf_lab_tab",          "RFLabTab",          lambda s, _: (s.cfg,)),
        "help":     ("ui.tabs.help_tab",            "HelpTab",           lambda s, _: (s.cfg,)),
    }

    def _make_map_tab(self, ldb) -> "QWidget":
        """Build MapTab and wire the location-change callback."""
        from ui.tabs.map_tab import MapTab
        tab = MapTab(self.cfg, ldb)
        self.location.on_location_change(tab.on_location_change)
        # Wire Winlink tab → map once both are loaded
        from PyQt6.QtCore import QTimer as _QT
        _QT.singleShot(2000, lambda: self._wire_winlink_map(tab))
        return tab

    def _wire_winlink_map(self, map_tab) -> None:
        """Forward gateway list and repeaters to MapTab from other tabs."""
        for tab_key in ("winlink", "localrf"):
            try:
                tab = self._tab_map.get(tab_key)
                if tab and hasattr(tab, "set_map_tab"):
                    tab.set_map_tab(map_tab)
            except Exception:
                pass
        # Wire SDR auto-tune: LocalRF + Weak Signal → SDR tab
        try:
            localrf = self._tab_map.get("localrf")
            modes   = self._tab_map.get("modes")
            sdr     = self._tab_map.get("sdr")
            if localrf and sdr and hasattr(localrf, "set_sdr_tune_cb"):
                localrf.set_sdr_tune_cb(sdr._set_freq)
            if modes and sdr and hasattr(modes, "set_sdr_tune_cb"):
                modes.set_sdr_tune_cb(sdr._set_freq)
        except Exception:
            pass
        # Wire map right-click → Band Conditions path analysis
        try:
            bandcond = self._tab_map.get("bandcond")
            if (map_tab and bandcond and
                    hasattr(map_tab, "path_analysis_requested") and
                    hasattr(bandcond, "_handle_map_path")):
                map_tab.path_analysis_requested.connect(
                    bandcond._handle_map_path)
        except Exception:
            pass

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
        _t = get_theme(self.cfg.get("ui.theme", "Dark"))
        t.setStyleSheet(f"color:{_t.error_color};font-weight:bold;")
        err_l.addWidget(t)
        d = QLabel(f"{type(exc).__name__}: {exc}\n\nCheck logs/squelch.log for details.")
        d.setWordWrap(True)
        err_l.addWidget(d)
        err_l.addStretch()
        return err_w

    def _build_topbar(self) -> QFrame:
        _t = get_theme(self.cfg.get("ui.theme", "Dark"))
        bar = QFrame()
        bar.setFixedHeight(38)
        bar.setObjectName("topbar")
        bar.setStyleSheet(f"QFrame#topbar{{border-bottom:1px solid {_t.border};}}")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(12)
        title = QLabel(APP_NAME)
        title.setStyleSheet(
            f"color:{_t.accent};font-weight:bold;font-family:'Courier New';")
        lay.addWidget(title)
        lay.addWidget(_vsep(_t.border))
        self._topbar_add_station_group(lay)
        self._loc_lbl = QLabel("—")
        self._loc_lbl.setStyleSheet(f"color:{_t.fg_secondary};")
        lay.addWidget(self._loc_lbl)
        lay.addStretch()
        self._topbar_add_status_group(lay)
        return bar

    def _topbar_add_station_group(self, lay) -> None:
        """Add callsign label, profile combo, and grid label to the topbar layout."""
        _tb = get_theme(self.cfg.get("ui.theme", "Dark"))
        self._cs_lbl = ClickableLabel(
            self.cfg.callsign or "No callsign set",
            "e.g. W4XYZ",
            self._on_callsign_edit,
            max_length=12)
        self._cs_lbl.setStyleSheet("font-family:'Courier New';")
        self._cs_lbl.setToolTip(
            "Your FCC callsign\nClick to edit\n"
            "Used in all transmissions, logs, and beacons")
        lay.addWidget(self._cs_lbl)
        self._profile_combo = QComboBox()
        self._profile_combo.setFixedWidth(120)
        self._profile_combo.setFixedHeight(24)
        self._profile_combo.setStyleSheet(
            "QComboBox{background:#141414;border:1px solid #222;"
            "border-radius:3px;padding:2px 6px;}"
            "QComboBox::drop-down{border:none;width:16px;}"
            "QComboBox QAbstractItemView{background:#141414;"
            "selection-background-color:#1a3a1a;}")
        self._profile_combo.setToolTip(
            "Operator profile switcher\n"
            "Each profile has its own callsign, credentials, and settings.\n"
            "Click '+' to create a new profile\n"
            "Useful for club stations with multiple ops")
        self._profile_combo.currentIndexChanged.connect(self._on_profile_change)
        lay.addWidget(self._profile_combo)
        lay.addWidget(_vsep(_tb.border))
        self._grid_lbl = ClickableLabel(
            self.cfg.grid or "No grid set",
            "Maidenhead grid (DM79rr), ZIP (22030), city (Denver CO), or MGRS. "
            "All formats resolve to Maidenhead grid square.",
            self._on_grid_edit,
            max_length=30)
        self._grid_lbl.setStyleSheet("font-family:'Courier New';")
        lay.addWidget(self._grid_lbl)
        lay.addWidget(_vsep(_tb.border))

    def _topbar_add_status_group(self, lay) -> None:
        """Add UTC clock and rig status pill to the topbar layout."""
        _tb2 = get_theme(self.cfg.get("ui.theme", "Dark"))
        self._utc_lbl = QLabel("00:00:00 UTC")
        self._utc_lbl.setStyleSheet(
            f"color:{_tb2.accent};font-family:'Courier New';")
        self._utc_lbl.setToolTip("Click to toggle UTC / Local time")
        self._utc_lbl.mousePressEvent = self._toggle_clock
        self._show_utc = True
        lay.addWidget(self._utc_lbl)
        lay.addWidget(_vsep(_tb2.border))
        self._rig_pill = QLabel("● RIG")
        self._rig_pill.setStyleSheet("font-family:'Courier New';")
        lay.addWidget(self._rig_pill)

    # ── Menu ──────────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = self.menuBar()
        self._build_file_menu(mb)
        self._build_rig_menu(mb)
        self._build_view_menu(mb)
        self._build_help_menu(mb)

    def _build_file_menu(self, mb) -> None:
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

    def _build_rig_menu(self, mb) -> None:
        rm = mb.addMenu(self.tr("&Rig"))
        select_rig = QAction(self.tr("Select Radio Model…"), self)
        select_rig.triggered.connect(self._select_rig_model)
        rm.addAction(select_rig)
        connect_rig = QAction(self.tr("Connect Rig"), self)
        connect_rig.triggered.connect(
            lambda: self.tabs.setCurrentWidget(self._tab_map["rig"]))
        rm.addAction(connect_rig)

    def _build_view_menu(self, mb) -> None:
        vm = mb.addMenu(self.tr("&View"))
        self._build_presets_submenu(vm)
        vm.addSeparator()
        self._build_theme_submenu(vm)
        self._build_font_submenu(vm)
        vm.addSeparator()
        spec_a = QAction(self.tr("Toggle Spectrum / Waterfall"), self)
        spec_a.setShortcut("Ctrl+W")
        spec_a.triggered.connect(self._toggle_spectrum)
        self._spectrum_action = spec_a
        vm.addAction(spec_a)
        vm.addSeparator()
        self._build_tabs_submenu(vm)
        vm.addSeparator()
        clock_a = QAction(self.tr("Toggle UTC / Local Time"), self)
        clock_a.triggered.connect(lambda: self._toggle_clock(None))
        vm.addAction(clock_a)
        vm.addSeparator()
        # RF Lab Mode — SDR-only education mode; hides ham-specific tabs (C-16/C-21)
        rflab_a = QAction(self.tr("🔬  RF Lab / Education Mode"), self)
        rflab_a.setCheckable(True)
        rflab_a.setChecked(self.cfg.get("ui.mode", "ham") == "rf_lab")
        rflab_a.setShortcut("Ctrl+Shift+R")
        rflab_a.setToolTip(
            "Switches to SDR-only education layout  (Ctrl+Shift+R)\n"
            "Hides Rig, Modes, Log, Digital, Winlink, Local RF tabs.\n"
            "Shows SDR, RF Lab, Band Conditions, Map, Help.\n"
            "TX capability for USRP/HackRF remains available via the SDR tab.")
        rflab_a.triggered.connect(lambda checked: self._toggle_rf_lab_mode(checked))
        self._rflab_action = rflab_a
        vm.addAction(rflab_a)
        vm.addSeparator()
        locked = self.cfg.get("ui.layout_locked", False)
        lock_txt = "🔒 Lock UI Layout" if not locked else "🔓 Unlock UI Layout"
        lock_a = QAction(self.tr(lock_txt), self)
        lock_a.setCheckable(True)
        lock_a.setChecked(locked)
        lock_a.setToolTip(
            "Lock tab bar order to prevent accidental tab dragging.\n"
            "Also locks splitter resize handles.\n"
            "Does NOT affect section order within tabs.")
        lock_a.triggered.connect(lambda checked: self._toggle_ui_lock(checked))
        self._lock_action = lock_a
        vm.addAction(lock_a)
        vm.addSeparator()
        # Demo Mode — disables ALL transmit (C-06 Elena classroom use)
        demo_a = QAction(self.tr("Demo Mode (disable transmit)"), self)
        demo_a.setCheckable(True)
        demo_a.setChecked(self.cfg.get("demo.mode", False))
        demo_a.triggered.connect(self._toggle_demo_mode)
        self._demo_action = demo_a
        vm.addAction(demo_a)
        # Guest Operator — visitor transmits with their own callsign (C-15 Sam)
        guest_a = QAction(self.tr("Guest Operator…"), self)
        guest_a.triggered.connect(self._open_guest_operator)
        vm.addAction(guest_a)

    def _build_presets_submenu(self, vm) -> None:
        pm = vm.addMenu(self.tr("Tab Presets"))
        for name, keys in TAB_PRESETS.items():
            a = pm.addAction(name)
            a.triggered.connect(lambda _, k=keys: self._apply_tab_preset(k))
        pm.addSeparator()
        pm.addAction(self.tr("Show all tabs")).triggered.connect(self._show_all_tabs)
        pm.addSeparator()
        pm.addAction(self.tr("Save current layout…")).triggered.connect(
            self._save_tab_layout)
        self._saved_layouts_menu = pm.addMenu(self.tr("Saved layouts"))
        self._refresh_saved_layouts_menu()

    def _apply_tab_preset(self, visible_keys) -> None:
        """Show only the specified tabs; None means show all."""
        for key in self._tab_map:
            show = visible_keys is None or key in visible_keys
            self._set_tab_visible(key, show)
            if key in getattr(self, "_tab_actions", {}):
                self._tab_actions[key].setChecked(show)
        name = next(
            (n for n, k in TAB_PRESETS.items() if k == visible_keys), "custom")
        self.statusBar().showMessage(f"Tab preset applied: {name}", 3000)

    def _save_tab_layout(self) -> None:
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, self.tr("Save tab layout"), self.tr("Layout name:"))
        if not ok or not name.strip():
            return
        name = name.strip()
        visible = [k for k in self._tab_map
                   if self._tab_visibility.get(k, True)]
        layouts = dict(self.cfg.get("ui.saved_tab_layouts", {}) or {})
        layouts[name] = visible
        self.cfg.set("ui.saved_tab_layouts", layouts)
        self.cfg.save()
        self._refresh_saved_layouts_menu()
        self.statusBar().showMessage(f"Layout '{name}' saved", 3000)

    def _refresh_saved_layouts_menu(self) -> None:
        menu = getattr(self, "_saved_layouts_menu", None)
        if menu is None:
            return
        menu.clear()
        layouts = self.cfg.get("ui.saved_tab_layouts", {}) or {}
        if not layouts:
            menu.addAction(self.tr("(none saved yet)")).setEnabled(False)
            return
        for name, keys in layouts.items():
            a = menu.addAction(name)
            a.triggered.connect(lambda _, k=keys: self._apply_tab_preset(k))

    def _build_theme_submenu(self, vm) -> None:
        theme_menu = vm.addMenu(self.tr("Theme"))
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        current_theme = self.cfg.get("ui.theme", "Dark")
        for theme_name in THEMES:
            a = QAction(theme_name, self)
            a.setCheckable(True)
            a.setChecked(theme_name == current_theme)
            a.triggered.connect(lambda _, n=theme_name: self._set_theme(n))
            theme_group.addAction(a)
            theme_menu.addAction(a)

    def _build_font_submenu(self, vm) -> None:
        font_menu = vm.addMenu(self.tr("Font Size"))
        current_fs = self.cfg.get("ui.font_size", 11)
        fs_group = QActionGroup(self)
        fs_group.setExclusive(True)
        for size in [9, 10, 11, 12, 13, 14]:
            a = QAction(f"{size}pt", self)
            a.setCheckable(True)
            a.setChecked(size == current_fs)
            a.triggered.connect(lambda _, s=size: self._set_font_size(s))
            fs_group.addAction(a)
            font_menu.addAction(a)

    def _build_tabs_submenu(self, vm) -> None:
        tabs_menu = vm.addMenu(self.tr("Show / Hide Tabs"))
        self._tab_actions: dict[str, QAction] = {}
        for key, label, _ in TABS:
            clean_label = label.split("  ", 1)[-1] if "  " in label else label
            a = QAction(clean_label, self)
            a.setCheckable(True)
            a.setChecked(self._tab_visibility.get(key, True))
            a.triggered.connect(
                lambda checked, k=key: self._set_tab_visible(k, checked))
            self._tab_actions[key] = a
            tabs_menu.addAction(a)

    def _build_help_menu(self, mb) -> None:
        hm = mb.addMenu(self.tr("&Help"))
        open_help = QAction(self.tr("Open Help Window"), self)
        open_help.setShortcut("Ctrl+H")
        open_help.triggered.connect(self._open_help)
        hm.addAction(open_help)
        open_logs = QAction(self.tr("Open Diagnostic Logs"), self)
        open_logs.setToolTip(
            "Open the folder containing the software diagnostic log\n"
            "(not the QSO logbook)")
        open_logs.triggered.connect(self._open_log_folder)
        hm.addAction(open_logs)
        net_log_a = QAction(self.tr("Network Activity"), self)
        net_log_a.setToolTip(
            "Audit all outbound network connections made this session\n"
            "(C-12 Priya-38 compliance — Settings → APIs credential audit)")
        net_log_a.triggered.connect(self._show_network_log)
        hm.addAction(net_log_a)
        hm.addSeparator()
        update_cty = QAction(self.tr("Update DXCC Data (CTY.dat)"), self)
        update_cty.setToolTip(
            "Download the latest DXCC country file from country-files.com\n"
            "Improves DXCC tracking accuracy for all logged QSOs.")
        update_cty.triggered.connect(self._update_cty_dat)
        hm.addAction(update_cty)
        band_plan_a = QAction(self.tr("Frequency Reference…"), self)
        band_plan_a.setToolTip(
            "FCC Part 97 amateur bands + CB, FRS/GMRS, MURS,\n"
            "ISM/unlicensed frequency reference with category filter")
        band_plan_a.triggered.connect(self._show_band_plan)
        hm.addAction(band_plan_a)
        grid_calc_a = QAction(self.tr("Grid Square Calculator…"), self)
        grid_calc_a.setToolTip(
            "Convert between Maidenhead grid locators and lat/lon.\n"
            "Shows distance and bearing from your station.")
        grid_calc_a.triggered.connect(self._show_grid_calc)
        hm.addAction(grid_calc_a)
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

    def _show_all_tabs(self):
        for key in self._tab_map:
            self._set_tab_visible(key, True)
            if key in self._tab_actions:
                self._tab_actions[key].setChecked(True)

    # ── Tab switch handler — drives custom-tab auto-swap ─────────────────

    def _on_tab_switched(self, idx: int) -> None:
        """Called on every tab change."""
        self._update_spectrum_action(idx)

    # ── Custom tabs ───────────────────────────────────────────────────────

    def _add_custom_tab(self, title: str = "") -> None:
        from PyQt6.QtWidgets import QInputDialog
        from ui.tabs.custom_tab import CustomLayoutTab
        if not title:
            n = len(self._custom_tabs) + 1
            default = f"Custom {n}"
            title, ok = QInputDialog.getText(
                self, "New custom tab", "Tab name:", text=default)
            if not ok or not title.strip():
                return
            title = title.strip()
        tab_id = f"_custom_{len(self._custom_tabs)}_{title[:20]}"
        ct = CustomLayoutTab(tab_id, title, self.cfg, self)
        ct.panel_unassign_requested.connect(self._unassign_panel_from_custom_tab)
        ct.panel_navigate_requested.connect(self._navigate_to_panel)
        self._custom_tabs[tab_id] = ct
        ct.set_add_menu(self._make_add_panel_menu(ct))
        self.tabs.addTab(ct, title)
        self.tabs.setCurrentWidget(ct)
        self._save_custom_tabs_state()

    def _remove_custom_tab(self, tab_id: str) -> None:
        ct = self._custom_tabs.pop(tab_id, None)
        if ct is None:
            return
        idx = self.tabs.indexOf(ct)
        if idx >= 0:
            self.tabs.removeTab(idx)
        ct.deleteLater()
        self._save_custom_tabs_state()

    def _rename_custom_tab(self, tab_id: str, idx: int) -> None:
        from PyQt6.QtWidgets import QInputDialog
        ct = self._custom_tabs.get(tab_id)
        if ct is None:
            return
        name, ok = QInputDialog.getText(
            self, "Rename tab", "New name:", text=ct.panel_title)
        if ok and name.strip():
            ct.panel_title = name.strip()
            self.tabs.setTabText(idx, name.strip())
            self._save_custom_tabs_state()

    def _assign_panel_to_custom_tab(self, tab_id: str, panel_key: str) -> None:
        """Add a navigation card for panel_key to the custom tab."""
        ct = self._custom_tabs.get(tab_id)
        if ct is None:
            return
        label = next((lbl for k, lbl, _ in TABS if k == panel_key), panel_key)
        panel_title = label.split("  ", 1)[-1] if "  " in label else label
        ct.assign_panel(panel_key, panel_title)
        self._save_custom_tabs_state()

    def _unassign_panel_from_custom_tab(self, tab_id: str,
                                         panel_key: str) -> None:
        """Remove a panel's navigation card from a custom tab."""
        ct = self._custom_tabs.get(tab_id)
        if ct is None:
            return
        ct.unassign_panel(panel_key)
        self._save_custom_tabs_state()

    def _navigate_to_panel(self, panel_key: str) -> None:
        """Switch the main tab bar to the panel identified by panel_key."""
        panel = self._tab_map.get(panel_key)
        if panel:
            self.tabs.setCurrentWidget(panel)

    def _make_add_panel_menu(self, ct) -> "QMenu":
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)

        def _rebuild():
            menu.clear()
            assigned = set(ct.assigned_keys)
            for key, label, _ in TABS:
                if key in assigned:
                    continue  # already in this tab
                clean = label.split("  ", 1)[-1] if "  " in label else label
                a = menu.addAction(clean)
                a.triggered.connect(
                    lambda _, k=key: self._assign_panel_to_custom_tab(
                        ct.panel_id, k))

        menu.aboutToShow.connect(_rebuild)
        return menu

    def _save_custom_tabs_state(self) -> None:
        state = []
        for tab_id, ct in self._custom_tabs.items():
            state.append({**ct.save_state(), "tab_id": tab_id})
        self.cfg.set("ui.custom_tabs", state)
        self.cfg.save()

    def _restore_custom_tabs(self) -> None:
        from ui.tabs.custom_tab import CustomLayoutTab
        saved = self.cfg.get("ui.custom_tabs", []) or []
        for entry in saved:
            tab_id = entry.get("tab_id", "")
            title  = entry.get("title", "Custom")
            if not tab_id:
                continue
            ct = CustomLayoutTab(tab_id, title, self.cfg, self)
            ct.panel_unassign_requested.connect(
                self._unassign_panel_from_custom_tab)
            ct.panel_navigate_requested.connect(self._navigate_to_panel)
            self._custom_tabs[tab_id] = ct
            ct.set_add_menu(self._make_add_panel_menu(ct))
            self.tabs.addTab(ct, title)
            # Restore assigned panels (assign_panel creates the cards)
            for key in entry.get("assigned", []):
                label = next((lbl for k, lbl, _ in TABS if k == key), key)
                panel_title = label.split("  ", 1)[-1] if "  " in label else label
                ct.assign_panel(key, panel_title)

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




    def _show_band_plan(self):
        from ui.dialogs.band_plan_dialog import BandPlanDialog
        lic = self.cfg.get("station.license", "Extra")
        dlg = BandPlanDialog(license_class=lic, parent=self)
        dlg.exec()

    def _show_grid_calc(self):
        from ui.dialogs.grid_calc_dialog import GridCalcDialog
        dlg = GridCalcDialog(cfg=self.cfg, parent=self)
        # Pre-fill with currently entered path-to grid if available
        try:
            from ui.tabs.band_conditions_tab import BandConditionsTab
            bc = self._tab_map.get("bandcond")
            if bc and hasattr(bc, "_path_edit") and bc._path_edit.text():
                dlg._grid_in.setText(bc._path_edit.text())
        except Exception:
            pass
        dlg.exec()

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
            # _update_guest_banner sets _cs_lbl to operating_callsign(),
            # accounting for any active guest session
            self._update_guest_banner()
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

        self._save_custom_tabs_state()
        self.rig.disconnect()
        for key, w in self._tab_map.items():
            try:
                state = w.save_state()
                if state:
                    self.cfg.set(f"panels.state.{key}", state)
            except Exception:
                pass
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

def _vsep(border: str = "#2a2a2a") -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setFixedWidth(1)
    f.setStyleSheet(f"color:{border};")
    return f
