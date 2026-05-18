from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
#
# This program is free software: you can redistribute it
# and/or modify it under the terms of the GNU General
# Public License as published by the Free Software
# Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will
# be useful, but WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General
# Public License along with this program. If not, see
# <https://www.gnu.org/licenses/>.
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- winlink/templates.py
ARES/EmComm message templates for Winlink.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class WinlinkMessage:
    to:      str
    subject: str
    body:    str
    cc:      list = field(default_factory=list)


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H%MZ")


def ics213(incident, from_name, from_pos, to_name, to_pos,
           message, reply_to="", my_callsign=""):
    body = f"""ICS-213 GENERAL MESSAGE
{'='*40}
INCIDENT: {incident}
DATE/TIME: {_utcnow()}
TO:   {to_name} / {to_pos}
FROM: {from_name} / {from_pos}

{message}

{'='*40}
REPLY TO: {reply_to or my_callsign}
SENT VIA: Winlink / Squelch"""
    return WinlinkMessage(reply_to or to_name,
                          f"ICS-213: {incident}", body)


def ics214(incident, unit_name, unit_leader, period,
           activities, personnel, my_callsign=""):
    acts = "\n".join(f"{i+1:2d}. {a}"
                     for i, a in enumerate(activities)) or "none"
    pers = "\n".join(f"    {p}" for p in personnel) or "    none"
    body = f"""ICS-214 ACTIVITY LOG
{'='*40}
INCIDENT: {incident}
UNIT: {unit_name}  LEADER: {unit_leader}
PERIOD: {period}   DATE: {_utcnow()}

ACTIVITIES:
{acts}

PERSONNEL:
{pers}

{'='*40}
PREPARED BY: {my_callsign}"""
    return WinlinkMessage("TACTICAL",
                          f"ICS-214: {unit_name} {period}", body)


def winlink_wednesday(my_callsign, my_grid, my_name,
                      my_city, my_state, comments="",
                      gateway_used=""):
    body = f"""Winlink Wednesday Check-In
Date: {_utcnow()}
Callsign: {my_callsign}
Grid: {my_grid}
Name: {my_name}
Location: {my_city}, {my_state}
Gateway: {gateway_used or 'Direct'}
Software: Squelch v0.7.1
{f"Comments: {comments}" if comments else ""}
73 de {my_callsign}"""
    return WinlinkMessage("WW@winlink.org",
                          f"Winlink Wednesday de {my_callsign}",
                          body)


def welfare_message(my_callsign, my_name, to_name,
                    to_email, message):
    body = f"""WELFARE MESSAGE — {_utcnow()}
TO: {to_name}
FROM: {my_name} ({my_callsign})

{message}

Sent via Winlink amateur radio email.
Reply: {my_callsign}@winlink.org"""
    return WinlinkMessage(to_email,
                          f"Welfare: {my_name} is OK",
                          body)


def radiogram(precedence, to_call, to_name, to_address,
              to_phone, message, from_call, from_name):
    words = len(message.split())
    body = f"""NR ___ {precedence} {from_call} {words} RADIO {_utcnow()}
TO: {to_name}
    {to_address}
    {to_phone}

{message.upper()}

{from_name} {from_call} AR"""
    return WinlinkMessage(to_call,
                          f"Radiogram {precedence}: {to_name}",
                          body)


TEMPLATE_LIST = [
    ("ICS-213 General Message",   "Standard EmComm general message"),
    ("ICS-214 Activity Log",      "Operational period documentation"),
    ("ARRL Radiogram",            "NTS standard traffic format"),
    ("Winlink Wednesday Check-in","Weekly participation check-in"),
    ("Welfare Message",           "Safety message to family/friends"),
]
