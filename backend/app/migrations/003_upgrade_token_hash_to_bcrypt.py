"""Upgrade API token hashing from SHA-256 to bcrypt.

This migration:
1. Increases the token_hash column size from 64 to 255 characters
   to accommodate bcrypt hashes (which are ~60 chars).
2. Revokes all existing API tokens (they were hashed with SHA-256
   and are no longer valid with the bcrypt upgrade).

Run this script once to migrate existing data.
"""

from sqlalchemy import text


async def migrate(db):
    """Upgrade API token hashing to bcrypt."""
    # Check if migration already ran
    result = await db.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'api_tokens' AND column_name = 'token_hash' "
        "AND character_maximum_length = 255"
    ))
    if result.fetchone():
        print("  Migration already applied. Skipping.")
        return

    print("  Increasing token_hash column size to 255...")
    await db.execute(text(
        "ALTER TABLE api_tokens ALTER COLUMN token_hash TYPE VARCHAR(255)"
    ))

    print("  Revoking all existing API tokens (SHA-256 hashes are incompatible)...")
    await db.execute(text(
        "UPDATE api_tokens SET is_active = 0 WHERE is_active = 1"
    ))

    await db.commit()
    print("  Migration complete: token_hash upgraded to bcrypt.")
