from __future__ import annotations
"""MainWindow guest_demo mixin — extracted from main_window.py."""
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.config import Config

from PyQt6.QtWidgets import QMessageBox


class _MainWindowGuestDemoMixin:
    """Mixed into MainWindow. Do not instantiate directly."""
    cfg: "Config"

    def _apply_saved_guest_mode(self):
        """On startup, restore Demo mode (TX-block) and any active guest
        operator from config, and reflect both in the UI."""
        # Demo mode (TX disabled — for lectures, C-06 Elena)
        demo = self.cfg.get("demo.mode", False)
        try:
            from core.safety import get_safety
            get_safety().set_demo_mode(demo)
        except Exception:
            pass
        self._update_demo_banner(demo)
        # Guest operator (student/visitor at the controls — TX stays on)
        self._update_guest_banner()


    def _toggle_demo_mode(self):
        """Demo Mode: disable ALL transmit for a lecture/demo (C-06, Elena).
        Distinct from Guest Operator mode, which keeps TX enabled."""
        new_state = not self.cfg.get("demo.mode", False)
        self.cfg.set("demo.mode", new_state)
        self.cfg.save()
        try:
            from core.safety import get_safety
            get_safety().set_demo_mode(new_state)
        except Exception:
            pass
        if hasattr(self, "_demo_action"):
            self._demo_action.setChecked(new_state)
        self._update_demo_banner(new_state)
        QMessageBox.information(
            self, "Demo Mode",
            ("Demo Mode ON — transmit is disabled. Use this for "
             "lectures or demos with no risk of keying the rig."
             if new_state else "Demo Mode OFF — transmit re-enabled."))


    def _update_demo_banner(self, enabled: bool):
        """Persistent banner while Demo Mode blocks TX."""
        bar = getattr(self, "_demo_banner", None)
        if bar is None:
            from PyQt6.QtWidgets import QLabel
            from PyQt6.QtCore import Qt
            bar = QLabel("  DEMO MODE — transmit is disabled  ")
            bar.setStyleSheet(
                "background:#5a3a00;color:#ffcc66;font-weight:bold;"
                "padding:4px;border-bottom:1px solid #8a5a00;")
            bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._demo_banner = bar
            try:
                self._central_layout.insertWidget(0, bar)
            except Exception:
                pass
        bar.setVisible(enabled)


    def _build_guest_dialog_form(self, lay) -> "tuple":
        """Add intro + form + script view to *lay*; return (guest_edit, supervised, script_view)."""
        from PyQt6.QtWidgets import (QFormLayout, QLineEdit, QCheckBox,
                                     QLabel, QTextEdit)
        intro = QLabel(
            "A guest or student operator is getting on the air at this "
            "station. Transmit stays enabled — this is for real, supervised "
            "operating. Enter the guest's callsign so contacts and logs "
            "identify correctly, then use the contact script below.")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        form = QFormLayout()
        guest_edit = QLineEdit(self.cfg.get("guest.callsign", ""))
        guest_edit.setPlaceholderText("Guest / student callsign, e.g. KE2XYZ")
        guest_edit.setMaxLength(12)
        form.addRow("Guest callsign:", guest_edit)
        form.addRow("Station callsign:",
                    QLabel(self.cfg.callsign or "(station callsign not set)"))
        supervised = QCheckBox("Operating under a control operator (supervised)")
        supervised.setChecked(self.cfg.get("guest.supervised", True))
        form.addRow("", supervised)
        lay.addLayout(form)

        script_view = QTextEdit()
        script_view.setReadOnly(True)
        script_view.setMinimumHeight(220)
        lay.addWidget(QLabel("Contact script (read aloud for voice contacts):"))
        lay.addWidget(script_view)
        return guest_edit, supervised, script_view

    def _open_guest_operator(self):
        """Guest Operator: a student or visitor operates the station. TX stays
        enabled. Captures the guest's callsign for correct identification and
        offers a readable contact script. Used by students learning to operate."""
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QPushButton,
                                     QHBoxLayout)
        dlg = QDialog(self)
        dlg.setWindowTitle("Guest Operator")
        dlg.setMinimumWidth(520)
        lay = QVBoxLayout(dlg)

        guest_edit, supervised, script_view = \
            self._build_guest_dialog_form(lay)

        def _refresh_script():
            from core.guest_op import voice_contact_script
            script_view.setPlainText(voice_contact_script(
                guest_edit.text().strip().upper(),
                self.cfg.callsign or "",
                self.cfg.grid or "",
                supervised.isChecked()))
        guest_edit.textChanged.connect(lambda _: _refresh_script())
        supervised.toggled.connect(lambda _: _refresh_script())
        _refresh_script()

        clear_btn = QPushButton("End Guest Session")
        save_btn  = QPushButton("Start / Update")
        row = QHBoxLayout()
        row.addWidget(clear_btn)
        row.addStretch()
        row.addWidget(save_btn)
        lay.addLayout(row)

        def _save():
            gc = guest_edit.text().strip().upper()
            self.cfg.set("guest.callsign", gc)
            self.cfg.set("guest.active", bool(gc))
            self.cfg.set("guest.supervised", supervised.isChecked())
            self.cfg.save()
            self._update_guest_banner()
            dlg.accept()

        def _clear():
            self.cfg.set("guest.callsign", "")
            self.cfg.set("guest.active", False)
            self.cfg.save()
            self._update_guest_banner()
            dlg.accept()

        save_btn.clicked.connect(_save)
        clear_btn.clicked.connect(_clear)
        dlg.exec()


    def _update_guest_banner(self):
        """Show who the guest operator is (TX stays enabled)."""
        active = self.cfg.get("guest.active", False)
        gc     = self.cfg.get("guest.callsign", "")
        bar = getattr(self, "_guest_banner", None)
        if bar is None:
            from PyQt6.QtWidgets import QLabel
            from PyQt6.QtCore import Qt
            bar = QLabel()
            bar.setStyleSheet(
                "background:#0d2a3a;color:#66ccff;font-weight:bold;"
                "padding:4px;border-bottom:1px solid #1f5a7a;")
            bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._guest_banner = bar
            try:
                self._central_layout.insertWidget(0, bar)
            except Exception:
                pass
        station = self.cfg.callsign or "station"
        bar.setText(f"  GUEST OPERATOR: {gc} operating {station}  ")
        bar.setVisible(bool(active and gc))

