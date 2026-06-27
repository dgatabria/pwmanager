"""Migration 011: Make personal_group_id nullable.

This migration allows personal_group_id to be NULL so that user creation
can use a two-step flush pattern: first flush the user (to get an ID),
then create the personal group, then set the FK and commit.
"""

from sqlalchemy import text


async def migrate(db):
    """Perform the personal_group_id nullable migration."""

    await db.execute(text(
        "ALTER TABLE users ALTER COLUMN personal_group_id DROP NOT NULL"
    ))
    await db.commit()
    print("  personal_group_id is now nullable.")


async def rollback(db):
    """Rollback: make personal_group_id NOT NULL again.

    This will fail if any existing users have NULL personal_group_id.
    """
    await db.execute(text(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM users WHERE personal_group_id IS NULL
            ) THEN
                RAISE EXCEPTION 'Cannot set NOT NULL: some users have NULL personal_group_id';
            END IF;
        END $$;
        """
    ))
    await db.execute(text(
        "ALTER TABLE users ALTER COLUMN personal_group_id SET NOT NULL"
    ))
    await db.commit()
    print("  personal_group_id is now NOT NULL again.")
