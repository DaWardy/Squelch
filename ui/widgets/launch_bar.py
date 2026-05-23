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
Squelch -- ui/widgets/launch_bar.py
Reusable launch button bar shown at top of tabs
that depend on external software.
Green = found/running, amber = found/stopped,
gray = not configured.
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton,
    QLabel, QFrame
)
from PyQt6.QtCore import Qt, QTimer

from core.launcher import get_launcher, AppDef

log = logging.getLogger(__name__)


class LaunchButton(QPushButton):
    """
    Single launch button for one external app.
    Shows availability state via color.
    """

    def __init__(self, app: AppDef, config,
                 parent=None):
        super().__init__(parent)
        self._app    = app
        self._cfg    = config
        self._avail  = False
        self.setText(f"▶ {app.name}")
        self.setFixedHeight(26)
        self.setToolTip(app.description)
        self.clicked.connect(self._launch)
        self._refresh()

    def _refresh(self):
        launcher = get_launcher(self._cfg)
        self._avail = launcher.is_available(self._app.key)
        if self._avail:
            self.setStyleSheet("""
                QPushButton{
                  background:#1a3a1a;color:#3fbe6f;
                  border:1px solid #3fbe6f;
                  border-radius:4px;
                  padding:2px 8px;}
                QPushButton:hover{background:#2a4a2a;}
            """)
            self.setToolTip(
                f"{self._app.name}\n"
                f"{self._app.description}\n"
                f"Click to launch")
        else:
            self.setStyleSheet("""
                QPushButton{
                  background:#1a1a1a;
                  border:1px solid #2a2a2a;
                  border-radius:4px;
                  padding:2px 8px;}
                QPushButton:hover{
                  background:#1e1e1e;}
            """)
            self.setToolTip(
                f"{self._app.name} — not found\n"
                f"Click to configure path\n"
                f"Download: {self._app.download_url}")

    def _launch(self):
        launcher = get_launcher(self._cfg)
        if self._avail:
            launcher.launch(self._app.key)
        else:
            # Open paths dialog to configure
            try:
                from ui.dialogs.paths_dialog import \
                    PathsDialog
                dlg = PathsDialog(
                    self._cfg,
                    scroll_to=self._app.key,
                    parent=self.window())
                if dlg.exec():
                    self._refresh()
            except Exception as e:
                log.warning(f"Paths dialog: {e}")


class LaunchBar(QWidget):
    """
    Horizontal bar of launch buttons for a tab.
    Shown at top of any tab that needs external apps.
    """

    def __init__(self, tab_name: str, config,
                 rescan_callback=None,
                 parent=None):
        super().__init__(parent)
        self._tab    = tab_name
        self._cfg    = config
        self._rescan = rescan_callback
        self._btns:  list[LaunchButton] = []
        self._build()

    def _build(self):
        self.setFixedHeight(38)
        self.setStyleSheet(
            "background:#0d0d0d;"
            "border-bottom:1px solid #1a1a1a;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(6)

        from core.launcher import _BY_TAB
        apps = _BY_TAB.get(self._tab, [])

        if not apps:
            return

        lbl = QLabel(self.tr("External software:"))
        lbl.setStyleSheet(
            "")
        lay.addWidget(lbl)

        for app in apps:
            btn = LaunchButton(app, self._cfg)
            self._btns.append(btn)
            lay.addWidget(btn)

        lay.addWidget(_vsep())

        # Rescan button
        rescan = QPushButton(self.tr("↺ Rescan"))
        rescan.setFixedHeight(24)
        rescan.setFixedWidth(70)
        rescan.setStyleSheet(
            "background:#1a1a1a;"
            "border:1px solid #2a2a2a;"
            "border-radius:3px;")
        rescan.setToolTip(
            self.tr("Re-scan for running software"))
        rescan.clicked.connect(self._do_rescan)
        lay.addWidget(rescan)

        lay.addStretch()

    def _do_rescan(self):
        # Refresh all button states
        for btn in self._btns:
            btn._refresh()
        if self._rescan:
            try:
                self._rescan()
            except Exception:
                pass

    def refresh(self):
        """Call after paths are configured."""
        for btn in self._btns:
            btn._refresh()


def _vsep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setStyleSheet("color:#1e1e1e;")
    f.setFixedWidth(1)
    return f
