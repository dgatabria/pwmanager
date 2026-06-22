"""Application configuration."""

import os
from typing import List

from pydantic_settings import BaseSettings


def _read_secret(secret_name: str, default: str) -> str:
    """Read a secret value.

    Priority:
    1. Environment variable (same name as secret_name, uppercase)
    2. Docker secrets file (/run/secrets/<secret_name>)
    3. Default value

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

    # 3. Return default
    return default


class Settings(BaseSettings):
    """Application settings."""

    DATABASE_URL: str = _read_secret("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@db:5432/password_manager")
    SECRET_KEY: str = _read_secret("SECRET_KEY", "change-this-to-a-secure-random-string-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    ENCRYPTION_KEY: str = _read_secret("ENCRYPTION_KEY", "change-this-to-a-32-byte-base64-encoded-key")

    # CORS - comma-separated list of allowed origins (domains)
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # Rate limiting - requests per time window
    RATE_LIMIT: str = "5/minute"  # Default: 5 requests per minute for auth endpoints

    class Config:
        env_file = ".env"

    def get_allowed_origins_list(self) -> List[str]:
        """Parse ALLOWED_ORIGINS into a list of origin strings."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


settings = Settings()
