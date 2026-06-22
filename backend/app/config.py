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

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    class Config:
        env_file = ".env"

    def get_allowed_origins_list(self) -> List[str]:
        """Parse ALLOWED_ORIGINS into a list of origin strings."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


# ─── Startup validation ───────────────────────────────────────────────

settings = Settings()

# Require secrets at startup — never fall back to placeholders
settings.DATABASE_URL = _require_secret("DATABASE_URL")
settings.ENCRYPTION_KEY = _require_secret("ENCRYPTION_KEY")
