"""Secret group model for organizing secrets hierarchically."""

from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SecretGroup(Base):
    """Secret group for organizing secrets hierarchically."""

    __tablename__ = "secret_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("secret_groups.id"), nullable=True
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(default=True)

    # Relationships
    parent: Mapped["SecretGroup | None"] = relationship(
        "SecretGroup", remote_side=[id], back_populates="children"
    )
    children: Mapped[list["SecretGroup"]] = relationship(
        back_populates="parent", lazy="selectin"
    )
    secrets: Mapped[list["Secret"]] = relationship(
        back_populates="group", lazy="selectin"
    )
    groups: Mapped[list["Group"]] = relationship(
        secondary="secret_group_members", back_populates="secret_groups", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<SecretGroup {self.name}>"
