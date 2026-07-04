from __future__ import annotations
"""MainWindow firstrun mixin — extracted from main_window.py."""
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.config import Config

from core.constants import APP_NAME, APP_VERSION as VERSION

import re
from PyQt6.QtWidgets import (QLabel, QDialogButtonBox,
    QDialog, QFormLayout, QLineEdit, QComboBox, QPushButton,
    QVBoxLayout, QHBoxLayout, QWidget, QMessageBox)

import logging
log = logging.getLogger(__name__)
from PyQt6.QtCore import QTimer


class _MainWindowFirstrunMixin:
    """Mixed into MainWindow. Do not instantiate directly."""
    cfg: "Config"

    def _apply_rig_preset(self, name: str) -> None:
        from core.rig_presets import get_preset
        preset = get_preset(name)
        if not preset:
            return
        if preset.hamlib_model:
            self.cfg.set("rig.hamlib_model", preset.hamlib_model)
        self.cfg.set("rig.baud", preset.baud)
        self.cfg.save()
        rig_tab = self._tab_map.get("rig")
        if rig_tab and hasattr(rig_tab, "_populate_rig_models"):
            rig_tab._populate_rig_models()
        QMessageBox.information(
            self, "Radio Selected",
            f"{name} selected.\n"
            f"Baud rate: {preset.baud}\n\n"
            "Check Radio Setup in Help for required menu settings.")

    def _select_rig_model(self):
        from core.rig_presets import preset_names, get_preset
        from PyQt6.QtWidgets import QTextEdit
        dlg = QDialog(self)
        dlg.setWindowTitle("Select Radio Model")
        dlg.setMinimumWidth(420)
        lay = QVBoxLayout(dlg)

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
            "background:#111;font-family:'Courier New';border:1px solid #333;")
        lay.addWidget(info)

        def _on_select(idx):
            if idx <= 0:
                return
            preset = get_preset(combo.currentText())
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
            self._apply_rig_preset(combo.currentText())


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
        from core.legal import needs_legal_ack
        if needs_legal_ack(self.cfg):
            QTimer.singleShot(300, self._show_legal_ack)
        if not self.cfg.is_configured:
            QTimer.singleShot(600, self._first_run_dialog)

    def _show_legal_ack(self):
        """One-time legal disclaimer; quit the app if the user declines."""
        try:
            from ui.legal_ack import show_legal_ack
            if not show_legal_ack(self, self.cfg):
                self.close()
        except Exception as e:
            log.error(f"Legal acknowledgment failed: {e}")


    def _first_run_dialog(self):
        try:
            self._first_run_dialog_impl()
        except Exception as e:
            log.error(f"First run dialog failed: {e}")


    def _first_run_dialog_impl(self):
        dlg, cs_edit, loc_edit, rig_combo, mode_combo = self._build_firstrun_dialog()
        dlg.raise_()
        dlg.activateWindow()
        if not dlg.exec():
            return
        mode_key = mode_combo.currentData() or "ham"
        cs = re.sub(r'[^A-Z0-9/]', '', cs_edit.text().strip().upper())
        loc = loc_edit.text().strip()
        rig_choice = rig_combo.currentData()
        if rig_choice and rig_choice not in ("", "none"):
            self.cfg.set("rig.preset", rig_choice)
        if cs:
            self.cfg.callsign = cs
            self._cs_lbl.setText(cs)
        if loc:
            self._apply_firstrun_location(loc.strip())
        if mode_key == "rf_lab":
            self.cfg.set("ui.mode", "rf_lab")
            QTimer.singleShot(500, lambda: self._toggle_rf_lab_mode(True))
            if hasattr(self, "_rflab_action"):
                self._rflab_action.setChecked(True)
        self.cfg.save()

    def _build_firstrun_dialog(self) -> "tuple":
        """Build and return (dlg, cs_edit, loc_edit, rig_combo, mode_combo)."""
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Welcome to {APP_NAME}")
        dlg.setMinimumWidth(460)
        lay = QVBoxLayout(dlg)
        intro = QLabel(
            f"<b>Welcome to {APP_NAME} v{VERSION}</b><br><br>"
            "Choose your usage mode, then enter your location to get started.<br>"
            "You can switch modes at any time via <b>View → Monitor / Education Mode</b>.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        form = QFormLayout()

        mode_combo = QComboBox()
        mode_combo.addItem("🎙  Ham Radio Operator  (full rig + log + digital modes)", "ham")
        mode_combo.addItem("🔬  Monitor / Education  (SDR-only, no callsign required)", "rf_lab")
        form.addRow("Usage mode:", mode_combo)

        cs_edit = QLineEdit()
        cs_edit.setPlaceholderText("e.g. W4XYZ  (leave blank for Monitor mode)")
        cs_edit.setMaxLength(12)
        loc_edit = QLineEdit()
        loc_edit.setPlaceholderText("Maidenhead grid (DM79rr), ZIP, city, or MGRS")
        loc_edit.setMaxLength(30)
        self._auto_fill_location(loc_edit)
        rig_combo = QComboBox()
        rig_combo.addItem("I'll set this up later", "")
        rig_combo.addItem("No radio yet — just exploring", "none")
        try:
            from core.rig_presets import PRESETS
            for label in sorted(PRESETS.keys()):
                rig_combo.addItem(label, label)
        except Exception:
            for label in ("ICOM IC-7300", "ICOM IC-7100",
                          "YAESU FT-991A", "KENWOOD TS-590S",
                          "Other / configure later"):
                rig_combo.addItem(label, label)

        form.addRow("Callsign:", cs_edit)
        form.addRow("Location:", loc_edit)
        form.addRow("Radio:", rig_combo)
        lay.addLayout(form)

        def _on_mode_change(idx):
            is_rf_lab = mode_combo.currentData() == "rf_lab"
            cs_edit.setEnabled(not is_rf_lab)
            rig_combo.setEnabled(not is_rf_lab)
            cs_edit.setPlaceholderText(
                "Not needed in Monitor mode" if is_rf_lab
                else "e.g. W4XYZ  (leave blank for Monitor mode)")
        mode_combo.currentIndexChanged.connect(_on_mode_change)

        hint = QLabel(
            "Find your grid: "
            "<a href='https://www.levinecentral.com/ham/grid_square.php'"
            " style='color:#3fbe6f'>levinecentral.com</a>")
        hint.setOpenExternalLinks(True)
        hint.setStyleSheet("")
        lay.addWidget(hint)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btns.accepted.connect(dlg.accept)
        lay.addWidget(btns)
        return dlg, cs_edit, loc_edit, rig_combo, mode_combo

    def _apply_firstrun_location(self, loc_clean: str) -> None:
        """Apply first-run location: direct grid or async geocoder search."""
        import threading
        from core.location import _valid_grid
        if _valid_grid(loc_clean.upper()):
            self.cfg.grid = loc_clean.upper()
            self.location.set_from_grid(loc_clean.upper())
            self._grid_lbl.setText(loc_clean.upper())
            return
        self._grid_lbl.setText(self.tr("Searching…"))

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
                            self.cfg.set("location.lat", r.lat)
                            self.cfg.set("location.lon", r.lon)
                        self.cfg.save()
                        self._grid_lbl.setText(grid or q)
                        self._grid_lbl.setStyleSheet(
                            "color:#3fbe6f;font-family:'Courier New';")
                        city  = getattr(r, "city",  "")
                        state = getattr(r, "state", "")
                        disp  = ", ".join(filter(None, [city, state]))
                        if disp and hasattr(self, "_loc_lbl"):
                            self._loc_lbl.setText(disp)
                    QTimer.singleShot(0, _apply)
                else:
                    QTimer.singleShot(
                        0, lambda: self._grid_lbl.setText(
                            "Not found — try grid square"))
            except Exception as e:
                log.warning(f"First run location: {e}")
                QTimer.singleShot(
                    0, lambda: self._grid_lbl.setText("Search failed"))

        threading.Thread(target=_search, daemon=True).start()

