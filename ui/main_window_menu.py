from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/main_window_menu.py

Menu-bar construction for MainWindow, extracted from main_window.py
(HOUSE-CS complexity split): File / Rig / View / Help menus, the tab-preset
+ saved-layout submenus, and the theme / font / show-hide-tabs submenus.

`_MainWindowMenuMixin` is mixed into `MainWindow`. Every menu action connects
to a handler that lives on MainWindow or one of its other mixins (resolved via
`self`); this mixin only *builds* the menus. It also stores the action handles
other code toggles (`_spectrum_action`, `_rflab_action`, `_lock_action`,
`_demo_action`, `_saved_layouts_menu`, `_tab_actions`) as instance attributes.

TABS / TAB_PRESETS are module constants of ui.main_window — imported lazily
inside the methods that need them to avoid an import cycle.
"""

from PyQt6.QtGui import QAction, QActionGroup

from core.themes import THEMES


class _MainWindowMenuMixin:
    """Builds the menu bar and its submenus for MainWindow."""

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
        ex = QAction(self.tr("Export Settings…"), self)
        ex.setToolTip(self.tr("Save all settings to a file for backup / transfer"))
        ex.triggered.connect(self._export_settings)
        fm.addAction(ex)
        im = QAction(self.tr("Import Settings…"), self)
        im.setToolTip(self.tr("Load settings from a previously exported file"))
        im.triggered.connect(self._import_settings)
        fm.addAction(im)
        fm.addSeparator()
        qa = QAction(self.tr("Quit"), self)
        qa.setShortcut("Ctrl+Q")
        qa.triggered.connect(self.close)
        fm.addAction(qa)

    def _export_settings(self):
        """File → Export Settings: write all settings to a JSON backup file."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        self.cfg.save_if_dirty()          # flush pending changes before export
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Export Settings"),
            "squelch_settings.json", self.tr("JSON (*.json)"))
        if not path:
            return
        if self.cfg.export_to(path):
            QMessageBox.information(
                self, self.tr("Settings Exported"),
                self.tr(f"All settings saved to:\n{path}\n\n"
                        "Copy this file to another device and use "
                        "File → Import Settings."))
        else:
            QMessageBox.warning(self, self.tr("Export Failed"),
                                self.tr("Could not write the settings file."))

    def _import_settings(self):
        """File → Import Settings: load settings from a backup file."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Import Settings"), "", self.tr("JSON (*.json)"))
        if not path:
            return
        if self.cfg.import_from(path):
            QMessageBox.information(
                self, self.tr("Settings Imported"),
                self.tr("Settings imported. Restart Squelch for all of them "
                        "to take effect."))
        else:
            QMessageBox.warning(self, self.tr("Import Failed"),
                                self.tr("Could not read that settings file."))

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
        # Monitor Mode — SDR-only education mode; hides ham-specific tabs (C-16/C-21)
        rflab_a = QAction(self.tr("🔬  Monitor / Education Mode"), self)
        rflab_a.setCheckable(True)
        rflab_a.setChecked(self.cfg.get("ui.mode", "ham") == "rf_lab")
        rflab_a.setShortcut("Ctrl+Shift+R")
        rflab_a.setToolTip(
            "Switches to SDR-only education layout  (Ctrl+Shift+R)\n"
            "Hides Rig, Weak Signal, Log, Digital Voice, Winlink, Repeaters tabs.\n"
            "Shows SDR, Monitor, Propagation, Map, Help.\n"
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
        from ui.main_window import TAB_PRESETS
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
        from ui.main_window import TAB_PRESETS
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
        from ui.main_window import TABS
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
