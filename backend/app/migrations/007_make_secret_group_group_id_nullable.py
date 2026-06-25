"""Make secret_groups.group_id nullable.

This migration removes the NOT NULL constraint from the group_id column
in the secret_groups table, allowing users to create personal secret
groups that are not bound to a user group.

Run this script once to migrate existing data.
"""

from sqlalchemy import text


async def migrate(db):
    """Make group_id nullable on secret_groups."""
    # Check if column already exists (idempotent)
    result = await db.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'secret_groups' AND column_name = 'group_id'"
    ))
    if not result.fetchone():
        print("  group_id column does not exist. Skipping.")
        return

    print("  Making group_id nullable on secret_groups...")
    await db.execute(text(
        "ALTER TABLE secret_groups ALTER COLUMN group_id DROP NOT NULL"
    ))

    # Set existing groups with group_id=1 as fallback if they have NULL
    # (most existing groups already have a group_id, so this is just safety)
    await db.execute(text(
        "UPDATE secret_groups SET group_id = 1 WHERE group_id IS NULL"
    ))

    await db.commit()
    print("  Migration complete: group_id column is now nullable.")
