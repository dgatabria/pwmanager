"""API Token management service."""

import hashlib
import secrets
import bcrypt
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_token import APIToken


class APITokenService:
    """Service for managing API tokens."""

    TOKEN_PREFIX = "pm_"

    @staticmethod
    def generate_token() -> str:
        """Generate a new API token."""
        random_part = secrets.token_hex(32)
        return f"{APITokenService.TOKEN_PREFIX}{random_part}"

    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token for storage using SHA-256.

        SHA-256 enables fast O(1) indexed database lookups while ensuring
        that plaintext tokens are never stored at rest.
        """
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    async def create_token(
        db: AsyncSession,
        user_id: int,
        name: str,
        description: str | None = None,
        expires_at: datetime | None = None,
    ) -> tuple[str, APIToken]:
        """Create a new API token. Returns (plain_token, token_record)."""
        plain_token = APITokenService.generate_token()
        token_hash = APITokenService.hash_token(plain_token)

        api_token = APIToken(
            token_hash=token_hash,
            user_id=user_id,
            name=name,
            description=description,
            expires_at=expires_at,
        )

        db.add(api_token)
        await db.commit()
        await db.refresh(api_token)

        return plain_token, api_token

    @staticmethod
    async def validate_token(
        db: AsyncSession, token: str
    ) -> tuple[APIToken | None, dict | None]:
        """
        Validate an API token using deterministic O(1) SHA-256 lookup.

        Returns (api_token, user_info) if valid, (None, None) if invalid.
        """
        token_hash = APITokenService.hash_token(token)

        # 1. Fast O(1) indexed lookup for SHA-256 tokens
        result = await db.execute(
            select(APIToken)
            .where(APIToken.token_hash == token_hash)
            .where(APIToken.is_active == 1)
        )
        api_token = result.scalar_one_or_none()

        # 2. Backward compatibility fallback for legacy bcrypt tokens
        if not api_token:
            result = await db.execute(
                select(APIToken)
                .where(APIToken.token_hash.like("$2%"))
                .where(APIToken.is_active == 1)
            )
            legacy_tokens = result.scalars().all()
            for legacy in legacy_tokens:
                if bcrypt.checkpw(token.encode("utf-8"), legacy.token_hash.encode("utf-8")):
                    api_token = legacy
                    # Upgrade legacy token to SHA-256 on successful use
                    api_token.token_hash = token_hash
                    await db.commit()
                    break

        if not api_token:
            return None, None

        # Check user active status
        if not api_token.user or not api_token.user.is_active or api_token.user.is_deleted:
            return None, None

        # Check expiration
        if api_token.expires_at and datetime.now(timezone.utc) > api_token.expires_at:
            api_token.is_active = False
            await db.commit()
            return None, None

        # Update last used
        api_token.last_used_at = datetime.now(timezone.utc)
        await db.commit()

        # Get user info
        user_info = {
            "id": api_token.user_id,
            "username": api_token.user.username,
            "email": api_token.user.email,
            "full_name": api_token.user.full_name,
            "is_superuser": api_token.user.is_superuser,
        }

        return api_token, user_info

    @staticmethod
    async def list_user_tokens(
        db: AsyncSession, user_id: int
    ) -> list[APIToken]:
        """List all tokens for a user."""
        result = await db.execute(
            select(APIToken)
            .where(APIToken.user_id == user_id)
            .order_by(APIToken.created_at.desc())
        )
        return result.scalars().all()

    @staticmethod
    async def revoke_token(
        db: AsyncSession, token_id: int, user_id: int
    ) -> APIToken | None:
        """Revoke (soft delete) a token."""
        result = await db.execute(
            select(APIToken)
            .where(APIToken.id == token_id)
            .where(APIToken.user_id == user_id)
        )
        api_token = result.scalar_one_or_none()

        if api_token:
            api_token.is_active = False
            await db.commit()
            await db.refresh(api_token)

        return api_token

    @staticmethod
    async def recycle_token(
        db: AsyncSession, old_token: str, user_id: int, name: str, description: str | None = None
    ) -> tuple[str, APIToken]:
        """
        Recycle an API token: revoke the old one and create a new one.
        Returns (new_plain_token, new_token_record).
        """
        old_hash = APITokenService.hash_token(old_token)
        result = await db.execute(
            select(APIToken)
            .where(APIToken.user_id == user_id)
            .where(APIToken.token_hash == old_hash)
            .where(APIToken.is_active == True)
        )
        old_api_token = result.scalar_one_or_none()

        if not old_api_token:
            result = await db.execute(
                select(APIToken)
                .where(APIToken.user_id == user_id)
                .where(APIToken.token_hash.like("$2%"))
                .where(APIToken.is_active == True)
            )
            for legacy in result.scalars().all():
                if bcrypt.checkpw(old_token.encode("utf-8"), legacy.token_hash.encode("utf-8")):
                    old_api_token = legacy
                    break

        if not old_api_token:
            raise ValueError("Invalid or expired token")

        # Revoke old token
        old_api_token.is_active = False
        await db.commit()

        # Create new token with same name/description
        new_token, new_record = await APITokenService.create_token(
            db=db,
            user_id=user_id,
            name=name,
            description=description,
            expires_at=old_api_token.expires_at,
        )

        return new_token, new_record
