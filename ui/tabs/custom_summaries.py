from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/tabs/custom_summaries.py

Live "summary" widgets for custom-tab cards, each bound to the SAME singleton
backend the full panel uses. A custom card renders one of these when a factory
is registered for its panel key, otherwise it falls back to the plain
'Open tab →' navigation card.

The point (per the custom-tab design): a custom tab should not clone a heavy
panel or reparent it. It should host a small view/controller that reads/writes
the shared singleton (get_log_db(), get_sdr_manager(), the rig controller, …).
That reflects and drives the real app state with one instance, no redundant
compute, and no hardware conflict.

Add a new panel summary by writing a factory(cfg) -> QWidget and registering it
in SUMMARY_FACTORIES below.
"""

import logging

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QWidget, QGridLayout, QLabel

log = logging.getLogger(__name__)


class _LogSummary(QWidget):
    """Live logbook counters bound to the shared get_log_db() singleton.

    Polls the same database the Log tab writes to, so a QSO logged anywhere in
    the app updates this card within a few seconds — no second LogDB, no copy.
    """

    _ROWS = [
        ("total_qsos",   "QSOs"),
        ("dxcc_worked",  "DXCC"),
        ("was_worked",   "WAS"),
        ("bands_worked", "Bands"),
    ]

    def __init__(self, cfg, parent: QWidget | None = None):
        super().__init__(parent)
        self._cfg = cfg
        grid = QGridLayout(self)
        grid.setContentsMargins(4, 2, 4, 2)
        grid.setSpacing(3)
        self._vals: dict[str, QLabel] = {}
        for i, (key, label) in enumerate(self._ROWS):
            lab = QLabel(label + ":")
            lab.setStyleSheet("font-size:10px;color:#99aabb;")
            val = QLabel("—")
            val.setStyleSheet(
                "font-size:11px;font-weight:bold;color:#3fbe6f;"
                "font-family:'Courier New';")
            val.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(lab, i, 0)
            grid.addWidget(val, i, 1)
            self._vals[key] = val
        self._refresh()
        self._timer = QTimer(self)
        self._timer.setInterval(5000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _refresh(self) -> None:
        try:
            from core.log_db import get_log_db
            s = get_log_db().stats()
            for key, val in self._vals.items():
                val.setText(str(s.get(key, 0)))
        except Exception as e:
            log.debug("log summary refresh failed: %s", e)


def make_log_summary(cfg) -> QWidget:
    return _LogSummary(cfg)


class _LogAwards(QWidget):
    """Live award progress (DXCC / WAS / Grids) from the shared get_log_db()."""

    _ROWS = [
        ("dxcc_worked",  "DXCC",  340),
        ("was_worked",   "WAS",   50),
        ("grids_worked", "Grids", None),
    ]

    def __init__(self, cfg, parent: QWidget | None = None):
        super().__init__(parent)
        self._cfg = cfg
        grid = QGridLayout(self)
        grid.setContentsMargins(4, 2, 4, 2)
        grid.setSpacing(3)
        self._vals: dict[str, tuple] = {}
        for i, (key, label, total) in enumerate(self._ROWS):
            lab = QLabel(label + ":")
            lab.setStyleSheet("font-size:10px;color:#99aabb;")
            val = QLabel("—")
            val.setStyleSheet(
                "font-size:11px;font-weight:bold;color:#3fbe6f;"
                "font-family:'Courier New';")
            val.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(lab, i, 0)
            grid.addWidget(val, i, 1)
            self._vals[key] = (val, total)
        self._refresh()
        self._timer = QTimer(self)
        self._timer.setInterval(5000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _refresh(self) -> None:
        try:
            from core.log_db import get_log_db
            s = get_log_db().stats()
            for key, (val, total) in self._vals.items():
                n = s.get(key, 0)
                val.setText(f"{n}/{total}" if total else str(n))
        except Exception as e:
            log.debug("log awards refresh failed: %s", e)


def make_log_awards(cfg) -> QWidget:
    return _LogAwards(cfg)


class _PropSolar(QWidget):
    """Live solar indices from the shared get_prop_feed() the Propagation tab uses."""

    def __init__(self, cfg, parent: QWidget | None = None):
        super().__init__(parent)
        self._cfg = cfg
        grid = QGridLayout(self)
        grid.setContentsMargins(4, 2, 4, 2)
        grid.setSpacing(3)
        self._vals: dict[str, QLabel] = {}
        for i, (key, label) in enumerate(
                [("sfi", "SFI"), ("ssn", "SSN"), ("k", "K"), ("a", "A")]):
            lab = QLabel(label + ":")
            lab.setStyleSheet("font-size:10px;color:#99aabb;")
            val = QLabel("—")
            val.setStyleSheet(
                "font-size:11px;font-weight:bold;color:#3fbe6f;"
                "font-family:'Courier New';")
            val.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(lab, i, 0)
            grid.addWidget(val, i, 1)
            self._vals[key] = val
        self._refresh()
        self._timer = QTimer(self)
        self._timer.setInterval(60000)   # solar data changes slowly
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _refresh(self) -> None:
        try:
            from network.propagation import get_prop_feed
            s = get_prop_feed().solar()
            self._vals["sfi"].setText(f"{s.sfi:.0f}")
            self._vals["ssn"].setText(str(s.sunspot_num))
            self._vals["k"].setText(f"{s.k_index:.0f}")
            self._vals["a"].setText(f"{s.a_index:.0f}")
        except Exception as e:
            log.debug("solar summary refresh failed: %s", e)


def make_prop_solar(cfg) -> QWidget:
    return _PropSolar(cfg)


# À-la-carte widget catalog: (key, category, label, factory). Each factory
# builds a compact widget bound to the SAME singleton backend the full tab
# uses, so it reflects/drives real app state with no duplication.
WIDGET_CATALOG = [
    ("log.stats",  "Log",         "Statistics",      make_log_summary),
    ("log.awards", "Log",         "Awards progress", make_log_awards),
    ("prop.solar", "Propagation", "Solar indices",   make_prop_solar),
]

_CATALOG_BY_KEY = {e[0]: e for e in WIDGET_CATALOG}


def make_widget(key: str, cfg):
    """Build the catalog widget for *key*, or None (→ plain navigation card).

    Never raises — a broken factory just falls back to the nav card.
    """
    entry = _CATALOG_BY_KEY.get(key)
    if entry is None:
        return None
    try:
        return entry[3](cfg)
    except Exception as e:
        log.debug("widget build failed for %s: %s", key, e)
        return None


# Back-compat alias — custom_tab historically called make_summary().
make_summary = make_widget


def catalog_by_category() -> dict:
    """{category: [(key, label), …]} for building the Add-widget menu."""
    out: dict = {}
    for key, cat, label, _ in WIDGET_CATALOG:
        out.setdefault(cat, []).append((key, label))
    return out


def widget_title(key: str):
    """'Category: Label' display title for a catalog key, or None if unknown."""
    entry = _CATALOG_BY_KEY.get(key)
    if entry is None:
        return None
    return f"{entry[1]}: {entry[2]}"
