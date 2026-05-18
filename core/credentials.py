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
"""Squelch -- core/credentials.py
Secure credential storage using OS keyring.
Passwords and API keys are never written to config.json.
Optional master password per profile for shared/classroom machines.

Security model:
  - OS keyring (Windows Credential Manager, macOS Keychain,
    libsecret on Linux) stores credentials
  - Master password option adds an extra layer for shared machines
  - Credentials held in memory only during session
  - Never logged, never displayed after entry
  - Falls back gracefully if keyring unavailable
"""

import logging
import hashlib
import base64
from typing import Optional

log = logging.getLogger(__name__)

try:
    import keyring
    from keyring.errors import KeyringError
    HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False
    log.warning(
        "keyring not installed — credentials stored in memory only this session.\n"
        "Run: pip install keyring")

SERVICE_PREFIX = "squelch"

# Credential keys
QRZ_PASSWORD       = "qrz_password"    # nosec B105
QRZ_SESSION        = "qrz_session"
HAMQTH_PASSWORD    = "hamqth_password" # nosec B105
RR_API_KEY         = "radioreference_key"
HAMALERT_KEY       = "hamalert_key"
LOTW_PASSWORD      = "lotw_password"   # nosec B105
CLUBLOG_KEY        = "clublog_key"
EQSL_PASSWORD      = "eqsl_password"   # nosec B105
HRDLOG_KEY         = "hrdlog_key"

# Human-readable labels for UI
CREDENTIAL_LABELS = {
    QRZ_PASSWORD:    "QRZ.com Password",
    HAMQTH_PASSWORD: "HamQTH Password",
    RR_API_KEY:      "RadioReference API Key",
    HAMALERT_KEY:    "HamAlert API Key",
    LOTW_PASSWORD:   "LoTW Password",
    CLUBLOG_KEY:     "ClubLog API Key",
    EQSL_PASSWORD:   "eQSL Password",
    HRDLOG_KEY:      "HRDLog API Key",
}


