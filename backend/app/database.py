"""Database configuration."""

import re
from urllib.parse import urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Ensure SSL is always used for PostgreSQL connections.
# If the DATABASE_URL does not already contain an sslmode parameter,
# append ?sslmode=require to enforce TLS encryption.
_db_url = settings.DATABASE_URL
if "postgresql" in _db_url and "sslmode=" not in _db_url:
    # Append sslmode=require to enforce encrypted connections
    # This prevents man-in-the-middle attacks on database traffic.
    separator = "&" if "?" in _db_url else "?"
    settings.DATABASE_URL = f"{_db_url}{separator}sslmode=require"

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for ORM models."""

    pass


async def get_db() -> AsyncSession:
    """Dependency to get async database session."""
    async with async_session() as session:
        yield session


async def init_db():
    """Initialize database tables and run pending migrations."""
    from app.models.user import User
    from app.models.group import Group
    from app.models.secret_group import SecretGroup
    from app.models.secret import Secret
    from app.models.user_group import UserGroup
    from app.models.secret_group_member import SecretGroupMember
    from app.models.audit_log import AuditLog
    from app.models.api_token import APIToken
    from app.models.saml_config import SAMLConfig

    await engine.create_all()

    # Run pending migrations
    from app.migrations import run_migrations
    await run_migrations()
