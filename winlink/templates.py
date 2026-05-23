from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- winlink/templates.py
Comprehensive Winlink message templates.

Template categories:
  EmComm:     ICS-213, ICS-214, ICS-309 (comms log),
              Red Cross Welfare, ARRL Radiogram,
              FEMA Damage Assessment
  Check-in:   Winlink Wednesday, NTS Net, ARES Check-in
  P2P:        Peer-to-peer message, position report,
              relay request
  General:    Plain message, position + status
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class WinlinkMessage:
    """A complete Winlink message ready to send."""
    to:          str
    subject:     str
    body:        str
    cc:          list = field(default_factory=list)
    attachments: list = field(default_factory=list)
    msg_type:    str  = "STANDARD"   # STANDARD / P2P / RELAY

    @property
    def header_block(self) -> str:
        """Standard Winlink header fields."""
        return (f"To: {self.to}\n"
                f"Cc: {', '.join(self.cc)}\n"
                f"Subject: {self.subject}\n"
                f"Date: {_utcnow()}\n")


@dataclass
class TemplateCategory:
    name:        str
    icon:        str
    description: str
    templates:   list


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H%MZ")

def _date() -> str:
    return datetime.now(timezone.utc).strftime(
        "%Y-%m-%d")

def _time() -> str:
    return datetime.now(timezone.utc).strftime(
        "%H%MZ")


# ── EmComm Templates ─────────────────────────────────────────────────────

def ics213(incident="", from_name="", from_pos="",
           to_name="", to_pos="", message="",
           reply_to="", my_callsign="") -> WinlinkMessage:
    """ICS-213 General Message Form."""
    body = f"""ICS 213 - GENERAL MESSAGE
{'='*50}
INCIDENT NAME: {incident or '[INCIDENT NAME]'}
DATE: {_date()}    TIME: {_time()}

TO:       {to_name or '[Name/Position]'}
POSITION: {to_pos or '[Position/Title]'}

FROM:     {from_name or '[Name/Position]'}
POSITION: {from_pos or '[Position/Title]'}
CALLSIGN: {my_callsign or '[CALLSIGN]'}

MESSAGE:
{message or '[Enter message here]'}

{'─'*50}
REPLY (if applicable):



{'─'*50}
Operator Signature: _______________________
Date/Time of Reply: {_date()} ________Z

Sent via Winlink — {my_callsign}"""
    return WinlinkMessage(
        to      = reply_to or "WINLINK",
        subject = f"ICS-213 - {incident or 'GENERAL'} - {my_callsign}",
        body    = body)


def ics214(incident="", op_period="", unit_name="",
           unit_leader="", resources: list = None,
           activities: list = None,
           my_callsign="") -> WinlinkMessage:
    """ICS-214 Activity Log."""
    res_block = ""
    if resources:
        res_block = "\n".join(
            f"  {r}" for r in resources)
    else:
        res_block = "  [List personnel/resources]"

    act_block = ""
    if activities:
        act_block = "\n".join(
            f"  {_time()}  {a}" for a in activities)
    else:
        act_block = f"  {_time()}  [Activity description]\n  {_time()}  "

    body = f"""ICS 214 - ACTIVITY LOG
{'='*50}
INCIDENT NAME: {incident or '[INCIDENT NAME]'}
OPERATIONAL PERIOD: {op_period or f'{_date()} {_time()} - ________'}
UNIT NAME/DESIGNATOR: {unit_name or '[Unit/Designation]'}
UNIT LEADER: {unit_leader or '[Name/Title]'}
CALLSIGN: {my_callsign or '[CALLSIGN]'}

RESOURCES ASSIGNED:
{res_block}

ACTIVITY LOG:
TIME    NOTABLE ACTIVITIES
{act_block}

PREPARED BY: {my_callsign}
DATE/TIME: {_date()} {_time()}

Sent via Winlink — {my_callsign}"""
    return WinlinkMessage(
        to      = "WINLINK",
        subject = f"ICS-214 - {incident or 'ACTIVITY LOG'} - {my_callsign}",
        body    = body)


