"""Database configuration."""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

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
    """Initialize database tables."""
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
