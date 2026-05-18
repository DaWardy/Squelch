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
    QApplication, QAbstractItemView
)
from PyQt6.QtCore import Qt, QTimer, QSettings, pyqtSlot
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
            "border-radius:3px;color:#3fbe6f;font-size:12px;"
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

    def _commit(self):
        # Guard against double-commit (returnPressed + focusOut both fire)
        if self._edit is None or self._editing is False:
            return
        # Mark done immediately to block re-entry
        self._editing = False
        edit = self._edit
        self._edit = None

        raw = edit.text().strip()
        try:
            edit.hide()
            edit.deleteLater()
        except Exception:
            pass

        # Allow letters, digits, slash (portable calls), spaces for
        # location searches (ZIP codes, city names)
        val = raw.strip()
        if not val or val.lower() in self._PLACEHOLDERS:
            return

        # Callsign: uppercase, alphanumeric + /
        # Location: allow spaces, digits, letters (ZIP/city)
        import re
        # Check if it looks like a callsign or a location query
        val_upper = val.upper()
        is_callsign = bool(re.match(
            r'[A-Z0-9]{1,3}[0-9][A-Z0-9]{0,3}[A-Z]', val_upper))

        if self._placeholder and 'call' in self._placeholder.lower():
            # Callsign field - strip to safe chars only
            val_clean = re.sub(r'[^A-Z0-9/]', '', val_upper)
            if not val_clean:
                return
            self.setText(val_clean)
            try:
                self._on_commit(val_clean)
            except Exception as e:
                log.warning(f"Callsign commit: {e}")
        else:
            # Location field - allow spaces, digits, letters for
            # ZIP codes, city names, MGRS, grid squares
            val_clean = re.sub(r'[^A-Za-z0-9 ,./\-]', '', val).strip()
            if not val_clean:
                return
            # Don't setText here — let _on_grid_edit set the
            # final Maidenhead grid after resolution completes
            try:
                self._on_commit(val_clean)
            except Exception as e:
                log.warning(f"Location commit: {e}")

