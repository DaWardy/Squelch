from __future__ import annotations
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
Squelch -- ui/dialogs/paths_dialog.py
Settings → Paths & Executables.
Driven by core/launcher.py AppDef database.
Browse, Test, Launch, Auto-detect all.
"""

import sys
import subprocess
import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QGroupBox,
    QDialogButtonBox, QFileDialog, QScrollArea,
    QWidget, QMessageBox, QFrame, QTabWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl

from core.launcher import APPS, AppDef, get_launcher

log = logging.getLogger(__name__)

CATEGORY_LABELS = {
    "rig":         "🔌  Rig Control",
    "digital":     "📡  Digital Modes",
    "winlink":     "✉️  Winlink / VARA",
    "sdr":         "〰️  SDR",
    "programming": "🔧  Radio Programming",
    "log":         "📒  Logging",
}


class AppRow(QWidget):
    """Single app row: path field + browse + test + launch + status."""

    def __init__(self, app: AppDef, config, parent=None):
        super().__init__(parent)
        self._app    = app
        self._cfg    = config
        self._build()
        self._load()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(4)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText(
            "Path to executable…")
        self._edit.setMinimumWidth(260)
        lay.addWidget(self._edit, 1)

        browse = QPushButton(self.tr("Browse…"))
        browse.setFixedWidth(65)
        browse.clicked.connect(self._browse)
        lay.addWidget(browse)

        if self._app.args is not None:
            test = QPushButton(self.tr("Test"))
            test.setFixedWidth(44)
            test.clicked.connect(self._test)
            lay.addWidget(test)

        launch = QPushButton(self.tr("▶"))
        launch.setFixedWidth(28)
        launch.setToolTip(self.tr(
            f"Launch {self._app.name}"))
        launch.clicked.connect(self._launch)
        lay.addWidget(launch)

        self._status = QLabel("—")
        self._status.setFixedWidth(22)
        self._status.setAlignment(
            Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._status)

        if self._app.download_url:
            dl = QPushButton("↓")
            dl.setFixedWidth(24)
            dl.setToolTip(
                f"Download: {self._app.download_url}")
            dl.clicked.connect(self._download)
            lay.addWidget(dl)

    def _load(self):
        launcher = get_launcher(self._cfg)
        path = launcher.get_path(self._app.key)
        if path:
            self._edit.setText(path)
            self._set_status("✅", "#3fbe6f")
        else:
            configured = self._cfg.get(
                self._app.key, "")
            if configured:
                self._edit.setText(configured)
            self._set_status("⚠", "#888888")

    def _browse(self):
        if IS_WINDOWS := sys.platform == "win32":
            exts = "Executables (*.exe);All files (*)"
        else:
            exts = "All files (*)"
        path, _ = QFileDialog.getOpenFileName(
            self, f"Select {self._app.name}",
            "", exts)
        if path:
            self._edit.setText(path)
            self._check_exists(path)

    def _test(self):
        path = self._edit.text().strip()
        if not path:
            QMessageBox.warning(
                self, "No Path",
                "Enter a path first.")
            return
        self._set_status("…", "#aaaa22")
        try:
            result = subprocess.run(
                [path, "--version"],
                capture_output=True, text=True,
                timeout=5, shell=False)
            out = (result.stdout or
                   result.stderr or "").strip()[:200]
            self._set_status("✅", "#3fbe6f")
            QMessageBox.information(
                self, f"{self._app.name} — Test OK",
                f"Path: {path}\n\n{out or 'OK'}")
        except FileNotFoundError:
            self._set_status("❌", "#cc4444")
            QMessageBox.warning(
                self, "Not Found",
                f"Could not run:\n{path}")
        except Exception as e:
            self._set_status("⚠", "#aaaa22")
            QMessageBox.warning(
                self, "Test Error", str(e))

    def _launch(self):
        path = self._edit.text().strip()
        if not path or not Path(path).exists():
            QMessageBox.warning(
                self, "Not Found",
                f"{self._app.name} not found.\n"
                f"Configure path or click ↓ to download.")
            return
        try:
            import subprocess
            subprocess.Popen(
                [path],
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
        except Exception as e:
            QMessageBox.warning(
                self, "Launch Failed", str(e))

    def _download(self):
        QDesktopServices.openUrl(
            QUrl(self._app.download_url))

    def _check_exists(self, path: str):
        if Path(path).exists():
            self._set_status("✅", "#3fbe6f")
        else:
            self._set_status("❌", "#cc4444")

    def _set_status(self, icon: str, color: str):
        self._status.setText(icon)
        self._status.setStyleSheet(f"color:{color};")

    def save(self):
        val = self._edit.text().strip()
        self._cfg.set(self._app.key, val)
        self._cfg.save()

    def auto_detect(self) -> bool:
        launcher = get_launcher(self._cfg)
        path = launcher.get_path(self._app.key)
        if path:
            self._edit.setText(path)
            self._set_status("✅", "#3fbe6f")
            return True
        return False


class PathsDialog(QDialog):
    """Settings → Paths & Executables."""

    def __init__(self, config,
                 scroll_to: str = None,
                 parent=None):
        super().__init__(parent)
        self.cfg       = config
        self._rows:    list[AppRow] = []
        self._scroll_to = scroll_to
        self.setWindowTitle(
            self.tr("Paths & Executables"))
        self.setMinimumWidth(720)
        self.setMinimumHeight(560)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)

        intro = QLabel(self.tr(
            "Configure paths to external programs. "
            "Click ▶ to launch. "
            "Click ↓ to open the download page. "
            "Green ✅ = found, ⚠ = not configured."))
        intro.setWordWrap(True)
        intro.setStyleSheet(
            "")
        lay.addWidget(intro)

        # Tabs by category
        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabBar::tab{padding:5px 10px;"
            "}")

        # Group apps by category
        cats: dict[str, list[AppDef]] = {}
        for app in APPS:
            cats.setdefault(app.category, []).append(app)

        for cat_key, apps in cats.items():
            cat_label = CATEGORY_LABELS.get(
                cat_key, cat_key.title())
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)

            inner  = QWidget()
            grid   = QGridLayout(inner)
            grid.setSpacing(6)
            grid.setContentsMargins(6, 6, 6, 6)

            # Header
            for col, hdr in enumerate([
                    self.tr("Program"),
                    self.tr("Path / Status"), "", "", "", ""]):
                if hdr:
                    lbl = QLabel(hdr)
                    lbl.setStyleSheet(
                        ""
                        "font-weight:bold;")
                    grid.addWidget(lbl, 0, col)

            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet("color:#222;")
            grid.addWidget(sep, 1, 0, 1, 6)

            for i, app in enumerate(apps):
                row_idx = i + 2
                lbl_w   = QWidget()
                lbl_lay = QVBoxLayout(lbl_w)
                lbl_lay.setContentsMargins(0, 0, 0, 0)
                lbl_lay.setSpacing(0)
                name = QLabel(app.name)
                name.setStyleSheet(
                    ""
                    "font-weight:bold;")
                desc = QLabel(app.description)
                desc.setStyleSheet(
                    "")
                if app.download_note:
                    note = QLabel(app.download_note)
                    note.setStyleSheet(
                        "color:#446644;")
                    note.setWordWrap(True)
                    lbl_lay.addWidget(note)
                lbl_lay.addWidget(name)
                lbl_lay.addWidget(desc)
                grid.addWidget(lbl_w, row_idx, 0)

                row = AppRow(app, self.cfg)
                grid.addWidget(row, row_idx, 1, 1, 5)
                self._rows.append(row)

            scroll.setWidget(inner)
            tabs.addTab(scroll, cat_label)

        lay.addWidget(tabs)

        # Bottom buttons
        btn_row = QHBoxLayout()
        auto_btn = QPushButton(
            self.tr("Auto-detect all"))
        auto_btn.clicked.connect(
            self._auto_detect_all)
        btn_row.addWidget(auto_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save_and_accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _auto_detect_all(self):
        found = 0
        for row in self._rows:
            if row.auto_detect():
                found += 1
        QMessageBox.information(
            self, self.tr("Auto-detect"),
            f"Found {found} of "
            f"{len(self._rows)} programs.")

    def _save_and_accept(self):
        for row in self._rows:
            row.save()
        self.cfg.save()
        self.accept()
