"""Add owner_id column to secret_groups table.

This migration adds an owner_id column to track which user created each
secret group. It populates existing groups with a default owner (user_id=1,
the admin user, if it exists).

Run this script once to migrate existing data.
"""

from sqlalchemy import text


async def migrate(db):
    """Add owner_id column to secret_groups."""
    # Check if column already exists (idempotent)
    result = await db.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'secret_groups' AND column_name = 'owner_id'"
    ))
    if result.fetchone():
        print("  owner_id column already exists. Skipping.")
        return

    print("  Adding owner_id column to secret_groups...")
    await db.execute(text(
        "ALTER TABLE secret_groups ADD COLUMN owner_id INTEGER NOT NULL DEFAULT 1"
    ))

    # Set foreign key
    print("  Adding foreign key constraint...")
    await db.execute(text(
        "ALTER TABLE secret_groups ADD CONSTRAINT fk_secret_groups_owner "
        "FOREIGN KEY (owner_id) REFERENCES users(id)"
    ))

    # Populate existing groups with owner_id=1 (admin) if it exists
    result = await db.execute(text("SELECT COUNT(*) FROM users WHERE id = 1"))
    has_admin = result.scalar() > 0
    if has_admin:
        print("  Populating existing groups with owner_id=1 (admin)...")
        await db.execute(text(
            "UPDATE secret_groups SET owner_id = 1 WHERE owner_id IS NULL"
        ))

    await db.commit()
    print("  Migration complete: owner_id column added.")
