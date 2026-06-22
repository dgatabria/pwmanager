"""Seed script to create initial admin user and default groups."""

import asyncio
import os

os.environ.setdefault("SECRET_KEY", "change-this-to-a-secure-random-string-in-production")
os.environ.setdefault(
    "ENCRYPTION_KEY",
    "change-this-to-a-32-byte-base64-encoded-key",
)

from sqlalchemy import select

from app.database import async_session, init_db
from app.models.group import Group
from app.models.secret_group import SecretGroup
from app.models.user import User
from app.utils.security import SecurityUtils


async def seed():
    """Create initial admin user and default groups."""
    await init_db()

    async with async_session() as session:
        # Check if admin user already exists
        result = await session.execute(
            select(User).where(User.username == "admin")
        )
        if result.scalar_one_or_none():
            print("Admin user already exists. Skipping seed.")
            return

        # Create admin user
        hashed = SecurityUtils.hash_password("Admin@123")
        admin = User(
            username="admin",
            email="admin@company.local",
            hashed_password=hashed,
            full_name="System Administrator",
            is_superuser=True,
        )
        session.add(admin)
        await session.commit()
        print(f"✓ Created admin user (password: Admin@123)")

        # Create default groups
        default_groups = [
            ("IT Administrators", "IT team with full access"),
            ("Developers", "Development team members"),
            ("DBAs", "Database administrators"),
        ]

        for name, desc in default_groups:
            group = Group(name=name, description=desc)
            session.add(group)

        await session.commit()
        print("✓ Created default user groups")

        # Create default secret groups
        default_secret_groups = [
            ("SSH Keys", "SSH key pairs for server access", None),
            ("Database Credentials", "Database passwords and connection strings", None),
            ("API Keys", "API keys for external services", None),
            ("Other", "General credentials", None),
        ]

        for name, desc, parent_id in default_secret_groups:
            sg = SecretGroup(name=name, description=desc, parent_id=parent_id, group_id=1)
            session.add(sg)

        await session.commit()
        print("✓ Created default secret groups")
        print("\nSeed completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
