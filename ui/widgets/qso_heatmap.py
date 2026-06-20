from __future__ import annotations
"""QSOHeatmap — activity heatmap widget (day-of-week × hour-of-day).

Renders a 7-row × 24-column colour grid showing QSO volume.
Colour scale: dark (#111) = 0 QSOs → amber (#ff8800) → green (#3fbe6f).
"""
import math
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QFont, QBrush
from PyQt6.QtWidgets import QWidget

_DOW_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
_HOURS = [f"{h:02d}" for h in range(24)]

# Colour stops: fraction (0-1) → QColor
_SCALE = [
    (0.00, QColor("#111111")),
    (0.01, QColor("#1a1a2a")),
    (0.20, QColor("#334400")),
    (0.50, QColor("#ff8800")),
    (1.00, QColor("#3fbe6f")),
]


def _lerp_color(frac: float) -> QColor:
    frac = max(0.0, min(1.0, frac))
    for i in range(len(_SCALE) - 1):
        f0, c0 = _SCALE[i]
        f1, c1 = _SCALE[i + 1]
        if frac <= f1:
            t = (frac - f0) / max(f1 - f0, 0.001)
            r = int(c0.red()   + t * (c1.red()   - c0.red()))
            g = int(c0.green() + t * (c1.green() - c0.green()))
            b = int(c0.blue()  + t * (c1.blue()  - c0.blue()))
            return QColor(r, g, b)
    return _SCALE[-1][1]


class QSOHeatmap(QWidget):
    """Paints a 7-row × 24-col colour heatmap of QSO activity.

    Call ``set_data(rows)`` with the output of ``LogDB.qsos_by_hour_dow()``.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._grid: dict[tuple[int, int], int] = {}  # (dow, hr) → count
        self._max_count = 1
        self.setMinimumHeight(120)

    def set_data(self, rows: list[tuple[int, int, int]]) -> None:
        """Update from LogDB.qsos_by_hour_dow() output."""
        self._grid = {(dow, hr): n for dow, hr, n in rows}
        self._max_count = max((n for _, _, n in rows), default=1)
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        W, H = self.width(), self.height()

        label_w = 30
        label_h = 16
        cell_w  = max(6, (W - label_w) // 24)
        cell_h  = max(10, (H - label_h) // 7)
        grid_w  = cell_w * 24
        grid_h  = cell_h * 7

        p.setFont(QFont("", 7))
        p.setPen(QColor("#667788"))

        # Hour labels (top)
        for h in range(24):
            if h % 3 == 0:
                x = label_w + h * cell_w
                p.drawText(QRectF(x, 0, cell_w * 3, label_h),
                           Qt.AlignmentFlag.AlignLeft,
                           f"{h:02d}")

        # Day labels (left) + cells
        for dow in range(7):
            y = label_h + dow * cell_h
            p.setPen(QColor("#667788"))
            p.drawText(QRectF(0, y, label_w - 2, cell_h),
                       Qt.AlignmentFlag.AlignRight |
                       Qt.AlignmentFlag.AlignVCenter,
                       _DOW_LABELS[dow])
            for hr in range(24):
                count = self._grid.get((dow, hr), 0)
                frac  = math.sqrt(count / self._max_count) if count else 0
                col   = _lerp_color(frac)
                rx    = label_w + hr * cell_w
                p.setPen(Qt.PenStyle.NoPen)
                p.fillRect(QRectF(rx + 1, y + 1,
                                  cell_w - 2, cell_h - 2),
                           QBrush(col))
                if count and cell_h >= 12 and cell_w >= 12:
                    p.setPen(QColor(0, 0, 0, 120))
                    p.setFont(QFont("", 6))
                    p.drawText(QRectF(rx + 1, y + 1,
                                      cell_w - 2, cell_h - 2),
                               Qt.AlignmentFlag.AlignCenter,
                               str(count) if count < 100 else "99+")
                    p.setPen(Qt.PenStyle.NoPen)
