from __future__ import annotations
"""SMeterWidget — calibrated signal-strength meter.

Replaces the plain QProgressBar with a colour-coded bar that shows:
  • S0-S4  in green  (weak)
  • S5-S7  in yellow (fair)
  • S8-S9  in amber  (strong)
  • S9+    in red    (very strong)

Standard S-unit → dBm mapping used (HF receiver, 50 Ω):
  S9 = -73 dBm; each S-unit below = -6 dB; each 10 dB above S9 = +10 dBm.
"""
import math
from collections import deque
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (QPainter, QPen, QBrush, QColor,
                          QLinearGradient, QFont)
from PyQt6.QtWidgets import QWidget

# Calibrated dBm per S-level (indices 0-13 = S0 through S9+60)
_DBM: list[int] = [
    -127, -121, -115, -109, -103, -97, -91, -85,
    -79,  -73,   -63,  -53,   -33,  -13
]

# Label text per S-level (same as SMETER_LABELS in core/rig.py)
_LABELS: list[str] = [
    "S0","S1","S2","S3","S4","S5","S6","S7",
    "S8","S9","S9+10","S9+20","S9+40","S9+60",
]

# Colour per range
_SEG_COLS = [
    (0,  5,  QColor(63,  190, 111)),   # S0-S4 green
    (5,  8,  QColor(255, 204,  0)),    # S5-S7 yellow
    (8,  10, QColor(255, 140,  0)),    # S8-S9 amber
    (10, 14, QColor(204,  68,  68)),   # S9+   red
]

# Ticks shown on the scale (subset of S levels)
_TICK_LEVELS = {0, 3, 5, 7, 9, 11, 13}


_HISTORY_LEN = 120   # readings kept (one per rig poll, ~30-120 seconds)


class SMeterWidget(QWidget):
    """Horizontal signal-strength bar with S-unit scale, dBm readout,
    and a small rolling signal-history spark-line below the bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._level: int  = 0     # 0-13
        self._dbm:   int  = _DBM[0]
        self._cal_offset: int = 0  # user calibration offset in dB
        self._history: deque = deque(maxlen=_HISTORY_LEN)
        self.setMinimumWidth(140)
        self.setFixedHeight(46)   # extra 18px for history spark-line

    # ── Public API ────────────────────────────────────────────────────────

    def set_level(self, s_level: int, cal_offset: int = 0) -> None:
        """Update the meter and append to history.  s_level: 0-13."""
        self._level      = max(0, min(13, s_level))
        self._cal_offset = cal_offset
        self._history.append(self._level)
        self._dbm        = _DBM[self._level] + cal_offset
        self.update()

    @property
    def label(self) -> str:
        return _LABELS[self._level]

    @property
    def dbm(self) -> int:
        return self._dbm

    # ── Painting ─────────────────────────────────────────────────────────

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        bar_y   = 4
        bar_h   = 12
        scale_y = bar_y + bar_h + 2
        n       = 14
        bar_w   = W - 56   # leave room for dBm label on right

        # Background track
        p.fillRect(0, bar_y, bar_w, bar_h, QBrush(QColor(20, 25, 30)))
        p.setPen(QPen(QColor(40, 50, 60), 1))
        p.drawRect(0, bar_y, bar_w - 1, bar_h - 1)

        # Filled segment — colour-coded by S-range
        for lo, hi, col in _SEG_COLS:
            seg_lo = lo / n * bar_w
            seg_hi = min(hi, self._level + 1) / n * bar_w
            filled  = max(0.0, seg_hi - seg_lo)
            if filled > 0 and self._level >= lo:
                grad = QLinearGradient(seg_lo, 0, seg_lo + filled, 0)
                grad.setColorAt(0.0, col.lighter(130))
                grad.setColorAt(1.0, col)
                p.fillRect(QRectF(seg_lo, bar_y + 1,
                                  filled, bar_h - 2), QBrush(grad))

        # Scale ticks + labels
        p.setFont(QFont("", 6))
        for i in _TICK_LEVELS:
            x = int(i / n * bar_w)
            p.setPen(QColor(80, 100, 120))
            p.drawLine(x, scale_y, x, scale_y + 4)
            p.setPen(QColor(110, 130, 150))
            lbl = _LABELS[i].replace("S9+", "+")
            p.drawText(x - 6, scale_y + 11, lbl)

        # S-unit + dBm readout on right
        col = self._bar_color()
        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(col)
        p.drawText(bar_w + 4, bar_y + 9, self.label)
        p.setFont(QFont("Courier New", 7))
        p.setPen(col.darker(130))
        p.drawText(bar_w + 4, scale_y + 10, f"{self._dbm} dBm")

        # ── Spark-line history chart ──────────────────────────────────────
        if len(self._history) >= 2:
            spark_y  = scale_y + 14   # top of spark area
            spark_h  = H - spark_y - 2
            if spark_h >= 4:
                p.fillRect(0, spark_y, bar_w, spark_h,
                           QBrush(QColor(12, 16, 22)))
                hist = list(self._history)
                n_pts = len(hist)
                step  = bar_w / max(n_pts - 1, 1)
                pts   = []
                for i, lv in enumerate(hist):
                    x = i * step
                    y = spark_y + spark_h - 1 - int(lv / 13 * (spark_h - 2))
                    pts.append(QPointF(x, y))
                # Draw coloured line
                for i in range(len(pts) - 1):
                    mid_lv  = (hist[i] + hist[i + 1]) / 2
                    seg_col = self._bar_color_for(int(mid_lv))
                    p.setPen(QPen(seg_col, 1))
                    p.drawLine(pts[i], pts[i + 1])

    @staticmethod
    def _bar_color_for(level: int) -> QColor:
        if level < 5:
            return QColor(63, 190, 111)
        if level < 8:
            return QColor(255, 204, 0)
        if level < 10:
            return QColor(255, 140, 0)
        return QColor(204, 68, 68)

    def _bar_color(self) -> QColor:
        if self._level < 5:
            return QColor(63, 190, 111)
        if self._level < 8:
            return QColor(255, 204, 0)
        if self._level < 10:
            return QColor(255, 140, 0)
        return QColor(204, 68, 68)
