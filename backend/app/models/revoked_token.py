"""Revoked JWT tokens model for server-side token invalidation."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RevokedToken(Base):
    """Model for storing revoked JWT tokens.

    When a user logs out or a token is explicitly revoked, the JWT
    identifier (jti) is stored here. During token validation, the
    system checks this table to ensure revoked tokens are rejected
    even if they haven't expired yet.
    """

    __tablename__ = "revoked_tokens"

    id: Mapped[int] = mapped_column(
        "id", primary_key=True, autoincrement=True
    )
    jti: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        "user_id", String(64), index=True, nullable=False
    )
    reason: Mapped[str] = mapped_column(
        String(100), nullable=False, default="logout"
    )
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return f"<RevokedToken jti={self.jti} user_id={self.user_id}>"
