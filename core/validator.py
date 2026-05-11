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
Squelch -- core/validator.py
Input validation and sanitization.
All external data, user input, and subprocess arguments
pass through this module before use.
Prevents RCE, SQLi, path traversal, and injection attacks.
"""

import re
import logging
from pathlib import Path
from typing import Union, Optional

log = logging.getLogger(__name__)


# ── Callsign ──────────────────────────────────────────────────────────────

def callsign(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Callsign must be a string")
    clean = re.sub(r'[^A-Z0-9/]', '', value.upper().strip())
    if len(clean) < 3:
        raise ValueError(f"Callsign too short: {clean!r}")
    if len(clean) > 15:
        raise ValueError(f"Callsign too long: {clean!r}")
    return clean

def callsign_soft(value: str) -> str:
    try:
        return callsign(value)
    except (ValueError, TypeError):
        return ""


# ── Grid square ───────────────────────────────────────────────────────────

_GRID_RE = re.compile(
    r'^[A-R]{2}[0-9]{2}([A-X]{2}([0-9]{2})?)?$', re.IGNORECASE)

def grid_square(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Grid must be a string")
    clean = re.sub(r'[^A-Za-z0-9]', '', value.strip()).upper()
    if not _GRID_RE.match(clean):
        raise ValueError(f"Invalid grid square: {clean!r}")
    return clean

def grid_square_soft(value: str) -> str:
    try:
        return grid_square(value)
    except (ValueError, TypeError):
        return ""


# ── Frequency ─────────────────────────────────────────────────────────────

def frequency_hz(value: Union[str, int, float]) -> int:
    if isinstance(value, (int, float)):
        hz = int(value)
    else:
        s = str(value).strip().upper().replace(',', '').replace(' ', '')
        if s.endswith('GHZ'):
            hz = int(float(s[:-3]) * 1_000_000_000)
        elif s.endswith('MHZ'):
            hz = int(float(s[:-3]) * 1_000_000)
        elif s.endswith('KHZ'):
            hz = int(float(s[:-3]) * 1_000)
        elif s.endswith('HZ'):
            hz = int(float(s[:-2]))
        else:
            val = float(s)
            hz = int(val * 1_000_000) if val < 1_000 else int(val)
    if not (100 <= hz <= 450_000_000):
        raise ValueError(f"Frequency out of range: {hz} Hz")
    return hz

def frequency_hz_soft(value) -> int:
    try:
        return frequency_hz(value)
    except (ValueError, TypeError):
        return 0


# ── Power ─────────────────────────────────────────────────────────────────

def power_watts(value: float, max_watts: float = 200.0) -> float:
    try:
        w = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid power value: {value!r}")
    if w < 0:
        raise ValueError("Power cannot be negative")
    return min(w, max_watts)

def power_dbm(value: float, max_dbm: float = 53.0) -> float:
    try:
        dbm = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid dBm value: {value!r}")
    return min(max(dbm, -30.0), max_dbm)


# ── File paths ────────────────────────────────────────────────────────────

def safe_path(user_input: str, base_dir: Path,
              allowed_extensions: list = None) -> Path:
    if not isinstance(user_input, str):
        raise ValueError("Path must be a string")
    clean = re.sub(r'[\x00-\x1f\x7f]', '', user_input)
    filename = Path(clean).name
    if not filename:
        raise ValueError("Empty filename")
    resolved = (Path(base_dir).resolve() / filename).resolve()
    base_resolved = Path(base_dir).resolve()
    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        raise ValueError(f"Path traversal detected: {user_input!r}")
    if allowed_extensions:
        if resolved.suffix.lower() not in [
                e.lower() for e in allowed_extensions]:
            raise ValueError(f"Extension not allowed: {resolved.suffix}")
    return resolved


# ── Subprocess arguments ──────────────────────────────────────────────────

_SHELL_METACHAR = re.compile(r'[;&|`$<>()\{\}\\\'"]')

def subprocess_arg(value: str) -> str:
    if not isinstance(value, str):
        value = str(value)
    if _SHELL_METACHAR.search(value):
        raise ValueError(
            f"Unsafe characters in subprocess argument: {value!r}")
    if '\x00' in value:
        raise ValueError("Null byte in subprocess argument")
    return value

def executable_path(path: str, allowlist: list = None) -> str:
    if not isinstance(path, str):
        raise ValueError("Executable path must be a string")
    name = Path(path).name.lower()
    if allowlist:
        if name not in [a.lower() for a in allowlist]:
            raise ValueError(f"Executable not in allowlist: {name!r}")
    if '..' in path:
        raise ValueError(f"Path traversal in executable: {path!r}")
    return path


# Allowlist of executables Squelch is permitted to launch
ALLOWED_EXECUTABLES = [
    "rigctld", "rigctld.exe",
    "wsjtx", "wsjtx.exe",
    "js8call", "js8call.exe",
    "fldigi", "fldigi.exe",
    "varahf", "varahf.exe",
    "varafm", "varafm.exe",
    "dsdplus", "dsdplus.exe",
    "dump1090", "dump1090.exe",
    "dump1090-fa", "dump1090-fa.exe",
    "direwolf", "direwolf.exe",
    "python", "python3", "python.exe", "python3.exe",
]


# ── API response sanitization ─────────────────────────────────────────────

def api_string(value, max_length: int = 200) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    value = value[:max_length * 2]
    value = re.sub(r'<[^>]{0,200}>', '', value)
    value = ''.join(
        c for c in value
        if c.isprintable() or c in ('\n', '\r', '\t'))
    value = ' '.join(value.split())
    return value[:max_length].strip()

def api_callsign(value) -> str:
    return callsign_soft(api_string(value, 15))

def api_float(value, default: float = 0.0,
              min_val: float = None,
              max_val: float = None) -> float:
    try:
        f = float(value)
        if min_val is not None:
            f = max(f, min_val)
        if max_val is not None:
            f = min(f, max_val)
        return f
    except (TypeError, ValueError):
        return default

def api_int(value, default: int = 0,
            min_val: int = None,
            max_val: int = None) -> int:
    try:
        i = int(float(value))
        if min_val is not None:
            i = max(i, min_val)
        if max_val is not None:
            i = min(i, max_val)
        return i
    except (TypeError, ValueError):
        return default


# ── SQL safety ────────────────────────────────────────────────────────────

def sql_like_pattern(value: str) -> str:
    """Escape for SQL LIKE — always use parameterized queries."""
    if not isinstance(value, str):
        value = str(value)
    value = value.replace('\\', '\\\\')
    value = value.replace('%', '\\%')
    value = value.replace('_', '\\_')
    return value


# ── Network URLs ──────────────────────────────────────────────────────────

_SAFE_SCHEMES = {'http', 'https'}

def safe_url(url: str) -> str:
    from urllib.parse import urlparse
    if not isinstance(url, str):
        raise ValueError("URL must be a string")
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in _SAFE_SCHEMES:
        raise ValueError(f"URL scheme not allowed: {parsed.scheme!r}")
    if any(c in url for c in ['\n', '\r', '\x00']):
        raise ValueError("Control characters in URL")
    return url.strip()

def localhost_only(host: str) -> str:
    allowed = {'127.0.0.1', 'localhost', '::1'}
    if host.strip().lower() not in allowed:
        raise ValueError(
            f"Non-localhost host rejected: {host!r}")
    return host.strip()


# ── CTCSS / DCS ───────────────────────────────────────────────────────────

CTCSS_TONES = [
    67.0, 69.3, 71.9, 74.4, 77.0, 79.7, 82.5, 85.4,
    88.5, 91.5, 94.8, 97.4, 100.0, 103.5, 107.2, 110.9,
    114.8, 118.8, 123.0, 127.3, 131.8, 136.5, 141.3, 146.2,
    151.4, 156.7, 159.8, 162.2, 165.5, 167.9, 171.3, 173.8,
    177.3, 179.9, 183.5, 186.2, 189.9, 192.8, 196.6, 199.5,
    203.5, 206.5, 210.7, 218.1, 225.7, 229.1, 233.6, 241.8,
    250.3, 254.1,
]

DCS_CODES = [
    23, 25, 26, 31, 32, 36, 43, 47, 51, 53, 54, 65, 71,
    72, 73, 74, 114, 115, 116, 122, 125, 131, 132, 134, 143,
    145, 152, 155, 156, 162, 165, 172, 174, 205, 212, 223,
    225, 226, 243, 244, 245, 246, 251, 252, 255, 261, 263,
    265, 266, 271, 274, 306, 311, 315, 325, 331, 332, 343,
    346, 351, 356, 364, 365, 371, 411, 412, 413, 423, 431,
    432, 445, 446, 452, 454, 455, 462, 464, 465, 466, 503,
    506, 516, 523, 526, 532, 546, 565, 606, 612, 624, 627,
    631, 632, 654, 662, 664, 703, 712, 723, 731, 732, 734,
    743, 754,
]

def ctcss_tone(value: float) -> float:
    if value in CTCSS_TONES:
        return value
    return min(CTCSS_TONES, key=lambda t: abs(t - value))

def dcs_code(value: int) -> int:
    if value in DCS_CODES:
        return value
    raise ValueError(f"Invalid DCS code: {value}")


# ── Config values ─────────────────────────────────────────────────────────

def config_string(value, max_length: int = 500,
                  allow_empty: bool = True) -> str:
    if value is None:
        return ""
    s = str(value)[:max_length]
    s = ''.join(c for c in s if c.isprintable() or c in (' ', '\t'))
    s = s.strip()
    if not allow_empty and not s:
        raise ValueError("Required config value is empty")
    return s

def api_key(value) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if s and not re.match(r'^[A-Za-z0-9\-_\.]{4,200}$', s):
        log.warning("API key format looks unusual")
    return s[:200]


# ── Audio ─────────────────────────────────────────────────────────────────

def detect_clipping(audio_data, threshold: float = 0.95) -> float:
    """
    Returns fraction of samples at or near clipping level.
    0.0 = no clipping, 1.0 = all samples clipping.
    """
    try:
        import numpy as np
        arr = np.asarray(audio_data)
        clipped = np.sum(np.abs(arr) >= threshold)
        return float(clipped) / max(len(arr), 1)
    except Exception:
        return 0.0
