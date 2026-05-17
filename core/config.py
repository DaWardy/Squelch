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

from __future__ import annotations
"""Squelch -- core/config.py
Configuration manager. Dot-notation access, auto-save, singleton.
"""

import json
import copy
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

import sys
import os

def _user_config_dir() -> Path:
    """
    Return platform-appropriate user config directory.
    Survives app reinstalls — user data is never in the app folder.
    
    Windows: %APPDATA%/Squelch/
    Linux:   ~/.config/squelch/
    macOS:   ~/Library/Application Support/Squelch/
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA",
                    Path.home() / "AppData" / "Roaming"))
        return base / "Squelch"
    elif sys.platform == "darwin":
        return (Path.home() / "Library" /
                "Application Support" / "Squelch")
    else:
        # Linux / DragonOS
        xdg = os.environ.get("XDG_CONFIG_HOME", "")
        base = Path(xdg) if xdg else Path.home() / ".config"
        return base / "squelch"


APP_DIR      = Path(__file__).parent.parent.resolve()
USER_DIR     = _user_config_dir()
CONFIG_PATH  = USER_DIR / "config.json"
EXAMPLE_PATH = APP_DIR  / "config.example.json"
LOG_DIR      = USER_DIR / "logs"
PROFILES_DIR = USER_DIR / "profiles"

# Create all user directories immediately on import
# so nothing fails with FileNotFoundError on first run
for _d in (USER_DIR, LOG_DIR, PROFILES_DIR):
    _d.mkdir(parents=True, exist_ok=True)


class Config:
    def __init__(self, path: Path = CONFIG_PATH):
        self._path  = path
        # Ensure user config directory exists
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data  = {}
        self._dirty = False
        self._migrate_legacy()
        self.load()

    def _migrate_legacy(self):
        """
        Migrate config.json from app folder to user profile folder.
        Called once on first run after v0.6.0-alpha.
        Preserves all user settings across reinstalls from this point on.
        """
        if self._path.exists():
            return  # already migrated
        legacy = APP_DIR / "config.json"
        if legacy.exists():
            import shutil
            try:
                shutil.copy(legacy, self._path)
                log.info(
                    f"Migrated config from {legacy} "
                    f"to {self._path}")
            except Exception as e:
                log.warning(f"Config migration: {e}")

    def load(self):
        if self._path.exists():
            try:
                with open(self._path, "r",
                          encoding="utf-8") as f:
                    self._data = json.load(f)
                log.info(
                    f"Config loaded from "
                    f"{self._path.resolve()}")
            except Exception as e:
                log.error(
                    f"Config load failed: {e} "
                    f"-- using defaults")
                self._data = self._load_example()
        else:
            # Check app folder for legacy config
            legacy = APP_DIR / "config.json"
            if legacy.exists():
                try:
                    with open(legacy, "r",
                              encoding="utf-8") as f:
                        self._data = json.load(f)
                    log.info(
                        f"Config loaded from legacy "
                        f"path: {legacy}")
                    # Immediately save to APPDATA location
                    self.save()
                    log.info(
                        f"Config migrated to "
                        f"{self._path.resolve()}")
                except Exception as e:
                    log.warning(f"Legacy config: {e}")
                    self._data = self._load_example()
            else:
                log.info(
                    "No config found -- starting fresh")
                self._data = self._load_example()
            self.save()
        self._dirty = False

    def save(self):
        try:
            # Remove internal comment key before saving
            data = {k: v for k, v in self._data.items() if not k.startswith("_")}
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._dirty = False
            log.debug("Config saved.")
        except Exception as e:
            log.error(f"Config save failed: {e}")

    def save_if_dirty(self):
        if self._dirty:
            self.save()

    # ── Access ────────────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        parts = key.split(".")
        val = self._data
        try:
            for p in parts:
                val = val[p]
            return val
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any):
        parts = key.split(".")
        d = self._data
        for p in parts[:-1]:
            if p not in d or not isinstance(d[p], dict):
                d[p] = {}
            d = d[p]
        d[parts[-1]] = value
        self._dirty = True

    def get_section(self, section: str) -> dict:
        return copy.deepcopy(self._data.get(section, {}))

    def update_section(self, section: str, values: dict):
        if section not in self._data:
            self._data[section] = {}
        self._data[section].update(values)
        self._dirty = True

    # ── Convenience ───────────────────────────────────────────────────────

    @property
    def callsign(self) -> str:
        return self._data.get("callsign", "").upper().strip()

    @callsign.setter
    def callsign(self, v: str):
        self.set("callsign", v.upper().strip())

    @property
    def grid(self) -> str:
        # Prefer location.grid (set by LocationManager)
        # Fall back to legacy grid_square key
        g = (self._data.get("location.grid", "") or
             self._data.get("grid_square", ""))
        return g.upper().strip()

    @grid.setter
    def grid(self, v: str):
        # Write to both keys for compatibility
        v = v.upper().strip()
        self.set("location.grid", v)
        self.set("grid_square", v)

    @property
    def is_configured(self) -> bool:
        return bool(self.callsign and self.grid)

    def has_radioreference(self) -> bool:
        return bool(self.get("apis.radioreference_key") and
                    self.get("apis.radioreference_user"))

    def has_qrz(self) -> bool:
        return bool(self.get("apis.qrz_user") and
                    self.get("apis.qrz_pass"))

    @staticmethod
    def _load_example() -> dict:
        if EXAMPLE_PATH.exists():
            try:
                with open(EXAMPLE_PATH) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def __repr__(self):
        return f"<Config {self._path} cs={self.callsign} dirty={self._dirty}>"


_instance: "Config | None" = None

def get_config() -> Config:
    global _instance
    if _instance is None:
        _instance = Config()
    return _instance
