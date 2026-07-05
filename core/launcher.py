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

"""
Squelch -- core/launcher.py
External software launcher.
Auto-detects installed programs on startup.
Provides launch buttons for all integrated software.
Validates paths before launching.
"""

import sys
import shutil
import logging
import subprocess
from pathlib import Path
from core.validator import ALLOWED_EXECUTABLES
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

IS_WINDOWS = sys.platform == "win32"
IS_LINUX   = sys.platform.startswith("linux")


@dataclass
class AppDef:
    """Definition of an external application."""
    key:          str           # config key e.g. "paths.wsjtx"
    name:         str           # display name
    description:  str           # one-line description
    category:     str           # "digital" / "sdr" / "winlink" / "programming"
    exe_name:     str           # executable filename
    common_paths: list          # common Windows install paths
    linux_paths:  list          # common Linux paths
    download_url: str           # where to get it
    download_note: str          = ""
    args:         list          = field(default_factory=list)
    required:     bool          = False
    tab:          str           = ""  # which tab uses this


# All external applications Squelch integrates with
APPS: list[AppDef] = [

    AppDef(
        key          = "paths.rigctld",
        name         = "rigctld (Hamlib)",
        description  = "CAT rig control — required for all rig control",
        category     = "rig",
        exe_name     = "rigctld",
        common_paths = [
            r"C:\hamlib\bin\rigctld.exe",
            r"C:\Program Files\Hamlib\bin\rigctld.exe",
        ],
        linux_paths  = [
            "/usr/bin/rigctld",
            "/usr/local/bin/rigctld",
        ],
        download_url  = "https://github.com/Hamlib/Hamlib/releases",
        download_note = "Extract to C:\\hamlib, add C:\\hamlib\\bin to PATH",
        required      = True,
        tab           = "rig",
    ),

    AppDef(
        key          = "paths.wsjtx",
        name         = "WSJT-X",
        description  = "FT8, FT4, WSPR, JS8 weak signal digital modes",
        category     = "digital",
        exe_name     = "wsjtx",
        common_paths = [
            r"C:\Program Files\WSJT-X\bin\wsjtx.exe",
            r"C:\Program Files (x86)\WSJT-X\bin\wsjtx.exe",
        ],
        linux_paths  = [
            "/usr/bin/wsjtx",
            "/usr/local/bin/wsjtx",
            "/opt/wsjtx/bin/wsjtx",
        ],
        download_url  = "https://wsjt.sourceforge.io/wsjtx.html",
        tab           = "modes",
    ),

    AppDef(
        key          = "paths.fldigi",
        name         = "Fldigi",
        description  = "PSK31, RTTY, CW, SSTV, Olivia digital modes",
        category     = "digital",
        exe_name     = "fldigi",
        common_paths = [
            r"C:\Program Files\fldigi\fldigi.exe",
            r"C:\Program Files (x86)\fldigi\fldigi.exe",
        ],
        linux_paths  = [
            "/usr/bin/fldigi",
            "/usr/local/bin/fldigi",
        ],
        download_url  = "https://sourceforge.net/projects/fldigi/",
        tab           = "modes",
    ),

    AppDef(
        key          = "paths.js8call",
        name         = "JS8Call",
        description  = "JS8 keyboard messaging and store-and-forward",
        category     = "digital",
        exe_name     = "js8call",
        common_paths = [
            r"C:\Program Files\JS8Call\js8call.exe",
            r"C:\Program Files (x86)\JS8Call\js8call.exe",
        ],
        linux_paths  = [
            "/usr/bin/js8call",
            "/usr/local/bin/js8call",
        ],
        download_url  = "https://js8call.com/",
        tab           = "modes",
    ),

    AppDef(
        key          = "paths.vara_hf",
        name         = "VARA HF",
        description  = "Winlink HF modem (free/paid license)",
        category     = "winlink",
        exe_name     = "VARAHF",
        common_paths = [
            r"C:\VARA HF\VARAHF.exe",
            r"C:\VARA\VARAHF.exe",
            r"C:\Program Files\VARA HF\VARAHF.exe",
        ],
        linux_paths  = [],   # Wine only on Linux
        download_url  = "https://rosmodem.wordpress.com/",
        download_note = "Free version available. Full speed requires paid license.",
        tab           = "winlink",
    ),

    AppDef(
        key          = "paths.vara_fm",
        name         = "VARA FM",
        description  = "Winlink VHF/UHF modem",
        category     = "winlink",
        exe_name     = "VARAFM",
        common_paths = [
            r"C:\VARA FM\VARAFM.exe",
            r"C:\Program Files\VARA FM\VARAFM.exe",
        ],
        linux_paths  = [],
        download_url  = "https://rosmodem.wordpress.com/",
        tab           = "winlink",
    ),

    AppDef(
        key          = "paths.pat",
        name         = "Pat (Winlink)",
        description  = "Open source cross-platform Winlink client",
        category     = "winlink",
        exe_name     = "pat",
        common_paths = [
            r"C:\Program Files\Pat\pat.exe",
            r"C:\Users\%USERNAME%\AppData\Local\pat\pat.exe",
        ],
        linux_paths  = [
            "/usr/bin/pat",
            "/usr/local/bin/pat",
            str(Path.home() / "go/bin/pat"),
        ],
        download_url  = "https://github.com/la5nta/pat/releases",
        download_note = "Recommended open-source Winlink client. Cross-platform.",
        tab           = "winlink",
    ),

    AppDef(
        key          = "paths.rms_express",
        name         = "RMS Express (Winlink)",
        description  = "Traditional Winlink client (Windows only)",
        category     = "winlink",
        exe_name     = "RMS Express",
        common_paths = [
            r"C:\RMS Express\RMS Express.exe",
            r"C:\Program Files\RMS Express\RMS Express.exe",
            r"C:\Program Files (x86)\RMS Express\RMS Express.exe",
        ],
        linux_paths  = [],
        download_url  = "https://www.winlink.org/RMSExpress",
        tab           = "winlink",
    ),

    AppDef(
        key          = "paths.flrig",
        name         = "FLRig",
        description  = "Alternative rig control server (XML-RPC)",
        category     = "rig",
        exe_name     = "flrig",
        common_paths = [
            r"C:\Program Files\flrig\flrig.exe",
            r"C:\flrig\flrig.exe",
        ],
        linux_paths  = [
            "/usr/bin/flrig",
            "/usr/local/bin/flrig",
        ],
        download_url  = "https://w1hkj.com/files/flrig/",
        download_note = (
            "FLRig: free alternative to rigctld\n"
            "Better support for some Yaesu/Kenwood rigs"),
        tab           = "rig",
    ),

    AppDef(
        key          = "paths.dsdplus",
        name         = "DSD+",
        description  = "DMR / NXDN / YSF digital voice decode (Windows)",
        category     = "digital",
        exe_name     = "DSDPlus",
        common_paths = [
            r"C:\DSDPlus\DSDPlus.exe",
            r"C:\Program Files\DSDPlus\DSDPlus.exe",
            r"C:\DSD+\DSDPlus.exe",
        ],
        linux_paths  = [],
        download_url  = "https://www.dsdplus.com/",
        download_note = "Windows only. On Linux use OP25 (open source).",
        tab           = "digital",
    ),

    AppDef(
        key          = "paths.op25",
        name         = "OP25 (Linux)",
        description  = "P25 open source decoder for Linux / DragonOS",
        category     = "digital",
        exe_name     = "rx.py",
        common_paths = [],
        linux_paths  = [
            "/usr/src/op25/op25/gr-op25-r1/apps/rx.py",
            "/opt/op25/op25/gr-op25-r1/apps/rx.py",
            str(Path.home() / "op25/op25/gr-op25-r1/apps/rx.py"),
        ],
        download_url  = "https://github.com/osmocom/op25",
        download_note = (
            "Linux only. Requires GNU Radio. "
            "See README for DragonOS install."),
        tab           = "digital",
    ),

    AppDef(
        key          = "paths.sdrangel",
        name         = "SDRangel",
        description  = "Multi-mode SDR: P25, DMR, D-STAR, YSF, AIS, ADS-B — Windows/Linux",
        category     = "digital",
        exe_name     = "sdrangel",
        common_paths = [
            r"C:\Program Files\SDRangel\sdrangel.exe",
            r"C:\Program Files (x86)\SDRangel\sdrangel.exe",
        ],
        linux_paths  = [
            "/usr/bin/sdrangel",
            "/usr/local/bin/sdrangel",
            "/opt/sdrangel/bin/sdrangel",
        ],
        download_url  = "https://github.com/f4exb/sdrangel/releases",
        download_note = "Supports RTL-SDR, HackRF, SDRplay, USRP, LimeSDR and more.",
        tab           = "digital",
    ),

    AppDef(
        key          = "paths.trunk_recorder",
        name         = "Trunk Recorder",
        description  = "P25/DMR trunked scanner — records calls, Linux/macOS",
        category     = "digital",
        exe_name     = "trunk-recorder",
        common_paths = [],
        linux_paths  = [
            "/usr/local/bin/trunk-recorder",
            "/usr/bin/trunk-recorder",
            str(Path.home() / "trunk-recorder/trunk-recorder"),
        ],
        download_url  = "https://github.com/robotastic/trunk-recorder",
        download_note = "Linux/macOS. Requires config.json for your system.",
        tab           = "digital",
    ),

    AppDef(
        key          = "paths.rtl433",
        name         = "rtl_433",
        description  = "Decode 433/868/315/915 MHz sensors — weather, IoT, tire pressure",
        category     = "digital",
        exe_name     = "rtl_433",
        common_paths = [
            r"C:\Program Files\rtl_433\rtl_433.exe",
            r"C:\rtl_433\rtl_433.exe",
        ],
        linux_paths  = [
            "/usr/bin/rtl_433",
            "/usr/local/bin/rtl_433",
        ],
        download_url  = "https://github.com/merbanan/rtl_433",
        download_note = "Requires RTL-SDR. Over 1000 supported device protocols.",
        tab           = "digital",
    ),

    AppDef(
        key          = "paths.unitrunker",
        name         = "Unitrunker",
        description  = "P25/EDACS/LTR trunked scanner controller (Windows)",
        category     = "digital",
        exe_name     = "Unitrunker.exe",
        common_paths = [
            r"C:\Program Files\Unitrunker\Unitrunker.exe",
            r"C:\Program Files (x86)\Unitrunker\Unitrunker.exe",
            str(Path.home() / "Unitrunker" / "Unitrunker.exe"),
        ],
        linux_paths  = [],
        download_url  = "https://www.unitrunker.com/",
        download_note = "Windows only. Works with RTL-SDR via SDR# plugin or VB-Cable.",
        tab           = "digital",
    ),

    AppDef(
        key          = "paths.dump1090",
        name         = "dump1090-fa",
        description  = "ADS-B aircraft tracking decoder",
        category     = "sdr",
        exe_name     = "dump1090-fa",
        common_paths = [
            r"C:\dump1090\dump1090-fa.exe",
            r"C:\Program Files\dump1090\dump1090-fa.exe",
        ],
        linux_paths  = [
            "/usr/bin/dump1090-fa",
            "/usr/local/bin/dump1090-fa",
            "/usr/bin/dump1090",
        ],
        download_url  = "https://github.com/flightaware/dump1090",
        tab           = "sdr",
    ),

    AppDef(
        key          = "paths.chirp",
        name         = "CHIRP",
        description = "Radio programming for Baofeng UV-5R, IC-7100, FT-991A, QRZ-1, Kenwood, Yaesu, and 200+ other radios",
        category     = "programming",
        exe_name     = "chirp",
        common_paths = [
            r"C:\Program Files\CHIRP\chirpw.exe",
            r"C:\Program Files (x86)\CHIRP\chirpw.exe",
            r"C:\Program Files\CHIRP-daily\chirpw.exe",
        ],
        linux_paths  = [
            "/usr/bin/chirp",
            "/usr/local/bin/chirp",
            "/usr/bin/chirpw",
        ],
        download_url  = "https://chirpmyradio.com/projects/chirp/wiki/Download",
        download_note = (
            "QRZ-1 Explorer: use TYT TH-UV88 driver in CHIRP. "
            "Standard Kenwood/Baofeng K1 cable required."),
        tab           = "localrf",
    ),

    AppDef(
        key          = "paths.rt_systems",
        name         = "RT Systems (QRZ-1)",
        description  = "Proprietary QRZ-1 Explorer programmer",
        category     = "programming",
        exe_name     = "RPS-QRZ1",
        common_paths = [
            r"C:\Program Files\RT Systems\RPS-QRZ1\RPS-QRZ1.exe",
            r"C:\Program Files (x86)\RT Systems\RPS-QRZ1\RPS-QRZ1.exe",
        ],
        linux_paths  = [],
        download_url  = "https://www.rtsystemsinc.com/",
        download_note = "Required for reliable CTCSS programming on QRZ-1 Explorer.",
        tab           = "localrf",
    ),

    AppDef(
        key          = "paths.icom_cs7100",
        name         = "Icom CS-7100",
        description  = "Icom IC-7100 HF/VHF/UHF transceiver programmer",
        category     = "programming",
        exe_name     = "CS-7100",
        common_paths = [
            r"C:\Program Files (x86)\Icom\CS-7100\CS-7100.exe",
            r"C:\Program Files\Icom\CS-7100\CS-7100.exe",
        ],
        linux_paths  = [],
        download_url  = "https://www.icomamerica.com/en/support/",
        download_note = "Free from Icom America support page. Windows only. CHIRP is the Linux/Mac alternative.",
        tab           = "localrf",
    ),

    AppDef(
        key          = "paths.icom_cs7300",
        name         = "Icom CS-7300",
        description  = "Icom IC-7300 HF transceiver programmer",
        category     = "programming",
        exe_name     = "CS-7300",
        common_paths = [
            r"C:\Program Files (x86)\Icom\CS-7300\CS-7300.exe",
            r"C:\Program Files\Icom\CS-7300\CS-7300.exe",
        ],
        linux_paths  = [],
        download_url  = "https://www.icomamerica.com/en/support/",
        download_note = "Free from Icom America support page. Windows only.",
        tab           = "localrf",
    ),

    AppDef(
        key          = "paths.yaesu_adms12",
        name         = "Yaesu ADMS-12",
        description  = "Yaesu FT-991/FT-991A memory programmer",
        category     = "programming",
        exe_name     = "ADMS-12",
        common_paths = [
            r"C:\Program Files (x86)\Yaesu\ADMS-12\ADMS-12.exe",
            r"C:\Program Files\Yaesu\ADMS-12\ADMS-12.exe",
        ],
        linux_paths  = [],
        download_url  = "https://www.yaesu.com/indexVS.cfm?cmd=DisplayProducts&ProdCatID=102&encProdID=C9ADCE16C2B2D2E0EB4C5A0D3B493A88",
        download_note = "Free from Yaesu website. Windows only. CHIRP also supports FT-991A.",
        tab           = "localrf",
    ),

    AppDef(
        key          = "paths.yaesu_adms14",
        name         = "Yaesu ADMS-14",
        description  = "Yaesu FT-70D / FTM-300D memory programmer",
        category     = "programming",
        exe_name     = "ADMS-14",
        common_paths = [
            r"C:\Program Files (x86)\Yaesu\ADMS-14\ADMS-14.exe",
            r"C:\Program Files\Yaesu\ADMS-14\ADMS-14.exe",
        ],
        linux_paths  = [],
        download_url  = "https://www.yaesu.com/indexVS.cfm?cmd=DisplayProducts&ProdCatID=102",
        download_note = "Free from Yaesu website. CHIRP also supports FT-70D.",
        tab           = "localrf",
    ),

    AppDef(
        key          = "paths.kenwood_mcp2a",
        name         = "Kenwood MCP-2A",
        description  = "Kenwood VHF/UHF handheld memory programmer (TH-D72/TH-F6A etc.)",
        category     = "programming",
        exe_name     = "MCP-2A",
        common_paths = [
            r"C:\Program Files (x86)\Kenwood\MCP-2A\MCP-2A.exe",
            r"C:\Program Files\Kenwood\MCP-2A\MCP-2A.exe",
        ],
        linux_paths  = [],
        download_url  = "https://www.kenwood.com/i/products/info/amateur/software.html",
        download_note = "Free from Kenwood website. CHIRP is a free cross-platform alternative.",
        tab           = "localrf",
    ),

    AppDef(
        key          = "paths.kenwood_mcp5a",
        name         = "Kenwood MCP-5A",
        description  = "Kenwood HF/VHF transceiver programmer (TS-2000, TS-590 etc.)",
        category     = "programming",
        exe_name     = "MCP-5A",
        common_paths = [
            r"C:\Program Files (x86)\Kenwood\MCP-5A\MCP-5A.exe",
            r"C:\Program Files\Kenwood\MCP-5A\MCP-5A.exe",
        ],
        linux_paths  = [],
        download_url  = "https://www.kenwood.com/i/products/info/amateur/software.html",
        download_note = "Free from Kenwood website. Windows only.",
        tab           = "localrf",
    ),

    AppDef(
        key          = "paths.tqsl",
        name         = "TQSL (LoTW)",
        description  = "ARRL LoTW QSO signing and upload",
        category     = "log",
        exe_name     = "tqsl",
        common_paths = [
            r"C:\Program Files\TQSL\tqsl.exe",
            r"C:\Program Files (x86)\TQSL\tqsl.exe",
        ],
        linux_paths  = [
            "/usr/bin/tqsl",
            "/usr/local/bin/tqsl",
        ],
        download_url  = "https://lotw.arrl.org/lotw-user-guide/",
        tab          = "log",
    ),

    AppDef(
        key          = "paths.n1mm",
        name         = "N1MM Logger+",
        description  = "Most popular Windows contest logger — CW/SSB/RTTY/Digital",
        category     = "log",
        exe_name     = "N1MMLogger",
        args         = None,
        common_paths = [
            r"C:\Program Files (x86)\N1MM Logger+\N1MMLogger.exe",
            r"C:\Program Files\N1MM Logger+\N1MMLogger.exe",
            r"C:\N1MM Logger+\N1MMLogger.exe",
        ],
        linux_paths  = [],
        download_url  = "https://n1mmplus.hamdocs.com/",
        tab          = "log",
    ),

    AppDef(
        key          = "paths.log4om",
        name         = "Log4OM",
        description  = "Full-featured logging software with DX cluster and awards tracking",
        category     = "log",
        exe_name     = "Log4OM2",
        args         = None,
        common_paths = [
            r"C:\Program Files (x86)\Log4OM2\Log4OM2.exe",
            r"C:\Program Files\Log4OM2\Log4OM2.exe",
            r"C:\Log4OM2\Log4OM2.exe",
        ],
        linux_paths  = [],
        download_url  = "https://www.log4om.com/",
        tab          = "log",
    ),

    AppDef(
        key          = "paths.hrd",
        name         = "Ham Radio Deluxe (HRD)",
        description  = "Commercial suite: rig control, logging, digital modes, satellite",
        category     = "log",
        exe_name     = "HRD",
        args         = None,
        common_paths = [
            r"C:\Program Files (x86)\Ham Radio Deluxe\Ham Radio Deluxe.exe",
            r"C:\Program Files\Ham Radio Deluxe\Ham Radio Deluxe.exe",
        ],
        linux_paths  = [],
        download_url  = "https://www.hamradiodeluxe.com/",
        tab          = "log",
    ),

    AppDef(
        key          = "paths.sdrsharp",
        name         = "SDR# (SDRSharp)",
        description  = "Popular Windows SDR receiver — RTL-SDR, Airspy, HackRF",
        category     = "sdr",
        exe_name     = "SDRSharp",
        args         = None,
        common_paths = [
            r"C:\SDRSharp\SDRSharp.exe",
            r"C:\Program Files\SDRSharp\SDRSharp.exe",
            r"C:\airspy\SDRSharp.exe",
        ],
        linux_paths  = [],
        download_url  = "https://airspy.com/download/",
        tab          = "sdr",
    ),

    AppDef(
        key          = "paths.sdruno",
        name         = "SDRuno",
        description  = "SDRplay's official Windows SDR receiver (RSP series)",
        category     = "sdr",
        exe_name     = "SDRuno",
        args         = None,
        common_paths = [
            r"C:\Program Files\SDRplay\SDRuno\SDRuno.exe",
            r"C:\Program Files (x86)\SDRplay\SDRuno\SDRuno.exe",
        ],
        linux_paths  = [],
        download_url  = "https://www.sdrplay.com/sdruno/",
        tab          = "sdr",
    ),

    AppDef(
        key          = "paths.hdsdr",
        name         = "HDSDR",
        description  = "Free Windows SDR receiver — wideband RX, many front-ends",
        category     = "sdr",
        exe_name     = "HDSDR",
        args         = None,
        common_paths = [
            r"C:\Program Files (x86)\HDSDR\HDSDR.exe",
            r"C:\Program Files\HDSDR\HDSDR.exe",
        ],
        linux_paths  = [],
        download_url  = "http://www.hdsdr.de/",
        tab          = "sdr",
    ),

    AppDef(
        key          = "paths.sdrconsole",
        name         = "SDR Console",
        description  = "Simon Brown's Windows SDR receiver — wide hardware support",
        category     = "sdr",
        exe_name     = "SDRConsole",
        args         = None,
        common_paths = [
            r"C:\Program Files\SDR-Radio.com (V3)\SDRConsole.exe",
            r"C:\Program Files (x86)\SDR-Radio.com (V3)\SDRConsole.exe",
            r"C:\Program Files\SDR-Radio.com\SDRConsole.exe",
        ],
        linux_paths  = [],
        download_url  = "https://www.sdr-radio.com/download",
        tab          = "sdr",
    ),

    AppDef(
        key          = "paths.gnuradio",
        name         = "GNU Radio Companion",
        description  = "Visual flowgraph builder for signal processing and SDR",
        category     = "sdr",
        exe_name     = "gnuradio-companion",
        args         = ["--version"],
        common_paths = [
            r"C:\Program Files\GNURadio-3.10\bin\gnuradio-companion.exe",
            r"C:\GNURadio\bin\gnuradio-companion.exe",
        ],
        linux_paths  = [
            "/usr/bin/gnuradio-companion",
            "/usr/local/bin/gnuradio-companion",
        ],
        download_url  = "https://www.gnuradio.org/",
        tab          = "sdr",
    ),

    AppDef(
        key          = "paths.direwolf",
        name         = "Direwolf (AX.25 TNC)",
        description  = "Software AX.25 TNC for APRS, packet radio, and Winlink",
        category     = "digital",
        exe_name     = "direwolf",
        args         = ["--version"],
        common_paths = [
            r"C:\direwolf\direwolf.exe",
            r"C:\Program Files\Direwolf\direwolf.exe",
        ],
        linux_paths  = [
            "/usr/bin/direwolf",
            "/usr/local/bin/direwolf",
        ],
        download_url  = "https://github.com/wb2osz/direwolf",
        tab          = "digital",
    ),

    AppDef(
        key          = "paths.mmtty",
        name         = "MMTTY",
        description  = "RTTY modem — used standalone or as engine inside N1MM/MixW",
        category     = "digital",
        exe_name     = "MMTTY",
        args         = None,
        common_paths = [
            r"C:\MMTTY\MMTTY.exe",
            r"C:\Program Files (x86)\MMTTY\MMTTY.exe",
        ],
        linux_paths  = [],
        download_url  = "https://hamsoft.ca/pages/mmtty.php",
        tab          = "digital",
    ),
]

