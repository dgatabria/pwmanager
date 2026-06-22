"""Group model for user groups (RBAC)."""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Group(Base):
    """User group for RBAC."""

    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    users: Mapped[list["User"]] = relationship(
        secondary="user_groups", back_populates="groups", lazy="selectin"
    )
    secret_groups: Mapped[list["SecretGroup"]] = relationship(
        secondary="secret_group_members", back_populates="groups", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Group {self.name}>"
