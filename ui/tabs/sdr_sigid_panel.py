from __future__ import annotations
"""Squelch -- ui/tabs/sdr_sigid_panel.py
Signal ID results panel — persistent side panel shown next to the
SDR waterfall when the user right-clicks → Identify Signal.

Replaces the old modal QDialog with a panel that stays open while the
user continues tuning, and provides:
  • Confidence bars per match (colour-coded green/yellow/red)
  • Category badge (Amateur / Aviation / Marine / Military / Utility …)
  • One-click SigID Wiki link per match
  • "Annotate waterfall" button — highlights the matched frequency + BW
  • "Bookmark" button — saves to local signal log
  • Running bookmark log at the bottom (persists across identifications)
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices, QFont
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
    QTextEdit,
)

from core.themes import get_theme

log = logging.getLogger(__name__)

_CATEGORY_COLORS = {
    "amateur":   "#3fbe6f",
    "aviation":  "#4499ff",
    "marine":    "#44ccff",
    "military":  "#cc4444",
    "utility":   "#ffaa44",
    "broadcast": "#cc88ff",
    "satellite": "#44ffcc",
}
_DEFAULT_CAT_COLOR = "#888888"

_BOOKMARK_FILE = Path("assets/signal_bookmarks.json")


def _confidence_color(c: float) -> str:
    if c >= 0.7:
        return "#3fbe6f"
    if c >= 0.4:
        return "#ffaa44"
    return "#cc4444"


def _cat_color(category: str) -> str:
    return _CATEGORY_COLORS.get(category.lower().split("/")[0].strip(),
                                 _DEFAULT_CAT_COLOR)


class _MatchCard(QFrame):
    """One result card: name, confidence bar, badges, action buttons."""

    def __init__(self, match, on_annotate: Callable, on_bookmark: Callable,
                 theme_name: str = "Dark", parent=None):
        super().__init__(parent)
        _t = get_theme(theme_name)
        self._match = match
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            f"QFrame{{background:{_t.bg_alt};border:1px solid {_t.border};"
            f"border-radius:4px;margin:2px;padding:4px;}}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(3)

        # ── Row 1: name + category badge ──────────────────────────────────
        top = QHBoxLayout()
        name_lbl = QLabel(f"<b>{match.name}</b>")
        name_lbl.setStyleSheet(f"color:{_t.fg_primary};font-size:11px;")
        name_lbl.setWordWrap(True)
        top.addWidget(name_lbl, 1)

        if match.category:
            cat_lbl = QLabel(match.category[:18])
            cc = _cat_color(match.category)
            cat_lbl.setStyleSheet(
                f"color:#000;background:{cc};border-radius:3px;"
                f"padding:1px 4px;font-size:9px;font-weight:bold;")
            top.addWidget(cat_lbl)
        root.addLayout(top)

        # ── Row 2: modulation + bandwidth ─────────────────────────────────
        mid = QHBoxLayout()
        mod_lbl = QLabel(match.modulation or "—")
        mod_lbl.setStyleSheet(f"color:{_t.fg_secondary};font-size:10px;")
        mid.addWidget(mod_lbl)
        mid.addStretch()
        bw_lbl = QLabel(f"{match.bandwidth_hz/1e3:.1f} kHz")
        bw_lbl.setStyleSheet(f"color:{_t.accent};font-size:10px;font-family:'Courier New';")
        mid.addWidget(bw_lbl)
        root.addLayout(mid)

        # ── Row 3: confidence bar ─────────────────────────────────────────
        bar_row = QHBoxLayout()
        bar_row.addWidget(QLabel("Confidence:"))
        bar_bg = QFrame()
        bar_bg.setFixedHeight(8)
        bar_bg.setStyleSheet(f"background:{_t.border};border-radius:4px;")
        bar_fg = QFrame(bar_bg)
        bar_fg.setFixedHeight(8)
        pct = max(4, int(match.confidence * 100))
        cc = _confidence_color(match.confidence)
        bar_fg.setStyleSheet(
            f"background:{cc};border-radius:4px;")
        bar_fg.setFixedWidth(max(4, int(180 * match.confidence)))
        bar_row.addWidget(bar_bg, 1)
        pct_lbl = QLabel(f"{pct}%")
        pct_lbl.setStyleSheet(f"color:{cc};font-size:10px;min-width:32px;")
        bar_row.addWidget(pct_lbl)
        root.addLayout(bar_row)

        # ── Row 4: action buttons ─────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        ann_btn = QPushButton("▶ Annotate")
        ann_btn.setFixedHeight(22)
        ann_btn.setToolTip("Highlight this signal on the waterfall")
        ann_btn.setStyleSheet(
            f"QPushButton{{background:{_t.bg_primary};color:{_t.accent};"
            f"border:1px solid {_t.accent};border-radius:3px;font-size:10px;}}"
            f"QPushButton:hover{{background:{_t.accent};color:#000;}}")
        ann_btn.clicked.connect(lambda: on_annotate(match))
        btn_row.addWidget(ann_btn)

        bm_btn = QPushButton("★ Bookmark")
        bm_btn.setFixedHeight(22)
        bm_btn.setToolTip("Save to signal bookmark log")
        bm_btn.setStyleSheet(
            f"QPushButton{{background:{_t.bg_primary};color:{_t.fg_secondary};"
            f"border:1px solid {_t.border};border-radius:3px;font-size:10px;}}"
            f"QPushButton:hover{{background:{_t.header_bg};}}")
        bm_btn.clicked.connect(lambda: on_bookmark(match))
        btn_row.addWidget(bm_btn)

        if match.url:
            wiki_btn = QPushButton("🔗 Wiki")
            wiki_btn.setFixedHeight(22)
            wiki_btn.setToolTip(f"Open: {match.url}")
            wiki_btn.setStyleSheet(
                f"QPushButton{{background:{_t.bg_primary};color:#4499ff;"
                f"border:1px solid #224466;border-radius:3px;font-size:10px;}}"
                f"QPushButton:hover{{color:#88ccff;}}")
            wiki_btn.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl(match.url)))
            btn_row.addWidget(wiki_btn)

        btn_row.addStretch()
        root.addLayout(btn_row)

        # ── Description (collapsed, shown if not empty) ───────────────────
        if match.description:
            desc = QLabel(match.description[:180] +
                          ("…" if len(match.description) > 180 else ""))
            desc.setWordWrap(True)
            desc.setStyleSheet(
                f"color:{_t.fg_secondary};font-size:9px;"
                f"border-top:1px solid {_t.border};padding-top:3px;")
            root.addWidget(desc)


class SignalIDPanel(QWidget):
    """
    Persistent signal ID results panel.
    Call show_results(matches, bw_hz, freq_hz) to populate.
    Signals: on_annotate(match), on_bookmark(match) — set by caller.
    """

    def __init__(self, on_annotate: Callable, on_bookmark: Callable,
                 cfg=None, parent=None):
        super().__init__(parent)
        self._on_annotate = on_annotate
        self._on_bookmark = on_bookmark
        self._cfg = cfg
        self._theme = cfg.get("ui.theme", "Dark") if cfg else "Dark"
        self._build()

    # ── Public API ────────────────────────────────────────────────────────

    def show_results(self, matches: list, bandwidth_hz: int,
                     freq_hz: int) -> None:
        """Populate the panel with a new set of results."""
        _t = get_theme(self._theme)
        bw_k = bandwidth_hz / 1e3
        fq_m = freq_hz / 1e6

        self._header_lbl.setText(
            f"Signal ID — {fq_m:.3f} MHz  BW {bw_k:.1f} kHz")
        self._source_lbl.setText(
            f"{len(matches)} match{'es' if len(matches) != 1 else ''} "
            f"from Artemis database")

        # Clear old cards
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not matches:
            no_match = QLabel(
                "No match found.\n\nTry a wider bandwidth selection\n"
                "or adjust the frequency.")
            no_match.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_match.setStyleSheet(f"color:{_t.fg_secondary};padding:16px;")
            self._cards_layout.addWidget(no_match)
        else:
            for match in matches:
                card = _MatchCard(
                    match,
                    on_annotate=self._on_annotate,
                    on_bookmark=self._on_bookmark,
                    theme_name=self._theme,
                )
                self._cards_layout.addWidget(card)
        self._cards_layout.addStretch()

        # Show panel if hidden
        self.show()

    def add_bookmark_entry(self, match, freq_hz: int) -> None:
        """Add a line to the bookmark log at the bottom."""
        ts = datetime.now(timezone.utc).strftime("%H:%Mz")
        fq = f"{freq_hz/1e6:.3f}"
        item = QListWidgetItem(
            f"{ts}  {fq} MHz  {match.name}  [{match.modulation}]")
        item.setForeground(QColor(_confidence_color(match.confidence)))
        self._bm_list.insertItem(0, item)
        # Keep max 50 entries visible
        while self._bm_list.count() > 50:
            self._bm_list.takeItem(self._bm_list.count() - 1)

    # ── Build ─────────────────────────────────────────────────────────────

    def _build(self) -> None:
        _t = get_theme(self._theme)
        self.setMinimumWidth(220)
        self.setMaximumWidth(340)
        self.setStyleSheet(
            f"QWidget{{background:{_t.bg_primary};color:{_t.fg_primary};}}"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # Header
        hdr = QHBoxLayout()
        self._header_lbl = QLabel("Signal ID")
        self._header_lbl.setStyleSheet(
            f"color:{_t.accent};font-weight:bold;font-size:11px;")
        hdr.addWidget(self._header_lbl, 1)
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(18, 18)
        close_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_t.fg_secondary};"
            f"border:none;font-size:10px;}}"
            f"QPushButton:hover{{color:{_t.fg_primary};}}")
        close_btn.clicked.connect(self.hide)
        hdr.addWidget(close_btn)
        root.addLayout(hdr)

        self._source_lbl = QLabel("")
        self._source_lbl.setStyleSheet(
            f"color:{_t.fg_secondary};font-size:9px;")
        root.addWidget(self._source_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{_t.border};")
        root.addWidget(sep)

        # Scrollable match cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        cards_w = QWidget()
        self._cards_layout = QVBoxLayout(cards_w)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(4)
        scroll.setWidget(cards_w)
        root.addWidget(scroll, 1)

        # Bookmark log
        bm_hdr = QLabel("Bookmarks")
        bm_hdr.setStyleSheet(
            f"color:{_t.fg_secondary};font-size:9px;font-weight:bold;"
            f"border-top:1px solid {_t.border};padding-top:4px;")
        root.addWidget(bm_hdr)

        self._bm_list = QListWidget()
        self._bm_list.setFixedHeight(90)
        self._bm_list.setStyleSheet(
            f"QListWidget{{background:{_t.bg_alt};border:none;"
            f"font-family:'Courier New';font-size:9px;}}")
        root.addWidget(self._bm_list)
