"""Encryption service for secrets at rest using Fernet symmetric encryption."""

import base64
import os

from cryptography.fernet import Fernet

from app.config import settings


class EncryptionService:
    """Service for encrypting and decrypting secrets."""

    @staticmethod
    def _get_fernet() -> Fernet:
        """Get Fernet instance from configured key."""
        key = settings.ENCRYPTION_KEY
        # If key is the default placeholder, generate a random one
        if key == settings.model_fields["ENCRYPTION_KEY"].default:
            key = base64.urlsafe_b64encode(os.urandom(32)).decode()
            settings.ENCRYPTION_KEY = key
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
