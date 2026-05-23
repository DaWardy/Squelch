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

from __future__ import annotations
"""Squelch -- ui/widgets/freq_display.py
Click-to-edit VFO frequency display. Green on black, band color coded.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QFrame
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

BAND_COLORS = {
    "160m":"#cc8844","80m":"#cc6644","60m":"#aa8844","40m":"#ccaa22",
    "30m":"#88aa22","20m":"#44aa66","17m":"#44aaaa","15m":"#4488cc",
    "12m":"#6644cc","10m":"#aa44cc","6m":"#cc44aa","2m":"#cc4466",
    "70cm":"#cc4444","OOB":"#666666",
}


class FreqDisplay(QWidget):
    freq_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._freq_hz = 14_074_000
        self._band    = "20m"
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(2)

        frame = QFrame()
        frame.setStyleSheet(
            "background:#0a0e0a; border:1px solid #1a3020; border-radius:6px;")
        fl = QHBoxLayout(frame)
        fl.setContentsMargins(12, 6, 12, 6)

        font = QFont("Courier New", 28, QFont.Weight.Bold)

        self._lbl = QLabel(self._fmt(self._freq_hz))
        self._lbl.setFont(font)
        self._lbl.setStyleSheet(
            "color:#3fbe6f; background:transparent; border:none;")
        self._lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._lbl.setCursor(Qt.CursorShape.IBeamCursor)
        self._lbl.setToolTip("Click to enter frequency (Hz or MHz)")
        self._lbl.mousePressEvent = self._start_edit

        self._edit = QLineEdit()
        self._edit.setFont(font)
        self._edit.setStyleSheet(
            "color:#ffdd44; background:transparent; border:none;")
        self._edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._edit.setPlaceholderText("e.g. 14.074 or 14074000")
        self._edit.returnPressed.connect(self._commit)
        self._edit.focusOutEvent = self._focus_out
        self._edit.hide()

        fl.addWidget(self._lbl)
        fl.addWidget(self._edit)

        info = QHBoxLayout()
        info.setContentsMargins(4, 0, 4, 0)
        self._band_lbl = QLabel(self._band)
        self._band_lbl.setStyleSheet(
            f"color:{BAND_COLORS[self._band]}; "
            "font-family:'Courier New'; font-weight:bold;")
        self._mhz_lbl = QLabel("MHz")
        self._mhz_lbl.setStyleSheet(
            "color:#334433;  font-family:'Courier New';")
        self._mhz_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        info.addWidget(self._band_lbl)
        info.addStretch()
        info.addWidget(self._mhz_lbl)

        root.addWidget(frame)
        root.addLayout(info)

    # ── Public ────────────────────────────────────────────────────────────

    def set_freq(self, hz: int):
        self._freq_hz = hz
        self._lbl.setText(self._fmt(hz))

    def set_band(self, band: str):
        self._band = band
        c = BAND_COLORS.get(band, "#666666")
        self._band_lbl.setText(band)
        self._band_lbl.setStyleSheet(
            f"color:{c}; "
            "font-family:'Courier New'; font-weight:bold;")

    def set_tx(self, tx: bool):
        color = "#ff4444" if tx else "#3fbe6f"
        self._lbl.setStyleSheet(
            f"color:{color}; background:transparent; border:none;")

    # ── Edit ──────────────────────────────────────────────────────────────

    def _start_edit(self, _event):
        self._lbl.hide()
        self._edit.setText(str(self._freq_hz))
        self._edit.show()
        self._edit.selectAll()
        self._edit.setFocus()

    def _commit(self):
        text = self._edit.text().strip().replace(",", "").replace(" ", "")
        try:
            val = float(text)
            hz  = int(val * 1_000_000) if val < 1_000 else int(val)
            if 1_000 <= hz <= 450_000_000:
                self._freq_hz = hz
                self.freq_changed.emit(hz)
        except ValueError:
            pass
        self._end_edit()

    def _end_edit(self):
        self._edit.hide()
        self._lbl.setText(self._fmt(self._freq_hz))
        self._lbl.show()

    def _focus_out(self, event):
        self._end_edit()
        QLineEdit.focusOutEvent(self._edit, event)

    @staticmethod
    def _fmt(hz: int) -> str:
        s = str(hz).zfill(9)
        return f"{s[:-6]}.{s[-6:-3]}.{s[-3:]}"
