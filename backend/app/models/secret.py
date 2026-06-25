"""Secret model for storing encrypted credentials."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

import enum


class SecretType(str, enum.Enum):
    """Types of secrets."""

    SSH_KEY = "ssh_key"
    PASSWORD = "password"
    CREDENTIAL = "credential"
    API_KEY = "api_key"
    CUSTOM = "custom"


class Secret(Base):
    """Encrypted secret storage."""

    __tablename__ = "secrets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    secret_type: Mapped[SecretType] = mapped_column(SAEnum(SecretType), nullable=False)
    encrypted_data: Mapped[str] = mapped_column(Text, nullable=False)
    key_length: Mapped[int | None] = mapped_column(Integer, nullable=True)  # For SSH keys
    username: Mapped[str | None] = mapped_column(String(200), nullable=True)  # For credentials
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("secret_groups.id"), nullable=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    group: Mapped["SecretGroup"] = relationship(
        back_populates="secrets", lazy="selectin"
    )
    owner: Mapped["User"] = relationship(
        back_populates="secrets", lazy="selectin"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="secret", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Secret {self.title} ({self.secret_type.value})>"
