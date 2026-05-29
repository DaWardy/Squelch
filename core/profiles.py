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
"""Squelch -- core/profiles.py
User profile system. Each profile has:
  - Separate config.json
  - Separate QSO log database
  - Separate credential store (keyring namespace)
  - Optional master password
  - Optional guest operator mode with control op designation

Profile data stored in:
  profiles/
    profiles.json       -- profile list and last used
    <name>/
      config.json       -- profile-specific settings
      squelch_log.db    -- profile QSO log
"""

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

from core.config import PROFILES_DIR as _PROFILES_DIR
PROFILES_DIR  = _PROFILES_DIR
PROFILES_META = PROFILES_DIR / "profiles.json"


@dataclass
class Profile:
    name:              str              # internal ID (alphanumeric)
    display_name:      str              # shown in UI
    callsign:          str  = ""
    operator_callsign: str  = ""        # separate from station callsign
    is_guest_op:       bool = False     # guest operator mode
    control_op:        str  = ""        # control operator callsign
    has_master_pass:   bool = False     # master password protection
    max_power_w:       float = 100.0   # power limit for guest op
    created_at:        str  = ""
    last_used:         str  = ""

    @property
    def config_path(self) -> Path:
        return PROFILES_DIR / self.name / "config.json"

    @property
    def db_path(self) -> Path:
        return PROFILES_DIR / self.name / "squelch_log.db"

    @property
    def dir(self) -> Path:
        return PROFILES_DIR / self.name


class ProfileManager:
    """
    Manages Squelch user profiles.
    Handles creation, selection, and migration from legacy config.
    """

    def __init__(self):
        self._profiles:  dict[str, Profile] = {}
        self._current:   Profile | None  = None
        self._loaded     = False

    # ── Load / Save ───────────────────────────────────────────────────────

    def load(self):
        """Load profile list from profiles.json."""
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)

        if not PROFILES_META.exists():
            self._migrate_legacy()
            return

        try:
            data = json.loads(
                PROFILES_META.read_text(encoding='utf-8'))
            for pd in data.get("profiles", []):
                profile = Profile(**{
                    k: v for k, v in pd.items()
                    if k in Profile.__dataclass_fields__})
                self._profiles[profile.name] = profile
            log.info(
                f"Loaded {len(self._profiles)} profiles")
        except Exception as e:
            log.error(f"Profile load failed: {e}")
            self._migrate_legacy()

        self._loaded = True

    def save(self):
        """Save profile list to profiles.json."""
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "profiles": [
                asdict(p) for p in self._profiles.values()],
            "last_used": (self._current.name
                         if self._current else "default"),
        }
        try:
            PROFILES_META.write_text(
                json.dumps(data, indent=2),
                encoding='utf-8')
        except Exception as e:
            log.error(f"Profile save failed: {e}")

    # ── Create / Select ───────────────────────────────────────────────────

    def create(self, name: str, display_name: str = "",
               callsign: str = "") -> Profile | None:
        """Create a new profile."""
        if name in self._profiles:
            log.warning(f"Profile {name} already exists")
            return None
        name = re.sub(r'[^a-zA-Z0-9_-]', '', name)[:32]
        if not name:
            log.error("Profile name invalid")
            return None

        p = Profile(
            name=name,
            display_name=display_name or name,
            callsign=callsign.upper() if callsign else "",
        )
        p.dir.mkdir(parents=True, exist_ok=True)
        self._profiles[name] = p
        self.save()
        log.info(f"Created profile: {name}")
        return p

    def select(self, name: str) -> Profile | None:
        """Switch to a profile by name."""
        if name not in self._profiles:
            log.warning(f"Profile {name} not found")
            return None
        self._current = self._profiles[name]
        self.save()
        log.info(f"Selected profile: {name}")
        return self._current

    def delete(self, name: str) -> bool:
        """Delete a profile."""
        if name not in self._profiles:
            return False
        if self._current and self._current.name == name:
            # Switch to default first
            if "default" in self._profiles:
                self._current = self._profiles["default"]
        # Don't delete the dir; keep it for history
        del self._profiles[name]
        self.save()
        log.info(f"Deleted profile: {name}")
        return True

    def _migrate_legacy(self):
        """Create default profile from legacy config.json."""
        log.info("Migrating legacy config to profile system")
        legacy_config = Path("config.json")
        default_dir   = PROFILES_DIR / "default"
        default_dir.mkdir(parents=True, exist_ok=True)

        if legacy_config.exists():
            # Copy legacy config to default profile
            import shutil
            dest = default_dir / "config.json"
            if not dest.exists():
                shutil.copy(legacy_config, dest)
                log.info("Migrated config.json to default profile")

        # Copy legacy log if exists
        legacy_log = Path("logs/squelch_log.db")
        if legacy_log.exists():
            import shutil
            dest_log = default_dir / "squelch_log.db"
            if not dest_log.exists():
                shutil.copy(legacy_log, dest_log)
                log.info("Migrated log DB to default profile")

        # Read callsign from legacy config
        callsign = ""
        try:
            cfg_data = json.loads(
                legacy_config.read_text())
            callsign = cfg_data.get("callsign", "")
        except Exception as e:
            log.debug(f"Profile migration read legacy config failed: {e}")

        default_profile = Profile(
            name         = "default",
            display_name = callsign or "Set Your Callsign",
            callsign     = callsign,
        )
        self._profiles["default"] = default_profile
        self._current = default_profile
        self.save()
        log.info("Default profile created from legacy config")

    # ── Properties ───────────────────────────────────────────────────────

    def list_profiles(self) -> list[str]:
        """Return list of profile display names."""
        pm = get_profile_manager()
        return [p.display_name or p.name
                for p in pm.profiles.values()]

    def current_name(self) -> str:
        """Return current profile display name."""
        pm = get_profile_manager()
        cur = pm.current()
        if cur:
            return cur.display_name or cur.name
        return "Default"

    def switch_to(self, display_name: str) -> bool:
        """Switch to profile by display name."""
        pm = get_profile_manager()
        for name, p in pm.profiles.items():
            if (p.display_name == display_name or
                    p.name == display_name):
                result = pm.select(name)
                return result is not None
        return False

    def create(self, display_name: str) -> bool:
        """Create a new profile with given display name."""
        pm = get_profile_manager()
        slug = display_name.upper().replace(" ", "_")[:20]
        try:
            pm.create(slug, display_name, display_name)
            return True
        except Exception:
            return False

    @property
    def profiles(self) -> dict[str, Profile]:
        return dict(self._profiles)

    @property
    def current(self) -> Profile | None:
        return self._current

    @property
    def count(self) -> int:
        return len(self._profiles)


# Module-level singleton
_manager: ProfileManager | None = None

def get_profile_manager() -> ProfileManager:
    global _manager
    if _manager is None:
        _manager = ProfileManager()
        _manager.load()
    return _manager
