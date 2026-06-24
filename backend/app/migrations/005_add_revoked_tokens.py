"""Add revoked_tokens table for server-side JWT invalidation.

This migration creates the `revoked_tokens` table which stores JWT
identifiers (JTI) for tokens that have been explicitly revoked
(e.g., on logout). During token validation, the system checks this
table to ensure revoked tokens are rejected even if they haven't
expired yet.

Run this script once to create the table.
"""

from sqlalchemy import text


async def migrate(db):
    """Create revoked_tokens table."""
    # Check if migration already ran
    result = await db.execute(text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_name = 'revoked_tokens'"
    ))
    if result.fetchone():
        print("  Migration already applied. Skipping.")
        return

    print("  Creating revoked_tokens table...")
    await db.execute(text("""
        CREATE TABLE revoked_tokens (
            id SERIAL PRIMARY KEY,
            jti VARCHAR(64) NOT NULL UNIQUE,
            user_id VARCHAR(64) NOT NULL,
            reason VARCHAR(100) NOT NULL DEFAULT 'logout',
            revoked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL
        )
    """))

    # Add index on user_id for faster lookups during logout
    await db.execute(text(
        "CREATE INDEX idx_revoked_tokens_user_id ON revoked_tokens (user_id)"
    ))

    # Add index on expires_at for cleanup
    await db.execute(text(
        "CREATE INDEX idx_revoked_tokens_expires_at ON revoked_tokens (expires_at)"
    ))

    await db.commit()
    print("  Migration complete: revoked_tokens table created.")
