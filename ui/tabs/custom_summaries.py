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


# panel_key → factory(cfg) -> QWidget.  Panels without an entry keep the plain
# navigation card.
SUMMARY_FACTORIES = {
    "log": make_log_summary,
}


def make_summary(panel_key: str, cfg):
    """Build a live summary widget for *panel_key*, or None if none registered.

    Never raises — a broken factory just falls back to the navigation card.
    """
    factory = SUMMARY_FACTORIES.get(panel_key)
    if factory is None:
        return None
    try:
        return factory(cfg)
    except Exception:
        return None
