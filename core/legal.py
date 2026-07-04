# Squelch — RF / SDR signal platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE.

from __future__ import annotations
"""Squelch -- core/legal.py

First-run legal-acknowledgment gate (the pure decision layer for the
disclaimer in DISCLAIMER.md).

Squelch can drive transmit hardware and decode/record RF, so — like the TX
license gate (ui/tx_confirm) and the authorization layer (core/authorization) —
the user must accept a plain-language statement of responsibility once before
use. This module holds only the pure config-backed decision; the dialog is
`ui/legal_ack.py`. Version-stamped so a material change to the disclaimer
re-prompts for acknowledgment.

No Qt, never raises — a broken cfg fails toward "acknowledgment still needed".
"""

import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# Bump when the disclaimer text materially changes → forces re-acknowledgment.
DISCLAIMER_VERSION = 1

_CFG_ACK_VERSION = "legal.ack_version"
_CFG_ACK_TS      = "legal.ack_ts"

# Short in-app summary (the dialog shows this; DISCLAIMER.md is the full text).
LEGAL_SUMMARY = (
    "Squelch is a general-purpose radio / SDR tool. It does NOT authorize you "
    "to transmit, receive, decode, or record any signal — that authorization "
    "comes only from your radio license and the laws where you are.\n\n"
    "• Transmitting without authorization may be illegal. Transmit paths are "
    "default-deny; enabling them does not make any operation lawful.\n"
    "• Laws on receiving, decoding, recording, and sharing communications vary "
    "and can be strict. Use Squelch only for lawful RF research, education, "
    "spectrum monitoring, and interference / transmitter location.\n"
    "• Signal IDs, propagation, and direction finding are estimates and may be "
    "wrong — do not rely on them for safety-of-life or legal decisions.\n"
    "• The software is provided \"as is\", without warranty (GPL v3).\n\n"
    "You accept sole responsibility for the legality of how you use Squelch. "
    "See DISCLAIMER.md for the full terms."
)


def needs_legal_ack(cfg) -> bool:
    """True if the current disclaimer version has not been acknowledged."""
    if cfg is None:
        return True
    try:
        return int(cfg.get(_CFG_ACK_VERSION, 0) or 0) < DISCLAIMER_VERSION
    except Exception:
        return True


def record_legal_ack(cfg) -> None:
    """Persist acceptance of the current disclaimer version. Never raises."""
    if cfg is None:
        return
    try:
        cfg.set(_CFG_ACK_VERSION, DISCLAIMER_VERSION)
        cfg.set(_CFG_ACK_TS, _utcnow())
        cfg.save()
    except Exception as exc:                   # pragma: no cover
        log.debug("record_legal_ack failed: %s", exc)


def legal_ack_status(cfg) -> dict:
    """Diagnostic snapshot of the acknowledgment state."""
    ver = 0
    ts = ""
    if cfg is not None:
        try:
            ver = int(cfg.get(_CFG_ACK_VERSION, 0) or 0)
            ts = cfg.get(_CFG_ACK_TS, "") or ""
        except Exception:
            ver, ts = 0, ""
    return {"acknowledged": ver >= DISCLAIMER_VERSION,
            "version": ver,
            "required_version": DISCLAIMER_VERSION,
            "ts": ts}


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
