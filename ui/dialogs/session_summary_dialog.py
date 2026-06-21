from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
#
# GPL v3 — see LICENSE.
"""
Session Summary dialog.

Shows stats for the current operating session:
  - QSOs worked
  - Bands / modes breakdown
  - New DXCC entities
  - Best DX distance
  - Session duration
"""
from datetime import datetime, timezone

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QGridLayout, QPushButton,
    QDialogButtonBox, QFrame,
)
from PyQt6.QtCore import Qt


def show_session_summary(parent, log_db, session_start: datetime) -> None:
    """Build and exec the session summary dialog."""
    dlg = SessionSummaryDialog(parent, log_db, session_start)
    dlg.exec()


class SessionSummaryDialog(QDialog):
    """Read-only session stats dialog."""

    def __init__(self, parent, log_db, session_start: datetime) -> None:
        super().__init__(parent)
        self.setWindowTitle("Session Summary")
        self.setMinimumWidth(420)
        self._log_db = log_db
        self._start  = session_start
        self._build(session_start)

    # ── build ─────────────────────────────────────────────────────────────

    def _build(self, session_start: datetime) -> None:
        since_iso = session_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            s = self._log_db.session_stats(since_iso)
        except Exception:
            s = {"total": 0, "bands": {}, "modes": {},
                 "new_dxcc": 0, "best_dist_km": None,
                 "best_dist_call": None, "best_dist_band": None}

        now  = datetime.now(timezone.utc)
        dur  = now - session_start
        hrs, rem = divmod(int(dur.total_seconds()), 3600)
        mins = rem // 60
        dur_str = (f"{hrs}h {mins}m" if hrs else f"{mins}m")

        vl = QVBoxLayout(self)
        vl.setSpacing(10)

        # ── header ──────────────────────────────────────────────────────
        hdr = QLabel(f"📋  Operating Session  —  {dur_str}")
        hdr.setStyleSheet("font-size:14px;font-weight:bold;")
        hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vl.addWidget(hdr)
        sub = QLabel(f"Started {session_start.strftime('%H:%Mz %d %b %Y')}")
        sub.setStyleSheet("font-size:10px;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vl.addWidget(sub)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        vl.addWidget(sep)

        # ── headline numbers ─────────────────────────────────────────────
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(6)
        items = [
            ("QSOs",        str(s["total"])),
            ("New DXCC",    str(s["new_dxcc"])),
            ("Bands",       str(len(s["bands"]))),
            ("Modes",       str(len(s["modes"]))),
        ]
        for col, (label, value) in enumerate(items):
            v_lbl = QLabel(value)
            v_lbl.setStyleSheet("font-size:22px;font-weight:bold;")
            v_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            k_lbl = QLabel(label)
            k_lbl.setStyleSheet("font-size:10px;")
            k_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(v_lbl, 0, col)
            grid.addWidget(k_lbl, 1, col)
        vl.addLayout(grid)

        # ── best DX ─────────────────────────────────────────────────────
        if s.get("best_dist_km"):
            km = s["best_dist_km"]
            call = s.get("best_dist_call") or "—"
            band = s.get("best_dist_band") or ""
            band_str = f"  ({band})" if band else ""
            dx_grp = QGroupBox("Best DX")
            dx_l = QVBoxLayout(dx_grp)
            dx_l.addWidget(QLabel(
                f"{call}{band_str}  ·  {km:,.0f} km"))
            vl.addWidget(dx_grp)

        # ── band breakdown ───────────────────────────────────────────────
        if s["bands"]:
            band_grp = QGroupBox("Bands")
            bl = QHBoxLayout(band_grp)
            for band, cnt in list(s["bands"].items())[:8]:
                lbl = QLabel(f"{band}\n{cnt}")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet("font-size:10px;")
                bl.addWidget(lbl)
            vl.addWidget(band_grp)

        # ── mode breakdown ────────────────────────────────────────────────
        if s["modes"]:
            mode_grp = QGroupBox("Modes")
            ml = QHBoxLayout(mode_grp)
            for mode, cnt in list(s["modes"].items())[:8]:
                lbl = QLabel(f"{mode}\n{cnt}")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet("font-size:10px;")
                ml.addWidget(lbl)
            vl.addWidget(mode_grp)

        if s["total"] == 0:
            no_qso = QLabel("No QSOs logged this session yet.")
            no_qso.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_qso.setStyleSheet("font-size:11px;")
            vl.addWidget(no_qso)

        # ── close button ────────────────────────────────────────────────
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        vl.addWidget(bb)
