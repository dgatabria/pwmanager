"""Application configuration."""

from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/password_manager"
    SECRET_KEY: str = "change-this-to-a-secure-random-string-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    ENCRYPTION_KEY: str = "change-this-to-a-32-byte-base64-encoded-key"

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
