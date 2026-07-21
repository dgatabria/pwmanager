"""Encryption service for secrets at rest using Fernet symmetric encryption."""

import base64

from cryptography.fernet import Fernet

from app.config import settings


class EncryptionService:
    """Service for encrypting and decrypting secrets."""

    @staticmethod
    def _is_valid_fernet_key(key: str) -> bool:
        """Check if a string is a valid Fernet key (32 url-safe base64 bytes)."""
        try:
            Fernet(key.encode())
            return True
        except Exception:
            return False

    @staticmethod
    def _get_encryption_key() -> str:
        """Load and validate the encryption key from application settings.

        Raises:
            RuntimeError: If ENCRYPTION_KEY is not configured or invalid.
        """
        key = settings.ENCRYPTION_KEY
        if key and EncryptionService._is_valid_fernet_key(key):
            return key

        raise RuntimeError(
            "FATAL: ENCRYPTION_KEY is not configured or is not a valid 32-byte base64 Fernet key. "
            "Set the ENCRYPTION_KEY environment variable (e.g., generated with `openssl rand -base64 32`)."
        )

    @staticmethod
    def _get_fernet() -> Fernet:
        """Get Fernet instance from configured key."""
        key = EncryptionService._get_encryption_key()
        return Fernet(key.encode())

    @staticmethod
    def encrypt(plaintext: str) -> str:
        """Encrypt a string value."""
        fernet = EncryptionService._get_fernet()
        encrypted = fernet.encrypt(plaintext.encode("utf-8"))
        return base64.b64encode(encrypted).decode("utf-8")

    @staticmethod
    def decrypt(ciphertext: str) -> str:
        """Decrypt a string value."""
        fernet = EncryptionService._get_fernet()
        decoded = base64.b64decode(ciphertext.encode("utf-8"))
        decrypted = fernet.decrypt(decoded)
        return decrypted.decode("utf-8")
