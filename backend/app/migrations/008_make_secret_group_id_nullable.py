"""Make secrets.group_id nullable.

This migration removes the NOT NULL constraint from the group_id column
in the secrets table, allowing users to create personal secrets that are
not bound to any secret group.

Run this script once to migrate existing data.
Idempotent — safe to run multiple times.
"""

from sqlalchemy import text


async def migrate(db):
    """Make group_id nullable on secrets."""
    # Check if column exists at all
    result = await db.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'secrets' AND column_name = 'group_id'"
    ))
    if not result.fetchone():
        print("  group_id column does not exist. Skipping.")
        return

    # Check if NOT NULL constraint still exists (idempotent check)
    result = await db.execute(text(
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_name = 'secrets' AND column_name = 'group_id'"
    ))
    row = result.fetchone()
    if row and row[0] == 'NO':
        print("  Making group_id nullable on secrets...")
        await db.execute(text(
            "ALTER TABLE secrets ALTER COLUMN group_id DROP NOT NULL"
        ))
        await db.commit()
        print("  Migration complete: group_id column is now nullable.")
    else:
        print("  group_id is already nullable. Skipping.")
