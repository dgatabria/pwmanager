"""Password hashing utilities."""

import bcrypt

from app.database import async_session
from app.models.user import User


class SecurityUtils:
    """Utilities for password hashing and SSH key generation."""

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
