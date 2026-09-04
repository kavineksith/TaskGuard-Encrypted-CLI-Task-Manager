"""Tests for AES-256-GCM Vault: encryption, decryption, KDF, tamper detection."""

from __future__ import annotations

import os
import struct
import tempfile
from pathlib import Path

import pytest

from src.crypto.vault import Vault
from src.core.exceptions import (
    EncryptionError, DecryptionError, TamperedDataError,
    InvalidKeyError, KeyStoreError,
)


@pytest.fixture
def vault():
    return Vault.from_key(b"\xAB" * 32)


@pytest.fixture
def tmp_cfg(tmp_path):
    return tmp_path / "taskguard.cfg"


class TestVaultCreation:
    def test_from_key_valid(self):
        v = Vault.from_key(b"\x00" * 32)
        assert bool(v) is True

    def test_from_key_short_raises(self):
        with pytest.raises(InvalidKeyError):
            Vault.from_key(b"\x00" * 16)

    def test_from_key_long_raises(self):
        with pytest.raises(InvalidKeyError):
            Vault.from_key(b"\x00" * 64)

    def test_repr(self):
        v = Vault.from_key(b"\x01" * 32)
        assert "AES-256" in repr(v)

    def test_bool(self):
        v = Vault.from_key(b"\x01" * 32)
        assert bool(v) is True

    def test_eq_same_key(self):
        v1 = Vault.from_key(b"\x01" * 32)
        v2 = Vault.from_key(b"\x01" * 32)
        assert v1 == v2

    def test_eq_different_key(self):
        v1 = Vault.from_key(b"\x01" * 32)
        v2 = Vault.from_key(b"\x02" * 32)
        assert v1 != v2


class TestEncryptDecrypt:
    def test_encrypt_returns_bytes(self, vault):
        ct, nonce = vault.encrypt(b"hello world")
        assert isinstance(ct, bytes) and isinstance(nonce, bytes)

    def test_nonce_is_12_bytes(self, vault):
        _, nonce = vault.encrypt(b"test")
        assert len(nonce) == 12

    def test_decrypt_roundtrip(self, vault):
        plaintext = b"TaskGuard secure data"
        ct, nonce = vault.encrypt(plaintext)
        result    = vault.decrypt(ct, nonce)
        assert result == plaintext

    def test_encrypt_different_nonces(self, vault):
        ct1, n1 = vault.encrypt(b"same")
        ct2, n2 = vault.encrypt(b"same")
        assert n1 != n2    # nonces must be random

    def test_tampered_ciphertext_raises(self, vault):
        ct, nonce = vault.encrypt(b"secret")
        bad_ct    = bytes([ct[0] ^ 0xFF]) + ct[1:]
        with pytest.raises(TamperedDataError):
            vault.decrypt(bad_ct, nonce)

    def test_tampered_nonce_raises(self, vault):
        ct, nonce = vault.encrypt(b"secret")
        bad_nonce = bytes([nonce[0] ^ 0xFF]) + nonce[1:]
        with pytest.raises(TamperedDataError):
            vault.decrypt(ct, bad_nonce)
    def test_wrong_key_raises(self, vault):
        ct, nonce   = vault.encrypt(b"data")
        other_vault = Vault.from_key(b"\xCC" * 32)
        with pytest.raises((TamperedDataError, DecryptionError)):
            other_vault.decrypt(ct, nonce)

    def test_empty_plaintext(self, vault):
        ct, nonce = vault.encrypt(b"")
        result    = vault.decrypt(ct, nonce)
        assert result == b""

    def test_large_plaintext(self, vault):
        data = os.urandom(100_000)
        ct, nonce = vault.encrypt(data)
        assert vault.decrypt(ct, nonce) == data


class TestEncryptDecryptJSON:
    def test_json_roundtrip(self, vault):
        payload = {"title": "Test", "tags": ["a", "b"], "notes": "ok"}
        ct, nonce = vault.encrypt_json(payload)
        result    = vault.decrypt_json(ct, nonce)
        assert result == payload

    def test_json_unicode(self, vault):
        payload = {"title": "Tâche spéciale — résumé"}
        ct, nonce = vault.encrypt_json(payload)
        assert vault.decrypt_json(ct, nonce)["title"] == payload["title"]

    def test_json_tamper_raises(self, vault):
        ct, nonce = vault.encrypt_json({"x": 1})
        bad_ct    = bytes([ct[0] ^ 0x01]) + ct[1:]
        with pytest.raises((TamperedDataError, DecryptionError)):
            vault.decrypt_json(bad_ct, nonce)


class TestSaltPersistence:
    def test_save_and_load_salt(self, tmp_cfg):
        v1 = Vault.from_password("test-password", tmp_cfg)
        assert tmp_cfg.exists()
        v2 = Vault.from_password("test-password", tmp_cfg)
        # Same password + same salt → same key → equal vaults
        assert v1 == v2

    def test_different_password_different_vault(self, tmp_cfg):
        v1 = Vault.from_password("password-one", tmp_cfg)
        # Remove config so second call generates a fresh salt
        tmp_cfg.unlink()
        v2 = Vault.from_password("password-two", tmp_cfg)
        assert v1 != v2

    def test_corrupt_config_raises(self, tmp_cfg):
        tmp_cfg.write_bytes(b"BADHEADER_NOTVALID")
        with pytest.raises(KeyStoreError):
            Vault.from_password("pw", tmp_cfg)

    def test_config_permissions(self, tmp_cfg):
        Vault.from_password("test", tmp_cfg)
        mode = oct(tmp_cfg.stat().st_mode)[-3:]
        assert mode == "600"
