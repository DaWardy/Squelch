from __future__ import annotations
# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.
"""Squelch -- ui/tx_confirm.py

License-class TX confirmation gate — the UI wiring for core/tx_license.py.

Any code about to key PTT should call `confirm_tx(parent, cfg, freq_hz)`
first and only transmit if it returns True. The check is silent (no dialog,
no delay) for any TX within the operator's amateur privileges. The FIRST time
ever a TX would be outside those privileges (or the operator has chosen
"Other / Emergency"), it blocks with an explicit warning dialog that must be
accepted; once accepted, the acknowledgment is remembered permanently — this
mirrors the one-time acknowledgment pattern in core/authorization.py.

This complements, and does not replace, core/authorization.py's per-band
allow-list gate — that one is the default-deny opt-in-per-band mechanism;
this one is the license-class-privilege / out-of-band tripwire.
"""

from core.tx_license import tx_privilege, TxLicenseDecision

# Shared with Settings → Station's "License Class" combo and BandPlanDialog —
# one canonical value (the combo's exact display text), not a separate key.
# See settings_dialog._load_station/_save_station for the history here.
_CFG_LICENSE_CLASS = "station.license"
_CFG_ACK           = "tx.out_of_band_ack"


def needs_tx_confirmation(cfg, freq_hz: int) -> TxLicenseDecision | None:
    """Pure decision: return the TxLicenseDecision if a warning is due, else None.

    None means TX may proceed silently — either the frequency is within the
    operator's amateur privileges, or the one-time acknowledgment was already
    given previously. No Qt; fully unit-testable.
    """
    license_class = cfg.get(_CFG_LICENSE_CLASS, "Technician") if cfg else "Technician"
    decision = tx_privilege(freq_hz, license_class)
    if not decision.needs_ack:
        return None
    if cfg and cfg.get(_CFG_ACK, False):
        return None
    return decision


def confirm_tx(parent, cfg, freq_hz: int) -> bool:
    """Gate a TX attempt at *freq_hz*. Returns True if TX may proceed.

    Shows a blocking Yes/No warning dialog only when needs_tx_confirmation()
    says one is due; accepting it persists the acknowledgment so it is not
    shown again. Declining returns False and does not persist anything.
    """
    decision = needs_tx_confirmation(cfg, freq_hz)
    if decision is None:
        return True

    from PyQt6.QtWidgets import QMessageBox
    mhz = freq_hz / 1e6
    reply = QMessageBox.warning(
        parent, "Transmit Outside Normal Amateur Privileges",
        f"{decision.label}\n\n"
        f"Frequency: {mhz:.4f} MHz\n"
        f"License class: {decision.license_class}\n\n"
        "This frequency may be outside your amateur radio license privileges "
        "or outside the amateur bands entirely. Verify you are legally "
        "authorized to transmit here before proceeding — the operator is "
        "responsible for complying with applicable regulations.\n\n"
        "This warning is shown once. Transmit anyway?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No)
    if reply == QMessageBox.StandardButton.Yes:
        if cfg:
            cfg.set(_CFG_ACK, True)
            cfg.save()
        return True
    return False
