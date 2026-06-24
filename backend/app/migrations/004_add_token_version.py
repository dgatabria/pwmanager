"""Add token_version column to users for session fixation prevention.

This migration adds a `token_version` integer column to the `users` table.
On each login the version is incremented, which invalidates all previously
issued JWT tokens for that user (because the JWT payload includes the
version at the time of issuance).

Run this script once to add the column.
"""

from sqlalchemy import text


async def migrate(db):
    """Add token_version column to users."""
    # Check if migration already ran
    result = await db.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'users' AND column_name = 'token_version'"
    ))
    if result.fetchone():
        print("  Migration already applied. Skipping.")
        return

    print("  Adding token_version column to users...")
    await db.execute(text(
        "ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0"
    ))

    await db.commit()
    print("  Migration complete: token_version column added.")
