"""Maintenance mode management (database-backed).

Persistent flag stored in the database so it survives restarts and works
correctly across multiple worker processes. Used during encryption key
rotation to prevent data corruption.

This module is intentionally separate from main.py to avoid circular imports.
"""

from app.database import async_session
from app.models.app_settings import AppSettings


async def set_maintenance_mode(active: bool) -> None:
    """Enable or disable maintenance mode (database-backed)."""
    async with async_session() as session:
        result = await session.execute(AppSettings.__table__.select().limit(1))
        row = result.scalar_one_or_none()
        if row is None:
            row = AppSettings(maintenance_mode=active)
            session.add(row)
        else:
            row.maintenance_mode = active
        await session.commit()


async def is_maintenance_mode() -> bool:
    """Check if the application is in maintenance mode (database-backed)."""
    async with async_session() as session:
        result = await session.execute(AppSettings.__table__.select().limit(1))
        row = result.scalar_one_or_none()
        return row.maintenance_mode if row else False
