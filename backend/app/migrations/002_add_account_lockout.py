"""Add account lockout fields to users table.

This migration adds failed_login_attempts and locked_until columns to
track failed login attempts and support account lockout after too many
failed attempts.

Run this script once to migrate existing data.
"""

from sqlalchemy import text


async def migrate(db):
    """Add account lockout columns to users."""
    # Check if columns already exist (idempotent)
    result = await db.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'users' AND column_name IN "
        "('failed_login_attempts', 'locked_until') "
        "ORDER BY column_name"
    ))
    existing = [row[0] for row in result.all()]

    if "failed_login_attempts" not in existing:
        print("  Adding failed_login_attempts column to users...")
        await db.execute(text(
            "ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER NOT NULL DEFAULT 0"
        ))

    if "locked_until" not in existing:
        print("  Adding locked_until column to users...")
        await db.execute(text(
            "ALTER TABLE users ADD COLUMN locked_until TIMESTAMP WITH TIME ZONE"
        ))

    await db.commit()
    print("  Migration complete: account lockout columns added.")