# Quick lookup by key
_BY_KEY: dict[str, AppDef] = {a.key: a for a in APPS}
_BY_TAB: dict[str, list[AppDef]] = {}
for _app in APPS:
    _BY_TAB.setdefault(_app.tab, []).append(_app)


class Launcher:
    """
    Auto-detects and launches external applications.
    Called on startup to silently populate paths.
    """

    def __init__(self, config):
        self.cfg = config
        self._detected: dict[str, str] = {}

    def auto_detect_all(self) -> dict[str, str]:
        """
        Silently scan for all known applications.
        Updates config with found paths.
        Returns dict of key → found_path.
        """
        found = {}
        for app in APPS:
            path = self._find(app)
            if path:
                found[app.key] = path
                # Only set if not already configured
                existing = self.cfg.get(app.key, "")
                if not existing or not Path(existing).exists():
                    self.cfg.set(app.key, path)
                    log.info(f"Auto-detected: {app.name} → {path}")
        self._detected = found
        return found

    def _find(self, app: AppDef) -> str:
        """Find an application's executable."""
        # 1. Check configured path
        configured = self.cfg.get(app.key, "")
        if configured and Path(configured).exists():
            return configured

        # 2. Check PATH
        found = shutil.which(app.exe_name)
        if found:
            return found

        # 3. Check exe_name.exe on Windows
        if IS_WINDOWS:
            found = shutil.which(app.exe_name + ".exe")
            if found:
                return found

        # 4. Check common paths
        paths = app.common_paths if IS_WINDOWS \
                else app.linux_paths
        for candidate in paths:
            # Expand environment variables
            expanded = str(Path(candidate).expanduser())
            if Path(expanded).exists():
                return expanded

        return ""

    def launch(self, key: str,
                args: list = None) -> bool:
        """Launch an application by config key."""
        app = _BY_KEY.get(key)
        if not app:
            log.warning(f"Unknown app key: {key}")
            return False

        path = self._find(app)
        if not path:
            log.warning(
                f"{app.name} not found. "
                f"Configure in Settings → Paths.")
            return False

        try:
            # Validate executable is in allowlist
            exe_name = Path(path).name.lower()
            if exe_name not in [a.lower()
                                 for a in ALLOWED_EXECUTABLES]:
                log.warning(
                    f"Launch blocked — not in allowlist: "
                    f"{exe_name!r}")
                return False
            # Block path traversal
            if ".." in path:
                log.warning(
                    f"Launch blocked — path traversal: {path!r}")
                return False
            cmd = [path] + (args or app.args)
            subprocess.Popen(
                cmd,
                shell=False,   # nosec B603 - shell=False is intentionally safe
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            log.info(f"Launched: {app.name} ({path})")
            return True
        except Exception as e:
            log.error(f"Launch {app.name}: {e}")
            return False

    def is_available(self, key: str) -> bool:
        app = _BY_KEY.get(key)
        if not app:
            return False
        return bool(self._find(app))

    def get_path(self, key: str) -> str:
        app = _BY_KEY.get(key)
        if not app:
            return ""
        return self._find(app)

    def apps_for_tab(self, tab: str) -> list[AppDef]:
        return _BY_TAB.get(tab, [])

    @staticmethod
    def all_apps() -> list[AppDef]:
        return list(APPS)


# Module singleton
_launcher: Launcher = None

def get_launcher(config=None) -> Launcher:
    global _launcher
    if _launcher is None:
        if config is None:
            from core.config import get_config
            config = get_config()
        _launcher = Launcher(config)
    return _launcher
