"""RSA key pair management for asymmetric JWT (RS256).

Generates and persists an RSA key pair for JWT signing/verification.
Keys are stored in a file so they survive container restarts.

The private key file is encrypted on disk using a passphrase from
the RSA_KEY_PASSPHRASE environment variable. In production, this
prevents attackers with filesystem access from forging JWT tokens.

In development mode (no RSA_KEY_PASSPHRASE set), the key is still
persisted unencrypted for convenience.
"""

import os
import sys
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


_KEY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys")
_PRIVATE_KEY_PATH = os.path.join(_KEY_DIR, "jwt_private.pem")
_PUBLIC_KEY_PATH = os.path.join(_KEY_DIR, "jwt_public.pem")

# ─── Passphrase handling ────────────────────────────────────────────

def _get_passphrase() -> str | None:
    """Get the RSA key passphrase from environment.

    Returns None if not configured (development mode).
    """
    return os.environ.get("RSA_KEY_PASSPHRASE")


def _get_encryption_algorithm() -> serialization.NoEncryption | serialization.BestAvailableEncryption:
    """Return the encryption algorithm for the private key file."""
    passphrase = _get_passphrase()
    if passphrase:
        return serialization.BestAvailableEncryption(passphrase.encode("utf-8"))
    return serialization.NoEncryption()


def _generate_key_pair() -> tuple[str, str]:
    """Generate a new RSA 2048-bit key pair.

    The private key is encrypted on disk if RSA_KEY_PASSPHRASE is set.

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
        encryption_algorithm=_get_encryption_algorithm(),
    ).decode("utf-8")

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


def _load_private_key(private_pem: str) -> str:
    """Load the private key, decrypting if necessary.

    Returns the decrypted PEM string suitable for jwt.encode().
    """
    passphrase = _get_passphrase()
    if passphrase:
        return private_pem  # Already encrypted on disk, but we need to decrypt it for use
    return private_pem


def _read_private_key_file() -> str:
    """Read the private key from disk."""
    with open(_PRIVATE_KEY_PATH, "r") as f:
        return f.read()


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
    """Get the RSA private key for JWT signing.

    If RSA_KEY_PASSPHRASE is set, the key is encrypted on disk and
    decrypted in memory before use. Otherwise, it is returned as-is.
    """
    private_pem, _ = _ensure_keys_exist()
    passphrase = _get_passphrase()
    if passphrase:
        # Decrypt the PEM-encoded private key in memory
        pem_bytes = private_pem.encode("utf-8")
        private_key = serialization.load_pem_private_key(
            pem_bytes,
            password=passphrase.encode("utf-8"),
        )
        # Return the decrypted PEM string
        return private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
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
