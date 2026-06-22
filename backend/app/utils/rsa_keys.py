"""RSA key pair management for asymmetric JWT (RS256).

Generates and persists an RSA key pair for JWT signing/verification.
Keys are stored in a file so they survive container restarts.
"""

import os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


_KEY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys")
_PRIVATE_KEY_PATH = os.path.join(_KEY_DIR, "jwt_private.pem")
_PUBLIC_KEY_PATH = os.path.join(_KEY_DIR, "jwt_public.pem")


def _generate_key_pair() -> tuple[str, str]:
    """Generate a new RSA 2048-bit key pair.

    Returns:
        Tuple of (private_pem, public_pem) strings.
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


def _ensure_keys_exist() -> tuple[str, str]:
    """Ensure both private and public keys exist, generating if necessary.

    This guarantees that the private and public keys come from the same
    key pair by generating both at the same time.

    Returns:
        Tuple of (private_pem, public_pem) strings.
    """
    os.makedirs(_KEY_DIR, exist_ok=True)

    # If neither key exists, generate both
    if not os.path.exists(_PRIVATE_KEY_PATH) and not os.path.exists(_PUBLIC_KEY_PATH):
        private_pem, public_pem = _generate_key_pair()
        with open(_PRIVATE_KEY_PATH, "w") as f:
            f.write(private_pem)
        with open(_PUBLIC_KEY_PATH, "w") as f:
            f.write(public_pem)
        return private_pem, public_pem

    # Load existing keys
    with open(_PRIVATE_KEY_PATH, "r") as f:
        private_pem = f.read()
    with open(_PUBLIC_KEY_PATH, "r") as f:
        public_pem = f.read()

    return private_pem, public_pem


def get_private_key() -> str:
    """Get the RSA private key, generating and persisting one if it does not exist."""
    private_pem, _ = _ensure_keys_exist()
    return private_pem


def get_public_key() -> str:
    """Get the RSA public key, generating a key pair if neither key exists."""
    _, public_pem = _ensure_keys_exist()
    return public_pem


def get_key_pair() -> tuple[str, str]:
    """Ensure both private and public keys exist and return them.

    Returns:
        Tuple of (private_pem, public_pem) strings.
    """
    return _ensure_keys_exist()
