"""Encryption service for secrets at rest using Fernet symmetric encryption."""

import base64
import os

from cryptography.fernet import Fernet

from app.config import settings

# Path to persist the encryption key across restarts
# Stored inside the app directory so it is bundled with the application image
# and can be mounted as a Docker volume for persistence across restarts
_ENCRYPTION_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".encryption_key")


class EncryptionService:
    """Service for encrypting and decrypting secrets."""

    @staticmethod
    def _load_or_generate_key() -> str:
        """Load encryption key from persistent storage or generate one.

        Priority:
        1. ENCRYPTION_KEY environment variable (set at startup by config)
        2. Persisted key file (read on first call, cached in settings)
        3. Generate new key and persist to file

        Raises:
            RuntimeError: If no encryption key is configured and no
                persistent storage is available (e.g., read-only filesystem).
        """
        key = settings.ENCRYPTION_KEY

        # If user provided a real key via env var, use it directly
        if key:
            return key

        # If we already generated and cached a key in this process, use it
        cached_key = settings.ENCRYPTION_KEY
        if cached_key:
            return cached_key

        # Try to load from persistent file
        if os.path.exists(_ENCRYPTION_KEY_FILE):
            try:
                with open(_ENCRYPTION_KEY_FILE, "r") as f:
                    persisted_key = f.read().strip()
                if persisted_key:
                    settings.ENCRYPTION_KEY = persisted_key
                    return persisted_key
            except OSError:
                pass  # Fall through to generation

        # Generate a new key and persist it (exclusive creation to prevent
        # TOCTOU race where two processes generate different keys)
        new_key = base64.urlsafe_b64encode(os.urandom(32)).decode()
        try:
            with open(_ENCRYPTION_KEY_FILE, "x") as f:
                f.write(new_key)
            settings.ENCRYPTION_KEY = new_key
            return new_key
        except FileExistsError:
            # Another process created the file between our exists() check
            # and the open() call — read it instead
            with open(_ENCRYPTION_KEY_FILE, "r") as f:
                persisted_key = f.read().strip()
            if persisted_key:
                settings.ENCRYPTION_KEY = persisted_key
                return persisted_key
            raise RuntimeError(
                "Cannot start: encryption key is not configured and "
                "the application cannot persist a new key to disk. "
                f"Set the ENCRYPTION_KEY environment variable to a valid "
                f"32-byte base64-encoded key, or ensure write access to {_ENCRYPTION_KEY_FILE}"
            )
        except OSError:
            raise RuntimeError(
                "Cannot start: encryption key is not configured and "
                "the application cannot persist a new key to disk. "
                f"Set the ENCRYPTION_KEY environment variable to a valid "
                f"32-byte base64-encoded key, or ensure write access to {_ENCRYPTION_KEY_FILE}"
            )

    @staticmethod
    def _get_fernet() -> Fernet:
        """Get Fernet instance from configured key."""
        key = EncryptionService._load_or_generate_key()
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
