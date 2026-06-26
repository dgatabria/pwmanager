"""Migration 010: Add personal_group_id to users table.

This migration adds a foreign key column to the users table that points
to the user's personal secret group. This allows the backend to identify
which group is the user's personal group so it can protect only that group
from modification (other personal groups can be edited/shared).
"""

from sqlalchemy import text


async def migrate(db):
    """Perform the personal_group_id migration."""

    # ── 1. Add column if it doesn't exist ────────────────────────────
    result = await db.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'users' AND column_name = 'personal_group_id'"
    ))
    if not result.fetchone():
        print("  Adding personal_group_id column to users...")
        await db.execute(text(
            "ALTER TABLE users ADD COLUMN personal_group_id INTEGER"
        ))
        await db.commit()
    else:
        print("  personal_group_id column already exists. Skipping.")

    # ── 2. Add foreign key constraint if it doesn't exist ─────────────
    await db.execute(text(
        "DO $$ "
        "BEGIN "
        "  IF NOT EXISTS ("
        "    SELECT 1 FROM pg_constraint "
        "    WHERE conname = 'users_personal_group_id_fkey' "
        "  ) THEN "
        "    ALTER TABLE users ADD CONSTRAINT users_personal_group_id_fkey "
        "    FOREIGN KEY (personal_group_id) REFERENCES secret_groups(id) "
        "    ON DELETE SET NULL; "
        "  END IF; "
        "END $$;"
    ))
    await db.commit()
    print("  Foreign key constraint ensured.")

    # ── 3. Set personal_group_id for all existing users ───────────────
    result = await db.execute(text(
        "SELECT COUNT(*) FROM users WHERE personal_group_id IS NULL"
    ))
    null_count = result.scalar()
    if null_count and null_count > 0:
        print(f"  Setting personal_group_id for {null_count} user(s)...")
        await db.execute(text(
            """UPDATE users u
               SET personal_group_id = sg.id
               FROM secret_groups sg
               WHERE u.personal_group_id IS NULL
                 AND sg.owner_id = u.id
                 AND sg.is_personal = true
                 AND sg.is_active = true"""
        ))
        await db.commit()
        print("  Migration complete.")
    else:
        print("  All users already have personal_group_id.")

    # ── 4. Make the column NOT NULL ───────────────────────────────────
    result = await db.execute(text(
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_name = 'users' AND column_name = 'personal_group_id'"
    ))
    row = result.fetchone()
    if row and row[0] == 'YES':
        print("  Making personal_group_id NOT NULL on users...")
        await db.execute(text(
            "ALTER TABLE users ALTER COLUMN personal_group_id SET NOT NULL"
        ))
        await db.commit()
        print("  Migration complete: personal_group_id column is now NOT NULL.")
    else:
        print("  personal_group_id is already NOT NULL. Skipping.")
