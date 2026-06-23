"""Password hashing utilities."""

import re

import bcrypt

from app.database import async_session
from app.models.user import User


class SecurityUtils:
    """Utilities for password hashing and SSH key generation."""

    # Minimum password requirements
    MIN_PASSWORD_LENGTH = 12
    COMMON_PASSWORDS = {
        "password", "password123", "12345678", "123456789", "1234567890",
        "qwerty123", "admin", "admin123", "root", "toor", "letmein",
        "welcome", "monkey", "master", "dragon", "login", "princess",
        "passw0rd", "abc12345", "111111", "000000", "qwerty",
    }

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )

    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, str]:
        """Validate password strength against security policy.

        Requirements:
        - At least 12 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character
        - Not a commonly used password

        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is empty.
        """
        if len(password) < SecurityUtils.MIN_PASSWORD_LENGTH:
            return False, f"Password must be at least {SecurityUtils.MIN_PASSWORD_LENGTH} characters long"

        if not re.search(r"[A-Z]", password):
            return False, "Password must contain at least one uppercase letter"

        if not re.search(r"[a-z]", password):
            return False, "Password must contain at least one lowercase letter"

        if not re.search(r"[0-9]", password):
            return False, "Password must contain at least one digit"

        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?`~]", password):
            return False, "Password must contain at least one special character"

        if password.lower() in SecurityUtils.COMMON_PASSWORDS:
            return False, "Password is too common, please choose a different one"

        return True, ""

    @staticmethod
    def generate_ssh_key(key_length: int = 4096, comment: str = "ssh-key") -> tuple[str, str, str]:
        """Generate an SSH key pair (RSA).

        Returns:
            Tuple of (private_key, public_key, fingerprint)
        """
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509 import Name, NameAttribute

        # Generate RSA key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_length,
        )

        # Serialize private key (PEM format, no encryption for storage)
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.OpenSSH,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        # Serialize public key
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH,
        ).decode("utf-8")

        # Generate fingerprint (SHA256)
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        import hashlib

        digest = hashlib.sha256(public_bytes).hexdigest()
        fingerprint = f"SHA256:{digest}"

        return private_pem, public_pem, fingerprint
