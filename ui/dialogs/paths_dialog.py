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
Settings → Paths & Executables dialog.
Browse + Test + Auto-detect for each external program.
"""

import os
import sys
import logging
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QGroupBox,
    QDialogButtonBox, QFileDialog, QScrollArea,
    QWidget, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from core.validator import executable_path, ALLOWED_EXECUTABLES

log = logging.getLogger(__name__)

# Executable definitions
EXECUTABLES = [
    {
        "key":    "paths.rigctld",
        "label":  "rigctld (Hamlib)",
        "hint":   "CAT rig control — required for rig tab",
        "exe":    "rigctld",
        "test":   ["--version"],
        "common": [
            r"C:\hamlib\bin\rigctld.exe",
            "/usr/bin/rigctld",
            "/usr/local/bin/rigctld",
        ],
        "download": "https://github.com/Hamlib/Hamlib/releases",
    },
    {
        "key":    "paths.wsjtx",
        "label":  "WSJT-X",
        "hint":   "FT8 / FT4 / WSPR / JS8 modes",
        "exe":    "wsjtx",
        "test":   ["--version"],
        "common": [
            r"C:\Program Files\WSJT-X\bin\wsjtx.exe",
            r"C:\Program Files (x86)\WSJT-X\bin\wsjtx.exe",
            "/usr/bin/wsjtx",
            "/usr/local/bin/wsjtx",
        ],
        "download": "https://wsjt.sourceforge.io/wsjtx.html",
    },
    {
        "key":    "paths.fldigi",
        "label":  "Fldigi",
        "hint":   "PSK31, RTTY, CW, SSTV digital modes",
        "exe":    "fldigi",
        "test":   ["--version"],
        "common": [
            r"C:\Program Files\fldigi\fldigi.exe",
            r"C:\Program Files (x86)\fldigi\fldigi.exe",
            "/usr/bin/fldigi",
            "/usr/local/bin/fldigi",
        ],
        "download": "https://sourceforge.net/projects/fldigi/",
    },
    {
        "key":    "paths.js8call",
        "label":  "JS8Call",
        "hint":   "JS8 keyboard-to-keyboard messaging",
        "exe":    "js8call",
        "test":   [],
        "common": [
            r"C:\Program Files\JS8Call\js8call.exe",
            "/usr/bin/js8call",
        ],
        "download": "https://js8call.com/",
    },
    {
        "key":    "paths.vara_hf",
        "label":  "VARA HF",
        "hint":   "Winlink HF modem (paid license for full speed)",
        "exe":    "VARAHF",
        "test":   [],
        "common": [
            r"C:\VARA HF\VARAHF.exe",
            r"C:\VARA\VARAHF.exe",
            r"C:\Program Files\VARA HF\VARAHF.exe",
        ],
        "download": "https://rosmodem.wordpress.com/",
    },
    {
        "key":    "paths.vara_fm",
        "label":  "VARA FM",
        "hint":   "Winlink VHF/UHF modem",
        "exe":    "VARAFM",
        "test":   [],
        "common": [
            r"C:\VARA FM\VARAFM.exe",
            r"C:\Program Files\VARA FM\VARAFM.exe",
        ],
        "download": "https://rosmodem.wordpress.com/",
    },
    {
        "key":    "paths.dsdplus",
        "label":  "DSD+",
        "hint":   "DMR / NXDN / YSF decode (Windows)",
        "exe":    "DSDPlus",
        "test":   [],
        "common": [
            r"C:\DSDPlus\DSDPlus.exe",
            r"C:\Program Files\DSDPlus\DSDPlus.exe",
        ],
        "download": "https://www.dsdplus.com/",
    },
    {
        "key":    "paths.dump1090",
        "label":  "dump1090-fa",
        "hint":   "ADS-B aircraft tracking decoder",
        "exe":    "dump1090-fa",
        "test":   ["--version"],
        "common": [
            r"C:\dump1090\dump1090-fa.exe",
            "/usr/bin/dump1090-fa",
            "/usr/local/bin/dump1090-fa",
        ],
        "download": "https://github.com/flightaware/dump1090",
    },
    {
        "key":    "paths.tqsl",
        "label":  "TQSL (LoTW)",
        "hint":   "LoTW QSO signing and upload",
        "exe":    "tqsl",
        "test":   [],
        "common": [
            r"C:\Program Files\TQSL\tqsl.exe",
            r"C:\Program Files (x86)\TQSL\tqsl.exe",
            "/usr/bin/tqsl",
            "/usr/local/bin/tqsl",
        ],
        "download": "https://lotw.arrl.org/lotw-user-guide/",
    },
    {
        "key":    "paths.iq_recordings",
        "label":  "IQ Recordings Folder",
        "hint":   "Where SDR IQ recordings are saved",
        "exe":    None,   # directory, not executable
        "test":   [],
        "common": [str(Path.home() / "squelch_recordings")],
        "download": "",
    },
]


class PathRow(QWidget):
    """Single path entry row with browse, test, and status."""

    def __init__(self, defn: dict, config, parent=None):
        super().__init__(parent)
        self._defn   = defn
        self._cfg    = config
        self._is_dir = defn["exe"] is None
        self._build()
        self._load()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(6)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText(
            "Path to executable…" if not self._is_dir
            else "Path to folder…")
        self._edit.setMinimumWidth(280)
        lay.addWidget(self._edit, 1)

        browse = QPushButton("Browse…")
        browse.setFixedWidth(70)
        browse.clicked.connect(self._browse)
        lay.addWidget(browse)

        self._test_btn = QPushButton("Test")
        self._test_btn.setFixedWidth(50)
        self._test_btn.clicked.connect(self._test)
        if not self._defn.get("test") and not self._is_dir:
            self._test_btn.setEnabled(False)
        lay.addWidget(self._test_btn)

        self._status = QLabel("—")
        self._status.setFixedWidth(22)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setFont(QFont("Segoe UI", 12))
        lay.addWidget(self._status)

        if self._defn.get("download"):
            dl = QPushButton("↓")
            dl.setFixedWidth(26)
            dl.setToolTip(
                f"Download: {self._defn['download']}")
            dl.clicked.connect(
                lambda: self._open_url(
                    self._defn["download"]))
            lay.addWidget(dl)

    def _load(self):
        val = self._cfg.get(self._defn["key"], "")
        if val:
            self._edit.setText(val)
            self._check_exists(val)
        else:
            # Try auto-detect
            found = self._auto_detect()
            if found:
                self._edit.setText(found)
                self._set_status("✅", "#3fbe6f")
            else:
                self._set_status("⚠", "#888888")

    def _browse(self):
        if self._is_dir:
            path = QFileDialog.getExistingDirectory(
                self, f"Select {self._defn['label']} folder")
        else:
            exts = ("*.exe" if sys.platform == "win32"
                    else "")
            path, _ = QFileDialog.getOpenFileName(
                self,
                f"Select {self._defn['label']}",
                "",
                f"Executables ({exts});;All files (*)")
        if path:
            self._edit.setText(path)
            self._check_exists(path)

    def _test(self):
        path = self._edit.text().strip()
        if not path:
            return
        self._set_status("…", "#aaaa22")
        try:
            cmd = [path] + self._defn.get("test", [])
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                shell=False)
            output = (result.stdout or result.stderr or "").strip()
            if result.returncode == 0 or output:
                self._set_status("✅", "#3fbe6f")
                QMessageBox.information(
                    self, "Test Result",
                    f"{self._defn['label']} OK\n\n{output[:200]}")
            else:
                self._set_status("❌", "#cc4444")
        except FileNotFoundError:
            self._set_status("❌", "#cc4444")
            QMessageBox.warning(
                self, "Not Found",
                f"Could not run: {path}\n"
                "Check the path is correct.")
        except Exception as e:
            self._set_status("⚠", "#aaaa22")
            QMessageBox.warning(self, "Test Error", str(e))

    def _auto_detect(self) -> str:
        """Try common install locations."""
        for candidate in self._defn.get("common", []):
            if Path(candidate).exists():
                return candidate
        # Also try PATH
        exe = self._defn.get("exe")
        if exe:
            import shutil
            found = shutil.which(exe)
            if found:
                return found
        return ""

    def _check_exists(self, path: str):
        if Path(path).exists():
            self._set_status("✅", "#3fbe6f")
        else:
            self._set_status("❌", "#cc4444")

    def _set_status(self, icon: str, color: str):
        self._status.setText(icon)
        self._status.setStyleSheet(f"color:{color};")

    def _open_url(self, url: str):
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url))

    def save(self):
        val = self._edit.text().strip()
        self._cfg.set(self._defn["key"], val)

    def auto_detect(self):
        found = self._auto_detect()
        if found:
            self._edit.setText(found)
            self._check_exists(found)
        return bool(found)


class PathsDialog(QDialog):
    """Settings → Paths & Executables dialog."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.cfg  = config
        self.setWindowTitle(
            self.tr("Paths & Executables"))
        self.setMinimumWidth(680)
        self.setMinimumHeight(500)
        self._rows: list[PathRow] = []
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)

        intro = QLabel(
            self.tr(
                "Configure paths to external programs. "
                "Squelch launches these automatically when needed.\n"
                "Click Test to verify each path. "
                "Click ↓ to open the download page for missing tools."))
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#888;font-size:10px;")
        lay.addWidget(intro)

        # Scroll area for all rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner  = QWidget()
        grid   = QGridLayout(inner)
        grid.setSpacing(6)
        grid.setContentsMargins(4, 4, 4, 4)

        # Column headers
        for col, hdr in enumerate([
                self.tr("Program"),
                self.tr("Path"),
                "", "", "", ""]):
            if hdr:
                lbl = QLabel(hdr)
                lbl.setStyleSheet(
                    "color:#555;font-size:10px;"
                    "font-weight:bold;")
                grid.addWidget(lbl, 0, col)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#222;")
        grid.addWidget(sep, 1, 0, 1, 6)

        for i, defn in enumerate(EXECUTABLES):
            row_idx = i + 2

            # Label + hint
            lbl_widget = QWidget()
            lbl_lay    = QVBoxLayout(lbl_widget)
            lbl_lay.setContentsMargins(0, 0, 0, 0)
            lbl_lay.setSpacing(0)
            lbl = QLabel(defn["label"])
            lbl.setStyleSheet(
                "color:#ccc;font-size:11px;"
                "font-weight:bold;")
            hint = QLabel(defn["hint"])
            hint.setStyleSheet(
                "color:#555;font-size:9px;")
            lbl_lay.addWidget(lbl)
            lbl_lay.addWidget(hint)
            grid.addWidget(lbl_widget, row_idx, 0)

            path_row = PathRow(defn, self.cfg)
            grid.addWidget(path_row, row_idx, 1, 1, 5)
            self._rows.append(path_row)

        scroll.setWidget(inner)
        lay.addWidget(scroll)

        # Buttons
        btn_row = QHBoxLayout()
        auto_btn = QPushButton(self.tr("Auto-detect all"))
        auto_btn.clicked.connect(self._auto_detect_all)
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
            f"Found {found} of {len(self._rows)} programs.")

    def _save_and_accept(self):
        for row in self._rows:
            row.save()
        self.cfg.save()
        self.accept()
