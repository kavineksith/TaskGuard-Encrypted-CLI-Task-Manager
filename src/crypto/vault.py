"""
TaskGuard - Cryptographic Vault
AES-256-GCM encryption with Argon2id key derivation.
Keys live only in memory; the Argon2id salt is persisted to disk.
"""

from __future__ import annotations

import json
import os
import secrets
import struct
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from argon2.low_level import hash_secret_raw, Type

from src.constants import (
    ARGON2_TIME_COST, ARGON2_MEMORY_COST, ARGON2_PARALLELISM,
    ARGON2_HASH_LENGTH, ARGON2_SALT_LENGTH, AES_NONCE_LENGTH,
)
from src.core.exceptions import (
    EncryptionError, DecryptionError, KeyDerivationError,
    InvalidKeyError, TamperedDataError, KeyStoreError, NonceGenerationError,
)


class Vault:
    """
    Provides AES-256-GCM encrypt/decrypt backed by an Argon2id-derived key.

    Usage:
        vault = Vault.from_password("my-password", config_path)
        ciphertext, nonce = vault.encrypt(b"plaintext")
        plaintext         = vault.decrypt(ciphertext, nonce)
    """

    KEY_LENGTH = 32   # 256 bits
    _MAGIC     = b"TGVAULT1"   # 8-byte header for config validation

    def __init__(self, key: bytes) -> None:
        if len(key) != self.KEY_LENGTH:
            raise InvalidKeyError(self.KEY_LENGTH)
        self._key  = key
        self._gcm  = AESGCM(key)

    # ── factory constructors ──────────────────────────────────────────────────

    @classmethod
    def from_password(cls, password: str, config_path: Path) -> "Vault":
        """
        Derive a key from *password* using Argon2id.
        If *config_path* does not exist, a new salt is generated and saved.
        If it exists, the stored salt is loaded.
        """
        salt = cls._load_or_create_salt(config_path)
        key  = cls._derive_key(password, salt)
        return cls(key)

    @classmethod
    def from_key(cls, key: bytes) -> "Vault":
        """Construct directly from a 32-byte key (useful for testing)."""
        return cls(key)

    # ── encrypt / decrypt ─────────────────────────────────────────────────────

    def encrypt(self, plaintext: bytes) -> tuple[bytes, bytes]:
        """
        Encrypt *plaintext* with AES-256-GCM.

        Returns:
            (ciphertext_with_tag, nonce)  —  nonce is 12 random bytes.
        """
        try:
            nonce = self._generate_nonce()
        except Exception as exc:
            raise NonceGenerationError(str(exc)) from exc

        try:
            ciphertext = self._gcm.encrypt(nonce, plaintext, None)
            return ciphertext, nonce
        except Exception as exc:
            raise EncryptionError(str(exc)) from exc

    def decrypt(self, ciphertext: bytes, nonce: bytes, record_id: str = "") -> bytes:
        """
        Decrypt *ciphertext* (which includes the GCM auth tag) using *nonce*.

        Raises:
            TamperedDataError  — if the auth tag does not match.
            DecryptionError    — on any other failure.
        """
        from cryptography.exceptions import InvalidTag
        try:
            return self._gcm.decrypt(nonce, ciphertext, None)
        except InvalidTag as exc:
            raise TamperedDataError(record_id) from exc
        except Exception as exc:
            raise DecryptionError(str(exc)) from exc

    def encrypt_json(self, data: dict) -> tuple[bytes, bytes]:
        """Serialize *data* to JSON bytes then encrypt."""
        raw = json.dumps(data, ensure_ascii=False).encode()
        return self.encrypt(raw)

    def decrypt_json(self, ciphertext: bytes, nonce: bytes,
                     record_id: str = "") -> dict:
        """Decrypt and deserialize JSON bytes to a dict."""
        raw = self.decrypt(ciphertext, nonce, record_id)
        return json.loads(raw.decode())

    # ── key derivation ────────────────────────────────────────────────────────

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        """Argon2id key derivation — blocking but intentionally slow."""
        try:
            return hash_secret_raw(
                secret      = password.encode(),
                salt        = salt,
                time_cost   = ARGON2_TIME_COST,
                memory_cost = ARGON2_MEMORY_COST,
                parallelism = ARGON2_PARALLELISM,
                hash_len    = ARGON2_HASH_LENGTH,
                type        = Type.ID,
            )
        except Exception as exc:
            raise KeyDerivationError(str(exc)) from exc

    @staticmethod
    def _generate_nonce() -> bytes:
        """Generate a cryptographically random 12-byte GCM nonce."""
        return secrets.token_bytes(AES_NONCE_LENGTH)

    # ── salt persistence ──────────────────────────────────────────────────────

    @classmethod
    def _load_or_create_salt(cls, config_path: Path) -> bytes:
        if config_path.exists():
            return cls._load_salt(config_path)
        salt = secrets.token_bytes(ARGON2_SALT_LENGTH)
        cls._save_salt(config_path, salt)
        return salt

    @classmethod
    def _save_salt(cls, config_path: Path, salt: bytes) -> None:
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            # Format: magic(8) + salt_len(4, big-endian) + salt
            payload = cls._MAGIC + struct.pack(">I", len(salt)) + salt
            config_path.write_bytes(payload)
            config_path.chmod(0o600)
        except OSError as exc:
            raise KeyStoreError(str(config_path), str(exc)) from exc

    @classmethod
    def _load_salt(cls, config_path: Path) -> bytes:
        try:
            payload = config_path.read_bytes()
        except OSError as exc:
            raise KeyStoreError(str(config_path), str(exc)) from exc

        if len(payload) < 12 or payload[:8] != cls._MAGIC:
            raise KeyStoreError(str(config_path), "File is not a valid TaskGuard config.")

        salt_len = struct.unpack(">I", payload[8:12])[0]
        if len(payload) < 12 + salt_len:
            raise KeyStoreError(str(config_path), "Config file is truncated.")

        return payload[12 : 12 + salt_len]

    # ── helpers ───────────────────────────────────────────────────────────────

    def rekey(self, new_password: str, config_path: Path) -> "Vault":
        """Derive a new key from *new_password* and write a fresh salt."""
        salt = secrets.token_bytes(ARGON2_SALT_LENGTH)
        self.__class__._save_salt(config_path, salt)
        new_key = self._derive_key(new_password, salt)
        return Vault(new_key)

    def __repr__(self) -> str:
        return f"Vault(key=<{self.KEY_LENGTH}-byte AES-256 key>)"

    def __bool__(self) -> bool:
        return len(self._key) == self.KEY_LENGTH

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vault): return NotImplemented
        return secrets.compare_digest(self._key, other._key)

    def __hash__(self) -> int:
        # Constant hash so Vault can be a dict key without leaking key material
        return hash("Vault")