def ics309(incident="", period_from="", period_to="",
           log_entries: list = None,
           my_callsign="") -> WinlinkMessage:
    """ICS-309 Communications Log."""
    entries = log_entries or [
        "[TIME]  [STATION]  [MSG SUMMARY]"]
    log_block = "\n".join(
        f"  {e}" for e in entries)
    body = f"""ICS 309 - COMMUNICATIONS LOG
{'='*50}
INCIDENT: {incident or '[INCIDENT NAME]'}
PERIOD:   {period_from or _date()} to {period_to or '________'}
OPERATOR: {my_callsign or '[CALLSIGN]'}

TIME     STATION       MESSAGE SUMMARY
{'─'*50}
{log_block}

PREPARED BY: {my_callsign}
DATE/TIME:   {_date()} {_time()}

Sent via Winlink — {my_callsign}"""
    return WinlinkMessage(
        to      = "WINLINK",
        subject = f"ICS-309 COMMS LOG - {incident or 'LOG'} - {my_callsign}",
        body    = body)


def radiogram(to_name="", to_city="", to_state="",
              to_phone="", precedence="ROUTINE",
              handling_inst="", message="",
              from_name="", my_callsign="",
              check=0) -> WinlinkMessage:
    """ARRL NTS Radiogram format."""
    body = f"""NATIONAL TRAFFIC SYSTEM RADIOGRAM
{'='*50}
NUMBER: _______    PRECEDENCE: {precedence}
HANDLING: {handling_inst or 'HXG'}
STATION OF ORIGIN: {my_callsign}    DATE: {_date()}
CHECK: {check or len(message.split())}

TO: {to_name or '[NAME]'}
   {to_city or '[CITY]'}, {to_state or '[STATE]'}
   TEL: {to_phone or '[PHONE]'}

MESSAGE:
{message or '[Enter message text — count each word for CHECK]'}

{'─'*50}
FROM: {from_name or '[Sender Name]'}
SENT BY: {my_callsign}
DATE/TIME: {_date()} {_time()}

73 de {my_callsign}
Sent via Winlink"""
    return WinlinkMessage(
        to      = to_phone or "WINLINK",
        subject = f"RADIOGRAM {precedence} - {to_name or 'NTS'} - {my_callsign}",
        body    = body)


def welfare(to_name="", to_address="", to_city="",
            to_state="", to_zip="", from_name="",
            message="", my_callsign="") -> WinlinkMessage:
    """American Red Cross welfare / health-and-welfare message."""
    body = f"""WELFARE MESSAGE
{'='*50}
DATE: {_date()}    TIME: {_time()}
CALLSIGN: {my_callsign or '[CALLSIGN]'}

TO: {to_name or '[RECIPIENT NAME]'}
    {to_address or '[STREET ADDRESS]'}
    {to_city or '[CITY]'}, {to_state or '[ST]'} {to_zip or '[ZIP]'}

FROM: {from_name or '[YOUR NAME]'}

MESSAGE:
{message or '[Message — keep brief, welfare info only]'}

{'─'*50}
This message was sent via amateur radio emergency
communications (Winlink). Reply via email if able.
Operator: {my_callsign}"""
    return WinlinkMessage(
        to      = "WINLINK",
        subject = f"WELFARE - {to_name or 'WELFARE MSG'} - {my_callsign}",
        body    = body)


def fema_damage(location="", incident_type="",
                damage_level="", description="",
                my_callsign="") -> WinlinkMessage:
    """FEMA damage assessment report."""
    body = f"""DAMAGE ASSESSMENT REPORT
{'='*50}
DATE/TIME: {_date()} {_time()}
OPERATOR:  {my_callsign or '[CALLSIGN]'}

LOCATION:      {location or '[Address / GPS coords]'}
INCIDENT TYPE: {incident_type or '[Fire / Flood / Wind / Other]'}
DAMAGE LEVEL:  {damage_level or '[None / Minor / Major / Destroyed]'}

DESCRIPTION:
{description or '[Describe damage observed]'}

IMMEDIATE NEEDS: ________________________________
ROAD ACCESS:     ________________________________
UTILITIES:       Power __ Water __ Gas __

REPORTED BY: {my_callsign}
TIME:        {_time()}

Sent via Winlink — {my_callsign}"""
    return WinlinkMessage(
        to      = "WINLINK",
        subject = f"DAMAGE RPT - {location or 'ASSESSMENT'} - {my_callsign}",
        body    = body)


