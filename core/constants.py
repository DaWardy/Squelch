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
Squelch -- core/constants.py
Single source of truth for all application constants.
Import from here — never hardcode these elsewhere.
"""

# ── Application identity ──────────────────────────────────────────────────
APP_NAME        = "Squelch"
APP_FULL        = "Amateur Radio Operations Platform"
APP_VERSION     = "0.12.0-alpha"
APP_URL         = "https://github.com/dawardy/squelch"
APP_ISSUES_URL  = "https://github.com/dawardy/squelch/issues"
APP_LICENSE     = "GNU General Public License v3"
APP_COPYRIGHT   = "Copyright (C) 2026  github.com/dawardy/squelch"

# ── Network ports ─────────────────────────────────────────────────────────
PORT_HAMLIB_RIGCTLD = 4532      # rigctld default
PORT_WSJT_UDP       = 2237      # WSJT-X UDP broadcast
PORT_DUMP1090_HTTP  = 8080      # dump1090-fa HTTP/JSON
PORT_VARA_HF_CMD    = 8300      # VARA HF control
PORT_VARA_HF_DATA   = 8301      # VARA HF data
PORT_VARA_FM_CMD    = 8400      # VARA FM control
PORT_VARA_FM_DATA   = 8401      # VARA FM data
PORT_ARDOP_CMD      = 8515      # ARDOP (ardopcf) control
PORT_ARDOP_DATA     = 8516      # ARDOP (ardopcf) data
PORT_PAT_HTTP       = 8080      # Pat Winlink HTTP API
PORT_DIREWOLF_AGWPE = 8000      # Direwolf AGWPE

# ── Network hosts ─────────────────────────────────────────────────────────
HOST_LOCALHOST      = "localhost"
HOST_APRS_IS        = "rotate.aprs2.net"
PORT_APRS_IS        = 14580
HOST_QRZ_XML        = "xmldata.qrz.com"
HOST_HAMQTH         = "www.hamqth.com"
HOST_HAMALERT       = "api.hamalert.org"
HOST_PSKREPORTER    = "www.pskreporter.info"
HOST_WSPRNET        = "www.wsprnet.org"
HOST_RR             = "www.radioreference.com"

# ── NOAA SWPC URLs ────────────────────────────────────────────────────────
# NOAA SWPC real-time data endpoints
NOAA_SOLAR_URL  = (
    # Real-time 45-day solar flux index (F10.7)
    "https://services.swpc.noaa.gov/json/solar-cycle/"
    "observed-solar-cycle-indices.json")
NOAA_SOLAR_RT_URL = (
    # Real-time solar indices (preferred - updates every 3 hours)
    "https://services.swpc.noaa.gov/products/summary/"
    "10cm-flux.json")
NOAA_KP_URL     = (
    # 3-hour planetary K-index
    "https://services.swpc.noaa.gov/products/"
    "noaa-planetary-k-index.json")
NOAA_KP_RT_URL  = (
    # Real-time K-index (updates every 3 min)
    "https://services.swpc.noaa.gov/products/summary/"
    "geomag-field.json")
NOAA_XRAY_URL   = (
    "https://services.swpc.noaa.gov/json/goes/primary/"
    "xrays-1-day.json")
NOAA_ALERTS_URL = (
    "https://services.swpc.noaa.gov/products/alerts.json")
# All NOAA endpoints have CORS headers and are public/free

# ── Geolocation ───────────────────────────────────────────────────────────
IPAPI_URL           = "https://ipapi.co/json/"
NOMINATIM_URL       = (
    "https://nominatim.openstreetmap.org/search")
NOMINATIM_USER_AGENT = f"Squelch/{APP_VERSION}"

# ── Artemis signal database ───────────────────────────────────────────────
ARTEMIS_DB_URL  = (
    "https://raw.githubusercontent.com/AresValley/"
    "Artemis/master/db/signals.json")
ARTEMIS_CACHE   = "assets/artemis_signals.json"

# ── CAT / Hamlib ──────────────────────────────────────────────────────────
HAMLIB_IC7100_MODEL = 370
HAMLIB_DEFAULT_BAUD = 19200
HAMLIB_POLL_MS      = 500        # rig state poll interval
HAMLIB_CMD_TIMEOUT  = 2.0        # seconds per command
PTT_WATCHDOG_S      = 180        # max TX time (3 minutes)

# ── Audio ─────────────────────────────────────────────────────────────────
AUDIO_SAMPLE_RATE   = 48_000     # Hz — standard for digital modes
AUDIO_BLOCK_SIZE    = 512        # samples per callback block
AUDIO_CHANNELS      = 1          # mono for most digital modes

# ── SDR / FFT ─────────────────────────────────────────────────────────────
FFT_SIZE            = 2048       # FFT bins
WATERFALL_ROWS      = 100        # waterfall history rows
DEFAULT_SAMPLE_RATE = 2_400_000  # 2.4 MSPS default
MIN_SAMPLE_RATE     = 250_000    # minimum usable
SDR_GAIN_DEFAULT    = 30.0       # dB

# ── FT8 / Digital modes ───────────────────────────────────────────────────
FT8_CYCLE_S         = 15         # FT8 TX/RX cycle seconds
FT8_PERIOD_S        = 12.64      # FT8 transmission duration
FT8_FREQ_HZ         = 14_074_000 # 20m FT8 dial frequency
FT4_FREQ_HZ         = 14_080_000 # 20m FT4 dial frequency
WSPR_FREQ_HZ        = 14_097_200 # 20m WSPR dial frequency
JS8_FREQ_HZ         = 14_078_000 # 20m JS8Call frequency
FT8_BANDWIDTH_HZ    = 3_000      # FT8 audio passband width

# ── FT8 frequencies by band ──────────────────────────────────────────────
FT8_FREQUENCIES: dict[str, int] = {
    "160m": 1_840_000,
    "80m":  3_573_000,
    "40m":  7_074_000,
    "30m":  10_136_000,
    "20m":  14_074_000,
    "17m":  18_100_000,
    "15m":  21_074_000,
    "12m":  24_915_000,
    "10m":  28_074_000,
    "6m":   50_313_000,
}

FT4_FREQUENCIES: dict[str, int] = {
    "80m":  3_575_000,
    "40m":  7_047_500,
    "20m":  14_080_000,
    "17m":  18_104_000,
    "15m":  21_140_000,
    "10m":  28_180_000,
}

WSPR_FREQUENCIES: dict[str, int] = {
    "160m": 1_838_100,
    "80m":  3_594_100,
    "40m":  7_040_100,
    "30m":  10_140_200,
    "20m":  14_097_100,
    "17m":  18_106_100,
    "15m":  21_096_100,
    "12m":  24_926_100,
    "10m":  28_126_100,
}

# ── Band edges (ITU Region 2 — Americas) ─────────────────────────────────
BAND_EDGES_R2: dict[str, tuple[int, int]] = {
    "160m": (1_800_000,   2_000_000),
    "80m":  (3_500_000,   4_000_000),
    "60m":  (5_330_500,   5_406_400),
    "40m":  (7_000_000,   7_300_000),
    "30m":  (10_100_000,  10_150_000),
    "20m":  (14_000_000,  14_350_000),
    "17m":  (18_068_000,  18_168_000),
    "15m":  (21_000_000,  21_450_000),
    "12m":  (24_890_000,  24_990_000),
    "10m":  (28_000_000,  29_700_000),
    "6m":   (50_000_000,  54_000_000),
    "2m":   (144_000_000, 148_000_000),
    "1.25m":(222_000_000, 225_000_000),
    "70cm": (420_000_000, 450_000_000),
    "33cm": (902_000_000, 928_000_000),
    "23cm": (1_240_000_000, 1_300_000_000),
}

# ── ITU Region band edges ─────────────────────────────────────────────────
BAND_EDGES_R1: dict[str, tuple[int, int]] = {
    # Europe, Africa, Middle East
    "160m": (1_810_000,   2_000_000),
    "80m":  (3_500_000,   3_800_000),
    "40m":  (7_000_000,   7_200_000),
    "30m":  (10_100_000,  10_150_000),
    "20m":  (14_000_000,  14_350_000),
    "17m":  (18_068_000,  18_168_000),
    "15m":  (21_000_000,  21_450_000),
    "12m":  (24_890_000,  24_990_000),
    "10m":  (28_000_000,  29_700_000),
    "6m":   (50_000_000,  52_000_000),
    "2m":   (144_000_000, 146_000_000),
    "70cm": (430_000_000, 440_000_000),
}

BAND_EDGES_R3: dict[str, tuple[int, int]] = {
    # Asia, Pacific
    "160m": (1_800_000,   2_000_000),
    "80m":  (3_500_000,   3_900_000),
    "40m":  (7_000_000,   7_300_000),
    "30m":  (10_100_000,  10_150_000),
    "20m":  (14_000_000,  14_350_000),
    "17m":  (18_068_000,  18_168_000),
    "15m":  (21_000_000,  21_450_000),
    "12m":  (24_890_000,  24_990_000),
    "10m":  (28_000_000,  29_700_000),
    "6m":   (50_000_000,  54_000_000),
    "2m":   (144_000_000, 148_000_000),
    "70cm": (420_000_000, 450_000_000),
}

# Active region — default R2, set by user in settings
BAND_EDGES = BAND_EDGES_R2

# ── UI defaults ───────────────────────────────────────────────────────────
UI_FONT_SIZE_DEFAULT = 11
UI_FONT_SIZE_MIN     = 8
UI_FONT_SIZE_MAX     = 20
UI_THEME_DEFAULT     = "Dark"
UI_WINDOW_MIN_W      = 900
UI_WINDOW_MIN_H      = 600
UI_WINDOW_DEFAULT_W  = 1300
UI_WINDOW_DEFAULT_H  = 840

# ── Logging ───────────────────────────────────────────────────────────────
LOG_FILE            = "logs/squelch.log"
LOG_DB_FILE         = "logs/squelch_log.db"
LOG_MAX_BYTES       = 5_242_880   # 5MB
LOG_BACKUP_COUNT    = 3

# ── API limits ────────────────────────────────────────────────────────────
API_RESPONSE_MAX_BYTES = 10_000_000   # 10MB hard limit
API_TIMEOUT_S          = 10            # default timeout
API_TIMEOUT_SHORT_S    = 3             # for local services
API_TIMEOUT_LONG_S     = 30            # for large downloads

# ── IQ Recording ─────────────────────────────────────────────────────────
IQ_RECORDINGS_DIR   = "recordings"
IQ_MAX_FILE_GB      = 4.0             # max single recording size
IQ_SIGMF_VERSION    = "1.0.0"

# ── ADIF ─────────────────────────────────────────────────────────────────
ADIF_PROGRAM_ID     = "Squelch"
ADIF_PROGRAM_VER    = APP_VERSION

# ── Validators ───────────────────────────────────────────────────────────
CALLSIGN_MAX_LEN    = 12
GRID_SQUARE_MAX_LEN = 8
FREQUENCY_MIN_HZ    = 1_000          # 1 kHz
FREQUENCY_MAX_HZ    = 300_000_000_000  # 300 GHz theoretical
NOTE_MAX_LEN        = 1000
PATH_MAX_LEN        = 500
