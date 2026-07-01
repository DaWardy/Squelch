from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/main_window_customtabs.py

Custom-tab management for MainWindow, extracted from main_window.py
(HOUSE-CS complexity split): add / remove / rename user-built custom tabs,
assign / unassign panel navigation cards, the per-tab "add panel" menu, and
save / restore of custom-tab state across sessions.

`_MainWindowCustomTabsMixin` is mixed into `MainWindow`. It relies on
host-class state:
  * self._custom_tabs  — dict tab_id → CustomLayoutTab (created in _build_ui)
  * self.tabs          — the main QTabWidget
  * self._tab_map      — key → panel widget (for navigation)
  * self.cfg           — Config (ui.custom_tabs persistence)

TABS is a module constant of ui.main_window — imported lazily inside the
methods that need it to avoid an import cycle.
"""


class _MainWindowCustomTabsMixin:
    """Add/remove/rename custom tabs, assign panels, persist state."""

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
        """Add an à-la-carte widget (or whole-tab shortcut) to the custom tab."""
        from ui.main_window import TABS
        from ui.tabs.custom_summaries import widget_title
        ct = self._custom_tabs.get(tab_id)
        if ct is None:
            return
        # Prefer the catalog's 'Category: Label' title for widget keys; fall
        # back to the tab label for whole-tab shortcut keys.
        title = widget_title(panel_key)
        if title is None:
            label = next((lbl for k, lbl, _ in TABS if k == panel_key), panel_key)
            title = label.split("  ", 1)[-1] if "  " in label else label
        ct.assign_panel(panel_key, title)
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
        from ui.main_window import TABS
        from ui.tabs.custom_summaries import catalog_by_category
        menu = QMenu(self)

        def _add(target_menu, key, label, assigned):
            if key in assigned:
                return
            a = target_menu.addAction(label)
            a.triggered.connect(
                lambda _, k=key: self._assign_panel_to_custom_tab(
                    ct.panel_id, k))

        def _rebuild():
            menu.clear()
            assigned = set(ct.assigned_keys)
            # À-la-carte widgets, grouped by the tab they come from.
            for category, widgets in catalog_by_category().items():
                sub = menu.addMenu(category)
                for key, label in widgets:
                    _add(sub, key, label, assigned)
            menu.addSeparator()
            # Whole-tab shortcuts (jump to a tab) as before.
            open_sub = menu.addMenu(self.tr("Open a tab →"))
            for key, label, _ in TABS:
                clean = label.split("  ", 1)[-1] if "  " in label else label
                _add(open_sub, key, clean, assigned)

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
        from ui.main_window import TABS
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
            # Restore assigned widgets/shortcuts (assign_panel creates the cards)
            from ui.tabs.custom_summaries import widget_title
            for key in entry.get("assigned", []):
                panel_title = widget_title(key)
                if panel_title is None:
                    label = next((lbl for k, lbl, _ in TABS if k == key), key)
                    panel_title = (label.split("  ", 1)[-1]
                                   if "  " in label else label)
                ct.assign_panel(key, panel_title)
            # Re-apply the windows-locked state after the widgets are back.
            if entry.get("locked"):
                ct.apply_locked(True)
