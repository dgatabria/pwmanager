"""Add password_change_required column to users table.

This migration adds the password_change_required boolean column which
forces first-time users (created by the seed script) to change their
password on initial login.
"""

from sqlalchemy import text


async def migrate(db):
    """Add password_change_required column to users."""
    result = await db.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'users' AND column_name = 'password_change_required'"
    ))
    if result.fetchone():
        print("  Migration already applied. Skipping.")
        return

    print("  Adding password_change_required column to users...")
    await db.execute(text("""
        ALTER TABLE users
        ADD COLUMN password_change_required BOOLEAN NOT NULL DEFAULT TRUE
    """))

    await db.commit()
    print("  Migration complete: password_change_required column added.")
