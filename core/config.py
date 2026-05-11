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
Squelch -- core/config.py
Configuration manager. Dot-notation access, auto-save, singleton.
"""

import json
import copy
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

CONFIG_PATH  = Path("config.json")
EXAMPLE_PATH = Path("config.example.json")


class Config:
    def __init__(self, path: Path = CONFIG_PATH):
        self._path  = path
        self._data  = {}
        self._dirty = False
        self.load()

    def load(self):
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                log.info(f"Config loaded from {self._path}")
            except Exception as e:
                log.error(f"Config load failed: {e} -- using defaults")
                self._data = self._load_example()
        else:
            log.info("config.json not found -- loading from template")
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
        return self._data.get("grid_square", "").upper().strip()

    @grid.setter
    def grid(self, v: str):
        self.set("grid_square", v.upper().strip())

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
