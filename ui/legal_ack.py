from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/legal_ack.py

First-run legal-acknowledgment dialog — the UI wiring for core/legal.py.

Call `show_legal_ack(parent, cfg)` once at startup. It returns True if the
disclaimer has already been accepted (no dialog shown) or the user accepts it
now; False only if the user declines. The caller should not proceed into the
app on False. This mirrors the one-time acknowledgment pattern in
ui/tx_confirm.py and core/authorization.py.
"""

from core.legal import needs_legal_ack, record_legal_ack, LEGAL_SUMMARY


def show_legal_ack(parent, cfg) -> bool:
    """Show the one-time disclaimer if it has not been accepted.

    Returns True to proceed (already accepted, or accepted now), False if the
    user declines. Accepting persists the acknowledgment so it is not shown
    again unless the disclaimer version is bumped.
    """
    if not needs_legal_ack(cfg):
        return True

    from PyQt6.QtWidgets import QMessageBox

    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("Squelch — Terms of Use & Legal Disclaimer")
    box.setText("Please read and accept before using Squelch.")
    box.setInformativeText(LEGAL_SUMMARY)
    accept = box.addButton("I Accept", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Quit", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(accept)
    box.exec()

    if box.clickedButton() is accept:
        record_legal_ack(cfg)
        return True
    return False
