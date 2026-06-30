from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/tabs/modes_sstv_mixin.py

SSTV received-image viewer for the Weak-Signal (Modes) tab, extracted from
modes_tab.py (HOUSE-CS complexity split).

`_ModesSSTVMixin` is mixed into `ModesTab`. It is fully self-contained — it owns
`_sstv_panel`/`_sstv_image_lbl`/`_sstv_watcher`/`_sstv_image_path` and only needs
`self` as the QWidget parent for dialogs. `_build_sstv_image_panel()` is called
from the host `_build`; `_on_mode_tab` shows/hides `self._sstv_panel`.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)


class _ModesSSTVMixin:
    """SSTV image panel — watches fldigi's image output folder and shows it."""

    def _build_sstv_image_panel(self) -> QWidget:
        """SSTV received-image viewer — watches fldigi's image output folder."""
        from PyQt6.QtWidgets import QScrollArea, QFileDialog
        from PyQt6.QtGui import QPixmap
        from pathlib import Path
        import sys, os

        self._sstv_panel = QGroupBox("SSTV Image")
        self._sstv_panel.setVisible(False)
        sv = QVBoxLayout(self._sstv_panel)
        sv.setContentsMargins(4, 4, 4, 4)
        sv.setSpacing(4)

        self._sstv_image_lbl = QLabel("No image received yet")
        self._sstv_image_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sstv_image_lbl.setMinimumHeight(120)
        self._sstv_image_lbl.setStyleSheet("")
        sv.addWidget(self._sstv_image_lbl)

        btn_row = QHBoxLayout()
        open_btn = QPushButton("Open folder")
        open_btn.setFixedHeight(22)
        open_btn.setToolTip("Open fldigi's SSTV image folder in Explorer/Finder")
        open_btn.clicked.connect(self._sstv_open_folder)
        save_btn = QPushButton("Save copy…")
        save_btn.setFixedHeight(22)
        save_btn.clicked.connect(self._sstv_save)
        btn_row.addWidget(open_btn)
        btn_row.addWidget(save_btn)
        btn_row.addStretch()
        self._sstv_folder_lbl = QLabel("")
        self._sstv_folder_lbl.setStyleSheet("color:#555;font-size:9px;")
        sv.addLayout(btn_row)
        sv.addWidget(self._sstv_folder_lbl)

        # QFileSystemWatcher monitors fldigi SSTV image folder
        from PyQt6.QtCore import QFileSystemWatcher
        self._sstv_watcher = QFileSystemWatcher()
        self._sstv_watcher.directoryChanged.connect(self._sstv_refresh)
        self._sstv_image_path: "str | None" = None

        # Arm the watcher for the default fldigi image path
        if sys.platform == "win32":
            default = str(Path(os.environ.get("APPDATA", "~")) / "fldigi" / "images")
        else:
            default = str(Path.home() / ".fldigi" / "images")
        if Path(default).is_dir():
            self._sstv_watcher.addPath(default)
            self._sstv_folder_lbl.setText(default)
            self._sstv_refresh(default)

        return self._sstv_panel

    def _sstv_refresh(self, folder: str) -> None:
        """Scan folder for latest image and display it."""
        from pathlib import Path
        from PyQt6.QtGui import QPixmap
        p = Path(folder)
        images = sorted(
            [f for f in p.glob("*") if f.suffix.lower() in (".bmp", ".png", ".jpg")],
            key=lambda f: f.stat().st_mtime)
        if not images:
            return
        latest = str(images[-1])
        if latest == self._sstv_image_path:
            return
        self._sstv_image_path = latest
        px = QPixmap(latest)
        if not px.isNull():
            self._sstv_image_lbl.setPixmap(
                px.scaled(self._sstv_image_lbl.width() or 240,
                          200, Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation))

    def _sstv_open_folder(self) -> None:
        import sys, subprocess, os
        from pathlib import Path
        if sys.platform == "win32":
            d = str(Path(os.environ.get("APPDATA", "~")) / "fldigi" / "images")
        else:
            d = str(Path.home() / ".fldigi" / "images")
        try:
            if sys.platform == "win32":
                os.startfile(d)        # noqa: only on Windows
            elif sys.platform == "darwin":
                subprocess.Popen(["open", d])
            else:
                subprocess.Popen(["xdg-open", d])
        except Exception:
            pass

    def _sstv_save(self) -> None:
        from PyQt6.QtWidgets import QFileDialog
        if not self._sstv_image_path:
            return
        dst, _ = QFileDialog.getSaveFileName(
            self, "Save SSTV Image", "sstv_received.png",
            "Images (*.png *.bmp *.jpg)")
        if dst:
            import shutil
            shutil.copy2(self._sstv_image_path, dst)