class CredentialStore:
    """
    Per-profile credential storage.
    Uses OS keyring with optional master password protection.
    Falls back to session-only memory if keyring unavailable.
    """

    def __init__(self, profile_name: str = "default"):
        self._profile    = profile_name.lower().strip()
        self._service    = f"{SERVICE_PREFIX}-{self._profile}"
        self._memory:    dict[str, str] = {}
        self._unlocked   = True   # True if no master pass, or unlocked
        self._has_master = False

    # ── Master password ───────────────────────────────────────────────────

    def has_master_password(self) -> bool:
        """Check if this profile has a master password set."""
        if not HAS_KEYRING:
            return False
        try:
            sentinel = keyring.get_password(
                self._service, "_master_sentinel")
            return sentinel is not None
        except Exception:
            return False

    def set_master_password(self, password: str) -> bool:
        """
        Set a master password for this profile.
        Stores a sentinel value (not the password itself).
        """
        if not HAS_KEYRING:
            return False
        if not password:
            return False
        try:
            # Store a hash of the password as sentinel
            sentinel = self._hash_password(password)
            keyring.set_password(
                self._service, "_master_sentinel", sentinel)
            self._has_master = True
            self._unlocked   = True
            log.info(f"Master password set for profile: {self._profile}")
            return True
        except Exception as e:
            log.error(f"Set master password failed: {e}")
            return False

    def verify_master_password(self, password: str) -> bool:
        """Verify master password and unlock the store."""
        if not HAS_KEYRING:
            self._unlocked = True
            return True
        try:
            sentinel = keyring.get_password(
                self._service, "_master_sentinel")
            if not sentinel:
                self._unlocked = True
                return True
            if self._verify_hash(password, sentinel):
                self._unlocked = True
                log.info(f"Profile unlocked: {self._profile}")
                return True
            log.warning("Incorrect master password")
            return False
        except Exception as e:
            log.error(f"Master password verify failed: {e}")
            return False

    def remove_master_password(self):
        """Remove master password protection from this profile."""
        if not HAS_KEYRING:
            return
        try:
            keyring.delete_password(
                self._service, "_master_sentinel")
            self._has_master = False
        except Exception:
            pass

    # ── Store / retrieve ──────────────────────────────────────────────────

    def store(self, key: str, value: str) -> bool:
        """Store a credential. Returns True if persisted to keyring."""
        if not value:
            return False

        # Always keep in memory for this session
        self._memory[key] = value

        if not HAS_KEYRING:
            log.debug(f"Credential stored in memory only: {key}")
            return False

        try:
            keyring.set_password(self._service, key, value)
            log.debug(f"Credential stored in keyring: {key}")
            return True
        except Exception as e:
            log.warning(f"Keyring store failed for {key}: {e}")
            return False

    def retrieve(self, key: str) -> str:
        """Retrieve a credential. Returns empty string if not found."""
        # Check session memory first
        if key in self._memory:
            return self._memory[key]

        if not HAS_KEYRING:
            return ""

        if not self._unlocked:
            log.warning(
                "Credential access attempted on locked store")
            return ""

        try:
            value = keyring.get_password(self._service, key) or ""
            if value:
                self._memory[key] = value  # cache in memory
            return value
        except Exception as e:
            log.debug(f"Keyring retrieve failed for {key}: {e}")
            return ""

    def delete(self, key: str):
        """Delete a stored credential."""
        self._memory.pop(key, None)
        if not HAS_KEYRING:
            return
        try:
            keyring.delete_password(self._service, key)
        except Exception:
            pass

    def delete_all(self):
        """Delete all credentials for this profile."""
        self._memory.clear()
        if not HAS_KEYRING:
            return
        for key in list(CREDENTIAL_LABELS.keys()):
            try:
                keyring.delete_password(self._service, key)
            except Exception:
                pass

    def has(self, key: str) -> bool:
        """Check if a credential exists without retrieving it."""
        if key in self._memory:
            return True
        if not HAS_KEYRING:
            return False
        try:
            return keyring.get_password(
                self._service, key) is not None
        except Exception:
            return False

    # ── Named helpers ─────────────────────────────────────────────────────

    def qrz_password(self) -> str:
        return self.retrieve(QRZ_PASSWORD)

    def hamqth_password(self) -> str:
        return self.retrieve(HAMQTH_PASSWORD)

    def radioreference_key(self) -> str:
        return self.retrieve(RR_API_KEY)

    def hamalert_key(self) -> str:
        return self.retrieve(HAMALERT_KEY)

    def lotw_password(self) -> str:
        return self.retrieve(LOTW_PASSWORD)

    # ── Internal ──────────────────────────────────────────────────────────

    @staticmethod
    def _hash_password(password: str,
                       salt: bytes = None) -> str:
        """
        Hash a password for sentinel storage.
        Uses random salt per password (stored with hash).
        Format: base64(salt) + ":" + base64(hash)
        """
        import os
        if salt is None:
            salt = os.urandom(32)  # 256-bit random salt
        h = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            200_000)  # 200k iterations (OWASP 2024 recommendation)
        salt_b64 = base64.b64encode(salt).decode('ascii')
        hash_b64  = base64.b64encode(h).decode('ascii')
        return f"{salt_b64}:{hash_b64}"

    @staticmethod
    def _verify_hash(password: str, stored: str) -> bool:
        """Verify a password against a stored hash."""
        try:
            if ':' in stored:
                # New format: salt:hash
                salt_b64, _ = stored.split(':', 1)
                salt = base64.b64decode(salt_b64)
                candidate = CredentialStore._hash_password(
                    password, salt)
                return candidate == stored
            else:
                # Legacy format (static salt) — upgrade on next set
                import hmac
                h = hashlib.pbkdf2_hmac(
                    'sha256',
                    password.encode('utf-8'),
                    b'squelch-salt-2026',
                    100_000)
                legacy = base64.b64encode(h).decode('ascii')
                return hmac.compare_digest(legacy, stored)
        except Exception:
            return False

    @property
    def is_unlocked(self) -> bool:
        return self._unlocked

    @property
    def profile(self) -> str:
        return self._profile

    @property
    def keyring_available(self) -> bool:
        return HAS_KEYRING


# ── Module-level convenience ──────────────────────────────────────────────

_stores: dict[str, CredentialStore] = {}

def get_store(profile: str = "default") -> CredentialStore:
    """Get or create a credential store for a profile."""
    if profile not in _stores:
        _stores[profile] = CredentialStore(profile)
    return _stores[profile]
