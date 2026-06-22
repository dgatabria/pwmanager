"""Secret Group - Group relationship table (RBAC)."""

from sqlalchemy import Column, ForeignKey, Integer

from app.database import Base


class SecretGroupMember(Base):
    """Junction table between SecretGroup and Group (RBAC)."""

    __tablename__ = "secret_group_members"

    secret_group_id = Column(
        Integer, ForeignKey("secret_groups.id"), primary_key=True
    )
    group_id = Column(Integer, ForeignKey("groups.id"), primary_key=True)
