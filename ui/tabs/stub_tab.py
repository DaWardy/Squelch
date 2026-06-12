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
Squelch -- ui/tabs/stub_tab.py
Placeholder tab shown while a feature is under development.
Shows launch bar for tabs that need external software.
Shows roadmap info and what is coming.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame
)
from core.themes import get_theme as _get_theme

TAB_INFO = {
    "digital": {
        "title":   "Digital Monitor",
        "desc":    "P25 / DMR / NXDN / YSF / D-STAR decode, "
                   "RFDF foxhunt mode, signal routing from SDR.",
        "coming":  "Chunk 7",
        "needs":   ["DSD+ (Windows) or OP25 (Linux)"],
        "tab_key": "digital",
    },
    "localrf": {
        "title":   "Local RF",
        "desc":    "RadioReference Premium, RepeaterBook, "
                   "APRS map + beacon, SOTA/POTA, radio programming.",
        "coming":  "Chunk 8",
        "needs":   ["RadioReference Premium API key",
                    "CHIRP (memory programming)",
                    "RT Systems (QRZ-1 programming)"],
        "tab_key": "localrf",
    },
    "winlink": {
        "title":   "Winlink / VARA",
        "desc":    "Winlink email over radio, VARA HF/FM, "
                   "ARES EmComm templates, RMS gateway selection.",
        "coming":  "Chunk 9",
        "needs":   ["VARA HF and/or VARA FM",
                    "Pat (open source) or RMS Express"],
        "tab_key": "winlink",
    },
    "help": {
        "title":   "Help",
        "desc":    "Searchable help, radio setup guides, "
                   "keyboard shortcuts, legal/ethics docs, "
                   "instructor guide.",
        "coming":  "Chunk 10",
        "needs":   [],
        "tab_key": None,
    },
}


class StubTab(QWidget):
    def __init__(self, label: str, key: str,
                 config=None, parent=None):
        super().__init__(parent)
        self._key    = key
        self._cfg    = config
        self._label  = label
        self._build()

    def _build_stub_content(self, info: dict, tab_key: "str | None") -> "QWidget":
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(40, 40, 40, 40)
        cl.setSpacing(10)

        title_text = info.get(
            "title",
            self._label.split("  ")[-1].strip())
        _t = _get_theme(
            self._cfg.get("ui.theme", "Dark") if self._cfg else "Dark")
        title = QLabel(f"<b>{title_text}</b>")
        title.setStyleSheet(f"color:{_t.accent};")
        cl.addWidget(title)

        if info.get("desc"):
            desc = QLabel(info["desc"])
            desc.setWordWrap(True)
            cl.addWidget(desc)

        if info.get("coming"):
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet(f"color:{_t.border};margin:8px 0;")
            cl.addWidget(sep)
            coming = QLabel(
                f"Coming in {info['coming']}  "
                f"— check ROADMAP.md for details.")
            coming.setStyleSheet("font-style:italic;")
            cl.addWidget(coming)

        needs = info.get("needs", [])
        if needs:
            needs_lbl = QLabel("Required software:")
            needs_lbl.setStyleSheet(
                "font-weight:bold;margin-top:8px;")
            cl.addWidget(needs_lbl)
            for item in needs:
                cl.addWidget(QLabel(f"  • {item}"))

        if tab_key and self._cfg:
            hint = QLabel(
                "Use the launch bar above to "
                "install or configure required software.")
            hint.setStyleSheet(f"color:{_t.accent};margin-top:12px;")
            cl.addWidget(hint)

        cl.addStretch()
        return content

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        info    = TAB_INFO.get(self._key, {})
        tab_key = info.get("tab_key")

        if tab_key and self._cfg:
            try:
                from ui.widgets.launch_bar import LaunchBar
                root.addWidget(LaunchBar(tab_key, self._cfg))
            except Exception:
                pass

        root.addWidget(self._build_stub_content(info, tab_key), 1)
