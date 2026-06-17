"""Squelch — ui/dialogs/band_plan_dialog.py
Band Plan Reference dialog — shows FCC Part 97 amateur band segments
color-coded by type, with license class privilege indicators.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QScrollArea,
    QWidget, QGridLayout, QFrame, QDialogButtonBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from core.band_plan import BANDS, SegType, SEG_COLORS, License

# License hierarchy for privilege check
_LICENSE_RANK = {"Technician": 0, "General": 1, "Extra": 2, "Other / Non-US": 2}
_SEG_TYPE_LABELS = {
    SegType.CW:         "CW",
    SegType.CW_DIGITAL: "CW / Digital",
    SegType.DIGITAL:    "Digital",
    SegType.PHONE:      "Phone",
    SegType.AM:         "AM",
    SegType.IMAGE:      "Image",
    SegType.BEACON:     "Beacons",
    SegType.SATELLITE:  "Satellite",
    SegType.REPEATER:   "Repeater",
    SegType.SIMPLEX:    "Simplex",
    SegType.CALLING:    "Calling",
    SegType.GUARD:      "Guard",
    SegType.MIXED:      "Mixed",
    SegType.NOVICE:     "Novice",
}
_LICENSE_LABELS = {
    License.ALL:        "All classes",
    License.GENERAL:    "General / Extra",
    License.EXTRA:      "Extra only",
    License.NOVICE:     "Novice / Tech",
    License.TECHNICIAN: "Technician",
}


def _freq_label(hz: int) -> str:
    if hz >= 1_000_000:
        mhz = hz / 1_000_000
        return f"{mhz:.3f}".rstrip("0").rstrip(".") + " MHz"
    return f"{hz / 1000:.1f} kHz"


class BandPlanDialog(QDialog):
    def __init__(self, license_class: str = "Extra", parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Band Plan Reference (FCC Part 97)"))
        self.resize(680, 520)
        self._license_rank = _LICENSE_RANK.get(license_class, 2)
        self._license_class = license_class
        self._build()

    # ── build ──────────────────────────────────────────────────────────────

    def _build(self):
        lay = QHBoxLayout(self)

        # Left: band list
        self._band_list = QListWidget()
        self._band_list.setFixedWidth(90)
        for band in BANDS:
            item = QListWidgetItem(band.name)
            item.setData(Qt.ItemDataRole.UserRole, band)
            self._band_list.addItem(item)
        self._band_list.currentRowChanged.connect(self._on_band_selected)
        lay.addWidget(self._band_list)

        # Right: segment detail
        right = QVBoxLayout()
        lic_info = QLabel(
            self.tr(f"License class: <b>{self._license_class}</b>  "
                    "— dimmed segments require a higher class."))
        lic_info.setWordWrap(True)
        right.addWidget(lic_info)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        right.addWidget(self._scroll)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.accept)
        right.addWidget(btns)
        lay.addLayout(right)

        if self._band_list.count():
            self._band_list.setCurrentRow(0)

    # ── segment panel ──────────────────────────────────────────────────────

    def _on_band_selected(self, row: int):
        item = self._band_list.item(row)
        if not item:
            return
        band = item.data(Qt.ItemDataRole.UserRole)
        self._scroll.setWidget(self._build_band_panel(band))

    def _build_band_panel(self, band) -> QWidget:
        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setSpacing(4)
        grid.setContentsMargins(8, 8, 8, 8)
        # cols: 0=swatch, 1=range, 2=type, 3=license, 4=notes(stretch)
        grid.setColumnStretch(4, 1)

        headers = ["", "Range", "Type", "License", "Notes"]
        for col, h in enumerate(headers):
            lbl = QLabel(f"<b>{h}</b>")
            grid.addWidget(lbl, 0, col)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        grid.addWidget(sep, 1, 0, 1, 5)

        for row_idx, seg in enumerate(band.segments, start=2):
            accessible = self._is_accessible(seg.license)
            alpha = "ff" if accessible else "40"
            hex_color = seg.color[:7]
            swatch = QLabel("  ")
            swatch.setFixedWidth(14)
            swatch.setStyleSheet(
                f"background-color: {hex_color}{alpha}; border-radius: 2px;")
            grid.addWidget(swatch, row_idx, 0)

            freq_range = (f"{_freq_label(seg.freq_lo)} –\n"
                          f"{_freq_label(seg.freq_hi)}")
            self._add_cell(grid, row_idx, 1, freq_range, accessible)
            self._add_cell(
                grid, row_idx, 2,
                _SEG_TYPE_LABELS.get(seg.seg_type, seg.seg_type), accessible)
            self._add_cell(
                grid, row_idx, 3,
                _LICENSE_LABELS.get(seg.license, seg.license), accessible)
            notes_lbl = QLabel(seg.mode_notes)
            notes_lbl.setWordWrap(True)
            if not accessible:
                notes_lbl.setEnabled(False)
            grid.addWidget(notes_lbl, row_idx, 4)

        return inner

    # ── helpers ────────────────────────────────────────────────────────────

    def _is_accessible(self, seg_license: str) -> bool:
        seg_rank = {
            License.ALL:        0,
            License.TECHNICIAN: 0,
            License.NOVICE:     0,
            License.GENERAL:    1,
            License.EXTRA:      2,
        }.get(seg_license, 0)
        return self._license_rank >= seg_rank

    def _add_cell(self, grid, row: int, col: int, text: str,
                  accessible: bool):
        lbl = QLabel(text)
        if not accessible:
            lbl.setEnabled(False)
        grid.addWidget(lbl, row, col)
