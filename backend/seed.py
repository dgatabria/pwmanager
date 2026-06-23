"""Seed script to create initial admin user and default groups.

Required environment variables (must be set before running):
  - DATABASE_URL:      PostgreSQL connection string (e.g. postgresql+asyncpg://...)
  - ENCRYPTION_KEY:    32-byte base64-encoded Fernet key

In production these must come from a secrets manager, Docker secrets,
or a vault — never from hardcoded defaults.
"""

import asyncio
import os
import sys
import secrets
import string


def _require_env(name: str) -> str:
    """Read an environment variable and exit if it is not set.

    This ensures that placeholder/default values are never used in production.
    """
    value = os.environ.get(name)
    if not value:
        print(
            f"ERROR: Required environment variable '{name}' is not set. "
            f"Set it via environment variables, Docker secrets, or a vault.",
            file=sys.stderr,
        )
        sys.exit(1)
    return value


# ─── Startup validation ─────────────────────────────────────────────
# Require secrets at startup — never fall back to placeholders
_require_env("DATABASE_URL")
_require_env("ENCRYPTION_KEY")

from sqlalchemy import select

from app.database import async_session, init_db
from app.models.group import Group
from app.models.secret_group import SecretGroup
from app.models.user import User
from app.utils.security import SecurityUtils


def _generate_secure_password(length: int = 32) -> str:
    """Generate a cryptographically secure random password.

    Includes uppercase, lowercase, digits, and special characters.
    Ensures at least one character from each required category.
    """
    alphabet = string.ascii_letters + string.digits + string.punctuation
    # Ensure at least one character from each required category
    password_chars = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(string.punctuation),
    ]
    # Fill remaining length with random characters from full alphabet
    password_chars += [secrets.choice(alphabet) for _ in range(length - 4)]
    # Shuffle to avoid predictable positions
    secrets.SystemRandom().shuffle(password_chars)
    return "".join(password_chars)


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

        # Generate a cryptographically secure random password
        admin_password = _generate_secure_password(32)
        hashed = SecurityUtils.hash_password(admin_password)
        admin = User(
            username="admin",
            email="admin@company.local",
            hashed_password=hashed,
            full_name="System Administrator",
            is_superuser=True,
        )
        session.add(admin)
        await session.commit()
        print(f"✓ Created admin user (password: {admin_password})")
        print("⚠️  WARNING: Save this password securely. It will not be shown again.")

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

        # Use admin user (id=1) as owner of default groups
        admin_id = admin.id
        for name, desc, parent_id in default_secret_groups:
            sg = SecretGroup(
                name=name,
                description=desc,
                parent_id=parent_id,
                group_id=1,
                owner_id=admin_id,
            )
            session.add(sg)

        await session.commit()
        print("✓ Created default secret groups")
        print("\nSeed completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
