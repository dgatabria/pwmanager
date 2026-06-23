"""Application configuration."""

import os
import sys
from typing import List

from pydantic_settings import BaseSettings


def _read_secret(secret_name: str) -> str | None:
    """Read a secret value from environment variable or Docker secrets.

    Priority:
    1. Environment variable (same name as secret_name, uppercase)
    2. Docker secrets file (/run/secrets/<secret_name>)

    Returns None if the secret is not found.

    This allows using Docker secrets in production while keeping
    environment variables for local development.
    """
    # 1. Check environment variable first
    env_value = os.environ.get(secret_name)
    if env_value:
        return env_value

    # 2. Check Docker secrets file
    secret_path = f"/run/secrets/{secret_name}"
    if os.path.exists(secret_path):
        try:
            with open(secret_path, "r") as f:
                value = f.read().strip()
            if value:
                return value
        except OSError:
            pass

    return None


def _require_secret(secret_name: str) -> str:
    """Read a secret and raise an error if it is not configured.

    This ensures that placeholder/default values are never used in production.
    """
    value = _read_secret(secret_name)
    if not value:
        print(
            f"ERROR: Required secret '{secret_name}' is not configured. "
            f"Set the {secret_name} environment variable or provide it via Docker secrets.",
            file=sys.stderr,
        )
        sys.exit(1)
    return value


class Settings(BaseSettings):
    """Application settings."""

    DATABASE_URL: str = ""
    ENCRYPTION_KEY: str = ""

    # CORS - comma-separated list of allowed origins (domains)
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # Rate limiting - requests per time window
    RATE_LIMIT: str = "5/minute"  # Default: 5 requests per minute for auth endpoints

    # Trusted proxy IPs for X-Forwarded-For validation (comma-separated)
    # When configured, X-Forwarded-For is only trusted if the request
    # comes from one of these IPs. Otherwise, the direct connection IP is used.
    TRUSTED_PROXY_IPS: str = ""

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Account lockout settings
    # Maximum number of failed login attempts before account is locked
    MAX_FAILED_LOGIN_ATTEMPTS: int = 5
    # Duration (in minutes) that an account remains locked after exceeding
    # the maximum failed attempts
    LOCKOUT_DURATION_MINUTES: int = 15

    # Enable/disable Swagger UI and ReDoc documentation endpoints
    # Disabled by default in production to avoid leaking API surface
    DOCS_ENABLED: bool = False

    class Config:
        env_file = ".env"

    def get_allowed_origins_list(self) -> List[str]:
        """Parse ALLOWED_ORIGINS into a list of origin strings."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    def get_trusted_proxy_ips(self) -> set[str]:
        """Parse TRUSTED_PROXY_IPS into a set of IP addresses."""
        if not self.TRUSTED_PROXY_IPS:
            return set()
        return {ip.strip() for ip in self.TRUSTED_PROXY_IPS.split(",") if ip.strip()}


# ─── Startup validation ───────────────────────────────────────────────

settings = Settings()

# Require secrets at startup — never fall back to placeholders
settings.DATABASE_URL = _require_secret("DATABASE_URL")
settings.ENCRYPTION_KEY = _require_secret("ENCRYPTION_KEY")

# In production, RSA_KEY_PASSPHRASE must be set to encrypt the RSA private key
# on disk. Without it, anyone with filesystem access can forge JWT tokens.
_rsa_passphrase = _read_secret("RSA_KEY_PASSPHRASE")
if not _rsa_passphrase:
    print(
        "WARNING: RSA_KEY_PASSPHRASE is not set. The RSA private key will be "
        "stored unencrypted on disk. In production, set the RSA_KEY_PASSPHRASE "
        "environment variable or provide it via Docker secrets.",
        file=sys.stderr,
    )
