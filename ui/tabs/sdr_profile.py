from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/tabs/sdr_profile.py

Demodulator-profile quick-select for the SDR tab, extracted from sdr_tab.py
(HOUSE-CS complexity split): a named preset that sets mode / bandwidth / NR /
squelch in one click, plus save/delete of custom profiles.

`_SDRProfileMixin` is mixed into `SDRTab`. It relies on host-class state:
  * self.cfg                — Config (sdr.profiles persistence)
  * self._BUILTIN_PROFILES  — class-level dict of built-in presets
  * self._profile_combo     — created here in _build_profile_group
  * self._demod_combo / self._demod_bw / self._nr_cb / self._nr_slider /
    self._squelch_cb / self._squelch_slider  — demod controls built elsewhere
  * self._nr_enabled / self._nr_level / self._squelch_enabled / self._squelch_db
"""

from PyQt6.QtWidgets import QGroupBox, QGridLayout, QComboBox, QPushButton


class _SDRProfileMixin:
    """Demodulator profile quick-select (load/save/delete named presets)."""

    def _build_profile_group(self) -> QGroupBox:
        """Demodulator profile quick-select."""
        grp = QGroupBox(self.tr("Profile"))
        gl  = QGridLayout(grp)
        gl.setSpacing(3)
        self._profile_combo = QComboBox()
        self._profile_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self._profile_combo.setMinimumWidth(110)
        self._profile_combo.setToolTip(
            "Quick-load a demodulator preset.\n"
            "Sets mode, bandwidth, NR, and squelch in one click.")
        self._refresh_profile_combo()
        gl.addWidget(self._profile_combo, 0, 0, 1, 2)
        load_btn = QPushButton(self.tr("Load"))
        load_btn.setFixedHeight(22)
        load_btn.setFixedWidth(48)
        load_btn.clicked.connect(self._apply_profile)
        gl.addWidget(load_btn, 1, 0)
        save_btn = QPushButton(self.tr("Save…"))
        save_btn.setFixedHeight(22)
        save_btn.setFixedWidth(48)
        save_btn.setToolTip("Save current demod settings as a named profile")
        save_btn.clicked.connect(self._save_profile)
        gl.addWidget(save_btn, 1, 1)
        del_btn  = QPushButton(self.tr("Del"))
        del_btn.setFixedHeight(22)
        del_btn.setFixedWidth(36)
        del_btn.setToolTip("Delete the selected custom profile")
        del_btn.clicked.connect(self._delete_profile)
        gl.addWidget(del_btn, 1, 2)
        return grp

    def _refresh_profile_combo(self) -> None:
        self._profile_combo.clear()
        for name in self._BUILTIN_PROFILES:
            self._profile_combo.addItem(name)
        custom = self.cfg.get("sdr.profiles", {}) if self.cfg else {}
        for name in sorted(custom.keys()):
            self._profile_combo.addItem(f"★ {name}")

    def _apply_profile(self) -> None:
        name = self._profile_combo.currentText()
        # Strip ★ prefix from custom profile names
        key = name.lstrip("★ ")
        prof = self._BUILTIN_PROFILES.get(key)
        if prof is None and self.cfg:
            prof = (self.cfg.get("sdr.profiles", {}) or {}).get(key)
        if not prof:
            return
        self._demod_combo.setCurrentText(prof.get("mode", "USB"))
        self._demod_bw.setCurrentText(prof.get("bw", "2.5 kHz"))
        self._nr_cb.setChecked(bool(prof.get("nr", False)))
        self._nr_slider.setValue(int(prof.get("nr_lvl", 0)))
        self._squelch_cb.setChecked(bool(prof.get("sq", False)))
        self._squelch_slider.setValue(int(prof.get("sq_db", -60)))

    def _save_profile(self) -> None:
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, self.tr("Save Profile"),
            self.tr("Profile name:"),
            text="My Profile")
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in self._BUILTIN_PROFILES:
            return   # can't overwrite built-ins
        prof = {
            "mode":   self._demod_combo.currentText(),
            "bw":     self._demod_bw.currentText(),
            "nr":     self._nr_enabled,
            "nr_lvl": self._nr_level,
            "sq":     self._squelch_enabled,
            "sq_db":  self._squelch_db,
        }
        if self.cfg:
            customs = dict(self.cfg.get("sdr.profiles", {}) or {})
            customs[name] = prof
            self.cfg.set("sdr.profiles", customs)
        self._refresh_profile_combo()

    def _delete_profile(self) -> None:
        name = self._profile_combo.currentText().lstrip("★ ")
        if name in self._BUILTIN_PROFILES or not self.cfg:
            return
        customs = dict(self.cfg.get("sdr.profiles", {}) or {})
        customs.pop(name, None)
        self.cfg.set("sdr.profiles", customs)
        self._refresh_profile_combo()
