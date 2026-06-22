"""Secret Group - Group relationship table (RBAC)."""

from sqlalchemy import Column, Enum, ForeignKey, Integer, String

from app.database import Base


class SecretGroupMember(Base):
    """Junction table between SecretGroup and Group (RBAC)."""

    __tablename__ = "secret_group_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    secret_group_id = Column(
        Integer, ForeignKey("secret_groups.id"), nullable=False, index=True
    )
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False, index=True)
    permission = Column(
        String(20), nullable=False, default="read", server_default="read"
    )

    def __repr__(self) -> str:
        return f"<SecretGroupMember sg={self.secret_group_id} group={self.group_id} perm={self.permission}>"
