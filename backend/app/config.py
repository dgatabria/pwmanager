"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/password_manager"
    SECRET_KEY: str = "change-this-to-a-secure-random-string-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    ENCRYPTION_KEY: str = "change-this-to-a-32-byte-base64-encoded-key"

    class Config:
        env_file = ".env"


settings = Settings()
