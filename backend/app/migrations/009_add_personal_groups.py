"""Add personal groups and enforce non-nullable group_id on secrets.

This migration:
1. Adds `is_personal` (boolean) and `user_id` (FK to users) columns to secret_groups
2. Creates a "Personal" secret group for every existing user
3. Moves secrets with group_id=NULL into their owner's personal group
4. Makes secrets.group_id NOT NULL
5. Adds a CASCADE delete on secret_groups.user_id so personal groups
   (and their secrets) are removed when the owning user is deleted

Run this script once. It is idempotent — safe to run multiple times.
"""

from sqlalchemy import text


async def migrate(db):
    """Perform the personal-groups migration."""

    # ── 1. Add columns to secret_groups (idempotent) ──────────────────
    result = await db.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'secret_groups' AND column_name = 'is_personal'"
    ))
    if not result.fetchone():
        print("  Adding is_personal column to secret_groups...")
        await db.execute(text(
            "ALTER TABLE secret_groups ADD COLUMN is_personal BOOLEAN NOT NULL DEFAULT FALSE"
        ))
        await db.commit()
    else:
        print("  is_personal column already exists. Skipping.")

    result = await db.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'secret_groups' AND column_name = 'user_id'"
    ))
    if not result.fetchone():
        print("  Adding user_id column to secret_groups...")
        await db.execute(text(
            "ALTER TABLE secret_groups ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE"
        ))
        await db.commit()
    else:
        print("  user_id column already exists. Skipping.")

    # ── 2. Create personal groups for existing users ──────────────────
    result = await db.execute(text(
        "SELECT id, username FROM users WHERE is_deleted = false AND is_active = true"
    ))
    users = result.fetchall()

    created = 0
    for user_id, username in users:
        # Check if user already has a personal group
        result = await db.execute(text(
            "SELECT id FROM secret_groups WHERE owner_id = :uid AND is_personal = true LIMIT 1"
        ), {"uid": user_id})
        if not result.fetchone():
            await db.execute(text(
                "INSERT INTO secret_groups (name, description, owner_id, is_personal, is_active) "
                "VALUES ('Personal', 'Your personal secret group', :uid, true, true)"
            ), {"uid": user_id})
            created += 1

    if created:
        print(f"  Created {created} personal group(s).")
    else:
        print("  All users already have personal groups.")
    await db.commit()

    # ── 3. Move secrets with group_id=NULL into owner's personal group ─
    result = await db.execute(text(
        "SELECT COUNT(*) FROM secrets WHERE group_id IS NULL"
    ))
    null_count = result.scalar()
    if null_count and null_count > 0:
        print(f"  Migrating {null_count} secret(s) with NULL group_id to personal groups...")
        await db.execute(text(
            """UPDATE secrets s
               SET group_id = sg.id
               FROM secret_groups sg
               WHERE s.group_id IS NULL
                 AND sg.owner_id = s.owner_id
                 AND sg.is_personal = true
                 AND sg.is_active = true"""
        ))
        await db.commit()
        print("  Migration complete.")
    else:
        print("  No secrets with NULL group_id found.")

    # ── 4. Make secrets.group_id NOT NULL ─────────────────────────────
    result = await db.execute(text(
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_name = 'secrets' AND column_name = 'group_id'"
    ))
    row = result.fetchone()
    if row and row[0] == 'YES':
        print("  Making group_id NOT NULL on secrets...")
        await db.execute(text(
            "ALTER TABLE secrets ALTER COLUMN group_id SET NOT NULL"
        ))
        await db.commit()
        print("  Migration complete: group_id column is now NOT NULL.")
    else:
        print("  group_id is already NOT NULL. Skipping.")