# ── Check-in Templates ────────────────────────────────────────────────────

def winlink_wednesday(my_callsign="", grid="",
                      location="", comments="") -> WinlinkMessage:
    """Winlink Wednesday check-in."""
    body = f"""WINLINK WEDNESDAY CHECK-IN
{'='*50}
CALLSIGN:  {my_callsign or '[CALLSIGN]'}
DATE/TIME: {_date()} {_time()}
GRID:      {grid or '[GRID SQUARE]'}
LOCATION:  {location or '[City, State]'}

GATEWAY USED:  [GATEWAY CALLSIGN]
MODE:          [VARA HF / VARA FM / WINMOR]
FREQUENCY:     [MHz]

EQUIPMENT:
  Radio:    [RIG MODEL]
  Antenna:  [ANTENNA TYPE]
  Power:    [WATTS]

COMMENTS: {comments or 'Routine weekly check-in.'}

73 de {my_callsign}"""
    return WinlinkMessage(
        to      = "QTH@WINLINK.ORG",
        subject = f"Winlink Wednesday - {my_callsign} - {_date()}",
        body    = body)


def ares_checkin(my_callsign="", name="", grid="",
                 location="", served_agency="",
                 availability="Available",
                 training_hours=0) -> WinlinkMessage:
    """ARES/RACES monthly check-in."""
    body = f"""ARES/RACES CHECK-IN
{'='*50}
CALLSIGN:       {my_callsign or '[CALLSIGN]'}
NAME:           {name or '[NAME]'}
GRID:           {grid or '[GRID]'}
LOCATION:       {location or '[City, State]'}
SERVED AGENCY:  {served_agency or '[Agency / None]'}
DATE/TIME:      {_date()} {_time()}

STATUS:
  Availability:   {availability}
  Training Hours: {training_hours} (this month)
  Go-Kit Ready:   [YES / NO]
  Winlink Ready:  YES

EQUIPMENT ON AIR:
  HF:   [RIG / POWER / ANTENNA]
  VHF:  [RIG / POWER / ANTENNA]

COMMENTS:


73 de {my_callsign}"""
    return WinlinkMessage(
        to      = "WINLINK",
        subject = f"ARES CHECK-IN - {my_callsign} - {_date()}",
        body    = body)


def nts_net_checkin(my_callsign="", name="",
                    location="", traffic: list = None) -> WinlinkMessage:
    """NTS net check-in with traffic listing."""
    traffic_block = ""
    if traffic:
        traffic_block = "\n".join(
            f"  {t}" for t in traffic)
    else:
        traffic_block = "  None"
    body = f"""NTS NET CHECK-IN
{'='*50}
CALLSIGN: {my_callsign or '[CALLSIGN]'}
NAME:     {name or '[NAME]'}
LOCATION: {location or '[City, State]'}
DATE:     {_date()} {_time()}

TRAFFIC FOR DELIVERY:
{traffic_block}

COMMENTS:


73 de {my_callsign}"""
    return WinlinkMessage(
        to      = "WINLINK",
        subject = f"NTS CHECK-IN - {my_callsign}",
        body    = body)


# ── P2P and General Templates ─────────────────────────────────────────────

def p2p_message(to_callsign="", message="",
                my_callsign="") -> WinlinkMessage:
    """Peer-to-peer direct message between stations."""
    body = f"""{'='*50}
FROM: {my_callsign or '[YOUR CALLSIGN]'}
TO:   {to_callsign or '[THEIR CALLSIGN]'}
DATE: {_date()} {_time()}
TYPE: PEER-TO-PEER

{message or '[Enter your message here]'}

{'─'*50}
73 de {my_callsign or '[CALLSIGN]'}
Sent via Winlink P2P"""
    return WinlinkMessage(
        to      = to_callsign or "CALLSIGN@WINLINK.ORG",
        subject = f"P2P - {my_callsign} to {to_callsign} - {_date()}",
        body    = body,
        msg_type= "P2P")


