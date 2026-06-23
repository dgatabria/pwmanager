"""Migration runner — discovers and executes pending migrations."""

import importlib
import pkgutil
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

_MIGRATIONS_DIR = Path(__file__).parent


async def run_migrations():
    """Discover and run all pending migrations in order."""
    migrations = sorted(
        [m.name.replace(".py", "") for m in _MIGRATIONS_DIR.glob("*.py") if m.name != "__init__.py"]
    )

    for name in migrations:
        try:
            module = importlib.import_module(f"app.migrations.{name}")
            if hasattr(module, "migrate") and callable(module.migrate):
                from app.database import async_session
                async with async_session() as db:
                    await module.migrate(db)
        except Exception as exc:
            print(f"  ⚠ Migration {name} failed: {exc}")
