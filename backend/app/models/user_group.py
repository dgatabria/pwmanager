"""User-Group relationship table."""

from sqlalchemy import Column, ForeignKey, Integer

from app.database import Base


class UserGroup(Base):
    """Junction table between User and Group."""

    __tablename__ = "user_groups"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id"), primary_key=True)