def position_report(my_callsign="", grid="",
                    lat=0.0, lon=0.0,
                    altitude_ft=0,
                    speed_mph=0, heading=0,
                    status="Normal", comments="") -> WinlinkMessage:
    """Station position and status report."""
    coord_str = ""
    if lat or lon:
        coord_str = (f"\nCOORDS:   {lat:.4f}N "
                     f"{abs(lon):.4f}{'W' if lon < 0 else 'E'}")
    body = f"""POSITION REPORT
{'='*50}
CALLSIGN: {my_callsign or '[CALLSIGN]'}
DATE/TIME:{_date()} {_time()}

POSITION:
  GRID:     {grid or '[GRID SQUARE]'}{coord_str}
  ALTITUDE: {altitude_ft or '—'} ft MSL

MOVEMENT:
  SPEED:    {speed_mph or '0'} mph
  HEADING:  {heading or '—'}°

STATUS:     {status}
COMMENTS:   {comments or '—'}

73 de {my_callsign}"""
    return WinlinkMessage(
        to      = "WINLINK",
        subject = f"POSRPT - {my_callsign} - {grid or 'POSITION'}",
        body    = body)


def relay_request(to_callsign="", relay_callsign="",
                  message="", my_callsign="") -> WinlinkMessage:
    """Ask a relay station to forward a message."""
    body = f"""RELAY REQUEST
{'='*50}
FROM:           {my_callsign or '[YOUR CALLSIGN]'}
FINAL DEST:     {to_callsign or '[DESTINATION CALLSIGN]'}
RELAY VIA:      {relay_callsign or '[RELAY CALLSIGN]'}
DATE/TIME:      {_date()} {_time()}

Please relay the following message to {to_callsign}:
{'─'*50}
{message or '[Message to relay]'}
{'─'*50}

73 de {my_callsign}"""
    return WinlinkMessage(
        to      = relay_callsign or "RELAY@WINLINK.ORG",
        subject = f"RELAY REQUEST via {relay_callsign} to {to_callsign}",
        body    = body,
        msg_type= "RELAY")


def plain_message(to="", subject="", body_text="",
                  my_callsign="") -> WinlinkMessage:
    """Plain Winlink message — no specific format."""
    body = f"""{body_text or '[Your message here]'}

73 de {my_callsign or '[CALLSIGN]'}"""
    return WinlinkMessage(
        to      = to or "WINLINK",
        subject = subject or f"MSG - {my_callsign} - {_date()}",
        body    = body)


# ── Template catalog ──────────────────────────────────────────────────────

TEMPLATE_CATEGORIES = [
    TemplateCategory(
        name="EmComm",
        icon="🚨",
        description="Emergency communications forms",
        templates=[
            ("ICS-213 General Message",
             ics213,
             "Standard ICS general message form"),
            ("ICS-214 Activity Log",
             ics214,
             "Personnel and activity log"),
            ("ICS-309 Communications Log",
             ics309,
             "Operator communications log"),
            ("ARRL NTS Radiogram",
             radiogram,
             "National Traffic System message"),
            ("Red Cross Welfare Message",
             welfare,
             "Health and welfare inquiry"),
            ("FEMA Damage Assessment",
             fema_damage,
             "Field damage assessment report"),
        ]
    ),
    TemplateCategory(
        name="Check-in",
        icon="✅",
        description="Net and activity check-ins",
        templates=[
            ("Winlink Wednesday Check-in",
             winlink_wednesday,
             "Weekly Winlink Wednesday test"),
            ("ARES/RACES Check-in",
             ares_checkin,
             "Monthly ARES/RACES activity report"),
            ("NTS Net Check-in",
             nts_net_checkin,
             "National Traffic System net check-in"),
        ]
    ),
    TemplateCategory(
        name="P2P / Direct",
        icon="📡",
        description="Peer-to-peer and direct messages",
        templates=[
            ("P2P Direct Message",
             p2p_message,
             "Peer-to-peer message to a specific station"),
            ("Position Report",
             position_report,
             "GPS position and status update"),
            ("Relay Request",
             relay_request,
             "Ask a station to relay your message"),
        ]
    ),
    TemplateCategory(
        name="General",
        icon="✉",
        description="Plain messages and general use",
        templates=[
            ("Plain Message",
             plain_message,
             "No specific format — free text"),
        ]
    ),
]

# Flat list for compatibility
TEMPLATE_LIST = [
    t for cat in TEMPLATE_CATEGORIES
    for t in cat.templates]
