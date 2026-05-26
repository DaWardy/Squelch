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
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.credentials import CredentialStore, get_store


class TestCredentialStoreMemory:
    """Tests using memory-only storage (no actual keyring needed)."""

    def setup_method(self):
        """Fresh store for each test, won't persist to keyring."""
        self.store = CredentialStore("test_profile_xxx")
        # Only use memory-based operations in these tests
        self.store._memory = {}

    def test_store_and_retrieve(self):
        """Basic store and retrieve."""
        self.store._memory["test_key"] = "test_value"
        assert self.store._memory.get("test_key") == "test_value"

    def test_empty_key_not_stored(self):
        """Empty values should not be stored."""
        result = self.store.store("empty_key", "")
        assert "empty_key" not in self.store._memory

    def test_store_sets_memory(self):
        """Store should always update memory cache."""
        self.store.store("qrz_test", "mypassword")
        # Memory should be set regardless of keyring
        assert self.store._memory.get("qrz_test") == "mypassword"

    def test_retrieve_from_memory(self):
        """Retrieve should check memory first."""
        self.store._memory["cached_key"] = "cached_value"
        result = self.store.retrieve("cached_key")
        assert result == "cached_value"

    def test_retrieve_missing_returns_empty(self):
        """Missing key returns empty string."""
        result = self.store.retrieve("nonexistent_key_xyz")
        assert result == ""

    def test_has_key(self):
        """has() checks memory correctly."""
        self.store._memory["present_key"] = "value"
        assert self.store.has("present_key") is True
        assert self.store.has("absent_key") is False

    def test_delete_from_memory(self):
        """Delete removes from memory."""
        self.store._memory["del_key"] = "del_value"
        self.store.delete("del_key")
        assert "del_key" not in self.store._memory

    def test_delete_nonexistent_safe(self):
        """Deleting non-existent key should not raise."""
        self.store.delete("never_existed_key")  # should not raise

    def test_profile_name_preserved(self):
        assert self.store.profile == "test_profile_xxx"

    def test_service_name_includes_profile(self):
        assert "test_profile_xxx" in self.store._service

    def test_credential_never_empty_string_stored(self):
        """Empty string credentials should be rejected."""
        self.store.store("key", "")
        assert "key" not in self.store._memory


class TestCredentialStoreIsolation:
    """Tests that profiles are isolated from each other."""

    def test_different_profiles_isolated(self):
        """Two profiles should have separate memory caches."""
        store1 = CredentialStore("profile_alpha_test")
        store2 = CredentialStore("profile_beta_test")

        store1._memory["shared_key"] = "profile1_value"
        store2._memory["shared_key"] = "profile2_value"

        assert store1.retrieve("shared_key") == "profile1_value"
        assert store2.retrieve("shared_key") == "profile2_value"

    def test_different_service_names(self):
        """Different profiles should use different service names."""
        store1 = CredentialStore("profile_aaa_test")
        store2 = CredentialStore("profile_bbb_test")
        assert store1._service != store2._service

    def test_delete_in_one_profile_not_affects_other(self):
        """Deleting in one profile should not affect another."""
        store1 = CredentialStore("del_test_profile_1")
        store2 = CredentialStore("del_test_profile_2")

        store1._memory["key"] = "val1"
        store2._memory["key"] = "val2"

        store1.delete("key")
        assert "key" not in store1._memory
        assert store2._memory.get("key") == "val2"


class TestPasswordHashing:
    """Test master password hashing."""

    def test_hash_with_same_salt_is_deterministic(self):
        """Same password + same salt should produce same hash."""
        import os
        store = CredentialStore("hash_test_profile")
        salt = os.urandom(32)
        h1 = store._hash_password("test_password_123", salt)
        h2 = store._hash_password("test_password_123", salt)
        assert h1 == h2

    def test_hash_with_random_salt_not_deterministic(self):
        """Random salt means same password gives different hashes."""
        store = CredentialStore("hash_test_profile")
        h1 = store._hash_password("test_password_123")
        h2 = store._hash_password("test_password_123")
        assert h1 != h2  # random salt ensures uniqueness

    def test_different_passwords_different_hashes(self):
        """Different passwords should produce different hashes."""
        store = CredentialStore("hash_test_profile_2")
        h1 = store._hash_password("password_one")
        h2 = store._hash_password("password_two")
        assert h1 != h2

    def test_hash_not_plaintext(self):
        """Hash should not contain the plaintext password."""
        store = CredentialStore("hash_test_profile_3")
        password = "super_secret_password_xyz"
        h = store._hash_password(password)
        assert password not in h

    def test_hash_has_salt(self):
        """New format should include salt:hash separated by colon."""
        store = CredentialStore("hash_test_profile_salt")
        h = store._hash_password("test_password")
        assert ":" in h, "Hash should be salt:hash format"
        parts = h.split(":")
        assert len(parts) == 2
        assert len(parts[0]) > 20  # salt is base64 encoded
        assert len(parts[1]) > 20  # hash is base64 encoded

    def test_different_hashes_with_same_password(self):
        """Same password should produce different hashes (random salt)."""
        store = CredentialStore("hash_test_random_salt")
        h1 = store._hash_password("same_password")
        h2 = store._hash_password("same_password")
        assert h1 != h2, "Random salt should produce unique hashes"

    def test_verify_hash_correct_password(self):
        """_verify_hash should return True for correct password."""
        store = CredentialStore("verify_test_profile")
        h = store._hash_password("correct_password")
        assert store._verify_hash("correct_password", h) is True

    def test_verify_hash_wrong_password(self):
        """_verify_hash should return False for wrong password."""
        store = CredentialStore("verify_test_profile_2")
        h = store._hash_password("correct_password")
        assert store._verify_hash("wrong_password", h) is False

    def test_hash_is_string(self):
        store = CredentialStore("hash_test_profile_4")
        h = store._hash_password("any_password")
        assert isinstance(h, str)
        assert len(h) > 20

    def test_empty_password_hashes(self):
        """Empty password should still produce a hash."""
        store = CredentialStore("hash_test_profile_5")
        h = store._hash_password("")
        assert isinstance(h, str)
        assert len(h) > 0


class TestGetStore:

    def test_get_store_returns_store(self):
        store = get_store("module_test_profile")
        assert isinstance(store, CredentialStore)

    def test_get_store_same_profile_same_instance(self):
        """Same profile name should return same instance."""
        store1 = get_store("singleton_test_profile_abc")
        store2 = get_store("singleton_test_profile_abc")
        assert store1 is store2

    def test_get_store_different_profiles_different_instances(self):
        store1 = get_store("singleton_test_1")
        store2 = get_store("singleton_test_2")
        assert store1 is not store2
