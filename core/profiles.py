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
            "profiles": [asdict(p) for p in self._profiles.values()],
            "last_used": (self._current.name if self._current else "default"),
        }
        try:
            PROFILES_META.write_text(
                json.dumps(data, indent=2), encoding='utf-8')
        except Exception as e:
            log.error(f"Profile save failed: {e}")

    # ── Profile CRUD ──────────────────────────────────────────────────────

    def create(self, name: str, display_name: str = "",
               callsign: str = "") -> Profile:
        """Create a new profile with the given slug name, display name, and callsign.

        Guest operator fields (is_guest_op, control_op) are set separately
        via configure_guest_op() to keep this signature lean.
        """
        safe_name = re.sub(r'[^a-z0-9_]', '_', name.lower().strip())[:20] or "profile"
        base, counter = safe_name, 1
        while safe_name in self._profiles:
            safe_name = f"{base}_{counter}"
            counter += 1
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        profile = Profile(
            name         = safe_name,
            display_name = (display_name or name)[:50],
            callsign     = callsign.upper().strip()[:12],
            created_at   = now,
            last_used    = now,
        )
        profile.dir.mkdir(parents=True, exist_ok=True)
        self._profiles[safe_name] = profile
        self.save()
        log.info(f"Profile created: {safe_name}")
        return profile

    def configure_guest_op(self, name: str, control_op: str,
                           is_guest_op: bool = True) -> bool:
        """Set guest operator fields on an existing profile.

        Separated from create() to keep argument count lean (C-15 Sam use case).
        Returns True if the profile was found and updated.
        """
        profile = self._profiles.get(name)
        if not profile:
            log.warning(f"configure_guest_op: profile {name!r} not found")
            return False
        profile.is_guest_op = is_guest_op
        profile.control_op  = control_op.upper().strip()[:12]
        self.save()
        log.info(f"Guest op configured for {name}: control_op={profile.control_op}")
        return True

    def delete(self, name: str):
        """Delete a profile. Cannot delete the last profile."""
        if len(self._profiles) <= 1:
            raise ValueError(
                "Cannot delete the only profile")
        if name not in self._profiles:
            return
        if (self._current and
                self._current.name == name):
            raise ValueError(
                "Cannot delete the active profile")
        del self._profiles[name]
        self.save()

    def rename(self, name: str, new_display: str):
        if name in self._profiles:
            self._profiles[name].display_name = \
                new_display[:50]
            self.save()

    # ── Selection ─────────────────────────────────────────────────────────

    def select(self, name: str) -> Profile | None:
        """Select a profile as current."""
        profile = self._profiles.get(name)
        if not profile:
            return None
        self._current = profile
        from datetime import datetime, timezone
        profile.last_used = \
            datetime.now(timezone.utc).isoformat()
        self.save()
        return profile

    def last_used(self) -> Profile | None:
        """Return the last used profile."""
        if not PROFILES_META.exists():
            return None
        try:
            data = json.loads(
                PROFILES_META.read_text())
            name = data.get("last_used", "default")
            return self._profiles.get(name)
        except Exception:
            return None

    # ── Migration ─────────────────────────────────────────────────────────

    def _migrate_legacy(self):
        """
        Migrate from pre-profile config.json to default profile.
        Called on first launch with profile support.
        """
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
        except Exception:
            pass

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
        cur = pm.current   # @property — no parentheses
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

    def create_named(self, display_name: str) -> bool:
        """Create a new profile with given display name (convenience wrapper).
        Slug is auto-generated from display_name.
        """
        pm = get_profile_manager()
        slug = re.sub(r'[^a-z0-9_]', '_', display_name.lower().strip())[:20] or "profile"
        try:
            pm.create(slug, display_name)
            return True
        except Exception as e:
            log.debug(f"Profile create_named failed: {e}")
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