class MainWindow(QMainWindow):
    def __init__(self, config: Config,
                 rig: RigController,
                 location: LocationManager):
        super().__init__()
        self.cfg      = config
        self.rig      = rig
        self.location = location

        self.setWindowTitle(
            f"{APP_NAME}  v{VERSION}  —  {APP_FULL}")
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

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)
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

    def _make_tab(self, key: str, label: str) -> QWidget:
        """
        Lazy-load tab widgets — only import when first created.
        All imports are local to avoid top-level import failures.
        Each tab is wrapped in try/except so one bad tab
        never crashes the whole application.
        """
        ldb = self._get_log_db()
        try:
            if key == "rig":
                from ui.tabs.rig_tab import RigTab
                return RigTab(self.rig, self.cfg)
            elif key == "modes":
                from ui.tabs.modes_tab import ModesTab
                return ModesTab(self.rig, self.cfg, ldb)
            elif key == "log":
                from ui.tabs.log_tab import LogTab
                return LogTab(self.cfg)
            elif key == "bandcond":
                from ui.tabs.band_conditions_tab import (
                    BandConditionsTab)
                return BandConditionsTab(self.cfg)
            elif key == "sdr":
                from ui.tabs.sdr_tab import SDRTab
                return SDRTab(self.cfg, self.rig)
            elif key == "digital":
                from ui.tabs.digital_tab import DigitalTab
                return DigitalTab(self.cfg, self.rig)
            elif key == "localrf":
                from ui.tabs.localrf_tab import LocalRFTab
                return LocalRFTab(self.cfg, self.rig)
            elif key == "map":
                from ui.tabs.map_tab import MapTab
                tab = MapTab(self.cfg, self._get_log_db())
                self.location.on_location_change(
                    tab.on_location_change)
                return tab
            elif key == "winlink":
                from ui.tabs.winlink_tab import WinlinkTab
                return WinlinkTab(self.cfg, self.rig)
            elif key == "help":
                from ui.tabs.help_tab import HelpTab
                return HelpTab(self.cfg)
            else:
                from ui.tabs.stub_tab import StubTab
                return StubTab(label, key, self.cfg)
        except Exception as e:
            log.error(
                f"Tab '{key}' failed to load: "
                f"{type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            # Always return something visible
            err_w = QWidget()
            err_l = QVBoxLayout(err_w)
            err_l.setContentsMargins(30, 30, 30, 30)
            t = QLabel(f"Tab failed to load: {key}")
            t.setStyleSheet(
                "color:#cc4444;font-size:13px;"
                "font-weight:bold;")
            err_l.addWidget(t)
            d = QLabel(
                f"{type(e).__name__}: {e}\n\n"
                "Check logs/squelch.log for details.")
            d.setWordWrap(True)
            d.setStyleSheet(
                "color:#888;font-size:13px;")
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
            "color:#3fbe6f;font-size:15px;font-weight:bold;"
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
            "color:#aaa;font-size:12px;"
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
            "background:#141414;color:#888;"
            "border:1px solid #222;border-radius:3px;"
            "font-size:12px;padding:2px 6px;}"
            "QComboBox::drop-down{border:none;width:16px;}"
            "QComboBox QAbstractItemView{"
            "background:#141414;color:#aaa;"
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
            "color:#777;font-size:12px;"
            "font-family:'Courier New';")
        lay.addWidget(self._grid_lbl)
        lay.addWidget(_vsep())

        self._loc_lbl = QLabel("—")
        self._loc_lbl.setStyleSheet(
            "color:#4a4a4a;font-size:13px;")
        lay.addWidget(self._loc_lbl)
        lay.addStretch()

        # Clock display
        self._utc_lbl = QLabel("00:00:00 UTC")
        self._utc_lbl.setStyleSheet(
            "color:#3fbe6f;font-family:'Courier New';"
            "font-size:13px;")
        self._utc_lbl.setToolTip(
            "Click to toggle UTC / Local time")
        self._utc_lbl.mousePressEvent = self._toggle_clock
        self._show_utc = True
        lay.addWidget(self._utc_lbl)
        lay.addWidget(_vsep())

        self._rig_pill = QLabel("● RIG")
        self._rig_pill.setStyleSheet(
            "color:#444;font-size:13px;"
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

        # Guest Operator mode
        lab_a = QAction(self.tr("Toggle Guest Operator Mode"), self)
        lab_a.triggered.connect(self._toggle_lab)
        vm.addAction(lab_a)

        # ── Help ──────────────────────────────────────────────────────────
        hm = mb.addMenu(self.tr("&Help"))

        open_help = QAction(
            self.tr("Open Help Window"), self)
        open_help.setShortcut("Ctrl+H")
        open_help.triggered.connect(self._open_help)
        hm.addAction(open_help)

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
            f"color:{col};font-size:13px;"
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
                "color:#3fbe6f;font-size:12px;"
                "font-family:'Courier New';")
        elif loc.is_valid:
            # Have lat/lon, compute grid
            from core.location import _latlon_to_grid
            try:
                grid = _latlon_to_grid(loc.lat, loc.lon)
                self._grid_lbl.setText(grid)
                self._grid_lbl.setStyleSheet(
                    "color:#3fbe6f;font-size:12px;"
                    "font-family:'Courier New';")
            except Exception:
                pass

    # ── Callsign / Grid edits ─────────────────────────────────────────────

    def _on_callsign_edit(self, val: str):
        self.cfg.callsign = val
        self.cfg.save()
        log.info(f"Callsign: {val}")

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
                "color:#3fbe6f;font-size:12px;"
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
                "color:#888;font-size:12px;"
                "font-family:'Courier New';")

            def _search(q=val):
                try:
                    loc = self.location.search(q)
                    if loc and loc.is_valid:
                        # Ensure we have a grid
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
                            lat_v = getattr(loc, "lat", 0.0) or 0.0
                            lon_v = getattr(loc, "lon", 0.0) or 0.0
                            QTimer.singleShot(0,
                                lambda g=grid, d=disp,
                                       la=lat_v, lo=lon_v:
                                _set_grid(g, d, la, lo))
                        else:
                            QTimer.singleShot(0,
                                lambda: (
                                    self._grid_lbl.setText(
                                        "Not found"),
                                    QTimer.singleShot(
                                        2500, lambda:
                                        self._grid_lbl.setText(
                                            self.cfg.grid or
                                            "No grid set"))))
                    else:
                        QTimer.singleShot(0,
                            lambda: (
                                self._grid_lbl.setText(
                                    "Not found — try a grid or city"),
                                QTimer.singleShot(
                                    2500, lambda:
                                    self._grid_lbl.setText(
                                        self.cfg.grid or
                                        "No grid set"))))
                except Exception as e:
                    log.warning(f"Location search: {e}")
                    QTimer.singleShot(0,
                        lambda: self._grid_lbl.setText(
                            self.cfg.grid or "No grid set"))

            threading.Thread(
                target=_search, daemon=True).start()

    # ── Safety alerts ─────────────────────────────────────────────────────

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
        self.cfg.set("ui.font_size", size)
        self.cfg.save()

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
        from PyQt6.QtGui import QFont
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
                f"background:#1a1a1a;color:#ccc;}}")
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

    def _toggle_lab(self):
        current = self.cfg.get("classroom.lab_mode", False)
        self.cfg.set("classroom.lab_mode", not current)
        self.cfg.save()
        state = "ENABLED" if not current else "DISABLED"
        QMessageBox.information(
            self, "Guest Operator Mode",
            f"Guest Operator mode {state}.\nRestart Squelch to apply.")

    # ── Rig model selector ────────────────────────────────────────────────

    def _select_rig_model(self):
        from core.rig_presets import preset_names, get_preset
        dlg = QDialog(self)
        dlg.setWindowTitle("Select Radio Model")
        dlg.setMinimumWidth(420)
        lay = QVBoxLayout(dlg)

        from PyQt6.QtWidgets import QComboBox, QTextEdit
        combo = QComboBox()
        combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        combo.addItem("— Select radio —")
        for name in preset_names():
            combo.addItem(name)
        lay.addWidget(combo)

        info = QTextEdit()
        info.setReadOnly(True)
        info.setMaximumHeight(200)
        info.setStyleSheet(
            "background:#111;color:#aaa;font-size:12px;"
            "font-family:'Courier New';border:1px solid #333;")
        lay.addWidget(info)

        def _on_select(idx):
            if idx <= 0:
                return
            name = combo.currentText()
            preset = get_preset(name)
            if preset:
                lines = [f"<b>{preset.name}</b><br>"]
                if preset.notes:
                    lines.append(f"{preset.notes}<br><br>")
                if preset.radio_menu_steps:
                    lines.append("<b>Radio menu settings:</b><br>")
                    for step in preset.radio_menu_steps:
                        lines.append(f"  {step}<br>")
                info.setHtml("".join(lines))

        combo.currentIndexChanged.connect(_on_select)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec() and combo.currentIndex() > 0:
            name = combo.currentText()
            preset = get_preset(name)
            if preset:
                if preset.hamlib_model:
                    self.cfg.set("rig.hamlib_model",
                                 preset.hamlib_model)
                self.cfg.set("rig.baud", preset.baud)
                self.cfg.save()
                # Update rig tab if visible
                rig_tab = self._tab_map.get("rig")
                if rig_tab and hasattr(rig_tab, '_populate_rig_models'):
                    rig_tab._populate_rig_models()
                QMessageBox.information(
                    self, "Radio Selected",
                    f"{name} selected.\n"
                    f"Baud rate: {preset.baud}\n\n"
                    "Check Radio Setup in Help for "
                    "required menu settings.")

    # ── First run ─────────────────────────────────────────────────────────

    def _auto_fill_location(self, edit):
        """
        Try to auto-fill location field using IP geolocation.
        Runs in background — pre-fills edit if successful.
        """
        import threading
        def _detect():
            try:
                loc = self.location._ip_geolocation()
                if loc and loc.is_valid:
                    city = loc.display.split(",")[0].strip()
                    QTimer.singleShot(0, lambda l=loc, c=city: (
                        edit.setPlaceholderText(
                            f"Detected: {l.grid} "
                            f"({c}) — confirm or change"),
                        edit.setText(l.grid),
                        edit.setToolTip(
                            f"Auto-detected via IP geolocation\n"
                            f"{l.display}\n"
                            f"Grid: {l.grid}\n"
                            f"Edit if incorrect.")))
            except Exception:
                pass
        threading.Thread(
            target=_detect, daemon=True).start()

    def _check_first_run(self):
        if not self.cfg.is_configured:
            QTimer.singleShot(600, self._first_run_dialog)

    def _first_run_dialog(self):
        try:
            self._first_run_dialog_impl()
        except Exception as e:
            log.error(f"First run dialog failed: {e}")
            # Don't crash — just skip it

    def _first_run_dialog_impl(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Welcome to {APP_NAME}")
        dlg.setMinimumWidth(440)
        lay = QVBoxLayout(dlg)

        intro = QLabel(
            f"<b style='font-size:14px'>"
            f"Welcome to {APP_NAME} v{VERSION}</b><br><br>"
            "Enter your callsign and location to get started.<br>"
            "Location resolves to a Maidenhead grid square — "
            "the universal reference for amateur radio.<br>"
            "You can also click either value in the top bar "
            "to edit at any time.")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        form = QFormLayout()
        cs_edit = QLineEdit()
        cs_edit.setPlaceholderText("e.g. W4XYZ")
        cs_edit.setMaxLength(12)

        loc_edit = QLineEdit()
        loc_edit.setPlaceholderText(
            "Maidenhead grid (DM79rr), ZIP, city, or MGRS")
        loc_edit.setMaxLength(30)

        # Try to auto-detect location
        self._auto_fill_location(loc_edit)

        form.addRow("Callsign:", cs_edit)
        form.addRow("Location:", loc_edit)
        lay.addLayout(form)

        hint = QLabel(
            "Find your grid: "
            "<a href='https://www.levinecentral.com/"
            "ham/grid_square.php' style='color:#3fbe6f'>"
            "levinecentral.com</a>")
        hint.setOpenExternalLinks(True)
        hint.setStyleSheet("color:#666;font-size:12px;")
        lay.addWidget(hint)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok)
        btns.accepted.connect(dlg.accept)
        lay.addWidget(btns)

        dlg.raise_()
        dlg.activateWindow()
        if dlg.exec():
            cs = re.sub(r'[^A-Z0-9/]', '',
                        cs_edit.text().strip().upper())
            loc = loc_edit.text().strip()

            if cs:
                self.cfg.callsign = cs
                self._cs_lbl.setText(cs)

            if loc:
                from core.location import _valid_grid
                loc_clean = loc.strip()
                if _valid_grid(loc_clean.upper()):
                    self.cfg.grid = loc_clean.upper()
                    self.location.set_from_grid(
                        loc_clean.upper())
                    self._grid_lbl.setText(loc_clean.upper())
                else:
                    import threading
                    self._grid_lbl.setText(
                        self.tr("Searching…"))
                    def _search(q=loc_clean):
                        try:
                            result = self.location.search(q)
                            if result and result.is_valid:
                                def _apply(r=result):
                                    self.location.apply(r)
                                    grid = r.grid or ""
                                    if grid:
                                        self.cfg.grid = grid
                                    if r.lat:
                                        self.cfg.set(
                                            "location.lat", r.lat)
                                        self.cfg.set(
                                            "location.lon", r.lon)
                                    self.cfg.save()
                                    self._grid_lbl.setText(
                                        grid or q)
                                    self._grid_lbl.setStyleSheet(
                                        "color:#3fbe6f;"
                                        "font-size:12px;"
                                        "font-family:'Courier New';")
                                    city  = getattr(r, "city",  "")
                                    state = getattr(r, "state", "")
                                    disp  = ", ".join(
                                        filter(None, [city, state]))
                                    if disp and hasattr(self, "_loc_lbl"):
                                        self._loc_lbl.setText(disp)
                                QTimer.singleShot(0, _apply)
                            else:
                                QTimer.singleShot(0,
                                    lambda: self._grid_lbl.setText(
                                        "Not found — try grid square"))
                        except Exception as e:
                            log.warning(f"First run location: {e}")
                            QTimer.singleShot(0,
                                lambda: self._grid_lbl.setText(
                                    "Search failed"))
                    threading.Thread(
                        target=_search, daemon=True).start()

            self.cfg.save()

    # ── Settings ──────────────────────────────────────────────────────────

    def _open_settings(self):
        """Open full settings editor (Ctrl+,)."""
        from ui.dialogs.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self.cfg, parent=self)
        if dlg.exec():
            # Apply all settings
            self._apply_station_settings()
            cs = self.cfg.callsign
            if cs:
                self._cs_lbl.setText(cs)
            grid = self.cfg.grid
            if grid:
                self._grid_lbl.setText(grid)
            # Reload stylesheet if theme changed
            from core.themes import get_stylesheet
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                theme = self.cfg.get("ui.theme", "Dark")
                fs    = self.cfg.get("ui.font_size", 11)
                app.setStyleSheet(
                    get_stylesheet(theme, fs))
        # placeholder to fix old stub reference
        if False:
            QMessageBox.information(
                self, "Settings",
            "Full in-app settings editor coming in v2.0.\n\n"
            "Current options:\n"
            "• Click callsign or grid in top bar to edit\n"
            "• View menu → Theme / Font Size / Tabs\n"
            "• Rig menu → Select Radio Model\n"
            "• Edit config.json for advanced options\n\n"
            "config.example.json documents all available keys.")

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
            f"IC-7100 CAT · FT8/FT4/WSPR · QSO logging<br>"
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

    def _populate_profiles(self):
        """Load operator profiles into the combo box."""
        try:
            from core.profiles import ProfileManager
            pm = ProfileManager()
            profiles = pm.list_profiles()
            current  = pm.current_name()

            self._profile_combo.blockSignals(True)
            self._profile_combo.clear()
            for p in profiles:
                self._profile_combo.addItem(p)
            # Always have "Add profile..."
            self._profile_combo.addItem("+ New profile…")
            # Select current
            idx = self._profile_combo.findText(current)
            if idx >= 0:
                self._profile_combo.setCurrentIndex(idx)
            self._profile_combo.blockSignals(False)
        except Exception as e:
            log.debug(f"Profile populate: {e}")
            self._profile_combo.clear()
            self._profile_combo.addItem(
                self.cfg.callsign or "Default")

    def _on_profile_change(self, idx: int):
        """Switch to selected operator profile."""
        name = self._profile_combo.currentText()
        if name == "+ New profile…":
            self._new_profile_dialog()
            return
        try:
            from core.profiles import ProfileManager
            pm = ProfileManager()
            if pm.switch_to(name):
                # Refresh UI from new profile
                cs = self.cfg.callsign
                if cs:
                    self._cs_lbl.setText(cs)
                grid = self.cfg.grid
                if grid:
                    self._grid_lbl.setText(grid)
                log.info(f"Switched to profile: {name}")
        except Exception as e:
            log.warning(f"Profile switch: {e}")

    def _new_profile_dialog(self):
        """Create a new operator profile."""
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, "New Profile",
            "Profile name (e.g. your callsign):")
        if ok and name.strip():
            try:
                from core.profiles import ProfileManager
                pm = ProfileManager()
                pm.create(name.strip())
                self._populate_profiles()
                # Switch to new profile
                idx = self._profile_combo.findText(name.strip())
                if idx >= 0:
                    self._profile_combo.setCurrentIndex(idx)
            except Exception as e:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self, "Error",
                    f"Could not create profile: {e}")
        else:
            # Revert combo to current profile
            self._populate_profiles()

    def _apply_station_settings(self):
        """
        Apply station settings from config to all subsystems.
        Called after settings dialog closes.
        """
        # Contest exchange
        exchange = self.cfg.get("station.contest_exchange", "")
        if exchange:
            self.cfg.set("modes.contest_exchange", exchange)

        # Station callsign (overrides operator callsign for club stations)
        station_cs = self.cfg.get("station.station_callsign", "")
        if station_cs:
            # Used in Winlink and log headers
            self.cfg.set("station.active_callsign", station_cs)
        else:
            self.cfg.set("station.active_callsign", self.cfg.callsign)

        # Auto-launch WSJT-X preference
        auto_launch = self.cfg.get("modes.auto_launch_wsjtx", True)
        modes_tab = self._tab_map.get("modes")
        if modes_tab and hasattr(modes_tab, "_auto_launch_wsjtx"):
            modes_tab._auto_launch_wsjtx = auto_launch

        # PTT timeout
        timeout = self.cfg.get("safety.ptt_timeout_s", 180)
        try:
            from core.safety import get_safety
            get_safety().set_ptt_timeout(timeout)
        except Exception:
            pass

        log.debug("Station settings applied")

    def _restore_location(self):
        """
        Show previously saved location on startup.
        Fires after UI is fully ready.
        """
        grid = self.cfg.get("location.grid_square", "") or                self.cfg.grid or ""
        if grid:
            self._grid_lbl.setText(grid)
            self._grid_lbl.setStyleSheet(
                "color:#3fbe6f;font-size:12px;"
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
            self._loc_lbl.setStyleSheet("color:#555;font-size:12px;")

    def _init_aprs(self):
        """
        Initialize APRS-IS client as app-level singleton.
        Auto-connects if APRS was running last session.
        """
        try:
            from aprs.aprs_client import APRSClient
            from aprs.beacon     import APRSBeacon
            self._aprs_client = APRSClient(self.cfg)
            self._aprs_beacon = APRSBeacon(
                self.cfg, self._aprs_client)
            # Auto-connect if configured
            if self.cfg.get("aprs.auto_connect", False):
                self._aprs_client.connect()
            # Update map when packets arrive
            self._aprs_client.on_packet(
                self._on_aprs_packet)
            log.info("APRS client initialized")
        except Exception as e:
            log.debug(f"APRS init: {e}")
            self._aprs_client = None
            self._aprs_beacon = None

    def _init_satellites(self):
        """Initialize satellite tracker (background thread)."""
        try:
            from network.satellites import SatTracker
            self._sat_tracker = SatTracker(self.cfg)
            self._sat_tracker.on_update(
                self._on_sat_update)
            self._sat_tracker.start()
            log.info("Satellite tracker started")
        except Exception as e:
            log.debug(f"Satellite tracker: {e}")
            self._sat_tracker = None

    def _on_sat_update(self, positions: list):
        """Push satellite positions to map."""
        try:
            map_tab = self._tab_map.get("map")
            if map_tab and hasattr(
                    map_tab, "set_satellite_positions"):
                from PyQt6.QtCore import QTimer
                sats = [{"name":   p.name,
                         "lat":    p.lat,
                         "lon":    p.lon,
                         "alt_km": p.alt_km,
                         "el_deg": p.el_deg,
                         "visible": p.is_visible}
                        for p in positions]
                QTimer.singleShot(0,
                    lambda s=sats:
                        map_tab.set_satellite_positions(s))
        except Exception:
            pass

    def _init_pskreporter(self):
        """
        Start PSKReporter submission if enabled.
        FT8 decodes from WSJT-X are forwarded here.
        """
        try:
            if not self.cfg.get(
                    "spotting.pskreporter_enabled",
                    True):
                self._pskreporter = None
                return
            from network.pskreporter import PSKReporter
            self._pskreporter = PSKReporter(self.cfg)
            self._pskreporter.start()
            log.info("PSKReporter submission started")
        except Exception as e:
            log.debug(f"PSKReporter init: {e}")
            self._pskreporter = None

    def _on_aprs_packet(self, packet):
        """Update map tab with new APRS station."""
        try:
            map_tab = self._tab_map.get("map")
            if map_tab and hasattr(map_tab, "set_aprs_stations"):
                stations = self._aprs_client.stations_on_map()
                QTimer.singleShot(0,
                    lambda s=stations:
                        map_tab.set_aprs_stations(s))
        except Exception:
            pass

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
