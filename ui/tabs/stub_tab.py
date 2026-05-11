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

"""
Squelch -- ui/tabs/stub_tab.py
Placeholder tabs for unbuilt chunks. Shows planned features.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt

STUBS = {
    "modes": {
        "title": "Modes — FT8 / FT4 / WSPR / JS8 / PSK31 / RTTY / CW / SSTV",
        "chunk": 2,
        "features": [
            "FT8 and FT4 full auto-sequence engine (WSJT-X equivalent)",
            "15s / 7.5s cycle timer with visual countdown",
            "Decode list: callsign / grid / SNR / DT / distance / bearing / DXCC",
            "WSJT-X style band + frequency selector per mode",
            "Smart TX frequency selection — avoids occupied slots",
            "Priority calling queue with target region / DXCC filter",
            "Auto CQ with configurable repeat and halt-after-QSO",
            "WSPR beacon with background TX duty cycle control",
            "JS8Call keyboard-to-keyboard messaging (TCP API)",
            "PSK31 / RTTY / CW / SSTV via Fldigi XML-RPC",
            "SQLite QSO log + ADIF export + LoTW queue + QRZ queue",
            "Duplicate QSO detection with color-coded decode list",
            "QRZ.com callsign lookup on decoded stations",
            "Awards tracking: DXCC / WAS / grids worked",
        ],
    },
    "bandcond": {
        "title": "Band Conditions — PSKReporter + Propagation + Greyline",
        "chunk": "3 + 4",
        "features": [
            "PSKReporter live world map — who hears you, who you hear",
            "Filter spots by band, mode, and time window",
            "Great circle path display with distance and bearing",
            "Live NOAA solar data: SFI, K-index, A-index",
            "VOACAP band predictions by target region",
            "WSPRnet real-spot-derived band condition display",
            "Greyline overlay with enhanced path highlighting",
            "Recommended band and frequency by time of day and conditions",
            "Solar cycle position indicator",
            "Estimated MUF from live WSPR spot data",
        ],
    },
    "sdr": {
        "title": "SDR — Waterfall / Spectrum / Scanner / IQ / Traffic",
        "chunk": 5,
        "features": [
            "Real-time FFT waterfall — RTL-SDR, B210, RSP series, HackRF, LimeSDR, Airspy",
            "Full spectrum analyzer with peak hold and average",
            "AM / FM wide / FM narrow / USB / LSB / CW demodulator",
            "Frequency scanner: sweep, channel list, band, RadioReference-fed",
            "IQ recorder and playback (SigMF format)",
            "ADS-B live aircraft tracking with map (dump1090-fa)",
            "FAA Remote ID drone monitor (open standard decode)",
            "NOAA APT weather satellite decoder (137 MHz)",
            "Artemis / SigID Wiki signal identification helper",
            "Signal markers from RadioReference and amateur band plan",
            "TX mode for capable hardware (HackRF, BladeRF, PlutoSDR)",
            "Click waterfall to tune IC-7100 or SDR TX frequency",
        ],
    },
    "digital": {
        "title": "Digital Monitor — P25 / DMR / NXDN / YSF / D-STAR",
        "chunk": 6,
        "features": [
            "P25 Phase 1 and Phase 2 decode (OP25)",
            "DMR Tier I/II/III decode (DSD+)",
            "NXDN, YSF/C4FM, D-STAR decode (DSD+)",
            "Live talkgroup activity: WACN / System ID / NAC / TG / BER",
            "Voice channel follower for trunked systems",
            "RFDF foxhunt mode — signal strength + GPS bearing map",
            "Protocol explainer panel — educational breakdown of signaling",
            "Legal and ethics notice per protocol type",
        ],
    },
    "localrf": {
        "title": "Local RF — Radio Reference + RepeaterBook + APRS",
        "chunk": "7 + 9",
        "features": [
            "RadioReference Premium API — local trunked systems and frequencies",
            "RepeaterBook nearest HAM repeater search",
            "Location: GPS / IC-7100 GPS / grid / ZIP / city / MGRS",
            "Search history with one-click recall",
            "HAM repeater list with auto-tune to IC-7100",
            "P25 / DMR trunked system browser with TG follow",
            "Click any entry to tune SDR waterfall",
            "Auto-refresh when grid changes (mobile / traveling ops)",
            "APRS position beaconing via IC-7100 built-in GPS",
            "APRS-IS iGate connection",
            "Live map of nearby APRS stations",
            "Station-to-station APRS messaging",
        ],
    },
    "winlink": {
        "title": "Winlink / VARA — Email Over Radio",
        "chunk": 8,
        "features": [
            "VARA HF and VARA FM TCP socket control",
            "Auto-launch VARA in background",
            "Automated VB-Cable audio routing",
            "Compose / send / receive Winlink messages",
            "ARES EmComm template library (ICS-213, ICS-214, etc.)",
            "Winlink Wednesday net check-in templates (w4akh.net)",
            "RMS gateway selection by band and distance",
            "Email to / from students via Winlink addresses",
            "Guest / student operator identification built in",
            "Nearest repeater quick lookup for VHF Winlink",
        ],
    },
    "help": {
        "title": "Help & Documentation",
        "chunk": 10,
        "features": [
            "Getting started and hardware setup guide",
            "Rig control, Hamlib, and COM port troubleshooting",
            "SDR driver installation by hardware type",
            "FT8 / digital modes operating guide",
            "WSPR propagation guide",
            "Digital protocol monitoring (P25/DMR/NXDN) — legal and technical",
            "Winlink / VARA setup and EmComm template guide",
            "APRS and RadioReference setup",
            "Propagation and solar data explained",
            "Guest and student operator identification (FCC Part 97.105)",
            "Legal and ethics — monitoring laws by protocol type",
            "Instructor lab guide with exercises and learning objectives",
        ],
    },
}


class StubTab(QWidget):
    def __init__(self, label: str, key: str, parent=None):
        super().__init__(parent)
        info     = STUBS.get(key, {})
        title    = info.get("title", label.strip())
        chunk    = info.get("chunk", "?")
        features = info.get("features", [])
        self._build(title, chunk, features)

    def _build(self, title: str, chunk, features: list):
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 24)
        root.setSpacing(8)

        t = QLabel(title)
        t.setStyleSheet(
            "color:#3fbe6f;font-size:15px;font-weight:bold;")
        root.addWidget(t)

        badge = QLabel(f"Chunk {chunk}  —  In development")
        badge.setStyleSheet(
            "color:#555;font-size:11px;background:#161616;"
            "border:1px solid #222;border-radius:4px;"
            "padding:3px 10px;")
        badge.setFixedHeight(24)
        root.addWidget(badge)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color:#1a1a1a;")
        root.addWidget(div)

        if features:
            lbl = QLabel("Planned features:")
            lbl.setStyleSheet(
                "color:#555;font-size:11px;font-weight:bold;")
            root.addWidget(lbl)
            for f in features:
                row = QLabel(f"  ✦  {f}")
                row.setStyleSheet("color:#444;font-size:11px;")
                root.addWidget(row)

        root.addStretch()

        note = QLabel(
            "Rig Control is fully functional — connect your IC-7100 there.  "
            "Remaining tabs build out in subsequent chunks.")
        note.setWordWrap(True)
        note.setStyleSheet(
            "color:#2a2a2a;font-size:10px;font-style:italic;")
        root.addWidget(note)
