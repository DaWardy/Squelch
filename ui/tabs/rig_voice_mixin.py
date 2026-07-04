from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/tabs/rig_voice_mixin.py

Voice keyer (V1-V8 SSB/phone clip player) for the Rig tab, extracted from
rig_tab.py (HOUSE-CS complexity split).

`_RigVoiceMixin` is mixed into `RigTab`. It relies on host-class state:
  * self._rig_root  — the rig tab's root QVBoxLayout
  * self.cfg        — Config (VoiceKeyer reads clip paths/labels from it)
`self._voice_keyer` is created in `_build_voice_section` (no __init__ dep).
"""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)


class _RigVoiceMixin:
    """Voice keyer collapsible section (record/load/play 8 phone clips)."""

    def _build_voice_section(self, inner) -> None:
        # ── Voice Keyer (collapsible) ────────────────────────────────────
        from core.voice_keyer import VoiceKeyer
        from ui.tabs.rig_tab import _collapse_btn
        self._voice_keyer = VoiceKeyer(self.cfg)

        self._voice_toggle = _collapse_btn("Voice Keyer")
        self._voice_toggle.toggled.connect(
            lambda c: self._voice_body.setVisible(c))
        self._rig_root.addWidget(self._voice_toggle)

        self._voice_body = QWidget()
        self._voice_body.setVisible(False)
        vl = QVBoxLayout(self._voice_body)
        vl.setContentsMargins(8, 4, 8, 4)
        vl.setSpacing(4)

        # V1-V8 clip buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(3)
        self._voice_btns: list[QPushButton] = []
        for i, (key, clip) in enumerate(self._voice_keyer.all_clips(), start=1):
            btn = QPushButton(f"V{i}: {clip['label']}")
            btn.setFixedHeight(22)
            path = clip.get("path", "")
            tip = path if path else "(no clip — right-click to set)"
            btn.setToolTip(f"{tip}\n\nLeft-click = play · Right-click = options")
            btn.setStyleSheet(
                "background:#1a1a1a;border:1px solid #333;border-radius:2px;"
                "font-size:10px;padding:0 3px;")
            btn.clicked.connect(lambda _, k=key: self._voice_play(k))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda _, k=key, b=btn: self._voice_btn_menu(k, b))
            self._voice_btns.append(btn)
            btn_row.addWidget(btn)
        vl.addLayout(btn_row)

        # Stop + status row
        ctrl_row = QHBoxLayout()
        stop_btn = QPushButton("■ Stop")
        stop_btn.setFixedHeight(22)
        stop_btn.setFixedWidth(70)
        stop_btn.setToolTip("Stop current voice playback or recording")
        stop_btn.clicked.connect(self._voice_stop)
        ctrl_row.addWidget(stop_btn)
        self._voice_status = QLabel("Ready")
        self._voice_status.setStyleSheet("color:#555;font-size:9px;")
        ctrl_row.addWidget(self._voice_status, 1)
        vl.addLayout(ctrl_row)

        self._rig_root.addWidget(self._voice_body)

    def _voice_play(self, key: str) -> None:
        clip = self._voice_keyer.get_clip(key)
        path = clip.get("path", "")
        if not path or not os.path.isfile(path):
            self._voice_status.setText(f"No clip for {key.upper()} — right-click to set")
            return
        # License-class TX gate — playing a voice clip transmits (VOX/PTT).
        from ui.tx_confirm import confirm_tx
        if not confirm_tx(self, self.cfg, self.rig.state.freq_hz):
            return
        ok = self._voice_keyer.play(key)
        if ok:
            self._voice_status.setText(f"▶ Playing {key.upper()}: {clip['label']}")
        else:
            self._voice_status.setText("sounddevice not available — cannot play")

    def _voice_stop(self) -> None:
        self._voice_keyer.stop()
        self._voice_status.setText("Stopped")

    def _voice_btn_menu(self, key: str, btn: "QPushButton") -> None:
        from PyQt6.QtWidgets import QMenu, QDialog, QVBoxLayout as _VL
        from PyQt6.QtWidgets import QFormLayout, QDialogButtonBox, QLineEdit
        from PyQt6.QtWidgets import QFileDialog
        menu = QMenu(self)
        idx = int(key[1])
        act_record = menu.addAction(f"🎙 Record V{idx} ({self._voice_keyer._SAMPLE_RATE//1000}k, 8 s)…")
        act_load   = menu.addAction(f"📂 Load WAV for V{idx}…")
        act_label  = menu.addAction(f"✏ Edit label for V{idx}…")
        act_clear  = menu.addAction(f"✖ Clear V{idx}")
        chosen = menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
        if chosen == act_record:
            self._voice_record(key, btn)
        elif chosen == act_load:
            self._voice_load(key, btn)
        elif chosen == act_label:
            self._voice_edit_label(key, btn)
        elif chosen == act_clear:
            self._voice_keyer.set_clip(key, self._voice_keyer.get_clip(key)["label"], "")
            btn.setToolTip("(no clip — right-click to set)")
            self._voice_status.setText(f"{key.upper()} cleared")

    def _voice_record(self, key: str, btn: "QPushButton") -> None:
        self._voice_status.setText(f"🔴 Recording {key.upper()} for 8 s…")
        def _done(path: str) -> None:
            clip = self._voice_keyer.get_clip(key)
            self._voice_keyer.set_clip(key, clip["label"], path)
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: (
                btn.setToolTip(path),
                self._voice_status.setText(f"Saved {key.upper()} → {os.path.basename(path)}")
            ))
        ok = self._voice_keyer.record(key, duration=8.0, on_done=_done)
        if not ok:
            self._voice_status.setText("sounddevice not available — cannot record")

    def _voice_load(self, key: str, btn: "QPushButton") -> None:
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, f"Load WAV clip for {key.upper()}", "",
            "WAV files (*.wav);;All files (*)")
        if path:
            clip = self._voice_keyer.get_clip(key)
            self._voice_keyer.set_clip(key, clip["label"], path)
            btn.setToolTip(path)
            self._voice_status.setText(f"Loaded {key.upper()} ← {os.path.basename(path)}")

    def _voice_edit_label(self, key: str, btn: "QPushButton") -> None:
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout as _VL,
                                     QFormLayout, QDialogButtonBox, QLineEdit)
        clip = self._voice_keyer.get_clip(key)
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Edit label for {key.upper()}")
        dlg.setMinimumWidth(300)
        vl = _VL(dlg)
        form = QFormLayout()
        lbl_edit = QLineEdit(clip["label"])
        form.addRow("Label:", lbl_edit)
        vl.addLayout(form)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        vl.addWidget(bb)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            label = lbl_edit.text().strip() or clip["label"]
            self._voice_keyer.set_clip(key, label, clip["path"])
            idx = int(key[1])
            btn.setText(f"V{idx}: {label}")
