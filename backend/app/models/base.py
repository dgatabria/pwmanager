"""Base model with common fields."""

from datetime import datetime

from sqlalchemy import Column, DateTime, func
from sqlalchemy.orm import DeclarativeBase

from app.database import Base


class TimestampMixin:
    """Mixin for models with timestamps."""

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
