"""Make secrets.group_id nullable.

This migration removes the NOT NULL constraint from the group_id column
in the secrets table, allowing users to create personal secrets that are
not bound to any secret group.

Run this script once to migrate existing data.
"""

from sqlalchemy import text


async def migrate(db):
    """Make group_id nullable on secrets."""
    # Check if column already exists (idempotent)
    result = await db.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'secrets' AND column_name = 'group_id'"
    ))
    if not result.fetchone():
        print("  group_id column does not exist. Skipping.")
        return

    print("  Making group_id nullable on secrets...")
    await db.execute(text(
        "ALTER TABLE secrets ALTER COLUMN group_id DROP NOT NULL"
    ))

    await db.commit()
    print("  Migration complete: group_id column is now nullable.")
