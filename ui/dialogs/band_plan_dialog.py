"""Squelch — ui/dialogs/band_plan_dialog.py
Frequency Reference dialog — FCC Part 97 amateur bands + service allocations
(CB, FRS/GMRS, MURS, ISM/unlicensed).  Color-coded by mode type; amateur
bands dim segments that require a higher license class.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QScrollArea,
    QWidget, QGridLayout, QFrame, QDialogButtonBox,
    QComboBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from core.band_plan import ALL_BANDS, BANDS, SERVICE_BANDS, SegType, SEG_COLORS, License

# License hierarchy for amateur privilege check
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
    SegType.FRS:        "FRS",
    SegType.GMRS_CHAN:  "GMRS",
    SegType.CB:         "CB",
    SegType.MURS:       "MURS",
    SegType.ISM:        "ISM/Unlicensed",
    SegType.WIFI:       "Wi-Fi / BT",
}
_LICENSE_LABELS = {
    License.ALL:        "All classes",
    License.GENERAL:    "General / Extra",
    License.EXTRA:      "Extra only",
    License.NOVICE:     "Novice / Tech",
    License.TECHNICIAN: "Technician",
    License.NONE:       "No license required",
    License.GMRS_LIC:   "GMRS license required",
}

# Category filter entries — (display label, category value or None for all)
_CATEGORIES = [
    ("All bands",           None),
    ("Amateur (Part 97)",   "Amateur"),
    ("CB (Citizens Band)",  "CB"),
    ("FRS / GMRS",          "FRS/GMRS"),
    ("MURS",                "MURS"),
    ("ISM / Unlicensed",    "ISM/Unlicensed"),
]


def _freq_label(hz: int) -> str:
    if hz >= 1_000_000_000:
        return f"{hz / 1_000_000_000:.3f}".rstrip("0").rstrip(".") + " GHz"
    if hz >= 1_000_000:
        mhz = hz / 1_000_000
        return f"{mhz:.3f}".rstrip("0").rstrip(".") + " MHz"
    return f"{hz / 1000:.1f} kHz"


class BandPlanDialog(QDialog):
    def __init__(self, license_class: str = "Extra", parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Frequency Reference — FCC Part 97 + Service Bands"))
        self.resize(740, 540)
        self._license_rank = _LICENSE_RANK.get(license_class, 2)
        self._license_class = license_class
        self._build()

    # ── build ──────────────────────────────────────────────────────────────

    def _build(self):
        lay = QHBoxLayout(self)

        # Left: category filter + band list
        left = QVBoxLayout()

        cat_combo = QComboBox()
        for label, _ in _CATEGORIES:
            cat_combo.addItem(label)
        cat_combo.setCurrentIndex(0)
        cat_combo.currentIndexChanged.connect(self._on_category_changed)
        left.addWidget(cat_combo)
        self._cat_combo = cat_combo

        self._band_list = QListWidget()
        self._band_list.setFixedWidth(130)
        self._band_list.currentRowChanged.connect(self._on_band_selected)
        left.addWidget(self._band_list)
        lay.addLayout(left)

        # Right: info label + segment detail
        right = QVBoxLayout()
        self._lic_info = QLabel()
        self._lic_info.setWordWrap(True)
        right.addWidget(self._lic_info)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        right.addWidget(self._scroll)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.accept)
        right.addWidget(btns)
        lay.addLayout(right)

        self._populate_band_list(None)

    # ── category + band list ───────────────────────────────────────────────

    def _populate_band_list(self, category: str | None):
        self._band_list.clear()
        if category is None:
            bands = ALL_BANDS
        else:
            bands = [b for b in ALL_BANDS if b.category == category]
        for band in bands:
            item = QListWidgetItem(band.name)
            item.setData(Qt.ItemDataRole.UserRole, band)
            self._band_list.addItem(item)
        if self._band_list.count():
            self._band_list.setCurrentRow(0)

    def _on_category_changed(self, index: int):
        _, category = _CATEGORIES[index] if index < len(_CATEGORIES) else (None, None)
        self._populate_band_list(category)

    # ── segment panel ──────────────────────────────────────────────────────

    def _on_band_selected(self, row: int):
        item = self._band_list.item(row)
        if not item:
            self._lic_info.setText("")
            return
        band = item.data(Qt.ItemDataRole.UserRole)
        if band.category == "Amateur":
            self._lic_info.setText(
                self.tr(f"License class: <b>{self._license_class}</b>"
                        " — dimmed segments require a higher class."))
        else:
            self._lic_info.setText(
                self.tr(f"<b>{band.category}</b> — {band.notes}"))
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
            accessible = self._is_accessible(band, seg.license)
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

    def _is_accessible(self, band, seg_license: str) -> bool:
        # Service bands are always "accessible" — privilege dimming is amateur-only
        if band.category != "Amateur":
            return True
        if seg_license in (License.NONE, License.GMRS_LIC):
            return True
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
