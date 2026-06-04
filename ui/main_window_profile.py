"""MainWindow profile mixin — extracted from main_window.py."""
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.config import Config

import logging
log = logging.getLogger(__name__)


class _MainWindowProfileMixin:
    """Mixed into MainWindow. Do not instantiate directly."""
    cfg: "Config"

    def _populate_profiles(self):
        """Load operator profiles into the combo box."""
        try:
            from core.profiles import get_profile_manager
            pm = get_profile_manager()
            profiles = pm.list_profiles()
            current  = pm.current_name()

            self._profile_combo.blockSignals(True)
            self._profile_combo.clear()
            for p in profiles:
                self._profile_combo.addItem(p)
            # Always have "Add profile..."
            self._profile_combo.addItem("+ New profile…")
            self._profile_combo.addItem("✎ Manage profiles…")
            # Select current
            idx = self._profile_combo.findText(current)
            if idx >= 0:
                self._profile_combo.setCurrentIndex(idx)
            self._profile_combo.blockSignals(False)
        except Exception as e:
            log.debug(f"Profile populate: {e}")
            self._profile_combo.clear()
            self._profile_combo.addItem("Default")


    def _on_profile_change(self, idx: int):
        """Switch to selected operator profile."""
        name = self._profile_combo.currentText()
        if name == "+ New profile…":
            self._new_profile_dialog()
            return
        if name == "✎ Manage profiles…":
            self._manage_profiles_dialog()
            return
        try:
            from core.profiles import get_profile_manager
            pm = get_profile_manager()
            if pm.switch_to(name):
                # Refresh UI from new profile
                cs = self.cfg.callsign
                if cs:
                    self._cs_lbl.setText(cs)
                grid = self.cfg.grid
                if grid:
                    self._grid_lbl.setText(grid)
                log.info(f"Switched to profile: {name} "
                         f"(TX callsign now {cs})")
        except Exception as e:
            log.warning(f"Profile switch: {e}")


    def _manage_profiles_dialog(self):
        """Rename or delete operator profiles (edit path the user wanted)."""
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QListWidget,
                                     QHBoxLayout, QPushButton, QInputDialog,
                                     QMessageBox, QLabel)
        from core.profiles import get_profile_manager
        pm = get_profile_manager()
        dlg = QDialog(self)
        dlg.setWindowTitle("Manage Operator Profiles")
        dlg.setMinimumWidth(380)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(
            "Each profile has its own callsign, grid, and credentials. "
            "The selected profile's callsign is used on transmit."))
        lst = QListWidget()
        lst.addItems(pm.list_profiles())
        lay.addWidget(lst)
        row = QHBoxLayout()
        rename_b = QPushButton("Rename")
        delete_b = QPushButton("Delete")
        close_b  = QPushButton("Close")
        row.addWidget(rename_b); row.addWidget(delete_b)
        row.addStretch(); row.addWidget(close_b)
        lay.addLayout(row)

        def _rename():
            it = lst.currentItem()
            if not it:
                return
            new, ok = QInputDialog.getText(
                dlg, "Rename Profile", "New name:", text=it.text())
            if ok and new.strip():
                try:
                    pm.rename(it.text(), new.strip())
                    it.setText(new.strip())
                    self._populate_profiles()
                except Exception as e:
                    QMessageBox.warning(dlg, "Rename failed", str(e))

        def _delete():
            it = lst.currentItem()
            if not it:
                return
            if pm.count() <= 1:
                QMessageBox.information(
                    dlg, "Cannot delete",
                    "At least one profile must remain.")
                return
            if QMessageBox.question(
                    dlg, "Delete Profile",
                    f"Delete profile '{it.text()}'? This cannot be undone."
                    ) == QMessageBox.StandardButton.Yes:
                try:
                    pm.delete(it.text())
                    lst.takeItem(lst.row(it))
                    self._populate_profiles()
                except Exception as e:
                    QMessageBox.warning(dlg, "Delete failed", str(e))

        rename_b.clicked.connect(_rename)
        delete_b.clicked.connect(_delete)
        close_b.clicked.connect(dlg.accept)
        dlg.exec()


    def _new_profile_dialog(self):
        """Create a new operator profile."""
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, "New Profile",
            "Profile name (e.g. your callsign):")
        if ok and name.strip():
            try:
                from core.profiles import get_profile_manager
                pm = get_profile_manager()
                pm.create_named(name.strip())
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

