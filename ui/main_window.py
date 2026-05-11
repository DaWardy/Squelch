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
Squelch -- ui/main_window.py
Main application window.
9 tabs, inline callsign/grid editing, theme system,
tab show/hide, UTC+local clock, safety alerts,
window size/position persistence, plugin tabs.
"""

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QFrame, QDialog, QFormLayout, QLineEdit,
    QDialogButtonBox, QMenu, QSizePolicy,
    QCheckBox, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, QSettings, pyqtSlot
from PyQt6.QtGui import QAction, QActionGroup, QFont, QCursor

import re
from core.rig import RigController, RigStatus
from core.config import Config
from core.location import LocationManager
from core.themes import THEMES, get_stylesheet
from core.plugins import get_plugin_manager
from ui.tabs.rig_tab import RigTab
from ui.tabs.modes_tab import ModesTab
from ui.tabs.log_tab import LogTab
from ui.tabs.band_conditions_tab import BandConditionsTab
from ui.dialogs.paths_dialog import PathsDialog
from ui.tabs.stub_tab import StubTab

log = logging.getLogger(__name__)
VERSION = "1.4.0"
APP_NAME = "Squelch"
APP_FULL = "Amateur Radio Operations Platform"

# Tab definitions — key, label, default visible
TABS = [
    ("rig",       "📻  Rig",            True),
    ("modes",     "📡  Modes",          True),
    ("log",       "📒  Log",            True),
    ("bandcond",  "☀️  Band Cond.",     True),
    ("sdr",       "〰️  SDR",            True),
    ("digital",   "🔊  Digital",        True),
    ("localrf",   "📋  Local RF",       True),
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
        if not self._edit:
            self._editing = False
            return
        raw = self._edit.text().strip()
        self._edit.hide()
        self._edit.deleteLater()
        self._edit    = None
        self._editing = False

        # Sanitize and validate
        val = raw.upper()
        if not val or val.lower() in self._PLACEHOLDERS:
            return
        # Remove non-alphanumeric except / for portable calls
        import re
        val = re.sub(r'[^A-Z0-9/]', '', val)
        if not val:
            return

        self.setText(val)
        try:
            self._on_commit(val)
        except Exception as e:
            log.warning(f"ClickableLabel commit: {e}")


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

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        vbox.addWidget(self._build_topbar())

        self.tabs = QTabWidget()
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
        ldb = self._get_log_db()
        if key == "rig":
            return RigTab(self.rig, self.cfg)
        elif key == "modes":
            return ModesTab(self.rig, self.cfg, ldb)
        elif key == "log":
            return LogTab(self.cfg)
        else:
            return StubTab(label, key)

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
        lay.addWidget(self._cs_lbl)
        lay.addWidget(_vsep())

        # Inline-editable grid
        self._grid_lbl = ClickableLabel(
            self.cfg.grid or "No grid set",
            "grid / ZIP / city / MGRS",
            self._on_grid_edit,
            max_length=20)
        self._grid_lbl.setStyleSheet(
            "color:#777;font-size:12px;"
            "font-family:'Courier New';")
        lay.addWidget(self._grid_lbl)
        lay.addWidget(_vsep())

        self._loc_lbl = QLabel("—")
        self._loc_lbl.setStyleSheet(
            "color:#4a4a4a;font-size:11px;")
        lay.addWidget(self._loc_lbl)
        lay.addStretch()

        # Clock display
        self._utc_lbl = QLabel("00:00:00 UTC")
        self._utc_lbl.setStyleSheet(
            "color:#3fbe6f;font-family:'Courier New';"
            "font-size:13px;cursor:pointer;")
        self._utc_lbl.setToolTip(
            "Click to toggle UTC / Local time")
        self._utc_lbl.mousePressEvent = self._toggle_clock
        self._show_utc = True
        lay.addWidget(self._utc_lbl)
        lay.addWidget(_vsep())

        self._rig_pill = QLabel("● RIG")
        self._rig_pill.setStyleSheet(
            "color:#444;font-size:11px;"
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
        else:
            try:
                local_tz = ZoneInfo("localtime")
                now_local = now_utc.astimezone(local_tz)
                self._utc_lbl.setText(
                    now_local.strftime("%H:%M:%S LCL"))
            except Exception:
                self._utc_lbl.setText(
                    now_utc.strftime("%H:%M:%S UTC"))

    def _toggle_clock(self, _event):
        self._show_utc = not self._show_utc

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
            f"color:{col};font-size:11px;"
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
        if loc.grid:
            self._grid_lbl.setText(loc.grid)

    # ── Callsign / Grid edits ─────────────────────────────────────────────

    def _on_callsign_edit(self, val: str):
        self.cfg.callsign = val
        self.cfg.save()
        log.info(f"Callsign: {val}")

    def _on_grid_edit(self, val: str):
        """Handle grid/ZIP/city/MGRS entry from top bar."""
        from core.location import _valid_grid
        if _valid_grid(val):
            self.cfg.grid = val
            self.location.set_from_grid(val)
            self.cfg.save()
        else:
            # Treat as search query (ZIP/city/MGRS)
            import threading
            def _search():
                loc = self.location.search(val)
                if loc:
                    QTimer.singleShot(0, lambda l=loc: (
                        self.location.apply(l),
                        self._grid_lbl.setText(l.grid)))
            threading.Thread(target=_search,
                             daemon=True).start()

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
            "background:#111;color:#aaa;font-size:10px;"
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

    def _check_first_run(self):
        if not self.cfg.is_configured:
            QTimer.singleShot(600, self._first_run_dialog)

    def _first_run_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Welcome to {APP_NAME}")
        dlg.setMinimumWidth(440)
        lay = QVBoxLayout(dlg)

        intro = QLabel(
            f"<b style='font-size:14px'>"
            f"Welcome to {APP_NAME}!</b><br><br>"
            "Enter your callsign and location to get started.<br>"
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
            "Grid (FM18lv), ZIP (22030), city, or MGRS")
        loc_edit.setMaxLength(30)

        form.addRow("Callsign:", cs_edit)
        form.addRow("Location:", loc_edit)
        lay.addLayout(form)

        hint = QLabel(
            "Find your grid: "
            "<a href='https://www.levinecentral.com/"
            "ham/grid_square.php' style='color:#3fbe6f'>"
            "levinecentral.com</a>")
        hint.setOpenExternalLinks(True)
        hint.setStyleSheet("color:#666;font-size:10px;")
        lay.addWidget(hint)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok)
        btns.accepted.connect(dlg.accept)
        lay.addWidget(btns)

        if dlg.exec():
            cs = re.sub(r'[^A-Z0-9/]', '',
                        cs_edit.text().strip().upper())
            loc = loc_edit.text().strip()

            if cs:
                self.cfg.callsign = cs
                self._cs_lbl.setText(cs)

            if loc:
                from core.location import _valid_grid
                if _valid_grid(loc.upper()):
                    self.cfg.grid = loc.upper()
                    self.location.set_from_grid(loc.upper())
                    self._grid_lbl.setText(loc.upper())
                else:
                    import threading
                    def _search():
                        result = self.location.search(loc)
                        if result:
                            QTimer.singleShot(0,
                                lambda r=result: (
                                    self.location.apply(r),
                                    self._grid_lbl.setText(r.grid)))
                    threading.Thread(
                        target=_search, daemon=True).start()

            self.cfg.save()

    # ── Settings ──────────────────────────────────────────────────────────

    def _open_settings(self):
        """Full settings dialog — Chunk 10."""
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
            self, f"About {APP_NAME} v{VERSION}",
            f"<b>{APP_NAME} v{VERSION}</b><br>"
            f"{APP_FULL}<br><br>"
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
